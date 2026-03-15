"""
larry_nlp/ner.py — Named Entity Recognition & query parsing.

Extracts from a free-text search query:
  - Part numbers  (regex patterns from constants)
  - OEM / cross-ref numbers
  - Known brands / manufacturers
  - Part types / categories
  - Remaining keywords

Falls back gracefully if spaCy model is unavailable.
"""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── Load part-number patterns from existing constants ─────────────────────
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

try:
    from app.utils.constants import PART_NUMBER_PATTERNS, CATALOG_INDICATORS
except ImportError:
    PART_NUMBER_PATTERNS = []
    CATALOG_INDICATORS = {}

# ── Known brands / manufacturers ──────────────────────────────────────────
KNOWN_BRANDS: set[str] = {
    "fortpro", "fort pro", "velvac", "dayton", "nelson", "pai", "eaton",
    "fuller", "meritor", "spicer", "dana", "cummins", "caterpillar", "cat",
    "detroit diesel", "mack", "volvo", "kenworth", "peterbilt", "freightliner",
    "international", "navistar", "paccar", "wabco", "haldex", "bendix",
    "stemco", "garlock", "national seal", "timken", "skf", "ntn",
    "rtlo", "roadranger", "alliance",
}

# ── Part type keywords ────────────────────────────────────────────────────
PART_TYPE_KEYWORDS: dict[str, list[str]] = {
    "LED Light":        ["led", "light", "marker", "clearance", "tail light", "taillight",
                         "headlight", "lamp", "beacon", "strobe", "oval", "round"],
    "Brake":            ["brake", "rotor", "caliper", "pad", "drum", "shoe"],
    "Engine":           ["piston", "cylinder", "turbo", "pump", "gasket", "valve", "cam"],
    "Exhaust":          ["exhaust", "muffler", "stack", "elbow", "flex", "silencer"],
    "Transmission":     ["transmission", "clutch", "bearing", "gear", "shaft", "rtlo"],
    "Mirror":           ["mirror", "convex", "west coast", "hood mount", "2020"],
    "Suspension":       ["suspension", "spring", "shock", "airbag", "torque rod"],
    "Electrical":       ["switch", "relay", "harness", "wire", "connector", "fuse"],
    "Cab / Interior":   ["cab", "interior", "seat", "door", "window", "visor", "boot"],
    "Air / Pneumatic":  ["air", "valve", "tank", "dryer", "compressor", "gladhand"],
    "Fuel System":      ["fuel", "filter", "injector", "nozzle", "pump"],
    "Cooling":          ["radiator", "fan", "thermostat", "coolant", "hose"],
    "U-Joint / Yoke":   ["u-joint", "ujoint", "yoke", "driveshaft"],
}

# Build a flat list of (keyword → part_type) for O(1) lookup
_KEYWORD_MAP: dict[str, str] = {}
for _pt, _kws in PART_TYPE_KEYWORDS.items():
    for _kw in _kws:
        _KEYWORD_MAP[_kw.lower()] = _pt

# ── spaCy lazy loader ─────────────────────────────────────────────────────
_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])
        except Exception:
            import spacy
            _nlp = spacy.blank("en")
    return _nlp


# ── Result dataclass ──────────────────────────────────────────────────────
@dataclass
class ParsedQuery:
    raw: str
    part_numbers: list[str] = field(default_factory=list)
    oem_numbers:  list[str] = field(default_factory=list)
    brands:       list[str] = field(default_factory=list)
    part_types:   list[str] = field(default_factory=list)
    keywords:     list[str] = field(default_factory=list)
    intent:       str = "search"   # "exact_part" | "category_browse" | "search"

    def is_exact(self) -> bool:
        return self.intent == "exact_part"

    def search_tokens(self) -> list[str]:
        """All meaningful tokens for FTS / semantic search."""
        return self.part_numbers + self.oem_numbers + self.brands + self.keywords

    def to_semantic_text(self) -> str:
        """Flat string for SentenceTransformer encoding."""
        return " ".join(self.search_tokens()) or self.raw


