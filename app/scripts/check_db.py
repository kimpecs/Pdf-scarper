import sqlite3
from pathlib import Path
import sys
from datetime import datetime

# Add project root to Python path
script_dir = Path(__file__).parent  # app/scripts/
app_dir = script_dir.parent         # app/
sys.path.insert(0, str(app_dir))

def create_missing_tables():
    """Create any missing tables"""
    db_path = app_dir / "data" / "catalog.db"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    
    print("🔧 CHECKING FOR MISSING TABLES...")
    
    # Check if part_guides table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='part_guides'")
    if not cur.fetchone():
        print("Creating missing part_guides table...")
        cur.execute("""
            CREATE TABLE part_guides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                part_id INTEGER NOT NULL,
                guide_id INTEGER NOT NULL,
                confidence_score REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (part_id) REFERENCES parts (id),
                FOREIGN KEY (guide_id) REFERENCES technical_guides (id),
                UNIQUE(part_id, guide_id)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_part_guides_part_id ON part_guides(part_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_part_guides_guide_id ON part_guides(guide_id)")
        print("✅ Created part_guides table")
    
    conn.commit()
    conn.close()

def analyze_database():
    """Comprehensive database analysis"""
    db_path = app_dir / "data" / "catalog.db"
    
    if not db_path.exists():
        print("❌ Database not found!")
        return
    
    print("🔍 DATABASE ANALYSIS REPORT")
    print("=" * 60)
    print(f"Database: {db_path}")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # 1. Basic Table Info
    print("📊 TABLE OVERVIEW")
    print("-" * 40)
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cur.fetchall()]
    
    for table in tables:
        cur.execute(f"SELECT COUNT(*) as count FROM {table}")
        count = cur.fetchone()[0]
        print(f"  {table:25} : {count:>8,} rows")
    print()
    
    # 2. Parts Analysis
    print("🔧 PARTS ANALYSIS")
    print("-" * 40)
    
    # Total parts
    cur.execute("SELECT COUNT(*) FROM parts")
    total_parts = cur.fetchone()[0]
    print(f"Total parts: {total_parts:,}")
    
    # Parts with images
    cur.execute("SELECT COUNT(*) FROM parts WHERE image_path IS NOT NULL")
    parts_with_images = cur.fetchone()[0]
    print(f"Parts with images: {parts_with_images:,} ({parts_with_images/total_parts*100:.1f}%)")
    
    # Parts by catalog
    print("\n📁 TOP 10 CATALOGS:")
    cur.execute("""
        SELECT catalog_name, catalog_type, COUNT(*) as count 
        FROM parts 
        GROUP BY catalog_name, catalog_type 
        ORDER BY count DESC 
        LIMIT 10
    """)
    for row in cur.fetchall():
        percentage = (row['count'] / total_parts) * 100
        print(f"  {row['catalog_name']:40} : {row['count']:>6,} ({percentage:.1f}%) - {row['catalog_type']}")
    
    # Parts by category
    print("\n📂 TOP 10 CATEGORIES:")
    cur.execute("""
        SELECT category, COUNT(*) as count 
        FROM parts 
        WHERE category IS NOT NULL AND category != 'General'
        GROUP BY category 
        ORDER BY count DESC 
        LIMIT 10
    """)
    for row in cur.fetchall():
        percentage = (row['count'] / total_parts) * 100
        print(f"  {row['category']:25} : {row['count']:>6,} ({percentage:.1f}%)")
    
    # Parts by part type
    print("\n🔩 PARTS BY TYPE:")
    cur.execute("""
        SELECT part_type, COUNT(*) as count 
        FROM parts 
        WHERE part_type IS NOT NULL 
        GROUP BY part_type 
        ORDER BY count DESC
    """)
    for row in cur.fetchall():
        percentage = (row['count'] / total_parts) * 100
        print(f"  {row['part_type']:15} : {row['count']:>6,} ({percentage:.1f}%)")
    print()
    
    # 3. Images Analysis
    print("🖼️  IMAGES ANALYSIS")
    print("-" * 40)
    
    # Total images in database
    cur.execute("SELECT COUNT(*) FROM part_images")
    total_images = cur.fetchone()[0]
    print(f"Images in database: {total_images:,}")
    
    # Image size statistics
    cur.execute("""
        SELECT 
            MIN(file_size) as min_size,
            MAX(file_size) as max_size,
            AVG(file_size) as avg_size,
            SUM(file_size) as total_size,
            COUNT(*) as image_count
        FROM part_images
    """)
    size_stats = cur.fetchone()
    print(f"\nImage size statistics:")
    print(f"  Min: {size_stats[0]:,} bytes")
    print(f"  Max: {size_stats[1]:,} bytes")
    print(f"  Avg: {size_stats[2]:,.0f} bytes")
    print(f"  Total: {size_stats[3]:,} bytes ({size_stats[3]/1024/1024:.1f} MB)")
    print(f"  Images: {size_stats[4]:,}")
    
    # Images per part analysis
    cur.execute("""
        SELECT 
            COUNT(*) as parts_with_images,
            AVG(image_count) as avg_images_per_part,
            MAX(image_count) as max_images_per_part,
            SUM(image_count) as total_images
        FROM (
            SELECT part_id, COUNT(*) as image_count 
            FROM part_images 
            GROUP BY part_id
        )
    """)
    img_stats = cur.fetchone()
    print(f"\nImages per part analysis:")
    print(f"  Parts with images: {img_stats[0]:,}")
    print(f"  Avg images per part: {img_stats[1]:.2f}")
    print(f"  Max images per part: {img_stats[2]}")
    print(f"  Total image associations: {img_stats[3]:,}")
    
    # Image distribution
    print(f"\nImage distribution:")
    cur.execute("""
        SELECT image_count, COUNT(*) as part_count
        FROM (
            SELECT part_id, COUNT(*) as image_count 
            FROM part_images 
            GROUP BY part_id
        )
        GROUP BY image_count
        ORDER BY image_count
        LIMIT 10
    """)
    for row in cur.fetchall():
        print(f"  {row['image_count']:2} images: {row['part_count']:>5,} parts")
    print()
    
    # 4. Technical Guides Analysis
    print("📚 TECHNICAL GUIDES ANALYSIS")
    print("-" * 40)
    
    cur.execute("SELECT COUNT(*) FROM technical_guides")
    total_guides = cur.fetchone()[0]
    print(f"Total guides: {total_guides}")
    
    cur.execute("SELECT COUNT(*) FROM technical_guides WHERE is_active = 1")
    active_guides = cur.fetchone()[0]
    print(f"Active guides: {active_guides}")
    
    # Guide-part associations
    cur.execute("SELECT COUNT(*) FROM guide_parts")
    guide_part_assoc = cur.fetchone()[0]
    print(f"Guide-part associations: {guide_part_assoc:,}")
    
    # Check if part_guides exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='part_guides'")
    if cur.fetchone():
        cur.execute("SELECT COUNT(*) FROM part_guides")
        part_guide_assoc = cur.fetchone()[0]
        print(f"Part-guide associations: {part_guide_assoc:,}")
    else:
        print("Part-guide associations: Table not created yet")
    
    # Top guides by part associations
    print("\n📈 TOP GUIDES BY PART ASSOCIATIONS:")
    cur.execute("""
        SELECT tg.guide_name, tg.display_name, COUNT(gp.part_number) as part_count
        FROM technical_guides tg
        LEFT JOIN guide_parts gp ON tg.id = gp.guide_id
        GROUP BY tg.id, tg.guide_name, tg.display_name
        ORDER BY part_count DESC
        LIMIT 5
    """)
    for row in cur.fetchall():
        print(f"  {row['guide_name']:30} : {row['part_count']:>5,} parts - {row['display_name']}")
    
    # Guides by category
    print("\n🏷️  GUIDES BY CATEGORY:")
    cur.execute("SELECT category, COUNT(*) FROM technical_guides GROUP BY category ORDER BY COUNT(*) DESC")
    for row in cur.fetchall():
        print(f"  {row[0]:25} : {row[1]:>3}")
    print()
    
    # 5. Data Quality Checks
    print("✅ DATA QUALITY CHECKS")
    print("-" * 40)
    
    # Check for duplicate parts
    cur.execute("""
        SELECT COUNT(*) as duplicate_groups
        FROM (
            SELECT catalog_name, part_number, page, COUNT(*) as count
            FROM parts 
            GROUP BY catalog_name, part_number, page 
            HAVING COUNT(*) > 1
        )
    """)
    duplicate_groups = cur.fetchone()[0]
    print(f"Duplicate part groups: {duplicate_groups}")
    
    if duplicate_groups > 0:
        cur.execute("""
            SELECT catalog_name, part_number, page, COUNT(*) as count
            FROM parts 
            GROUP BY catalog_name, part_number, page 
            HAVING COUNT(*) > 1
            ORDER BY count DESC
            LIMIT 5
        """)
        print("  Top duplicates:")
        for row in cur.fetchall():
            print(f"    {row['catalog_name']} - {row['part_number']} - Page {row['page']} : {row['count']} copies")
    
    # Check for parts without descriptions
    cur.execute("SELECT COUNT(*) FROM parts WHERE description IS NULL OR description = ''")
    no_description = cur.fetchone()[0]
    print(f"Parts without description: {no_description:,} ({no_description/total_parts*100:.1f}%)")
    
    # Check for very short descriptions
    cur.execute("SELECT COUNT(*) FROM parts WHERE LENGTH(description) < 10")
    short_description = cur.fetchone()[0]
    print(f"Parts with very short descriptions: {short_description:,}")
    
    # Check image associations
    cur.execute("""
        SELECT COUNT(*) 
        FROM part_images pi 
        LEFT JOIN parts p ON pi.part_id = p.id 
        WHERE p.id IS NULL
    """)
    orphaned_images = cur.fetchone()[0]
    print(f"Orphaned images (no part): {orphaned_images}")
    
    # 6. Performance & Storage
    print("\n📈 PERFORMANCE & STORAGE")
    print("-" * 40)
    
    # Database file size
    db_size = db_path.stat().st_size
    print(f"Database file size: {db_size:,} bytes ({db_size/1024/1024:.1f} MB)")
    
    # Image data percentage
    cur.execute("SELECT SUM(file_size) FROM part_images")
    total_image_size = cur.fetchone()[0] or 0
    print(f"Image data size: {total_image_size:,} bytes ({total_image_size/1024/1024:.1f} MB)")
    print(f"Images as % of database: {total_image_size/db_size*100:.1f}%")
    
    # Data density
    print(f"Data density: {total_parts/db_size*1024*1024:.2f} parts per MB")
    
    # 7. Summary Statistics
    print("\n📋 SUMMARY STATISTICS")
    print("-" * 40)
    print(f"Total Parts: {total_parts:,}")
    print(f"Total Images: {total_images:,}")
    print(f"Total Guides: {total_guides}")
    print(f"Image Coverage: {parts_with_images/total_parts*100:.1f}% of parts have images")
    print(f"Avg Images per Part: {img_stats[1]:.2f}")
    print(f"Database Size: {db_size/1024/1024:.1f} MB")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("✅ ANALYSIS COMPLETE")

def check_data_issues():
    """Check for specific data issues that need cleaning"""
    db_path = app_dir / "data" / "catalog.db"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    
    print("\n🔧 DATA ISSUES TO CLEAN")
    print("=" * 60)
    
    issues_found = 0
    
    # 1. Check for duplicate parts
    cur.execute("""
        SELECT COUNT(*) as duplicate_groups
        FROM (
            SELECT catalog_name, part_number, page, COUNT(*) as count
            FROM parts 
            GROUP BY catalog_name, part_number, page 
            HAVING COUNT(*) > 1
        )
    """)
    duplicate_groups = cur.fetchone()[0]
    if duplicate_groups > 0:
        print(f"❌ DUPLICATE PARTS: {duplicate_groups} groups")
        issues_found += duplicate_groups
    
    # 2. Check for parts with "...." in descriptions
    cur.execute("SELECT COUNT(*) FROM parts WHERE description LIKE '%....%'")
    dot_descriptions = cur.fetchone()[0]
    if dot_descriptions > 0:
        print(f"❌ PARTS WITH '....' IN DESCRIPTIONS: {dot_descriptions:,}")
        issues_found += 1
    
    # 3. Check for very short useless descriptions
    cur.execute("""
        SELECT COUNT(*) FROM parts 
        WHERE description IN ('-', '--', '---', '....', '.....', '......')
        OR (description IS NOT NULL AND LENGTH(description) < 3)
    """)
    useless_descriptions = cur.fetchone()[0]
    if useless_descriptions > 0:
        print(f"❌ USELESS DESCRIPTIONS: {useless_descriptions:,}")
        issues_found += 1
    
    # 4. Check for orphaned images
    cur.execute("""
        SELECT COUNT(*) 
        FROM part_images pi 
        LEFT JOIN parts p ON pi.part_id = p.id 
        WHERE p.id IS NULL
    """)
    orphaned_images = cur.fetchone()[0]
    if orphaned_images > 0:
        print(f"❌ ORPHANED IMAGES: {orphaned_images}")
        issues_found += 1
    
    # 5. Check image filename consistency
    cur.execute("""
        SELECT COUNT(*) 
        FROM parts p 
        JOIN part_images pi ON p.id = pi.part_id
        WHERE p.image_path != pi.image_filename
    """)
    inconsistent_refs = cur.fetchone()[0]
    if inconsistent_refs > 0:
        print(f"❌ INCONSISTENT IMAGE REFERENCES: {inconsistent_refs}")
        issues_found += 1
    
    if issues_found == 0:
        print("✅ No major data issues found!")
    else:
        print(f"\n🔧 TOTAL ISSUES FOUND: {issues_found}")
    
    conn.close()

def cleanup_database():
    """Clean up common data issues"""
    db_path = app_dir / "data" / "catalog.db"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    
    print("\n🧹 DATABASE CLEANUP")
    print("=" * 60)
    
    changes_made = 0
    
    # 1. Remove duplicate parts (keep the one with lowest ID)
    print("1. Removing duplicate parts...")
    cur.execute("""
        DELETE FROM parts 
        WHERE id NOT IN (
            SELECT MIN(id) 
            FROM parts 
            GROUP BY catalog_name, part_number, page
        )
    """)
    duplicates_removed = cur.rowcount
    print(f"   ✅ Removed {duplicates_removed} duplicate parts")
    changes_made += duplicates_removed
    
    # 2. Clean up descriptions with excessive dots
    print("2. Cleaning descriptions...")
    cur.execute("SELECT COUNT(*) FROM parts WHERE description LIKE '%....%'")
    before_dots = cur.fetchone()[0]
    
    cur.execute("UPDATE parts SET description = REPLACE(description, '....', ' ')")
    cur.execute("UPDATE parts SET description = REPLACE(description, '.....', ' ')")
    cur.execute("UPDATE parts SET description = REPLACE(description, '......', ' ')")
    
    cur.execute("SELECT COUNT(*) FROM parts WHERE description LIKE '%....%'")
    after_dots = cur.fetchone()[0]
    dots_fixed = before_dots - after_dots
    print(f"   ✅ Fixed {dots_fixed} descriptions with excessive dots")
    changes_made += dots_fixed
    
    # 3. Remove very short useless descriptions
    print("3. Removing useless descriptions...")
    cur.execute("""
        SELECT COUNT(*) FROM parts 
        WHERE description IN ('-', '--', '---', '....', '.....', '......')
        OR (description IS NOT NULL AND LENGTH(description) < 3)
    """)
    before_useless = cur.fetchone()[0]
    
    cur.execute("""
        UPDATE parts 
        SET description = NULL 
        WHERE description IN ('-', '--', '---', '....', '.....', '......')
        OR (description IS NOT NULL AND LENGTH(description) < 3)
    """)
    
    cur.execute("""
        SELECT COUNT(*) FROM parts 
        WHERE description IN ('-', '--', '---', '....', '.....', '......')
        OR (description IS NOT NULL AND LENGTH(description) < 3)
    """)
    after_useless = cur.fetchone()[0]
    useless_removed = before_useless - after_useless
    print(f"   ✅ Removed {useless_removed} useless descriptions")
    changes_made += useless_removed
    
    # 4. Remove orphaned images
    print("4. Cleaning orphaned images...")
    cur.execute("""
        SELECT COUNT(*) FROM part_images 
        WHERE part_id NOT IN (SELECT id FROM parts)
    """)
    before_orphaned = cur.fetchone()[0]
    
    cur.execute("""
        DELETE FROM part_images 
        WHERE part_id NOT IN (SELECT id FROM parts)
    """)
    
    cur.execute("""
        SELECT COUNT(*) FROM part_images 
        WHERE part_id NOT IN (SELECT id FROM parts)
    """)
    after_orphaned = cur.fetchone()[0]
    orphaned_removed = before_orphaned - after_orphaned
    print(f"   ✅ Removed {orphaned_removed} orphaned images")
    changes_made += orphaned_removed
    
    # 5. Fix image references
    print("5. Fixing image references...")
    cur.execute("""
        UPDATE parts 
        SET image_path = (
            SELECT pi.image_filename 
            FROM part_images pi 
            WHERE pi.part_id = parts.id 
            ORDER BY pi.confidence DESC, pi.created_at DESC 
            LIMIT 1
        )
        WHERE image_path IS NULL 
        AND EXISTS (SELECT 1 FROM part_images pi WHERE pi.part_id = parts.id)
    """)
    refs_fixed = cur.rowcount
    print(f"   ✅ Fixed {refs_fixed} image references")
    changes_made += refs_fixed
    
    # 6. Trim whitespace from all text fields
    print("6. Trimming whitespace...")
    cur.execute("UPDATE parts SET description = TRIM(description) WHERE description IS NOT NULL")
    cur.execute("UPDATE parts SET applications = TRIM(applications) WHERE applications IS NOT NULL")
    cur.execute("UPDATE parts SET features = TRIM(features) WHERE features IS NOT NULL")
    print("   ✅ Trimmed whitespace from text fields")
    
    conn.commit()
    conn.close()
    
    print(f"\n🎉 Cleanup completed! {changes_made} changes made.")

if __name__ == "__main__":
    print("🚀 DATABASE ANALYSIS & CLEANUP TOOL")
    print("=" * 60)
    
    # Create any missing tables first
    create_missing_tables()
    
    # Run analysis
    analyze_database()
    
    # Check for issues
    check_data_issues()
    
    # Ask if user wants to clean up
    response = input("\nDo you want to clean up the issues? (y/n): ")
    if response.lower() == 'y':
        cleanup_database()
        print("\n✅ Running final analysis after cleanup...")
        analyze_database()
    else:
        print("\n⚠️  Cleanup skipped. Run this script again if you want to clean later.")