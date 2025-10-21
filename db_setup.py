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

    # --- Parts Table (Updated for flexibility) ---
    cur.execute("""
    CREATE TABLE parts (
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

    # --- Full Text Search Table (Updated) ---
    cur.execute("""
    CREATE VIRTUAL TABLE parts_fts USING fts5(
        catalog_name,
        catalog_type,
        part_number,
        description,
        page_text,
        machine_info,
        content='parts',
        content_rowid='id'
    );
    """)

    # --- FTS Triggers (Updated) ---
    cur.executescript("""
    CREATE TRIGGER parts_ai AFTER INSERT ON parts BEGIN
        INSERT INTO parts_fts(rowid, catalog_name, catalog_type, part_number, description, page_text, machine_info)
        VALUES (new.id, new.catalog_name, new.catalog_type, new.part_number, new.description, new.page_text, new.machine_info);
    END;

    CREATE TRIGGER parts_ad AFTER DELETE ON parts BEGIN
        INSERT INTO parts_fts(parts_fts, rowid, catalog_name, catalog_type, part_number, description, page_text, machine_info)
        VALUES ('delete', old.id, old.catalog_name, old.catalog_type, old.part_number, old.description, old.page_text, old.machine_info);
    END;

    CREATE TRIGGER parts_au AFTER UPDATE ON parts BEGIN
        INSERT INTO parts_fts(parts_fts, rowid, catalog_name, catalog_type, part_number, description, page_text, machine_info)
        VALUES ('delete', old.id, old.catalog_name, old.catalog_type, old.part_number, old.description, old.page_text, old.machine_info);
        INSERT INTO parts_fts(rowid, catalog_name, catalog_type, part_number, description, page_text, machine_info)
        VALUES (new.id, new.catalog_name, new.catalog_type, new.part_number, new.description, new.page_text, new.machine_info);
    END;
    """)

    # --- Indexes (Updated) ---
    cur.executescript("""
    CREATE INDEX idx_part_number ON parts(part_number);
    CREATE INDEX idx_catalog_name ON parts(catalog_name);
    CREATE INDEX idx_catalog_type ON parts(catalog_type);
    CREATE INDEX idx_page ON parts(page);
    CREATE INDEX idx_part_type ON parts(part_type);
    CREATE INDEX idx_category ON parts(category);
    """)
    
    conn.commit()
    conn.close()
    print("Recreated catalog.db with enhanced schema and FTS support")

def add_technical_guides_table():
    """Add technical_guides table to existing database"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
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
        )
    """)
    
    conn.commit()
    conn.close()
    print("Added technical_guides table to database")

def migrate_existing_data():
    """Migrate existing data to new schema"""
    if not DB_PATH.exists():
        print("No database found to migrate")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    try:
        # Check if migration is needed
        cur.execute("PRAGMA table_info(parts)")
        columns = [col[1] for col in cur.fetchall()]
        
        if 'catalog_name' not in columns:
            print("Migrating existing data to new schema...")
            
            # Add new columns
            cur.execute("ALTER TABLE parts ADD COLUMN catalog_name TEXT")
            cur.execute("ALTER TABLE parts ADD COLUMN machine_info TEXT")
            cur.execute("ALTER TABLE parts ADD COLUMN specifications TEXT")
            
            # Populate catalog_name from catalog_type
            cur.execute("UPDATE parts SET catalog_name = catalog_type")
            
            # Recreate FTS table with new schema
            cur.execute("DROP TABLE IF EXISTS parts_fts")
            cur.execute("""
                CREATE VIRTUAL TABLE parts_fts USING fts5(
                    catalog_name,
                    catalog_type,
                    part_number,
                    description,
                    page_text,
                    machine_info,
                    content='parts',
                    content_rowid='id'
                )
            """)
            
            # Recreate triggers
            cur.executescript("""
                DROP TRIGGER IF EXISTS parts_ai;
                DROP TRIGGER IF EXISTS parts_ad;
                DROP TRIGGER IF EXISTS parts_au;
                
                CREATE TRIGGER parts_ai AFTER INSERT ON parts BEGIN
                    INSERT INTO parts_fts(rowid, catalog_name, catalog_type, part_number, description, page_text, machine_info)
                    VALUES (new.id, new.catalog_name, new.catalog_type, new.part_number, new.description, new.page_text, new.machine_info);
                END;

                CREATE TRIGGER parts_ad AFTER DELETE ON parts BEGIN
                    INSERT INTO parts_fts(parts_fts, rowid, catalog_name, catalog_type, part_number, description, page_text, machine_info)
                    VALUES ('delete', old.id, old.catalog_name, old.catalog_type, old.part_number, old.description, old.page_text, old.machine_info);
                END;

                CREATE TRIGGER parts_au AFTER UPDATE ON parts BEGIN
                    INSERT INTO parts_fts(parts_fts, rowid, catalog_name, catalog_type, part_number, description, page_text, machine_info)
                    VALUES ('delete', old.id, old.catalog_name, old.catalog_type, old.part_number, old.description, old.page_text, old.machine_info);
                    INSERT INTO parts_fts(rowid, catalog_name, catalog_type, part_number, description, page_text, machine_info)
                    VALUES (new.id, new.catalog_name, new.catalog_type, new.part_number, new.description, new.page_text, new.machine_info);
                END;
            """)
            
            conn.commit()
            print("Migration completed successfully!")
        else:
            print("Database already uses new schema")
            
    except Exception as e:
        print(f"Migration error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    setup_database()