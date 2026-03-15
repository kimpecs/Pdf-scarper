"""
run_extraction.py — Extract parts from PDFs in app/data/pdfs/ and save to DB.

Usage:
    python3 run_extraction.py                         # process all PDFs
    python3 run_extraction.py FortPro_Lighting.pdf    # process one file
    python3 run_extraction.py --dry-run               # print counts, don't write DB
"""

import sys
import re
import json
import sqlite3
import argparse
import logging
from pathlib import Path

# ── Path setup ───────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.utils.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("extraction")

# ── Import extractor (fix relative import issue) ─────────────────────────
import importlib.util

spec = importlib.util.spec_from_file_location(
    "extract_catalog",
    PROJECT_ROOT / "app" / "services" / "pdf_processing" / "extract_catalog.py",
)
# Patch sys.path so the module's own relative imports resolve
sys.path.insert(0, str(PROJECT_ROOT / "app"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
CatalogExtractor = mod.CatalogExtractor


# ── DB helpers ───────────────────────────────────────────────────────────
def get_db():
    db_path = settings.DB_PATH
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def insert_parts(conn, parts: list[dict], dry_run: bool = False) -> tuple[int, int]:
    """Insert parts into DB. Returns (inserted, skipped)."""
    inserted = skipped = 0
    cur = conn.cursor()

    for p in parts:
        try:
            cur.execute("""
                INSERT OR IGNORE INTO parts (
                    catalog_name, catalog_type, part_type, part_number,
                    description, category, page, image_path,
                    page_text, pdf_path, machine_info,
                    specifications, oe_numbers, applications, features,
                    confidence_label, review_status, published
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                p.get("catalog_name"),
                p.get("catalog_type"),
                p.get("part_type"),
                p.get("part_number"),
                p.get("description"),
                p.get("category"),
                p.get("page"),
                p.get("image_path"),
                p.get("page_text"),
                p.get("pdf_path"),
                p.get("machine_info"),
                p.get("specifications"),
                p.get("oe_numbers"),
                p.get("applications"),
                p.get("features"),
                "ai_extracted",
                "pending",
                1,
            ))
            if cur.rowcount:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            log.warning("  row error [%s]: %s", p.get("part_number"), e)

    if not dry_run:
        conn.commit()

    return inserted, skipped


# ── FortPro-specific structured extractor ────────────────────────────────
def extract_fortpro_page(text: str, page_num: int, pdf_name: str) -> list[dict]:
    """
    FortPro catalogs use a consistent format:
        FortproUSA#: F235150
        Notes:  Red - Colored Lens
                Kit Includes Light, Grommet and Plug

    This parser captures that structure precisely.
    """
    parts = []

    # Split into blocks by part number line
    blocks = re.split(r'(?=FortproUSA#:)', text)

    for block in blocks:
        m = re.search(r'FortproUSA#:\s*(F\d{6}(?:-\d+)?)', block)
        if not m:
            continue

        part_number = m.group(1).strip()

        # Grab Notes line(s) as description
        notes_m = re.search(r'Notes?:\s*(.+?)(?:\n\s*\n|\Z)', block, re.DOTALL)
        description = ""
        if notes_m:
            description = re.sub(r'\s+', ' ', notes_m.group(1)).strip()

        # Infer category from surrounding text
        ctx = block.lower()
        if any(k in ctx for k in ["headlight", "head lamp", "headlamp"]):
            category = "Headlights"
        elif any(k in ctx for k in ["tail", "taillight", "stop"]):
            category = "Taillights"
        elif any(k in ctx for k in ["marker", "clearance", "side marker"]):
            category = "Marker Lights"
        elif any(k in ctx for k in ["led", "oval", "round"]):
            category = "LED Lighting"
        elif any(k in ctx for k in ["interior", "cab light", "dome"]):
            category = "Cab / Interior Lighting"
        elif any(k in ctx for k in ["work light", "flood"]):
            category = "Work Lights"
        else:
            category = "Lighting"

        # Determine voltage / LED count as part_type
        part_type = "LED" if "led" in ctx else "Incandescent"
        volts_m = re.search(r'(\d+)\s*Volt', block, re.I)
        if volts_m:
            part_type = f"{part_type} {volts_m.group(1)}V"

        parts.append({
            "catalog_name": pdf_name,
            "catalog_type": "fort_pro",
            "part_number":  part_number,
            "part_type":    part_type,
            "description":  description or block[:120].strip(),
            "category":     category,
            "page":         page_num,
            "pdf_path":     f"{pdf_name}.pdf",
            "page_text":    text[:8000],
        })

    return parts


# ── Main extractor ────────────────────────────────────────────────────────
def process_pdf(pdf_path: Path, dry_run: bool = False) -> int:
    import pdfplumber

    pdf_name = pdf_path.stem
    image_dir = settings.part_images_DIR
    if not image_dir.is_absolute():
        image_dir = PROJECT_ROOT / "app" / "data" / "part_images"
    image_dir.mkdir(parents=True, exist_ok=True)

    # Detect if this is a FortPro catalog (use structured parser)
    is_fortpro = any(k in pdf_name.lower() for k in ["fortpro", "fort_pro", "fort pro"])

    log.info("Processing: %s  (fortpro=%s)", pdf_path.name, is_fortpro)

    all_parts: list[dict] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        total_pages = len(pdf.pages)
        log.info("  Pages: %d", total_pages)

        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if not text.strip():
                continue

            if is_fortpro:
                page_parts = extract_fortpro_page(text, page_num, pdf_name)
            else:
                # Fall back to generic extractor
                try:
                    extractor = CatalogExtractor()
                    page_parts = []
                    extracted = extractor.extract_part_info(text, page_num)
                    machine_info = extractor.extract_machine_info(text)
                    catalog_type = extractor.detect_catalog_type(pdf_path)
                    for p in extracted:
                        page_parts.append({
                            "catalog_name": pdf_name,
                            "catalog_type": catalog_type,
                            "part_number":  p["number"],
                            "part_type":    p["type"],
                            "description":  p.get("context", ""),
                            "category":     extractor._infer_category(p.get("context", "")),
                            "page":         page_num,
                            "pdf_path":     f"{pdf_name}.pdf",
                            "page_text":    text[:8000],
                            "machine_info": json.dumps(machine_info) if machine_info else None,
                        })
                except Exception as e:
                    log.warning("  Generic extractor error page %d: %s", page_num, e)
                    page_parts = []

            all_parts.extend(page_parts)

    # Deduplicate by part_number within this run
    seen = set()
    unique_parts = []
    for p in all_parts:
        key = (p["part_number"], p.get("page"))
        if key not in seen:
            seen.add(key)
            unique_parts.append(p)

    log.info("  Found %d unique parts across %d pages", len(unique_parts), total_pages)

    if dry_run:
        for p in unique_parts[:20]:
            log.info("    [DRY] %s | %s | %s | p%s",
                     p["part_number"], p.get("catalog_type"), p.get("category"), p.get("page"))
        if len(unique_parts) > 20:
            log.info("    ... and %d more", len(unique_parts) - 20)
        return len(unique_parts)

    conn = get_db()
    inserted, skipped = insert_parts(conn, unique_parts)
    log.info("  DB: %d inserted, %d already existed", inserted, skipped)

    # Extract and store images
    extract_images_for_pdf(pdf_path, conn)
    conn.close()

    return inserted


# ── Image extraction ─────────────────────────────────────────────────────
def extract_images_for_pdf(pdf_path: Path, conn) -> int:
    """
    Extract images from a PDF and insert records into part_images.

    For each page, saves every image >= 80x80 px to disk and links it
    to every part already in the DB from that page.
    """
    import fitz  # PyMuPDF

    pdf_name = pdf_path.stem
    image_base = PROJECT_ROOT / "app" / "data" / "part_images"
    pdf_image_dir = image_base / pdf_name
    pdf_image_dir.mkdir(parents=True, exist_ok=True)

    # Parts already in DB for this catalog, keyed by page
    rows = conn.execute(
        "SELECT id, page FROM parts WHERE catalog_name = ?", (pdf_name,)
    ).fetchall()
    parts_by_page: dict[int, list[int]] = {}
    for r in rows:
        parts_by_page.setdefault(r["page"], []).append(r["id"])

    if not parts_by_page:
        log.info("  No parts in DB for %s — skipping image extraction", pdf_name)
        return 0

    doc = fitz.open(str(pdf_path))
    saved = 0

    for page_idx in range(len(doc)):
        page_num = page_idx + 1
        page = doc[page_idx]
        page_w = page.rect.width
        page_h = page.rect.height

        # Get image list with their positions via get_image_info
        img_info_list = page.get_image_info(xrefs=True)

        for info in img_info_list:
            xref   = info.get("xref", 0)
            bbox   = info.get("bbox")          # (x0, y0, x1, y1) in page coords
            width  = info.get("width", 0)
            height = info.get("height", 0)

            # Skip tiny images (icons, bullets, logos)
            if width < 80 or height < 80:
                continue

            # Skip full-page background images
            if bbox and (bbox[2] - bbox[0]) > page_w * 0.88 and (bbox[3] - bbox[1]) > page_h * 0.88:
                continue

            try:
                pix = fitz.Pixmap(doc, xref)

                # Convert anything that isn't plain RGB/grayscale → RGB
                # n - alpha gives the number of color channels:
                #   1 = grayscale, 3 = RGB, 4 = CMYK (needs conversion)
                if pix.n - pix.alpha not in (1, 3):
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                # Drop alpha channel if present (PNG with alpha is fine,
                # but some downstream viewers struggle — remove for safety)
                if pix.alpha:
                    pix = fitz.Pixmap(pix, 0)

                image_filename = f"{pdf_name}_p{page_num}_x{xref}.png"
                image_path     = pdf_image_dir / image_filename
                rel_path       = f"app/data/part_images/{pdf_name}/{image_filename}"

                pix.save(str(image_path))
                pix = None

                # Link to every part on this page
                part_ids = parts_by_page.get(page_num, [])
                for part_id in part_ids:
                    try:
                        conn.execute("""
                            INSERT OR IGNORE INTO part_images
                                (part_id, image_filename, image_path, image_type,
                                 image_width, image_height, page_number, confidence)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (part_id, image_filename, rel_path, "png",
                              width, height, page_num, 1.0))
                        saved += 1
                    except Exception as e:
                        log.debug("  part_images insert error part_id=%s: %s", part_id, e)

            except Exception as e:
                log.warning("  Image xref=%s page=%d error: %s", xref, page_num, e)

    conn.commit()
    doc.close()
    log.info("  Images: saved %d records for %s", saved, pdf_name)
    return saved


# ── CLI ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Extract parts from PDFs into the catalog DB")
    parser.add_argument("files", nargs="*", help="Specific PDF filenames (default: all in pdfs/)")
    parser.add_argument("--dry-run",     action="store_true", help="Parse but don't write to DB")
    parser.add_argument("--images-only", action="store_true", help="Skip part extraction; only extract images for PDFs already in DB")
    args = parser.parse_args()

    pdf_dir = PROJECT_ROOT / "app" / "data" / "pdfs"

    if args.files:
        pdfs = [pdf_dir / f if not Path(f).is_absolute() else Path(f) for f in args.files]
    else:
        pdfs = sorted(pdf_dir.glob("*.pdf"))

    if not pdfs:
        log.error("No PDFs found in %s", pdf_dir)
        sys.exit(1)

    total = 0
    for pdf_path in pdfs:
        if not pdf_path.exists():
            log.error("File not found: %s", pdf_path)
            continue

        if args.images_only:
            conn = get_db()
            count = extract_images_for_pdf(pdf_path, conn)
            conn.close()
            total += count
        else:
            count = process_pdf(pdf_path, dry_run=args.dry_run)
            total += count

    if args.images_only:
        log.info("Done. Total image records inserted: %d", total)
    else:
        mode = "would insert" if args.dry_run else "inserted"
        log.info("Done. Total parts %s: %d", mode, total)


if __name__ == "__main__":
    main()
