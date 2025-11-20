import sqlite3
from pathlib import Path
import re

def clean_descriptions(text: str) -> str:
    """Clean text by removing excessive dots and whitespace"""
    if not text:
        return ""
    
    # Remove sequences of 3 or more dots
    text = re.sub(r'\.{3,}', ' ', text)
    
    # Remove sequences of dashes
    text = re.sub(r'-{3,}', ' ', text)
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def merge_duplicate_parts(db_path: Path):
    """Merge duplicate parts and clean data"""
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    
    print("🔄 Finding duplicate parts...")
    
    # Find duplicates (same catalog, part_number, page)
    cur.execute("""
        SELECT catalog_name, part_number, page, COUNT(*) as count
        FROM parts 
        GROUP BY catalog_name, part_number, page 
        HAVING COUNT(*) > 1
    """)
    
    duplicates = cur.fetchall()
    print(f"📊 Found {len(duplicates)} duplicate groups")
    
    for catalog, part_num, page, count in duplicates:
        print(f"🔄 Processing {catalog} - {part_num} - Page {page} ({count} duplicates)")
        
        # Get all duplicates for this part
        cur.execute("""
            SELECT id, description, applications, features, specifications, machine_info
            FROM parts 
            WHERE catalog_name = ? AND part_number = ? AND page = ?
            ORDER BY id
        """, (catalog, part_num, page))
        
        parts = cur.fetchall()
        if len(parts) < 2:
            continue
        
        # Keep the first part, merge others into it
        keep_id = parts[0][0]
        merged_data = {
            'description': clean_descriptions(parts[0][1] or ""),
            'applications': parts[0][2] or "",
            'features': parts[0][3] or "",
            'specifications': parts[0][4] or "",
            'machine_info': parts[0][5] or ""
        }
        
        # Merge data from duplicates
        for part in parts[1:]:
            part_id, desc, apps, features, specs, machine = part
            
            if desc and desc not in merged_data['description']:
                merged_data['description'] += " " + clean_descriptions(desc)
            if apps and apps not in merged_data['applications']:
                merged_data['applications'] += ";" + apps
            if features and features not in merged_data['features']:
                merged_data['features'] += " " + clean_descriptions(features)
            if specs and specs not in merged_data['specifications']:
                merged_data['specifications'] += " " + clean_descriptions(specs)
            if machine and machine not in merged_data['machine_info']:
                merged_data['machine_info'] += " " + machine
        
        # Clean merged data
        for key in merged_data:
            if isinstance(merged_data[key], str):
                merged_data[key] = clean_descriptions(merged_data[key])
        
        # Update the kept part with merged data
        cur.execute("""
            UPDATE parts 
            SET description = ?, applications = ?, features = ?, specifications = ?, machine_info = ?
            WHERE id = ?
        """, (
            merged_data['description'][:500],  # Limit length
            merged_data['applications'][:1000],
            merged_data['features'][:1000],
            merged_data['specifications'][:1000],
            merged_data['machine_info'][:1000],
            keep_id
        ))
        
        # Delete duplicates (keep only the first one)
        duplicate_ids = [str(part[0]) for part in parts[1:]]
        placeholders = ','.join(['?'] * len(duplicate_ids))
        
        cur.execute(f"DELETE FROM parts WHERE id IN ({placeholders})", duplicate_ids)
        
        print(f"✅ Merged {len(parts)-1} duplicates into ID {keep_id}")
    
    conn.commit()
    
    # Clean all descriptions in the database
    print("🧹 Cleaning all part descriptions...")
    cur.execute("SELECT id, description FROM parts")
    parts = cur.fetchall()
    
    for part_id, description in parts:
        if description:
            cleaned = clean_descriptions(description)
            cur.execute("UPDATE parts SET description = ? WHERE id = ?", (cleaned, part_id))
    
    conn.commit()
    conn.close()
    print("✅ Data cleaning completed!")

def main():
    db_path = Path("app/data/catalog.db")
    if db_path.exists():
        merge_duplicate_parts(db_path)
    else:
        print("❌ Database not found. Please run setup first.")

if __name__ == "__main__":
    main()