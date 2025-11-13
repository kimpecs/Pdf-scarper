# [file name]: fix_database.py
import sqlite3
from pathlib import Path

def fix_database_schema():
    db_path = Path(r"C:\Users\kpecco\Desktop\codes\TESTING\app\data\catalog.db")
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    
    try:
        print("Adding missing columns to technical_guides table...")
        
        # Add pdf_path column
        cur.execute("ALTER TABLE technical_guides ADD COLUMN pdf_path TEXT")
        print("✓ Added pdf_path column")
        
        # Add related_parts column  
        cur.execute("ALTER TABLE technical_guides ADD COLUMN related_parts TEXT")
        print("✓ Added related_parts column")
        
        conn.commit()
        print("  Database schema updated successfully!")
        
        # Verify the changes
        cur.execute("PRAGMA table_info(technical_guides)")
        columns = [col[1] for col in cur.fetchall()]
        print("\nUpdated technical_guides columns:")
        for col in columns:
            print(f"  - {col}")
        
    except Exception as e:
        print(f"  Error updating database: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    fix_database_schema()
