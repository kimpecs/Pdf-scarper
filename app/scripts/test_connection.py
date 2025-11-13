import sqlite3
import json

def test_database():
    db_path = r"C:\Users\kpecco\Desktop\codes\TESTING\app\data\catalog.db"
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        print("=== DATABASE CONNECTION TEST ===")
        
        # Test parts count
        cur.execute("SELECT COUNT(*) as count FROM parts")
        parts_count = cur.fetchone()['count']
        print(f"  Total parts in database: {parts_count:,}")
        
        # Test catalogs
        cur.execute("SELECT DISTINCT catalog_type FROM parts WHERE catalog_type IS NOT NULL AND catalog_type != '' LIMIT 5")
        catalogs = [row['catalog_type'] for row in cur.fetchall()]
        print(f"  Sample catalogs: {catalogs}")
        
        # Test categories
        cur.execute("SELECT DISTINCT category FROM parts WHERE category IS NOT NULL AND category != '' LIMIT 5")
        categories = [row['category'] for row in cur.fetchall()]
        print(f"  Sample categories: {categories}")
        
        # Test a sample part
        cur.execute("SELECT part_number, description, catalog_type FROM parts LIMIT 1")
        sample_part = cur.fetchone()
        if sample_part:
            print(f"  Sample part: {dict(sample_part)}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"  Database error: {e}")
        return False

if __name__ == "__main__":
    test_database()