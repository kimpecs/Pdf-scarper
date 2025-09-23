# check_db.py
import sqlite3
from pathlib import Path

DB_PATH = Path("catalog.db")

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Check database structure
    print("=== Database Structure ===")
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cur.fetchall()
    print("Tables:", [table[0] for table in tables])
    
    # Check parts table structure
    cur.execute("PRAGMA table_info(parts);")
    columns = cur.fetchall()
    print("\nParts table columns:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    # Check first 30 rows with more details
    print("\n=== First 30 Parts ===")
    cur.execute("""
        SELECT id, part_type, part_number, description, category, page 
        FROM parts 
        ORDER BY page, part_number 
        LIMIT 30;
    """)
    rows = cur.fetchall()

    if not rows:
        print("No parts found in the database. Extraction may have failed.")
    else:
        for row in rows:
            print(f"ID: {row[0]}, Type: {row[1]}, Part: {row[2]}, Category: {row[4]}, Page: {row[5]}")
            if row[3]:
                print(f"  Description: {row[3][:80]}...")
    
    # Check distribution by category
    print("\n=== Parts by Category ===")
    cur.execute("SELECT category, COUNT(*) FROM parts GROUP BY category ORDER BY COUNT(*) DESC;")
    cats = cur.fetchall()
    for cat, count in cats:
        print(f"  {cat}: {count} parts")
    
    # Check distribution by page
    print("\n=== Parts by Page ===")
    cur.execute("SELECT page, COUNT(*) FROM parts GROUP BY page ORDER BY page;")
    pages = cur.fetchall()
    for page, count in pages:
        print(f"  Page {page}: {count} parts")
    
    conn.close()

if __name__ == "__main__":
    main()