#!/usr/bin/env python3
"""
Script to fix image paths in the database
"""
import sqlite3
import os
from pathlib import Path

def fix_image_paths():
    db_path = "app/data/catalog.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get all parts with image paths
    cur.execute("SELECT id, image_path FROM parts WHERE image_path IS NOT NULL")
    parts = cur.fetchall()
    
    updates = 0
    for part_id, image_path in parts:
        if image_path:
            # Extract just the filename from the path
            filename = Path(image_path).name
            new_path = f"part_images/{filename}"
            
            # Update the database
            cur.execute("UPDATE parts SET image_path = ? WHERE id = ?", (new_path, part_id))
            updates += 1
            print(f"Updated part {part_id}: {image_path} -> {new_path}")
    
    conn.commit()
    conn.close()
    print(f"Fixed {updates} image paths")

if __name__ == "__main__":
    fix_image_paths()