"""
build_index.py — Build the FAISS semantic search index from all catalog parts.

Run this:
  - After first extraction
  - After adding new PDFs
  - Any time parts data changes significantly

Usage:
    python3 build_index.py              # build from all published parts
    python3 build_index.py --force      # rebuild even if index exists
    python3 build_index.py --batch 128  # custom batch size (default 64)
"""

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("build_index")

# ── Path setup ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import config directly (avoids app/__init__.py pulling in FastAPI)
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("config", PROJECT_ROOT / "app" / "utils" / "config.py")
_cfg_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_cfg_mod)
settings = _cfg_mod.settings
from larry_nlp.embedder import encode_parts
from larry_nlp.faiss_index import FaissIndex, INDEX_PATH, IDS_PATH


def load_parts(db_path: Path) -> list[dict]:
    """Load all published parts from the DB."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, part_number, description, category,
               part_type, catalog_name, catalog_type,
               oe_numbers, applications, specifications
        FROM parts
        WHERE published = 1
        ORDER BY id
    """).fetchall()
    conn.close()
    parts = [dict(r) for r in rows]
    log.info("Loaded %d published parts from DB", len(parts))
    return parts


def build(force: bool = False, batch_size: int = 64):
    # ── Resolve DB path ───────────────────────────────────────────────────
    db_path = settings.DB_PATH
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path
    if not db_path.exists():
        log.error("Database not found: %s", db_path)
        log.error("Run: python3 -m app.services.db.setup")
        sys.exit(1)

    # ── Check if rebuild needed ───────────────────────────────────────────
    if INDEX_PATH.exists() and IDS_PATH.exists() and not force:
        log.info("Index already exists at %s", INDEX_PATH)
        log.info("Use --force to rebuild. Exiting.")
        return

    # ── Load parts ────────────────────────────────────────────────────────
    parts = load_parts(db_path)
    if not parts:
        log.error("No published parts in DB. Run extraction first.")
        sys.exit(1)

    # ── Encode ────────────────────────────────────────────────────────────
    log.info("Encoding %d parts with SentenceTransformer (this may take a minute)...", len(parts))
    vectors = encode_parts(parts, show_progress=True)
    log.info("Encoding done — shape: %s", vectors.shape)

    # ── Build FAISS index ─────────────────────────────────────────────────
    part_ids = [p["id"] for p in parts]
    idx = FaissIndex()
    idx.build(vectors, part_ids)

    log.info("Index built successfully.")
    log.info("  Location : %s", INDEX_PATH)
    log.info("  Vectors  : %d", idx._index.ntotal)
    log.info("  Dimension: %d", vectors.shape[1])
    log.info("")
    log.info("Restart the server to load the new index.")


def main():
    parser = argparse.ArgumentParser(description="Build FAISS semantic index for Larry")
    parser.add_argument("--force",   action="store_true", help="Rebuild even if index exists")
    parser.add_argument("--batch",   type=int, default=64, help="Encoding batch size")
    args = parser.parse_args()
    build(force=args.force, batch_size=args.batch)


if __name__ == "__main__":
    main()
