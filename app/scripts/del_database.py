import os
import sqlite3
from pathlib import Path
import sys

def delete_database():
    """Completely delete the database and all related files"""
    project_root = Path(__file__).resolve().parent
    db_path = project_root / "app" / "data" / "catalog.db"
    
    files_to_delete = [
        db_path,
        db_path.parent / f"{db_path.name}-shm",
        db_path.parent / f"{db_path.name}-wal",
        db_path.parent / f"{db_path.name}-journal"
    ]
    
    deleted_count = 0
    for file_path in files_to_delete:
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"✅ Deleted: {file_path}")
                deleted_count += 1
            except Exception as e:
                print(f"❌ Failed to delete {file_path}: {e}")
    
    if deleted_count == 0:
        print("ℹ️ No database files found to delete")
    else:
        print(f"🎯 Successfully deleted {deleted_count} database files")

if __name__ == "__main__":
    delete_database()