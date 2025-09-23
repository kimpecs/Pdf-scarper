# db_setup.py
import sqlite3
from pathlib import Path

DB_PATH = Path("catalog.db")

def setup_database():
    if DB_PATH.exists():
        DB_PATH.unlink()  # delete existing database
        print("Deleted existing catalog.db")

    # Recreate tables
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Create main parts table with catalog_type column
    cur.execute("""
    CREATE TABLE parts (
        id INTEGER PRIMARY KEY,
        catalog_type TEXT,  -- 'dayton' or 'fort_pro'
        part_type TEXT,     -- 'part', 'caliper', 'kit'
        part_number TEXT,
        description TEXT,
        category TEXT,
        page INTEGER,
        image_path TEXT,
        page_text TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # Create FTS table for full-text search
    cur.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS parts_fts USING fts5(
        catalog_type,
        part_number,
        description,
        page_text,
        content='parts',
        content_rowid='id'
    );
    """)

    # Add triggers for automatic FTS synchronization
    cur.execute("""
    CREATE TRIGGER IF NOT EXISTS parts_ai AFTER INSERT ON parts BEGIN
        INSERT INTO parts_fts(rowid, catalog_type, part_number, description, page_text)
        VALUES (new.id, new.catalog_type, new.part_number, new.description, new.page_text);
    END;
    """)

    cur.execute("""
    CREATE TRIGGER IF NOT EXISTS parts_ad AFTER DELETE ON parts BEGIN
        INSERT INTO parts_fts(parts_fts, rowid, catalog_type, part_number, description, page_text)
        VALUES ('delete', old.id, old.catalog_type, old.part_number, old.description, old.page_text);
    END;
    """)

    cur.execute("""
    CREATE TRIGGER IF NOT EXISTS parts_au AFTER UPDATE ON parts BEGIN
        INSERT INTO parts_fts(parts_fts, rowid, catalog_type, part_number, description, page_text)
        VALUES ('delete', old.id, old.catalog_type, old.part_number, old.description, old.page_text);
        INSERT INTO parts_fts(rowid, catalog_type, part_number, description, page_text)
        VALUES (new.id, new.catalog_type, new.part_number, new.description, new.page_text);
    END;
    """)

    # Create indexes for better performance
    cur.execute("CREATE INDEX IF NOT EXISTS idx_part_number ON parts(part_number)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_catalog_type ON parts(catalog_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_page ON parts(page)")

    conn.commit()
    conn.close()
    print("Recreated catalog.db with enhanced parts table and FTS triggers")

if __name__ == "__main__":
    setup_database()