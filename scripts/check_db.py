# check_db.py
import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path(r"C:\Users\kpecco\Desktop\codes\TESTING\data\catalog.db")

def print_header(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)

def print_tables(cur):
    print_header("Database Structure")
    cur.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY type, name;")
    tables = cur.fetchall()
    
    print("Tables & Views:")
    for table in tables:
        print(f"  {table[1].upper():6} {table[0]}")
    return [t[0] for t in tables if t[1] == 'table']

def print_table_info(cur, table_name: str):
    print_header(f"{table_name} Table Structure")
    cur.execute(f"PRAGMA table_info({table_name});")
    columns = cur.fetchall()
    
    print(f"Columns ({len(columns)}):")
    for col in columns:
        pk = " PRIMARY KEY" if col[5] else ""
        nn = " NOT NULL" if col[3] else ""
        default = f" DEFAULT {col[4]}" if col[4] else ""
        print(f"  {col[0]:2} {col[1]:20} {col[2]:15}{nn}{pk}{default}")

def print_table_stats(cur, table_name: str):
    print_header(f"{table_name} Statistics")
    
    # Row count
    cur.execute(f"SELECT COUNT(*) FROM {table_name};")
    count = cur.fetchone()[0]
    print(f"Total rows: {count:,}")
    
    if count > 0:
        # Date range
        cur.execute(f"SELECT MIN(created_at), MAX(created_at) FROM {table_name} WHERE created_at IS NOT NULL;")
        min_date, max_date = cur.fetchone()
        if min_date and max_date:
            print(f"Date range: {min_date} to {max_date}")

def print_sample_parts(cur, limit: int = 20):
    print_header(f"Sample Parts (First {limit})")
    
    cur.execute("""
        SELECT id, catalog_name, catalog_type, part_type, part_number, 
               description, category, page, pdf_path, machine_info
        FROM parts
        ORDER BY catalog_name, page, part_number
        LIMIT ?;
    """, (limit,))

    rows = cur.fetchall()

    if not rows:
        print("No parts found in the database.")
        return

    for row in rows:
        machine_info = json.loads(row[9]) if row[9] else {}
        models = machine_info.get('models', [])[:3] if machine_info else []
        
        print(f"ID: {row[0]}")
        print(f"  Catalog: {row[1]} ({row[2]})")
        print(f"  Part: {row[4]} ({row[3]})")
        print(f"  Page: {row[7]} | Category: {row[6]}")
        if models:
            print(f"  Models: {', '.join(models)}")
        if row[5]:
            desc = row[5][:100] + "..." if len(row[5]) > 100 else row[5]
            print(f"  Desc: {desc}")
        print()

def print_distribution(cur, field: str, label: str, limit=15):
    print_header(f"Parts by {label}")
    
    cur.execute(f"""
        SELECT {field}, COUNT(*) as count 
        FROM parts 
        WHERE {field} IS NOT NULL 
        GROUP BY {field} 
        ORDER BY count DESC 
        LIMIT ?;
    """, (limit,))
    
    results = cur.fetchall()
    total = sum(count for _, count in results)
    
    for val, count in results:
        percentage = (count / total) * 100 if total > 0 else 0
        print(f"  {val or 'NULL':30} {count:6,} ({percentage:5.1f}%)")

def print_fts_status(cur):
    print_header("Full Text Search Status")
    
    try:
        # Check FTS table content
        cur.execute("SELECT COUNT(*) FROM parts_fts;")
        fts_count = cur.fetchone()[0]
        print(f"FTS entries: {fts_count:,}")
        
        # Check FTS configuration
        cur.execute("SELECT * FROM parts_fts WHERE parts_fts MATCH 'test' LIMIT 1;")
        print("FTS operational: [OK]")
        
    except Exception as e:
        print(f"FTS status: [ERROR] ({e})")

def print_catalog_summary(cur):
    print_header("Catalog Summary")
    
    cur.execute("""
        SELECT 
            catalog_name,
            catalog_type,
            COUNT(*) as part_count,
            COUNT(DISTINCT page) as page_count,
            COUNT(DISTINCT category) as category_count,
            MIN(page) as min_page,
            MAX(page) as max_page
        FROM parts 
        GROUP BY catalog_name, catalog_type
        ORDER BY part_count DESC;
    """)
    
    catalogs = cur.fetchall()
    
    print(f"{'Catalog Name':25} {'Type':15} {'Parts':8} {'Pages':8} {'Categories':12} {'Page Range'}")
    print("-" * 80)
    
    for catalog in catalogs:
        name, ctype, parts, pages, cats, min_pg, max_pg = catalog
        page_range = f"{min_pg}-{max_pg}" if min_pg != max_pg else str(min_pg)
        print(f"{name:25} {ctype:15} {parts:8,} {pages:8} {cats:12} {page_range:10}")

