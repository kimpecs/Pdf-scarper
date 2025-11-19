import sys
from pathlib import Path
import sqlite3
from fastapi import File, UploadFile

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent  # Points to app/ directory
sys.path.insert(0, str(project_root))

def setup_database():
    """Initialize database without importing app modules"""
    
    # FIXED: Use the correct database path that matches your config
    db_path = project_root / "data" / "catalog.db"  # This matches what your PDF processing expects
    data_dir = project_root / "data"
    images_dir = data_dir / "part_images"
    pdf_dir = data_dir / "pdfs"
    guides_dir = data_dir / "guides"
    
    # Create directories
    for directory in [data_dir, images_dir, pdf_dir, guides_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    # Delete existing DB if it exists
    if db_path.exists():
        db_path.unlink()
        print(f"Deleted existing database at {db_path}")

    print(f"Creating database at: {db_path}")

    try:
        # Connect to SQLite
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()

        # --- Parts Table ---
        cur.execute("""
        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY,
            catalog_name TEXT NOT NULL,
            catalog_type TEXT,
            part_type TEXT,
            part_number TEXT NOT NULL,
            description TEXT,
            category TEXT,
            page INTEGER,
            image_path TEXT,
            page_text TEXT,
            pdf_path TEXT,
            machine_info TEXT,
            specifications TEXT,
            oe_numbers TEXT,
            applications TEXT,
            features TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # --- Technical Guides Table ---
        cur.execute("""
        CREATE TABLE IF NOT EXISTS technical_guides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guide_name TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            s3_key TEXT,
            template_fields TEXT,
            pdf_path TEXT,
            related_parts TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # --- Guide-Parts Association Table ---
        cur.execute("""
        CREATE TABLE IF NOT EXISTS guide_parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guide_id INTEGER,
            part_number TEXT,
            confidence_score REAL DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (guide_id) REFERENCES technical_guides (id),
            UNIQUE(guide_id, part_number)
        );
        """)

        # --- Full Text Search Table ---
        cur.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS parts_fts USING fts5(
            catalog_name,
            catalog_type,
            part_number,
            description,
            page_text,
            machine_info,
            specifications,
            oe_numbers,
            applications,
            content='parts',
            content_rowid='id'
        );
        """)

        # --- FTS Triggers ---
        cur.executescript("""
        CREATE TRIGGER IF NOT EXISTS parts_ai AFTER INSERT ON parts BEGIN
            INSERT INTO parts_fts(rowid, catalog_name, catalog_type, part_number, description, page_text, machine_info, specifications, oe_numbers, applications)
            VALUES (new.id, new.catalog_name, new.catalog_type, new.part_number, new.description, new.page_text, new.machine_info, new.specifications, new.oe_numbers, new.applications);
        END;

        CREATE TRIGGER IF NOT EXISTS parts_ad AFTER DELETE ON parts BEGIN
            INSERT INTO parts_fts(parts_fts, rowid, catalog_name, catalog_type, part_number, description, page_text, machine_info, specifications, oe_numbers, applications)
            VALUES ('delete', old.id, old.catalog_name, old.catalog_type, old.part_number, old.description, old.page_text, old.machine_info, old.specifications, old.oe_numbers, old.applications);
        END;

        CREATE TRIGGER IF NOT EXISTS parts_au AFTER UPDATE ON parts BEGIN
            INSERT INTO parts_fts(parts_fts, rowid, catalog_name, catalog_type, part_number, description, page_text, machine_info, specifications, oe_numbers, applications)
            VALUES ('delete', old.id, old.catalog_name, old.catalog_type, old.part_number, old.description, old.page_text, old.machine_info, old.specifications, old.oe_numbers, old.applications);
            INSERT INTO parts_fts(rowid, catalog_name, catalog_type, part_number, description, page_text, machine_info, specifications, oe_numbers, applications)
            VALUES (new.id, new.catalog_name, new.catalog_type, new.part_number, new.description, new.page_text, new.machine_info, new.specifications, new.oe_numbers, new.applications);
        END;
        """)

        # --- Indexes ---
        cur.executescript("""
        CREATE INDEX IF NOT EXISTS idx_part_number ON parts(part_number);
        CREATE INDEX IF NOT EXISTS idx_catalog_name ON parts(catalog_name);
        CREATE INDEX IF NOT EXISTS idx_catalog_type ON parts(catalog_type);
        CREATE INDEX IF NOT EXISTS idx_page ON parts(page);
        CREATE INDEX IF NOT EXISTS idx_part_type ON parts(part_type);
        CREATE INDEX IF NOT EXISTS idx_category ON parts(category);
        CREATE INDEX IF NOT EXISTS idx_oe_numbers ON parts(oe_numbers);
        
        -- Guide-Parts indexes
        CREATE INDEX IF NOT EXISTS idx_guide_parts_guide_id ON guide_parts(guide_id);
        CREATE INDEX IF NOT EXISTS idx_guide_parts_part_number ON guide_parts(part_number);
        """)

        conn.commit()
        conn.close()
        print(f"Database setup complete at {db_path}")
        print(f"Data directories created at: {data_dir}")
        
    except Exception as e:
        print(f"Database setup failed: {e}")
        raise

if __name__ == "__main__":
    setup_database()