#!/usr/bin/env python3
"""
Check system completion status
"""
import sqlite3
from pathlib import Path

def check_database():
    """Check if database is populated"""
    db_path = Path("catalog.db")
    if not db_path.exists():
        print("[ERROR] Database file not found")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        
        # Check parts table
        cur.execute("SELECT COUNT(*) FROM parts")
        part_count = cur.fetchone()[0]
        
        # Check guides table if exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='technical_guides'")
        has_guides = cur.fetchone() is not None
        
        conn.close()
        
        print(f"[INFO] Parts in database: {part_count}")
        print(f"[INFO] Guides table exists: {has_guides}")
        
        return part_count > 0
        
    except Exception as e:
        print(f"[ERROR] Database check failed: {e}")
        return False

def check_pdfs():
    """Check if PDF directories exist"""
    pdf_dirs = [
        Path("app/data/pdfs"),
        Path("app/data/guides")
    ]
    
    all_exist = True
    for pdf_dir in pdf_dirs:
        if pdf_dir.exists():
            pdf_count = len(list(pdf_dir.glob("*.pdf")))
            print(f"[INFO] PDFs in {pdf_dir}: {pdf_count}")
        else:
            print(f"[WARNING] Directory not found: {pdf_dir}")
            all_exist = False
    
    return all_exist

def main():
    """Run completion checks"""
    print("[CHECK] Running system completion check...")
    
    db_ok = check_database()
    pdfs_ok = check_pdfs()
    
    if db_ok and pdfs_ok:
        print("[SUCCESS] System check completed successfully")
        return True
    else:
        print("[WARNING] System check completed with issues")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)