def print_part_number_analysis(cur):
    print_header("Part Number Analysis")
    
    # Most common part number patterns
    cur.execute("""
        SELECT 
            CASE 
                WHEN part_number GLOB 'D[0-9]*' THEN 'Dayton (D*)'
                WHEN part_number GLOB '*-*' THEN 'Contains Dash'
                WHEN part_number GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]*' THEN '6+ Digits'
                WHEN part_number GLOB '[A-Z][A-Z]*[0-9]*' THEN 'Alpha-Numeric'
                ELSE 'Other'
            END as pattern,
            COUNT(*) as count
        FROM parts
        GROUP BY pattern
        ORDER BY count DESC;
    """)
    
    print("Part Number Patterns:")
    for pattern, count in cur.fetchall():
        print(f"  {pattern:20} {count:6,}")

def print_database_size():
    print_header("Database Size Information")
    
    if DB_PATH.exists():
        size_bytes = DB_PATH.stat().st_size
        size_mb = size_bytes / (1024 * 1024)
        print(f"Database file size: {size_mb:.2f} MB")
        
        # Estimate record size
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM parts;")
        count = cur.fetchone()[0]
        if count > 0:
            avg_size = size_bytes / count if count > 0 else 0
            print(f"Average bytes per record: {avg_size:.1f}")
        conn.close()
    else:
        print("Database file not found")

def print_technical_guides_status(cur):
    print_header("Technical Guides Status")
    
    cur.execute("SELECT COUNT(*) FROM technical_guides;")
    count = cur.fetchone()[0]
    
    if count > 0:
        print(f"Technical guides: {count}")
        cur.execute("SELECT guide_name, display_name, category FROM technical_guides LIMIT 10;")
        for guide in cur.fetchall():
            print(f"  {guide[0]:20} {guide[1]:25} ({guide[2]})")
    else:
        print("No technical guides found")

def print_technical_guides_stats(cur, limit=10):
    print_header("Technical Guides Stats")
    
    # Total guides
    cur.execute("SELECT COUNT(*) FROM technical_guides;")
    total = cur.fetchone()[0]
    print(f"Total technical guides: {total}")
    
    if total > 0:
        # Sample guides
        cur.execute(f"SELECT guide_name, display_name, category, created_at FROM technical_guides ORDER BY created_at DESC LIMIT ?;", (limit,))
        rows = cur.fetchall()
        print(f"Most recent {len(rows)} guides:")
        for guide in rows:
            print(f"  {guide[0]:20} {guide[1]:25} ({guide[2]}) Created: {guide[3]}")


def check_database_health(cur):
    print_header("Database Health Check")
    
    checks = []
    
    # Check 1: Parts table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='parts';")
    checks.append(("Parts table exists", bool(cur.fetchone())))
    
    # Check 2: FTS table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='parts_fts';")
    checks.append(("FTS table exists", bool(cur.fetchone())))
    
    # Check 3: Has data
    cur.execute("SELECT COUNT(*) FROM parts;")
    parts_count = cur.fetchone()[0]
    checks.append(("Has parts data", parts_count > 0))
    
    # Check 4: FTS has data
    cur.execute("SELECT COUNT(*) FROM parts_fts;")
    fts_count = cur.fetchone()[0]
    checks.append(("FTS has data", fts_count > 0))
    
    # Check 5: FTS matches parts count
    checks.append(("FTS in sync", fts_count == parts_count))
    
    # Check 6: Indexes exist
    cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%';")
    indexes = [row[0] for row in cur.fetchall()]
    checks.append(("Has indexes", len(indexes) >= 3))
    
    # Check 7: Technical guides table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='technical_guides';")
    checks.append(("Technical guides table exists", bool(cur.fetchone())))

    # Check 8: Technical guides has data
    cur.execute("SELECT COUNT(*) FROM technical_guides;")
    guides_count = cur.fetchone()[0]
    checks.append(("Has technical guides data", guides_count > 0))

    
    # Print results
    for check, passed in checks:
        status = "[OK]" if passed else "[ERROR]"
        print(f"  {status} {check}")

def main():
    if not DB_PATH.exists():
        print("[ERROR] Database not found. Run db_setup.py first.")
        return

    print_header("DATABASE ANALYSIS REPORT")
    print(f"Database: {DB_PATH}")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        # Basic health check
        check_database_health(cur)
        
        # Database structure
        tables = print_tables(cur)
        
        if "parts" in tables:
            print_table_info(cur, "parts")
            print_table_stats(cur, "parts")
            print_catalog_summary(cur)
            print_sample_parts(cur, 15)
            print_distribution(cur, "catalog_name", "Catalog")
            print_distribution(cur, "part_type", "Part Type")
            print_distribution(cur, "category", "Category", 10)
            print_part_number_analysis(cur)
            print_fts_status(cur)
        
        if "technical_guides" in tables:
            print_technical_guides_status(cur)
            print_table_info(cur, "technical_guides")
            print_table_stats(cur, "technical_guides")
            print_technical_guides_stats(cur, limit=10)
                
        # Database size
        print_database_size()
        
        # Performance tips
        print_header("Performance Tips")
        print("[OK] Ensure indexes exist on frequently searched columns")
        print("[OK] Regular VACUUM to optimize database")
        print("[OK] Use FTS for text searches")
        print("[OK] Consider partitioning for very large datasets")

    except Exception as e:
        print(f"[ERROR] Error during analysis: {e}")
    finally:
        conn.close()

    print_header("ANALYSIS COMPLETE")

if __name__ == "__main__":
    main()