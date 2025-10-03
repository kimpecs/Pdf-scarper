# db_setup.py
import sqlite3
from pathlib import Path

DB_PATH = Path("catalog.db")


def setup_database():
    if DB_PATH.exists():
        DB_PATH.unlink()
        print("Deleted existing catalog.db")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # --- Parts Table ---
    cur.execute("""
    CREATE TABLE parts (
        id INTEGER PRIMARY KEY,
        catalog_type TEXT CHECK(catalog_type IN ('dayton', 'fort_pro', 'caterpillar')),
        part_type TEXT CHECK(part_type IN ('part', 'caliper', 'kit', 'other')),
        part_number TEXT NOT NULL,
        description TEXT,
        category TEXT,
        page INTEGER,
        image_path TEXT,
        page_text TEXT,
        pdf_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # --- Full Text Search Table ---
    cur.execute("""
    CREATE VIRTUAL TABLE parts_fts USING fts5(
        catalog_type,
        part_number,
        description,
        page_text,
        content='parts',
        content_rowid='id'
    );
    """)

    # --- FTS Triggers ---
    cur.executescript("""
    CREATE TRIGGER parts_ai AFTER INSERT ON parts BEGIN
        INSERT INTO parts_fts(rowid, catalog_type, part_number, description, page_text)
        VALUES (new.id, new.catalog_type, new.part_number, new.description, new.page_text);
    END;

    CREATE TRIGGER parts_ad AFTER DELETE ON parts BEGIN
        INSERT INTO parts_fts(parts_fts, rowid, catalog_type, part_number, description, page_text)
        VALUES ('delete', old.id, old.catalog_type, old.part_number, old.description, old.page_text);
    END;

    CREATE TRIGGER parts_au AFTER UPDATE ON parts BEGIN
        INSERT INTO parts_fts(parts_fts, rowid, catalog_type, part_number, description, page_text)
        VALUES ('delete', old.id, old.catalog_type, old.part_number, old.description, old.page_text);
        INSERT INTO parts_fts(rowid, catalog_type, part_number, description, page_text)
        VALUES (new.id, new.catalog_type, new.part_number, new.description, new.page_text);
    END;
    """)

    # --- Indexes ---
    cur.executescript("""
    CREATE INDEX idx_part_number ON parts(part_number);
    CREATE INDEX idx_catalog_type ON parts(catalog_type);
    CREATE INDEX idx_page ON parts(page);
    """)
    conn.commit()
    conn.close()
    print("Recreated catalog.db with pdf_path support and FTS triggers")


if __name__ == "__main__":
    setup_database()