# ── Main parser ───────────────────────────────────────────────────────────
class QueryParser:
    """
    Rule-based query parser.  Does not require a trained NER model —
    falls back to regex + keyword lookup when spaCy ORG / PRODUCT
    entities are absent.
    """

    # FortPro part number: F followed by exactly 6 digits
    _FORTPRO_RE  = re.compile(r'\bF\d{6}(?:-\d+)?\b', re.I)
    # Generic 6-7 digit part numbers
    _NUMERIC_RE  = re.compile(r'\b\d{6,7}\b')
    # Standard alphanumeric with hyphens (e.g. AB-1234, RTLO-16913A)
    _ALPHA_NUM_RE = re.compile(r'\b[A-Z]{1,5}-\d{4,}[A-Z0-9]*\b', re.I)
    # OEM tag patterns
    _OEM_RE = re.compile(
        r'\b(?:MAK|AMB|SCH|AIR|RBB|NAT|BCA)\s+[\dA-Z]+\b', re.I
    )
    # "replaces", "cross ref", "fits" → likely has OEM / alt number
    _CROSS_REF_RE = re.compile(
        r'\b(?:replaces?|crosses?|fits?|cross[\s-]?ref(?:erence)?|alt(?:ernate)?)\b', re.I
    )

    def parse(self, raw_query: str) -> ParsedQuery:
        q = raw_query.strip()
        result = ParsedQuery(raw=q)

        # ── 1. Extract explicit part numbers ──────────────────────────────
        for pat in [self._FORTPRO_RE, self._ALPHA_NUM_RE, self._NUMERIC_RE]:
            for m in pat.finditer(q):
                pn = m.group(0).upper().strip()
                if pn not in result.part_numbers:
                    result.part_numbers.append(pn)

        # Also run through catalog constants patterns for completeness
        for compiled_pat, _ in [
            (re.compile(p, re.I), t) for p, t in PART_NUMBER_PATTERNS[:15]
        ]:
            for m in compiled_pat.finditer(q):
                pn = m.group(1).upper().strip() if m.lastindex else m.group(0).upper().strip()
                if len(pn) >= 4 and pn not in result.part_numbers:
                    result.part_numbers.append(pn)

        # ── 2. Extract OEM / cross-ref numbers ────────────────────────────
        for m in self._OEM_RE.finditer(q):
            result.oem_numbers.append(m.group(0).upper().strip())

        # ── 3. Detect brands (case-insensitive substring match) ───────────
        q_lower = q.lower()
        for brand in sorted(KNOWN_BRANDS, key=len, reverse=True):
            if brand in q_lower and brand not in result.brands:
                result.brands.append(brand)

        # ── 4. spaCy ORG / PRODUCT entities ──────────────────────────────
        try:
            doc = _get_nlp()(q)
            for ent in doc.ents:
                if ent.label_ in ("ORG", "PRODUCT") and ent.text.lower() not in result.brands:
                    result.brands.append(ent.text.lower())
        except Exception:
            pass

        # ── 5. Part type detection ────────────────────────────────────────
        for kw, pt in _KEYWORD_MAP.items():
            if kw in q_lower and pt not in result.part_types:
                result.part_types.append(pt)

        # ── 6. Remaining keywords (stopword-filtered) ─────────────────────
        stopwords = {
            "the", "a", "an", "for", "of", "and", "or", "in", "on", "to",
            "is", "are", "with", "what", "where", "how", "part", "number",
            "find", "show", "get", "need", "looking", "want", "my",
        }
        already_used = set(
            t.lower() for t in result.part_numbers + result.oem_numbers + result.brands
        )
        tokens = re.findall(r'\b[a-z0-9]{2,}\b', q_lower)
        result.keywords = [
            t for t in tokens
            if t not in stopwords and t not in already_used and len(t) > 2
        ]

        # ── 7. Infer intent ───────────────────────────────────────────────
        if result.part_numbers and len(q.split()) <= 3:
            result.intent = "exact_part"
        elif result.part_types and not result.part_numbers:
            result.intent = "category_browse"
        else:
            result.intent = "search"

        return result
