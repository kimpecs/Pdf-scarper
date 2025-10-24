import sys
from pathlib import Path
import sqlite3

# Add project root to sys.path so 'app' package is discoverable
project_root = Path(__file__).resolve().parents[3]
sys.path.append(str(project_root))

from app.utils.config import settings
from app.utils.logger import setup_logging

logger = setup_logging()

def init_database():
    """Initialize database using internal app packages and enhanced schema"""
    
    # Determine DB path from settings - FIXED PATH RESOLUTION
    db_url = getattr(settings, 'DATABASE_URL', 'sqlite:///knowledge_base.db')
    
    if db_url.startswith('sqlite:///'):
        db_path = db_url.replace('sqlite:///', '')
        # Make path absolute relative to project root
        db_path = project_root / db_path
    else:
        # Fallback to default location
        db_path = project_root / 'knowledge_base.db'
    
    # Create parent directories if they don't exist
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create data directories
    data_dir = project_root / 'data'
    images_dir = data_dir / 'page_images'
    pdf_dir = data_dir / 'pdfs'
    guides_dir = data_dir / 'guides'
    
    for directory in [data_dir, images_dir, pdf_dir, guides_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    # Delete existing DB if it exists
    if db_path.exists():
        db_path.unlink()
        logger.info(f"Deleted existing database at {db_path}")

    logger.info(f"Creating database at: {db_path}")

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
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        """)

        conn.commit()
        conn.close()
        logger.info(f"Database setup complete at {db_path}")
        logger.info(f"Data directories created at: {data_dir.resolve()}")
        
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        raise

if __name__ == "__main__":
    init_database()