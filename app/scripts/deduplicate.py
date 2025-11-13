# app/scripts/deduplicate.py
import sqlite3
import argparse
from pathlib import Path

def get_db_connection():
    """Get database connection with correct path"""
    db_path = Path(r"C:\Users\kpecco\Desktop\codes\TESTING\app\data\catalog.db")
    
    if not db_path.exists():
        print(f" Database not found at: {db_path}")
        raise FileNotFoundError(f"Database not found at {db_path}")
    
    print(f" Using database at: {db_path}")
    return sqlite3.connect(str(db_path))

def cleanup_duplicates(dry_run=True, keep_strategy='lowest_id'):
    """
    Clean duplicate parts from database
    
    Args:
        dry_run: If True, only show what would be deleted
        keep_strategy: Strategy for which record to keep
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print(" Finding duplicate parts...")
        
        # Find duplicates based on part_number, description, machine_info, catalog_name
        query = """
        SELECT 
            part_number,
            description,
            machine_info,
            catalog_name,
            COUNT(*) as duplicate_count,
            GROUP_CONCAT(id) as duplicate_ids,
            GROUP_CONCAT(page) as pages
        FROM parts 
        WHERE description IS NOT NULL 
        GROUP BY part_number, description, machine_info, catalog_name
        HAVING COUNT(*) > 1
        ORDER BY duplicate_count DESC, part_number
        """
        
        cursor.execute(query)
        duplicates = cursor.fetchall()
        
        if not duplicates:
            print(" No duplicates found!")
            conn.close()
            return
        
        print(f" Found {len(duplicates)} duplicate groups")
        
        total_to_remove = 0
        actions = []
        
        for dup in duplicates:
            part_number, description, machine_info, catalog_name, count, ids, pages = dup
            duplicate_ids = [int(id) for id in ids.split(',')]
            page_list = pages.split(',')
            
            # Determine which ID to keep
            if keep_strategy == 'lowest_id':
                keep_id = min(duplicate_ids)
                keep_reason = "oldest record (lowest ID)"
            elif keep_strategy == 'highest_id':
                keep_id = max(duplicate_ids)
                keep_reason = "newest record (highest ID)"
            else:
                keep_id = duplicate_ids[0]
                keep_reason = "first found record"
            
            remove_ids = [id for id in duplicate_ids if id != keep_id]
            
            actions.append({
                'part_number': part_number,
                'description': description[:50] + '...' if len(description) > 50 else description,
                'machine_info': machine_info,
                'catalog': catalog_name,
                'keep_id': keep_id,
                'remove_ids': remove_ids,
                'pages': page_list,
                'keep_reason': keep_reason
            })
            
            total_to_remove += len(remove_ids)
        
        # Display preview
        print(f"\n DUPLICATE ANALYSIS:")
        print(f"Total duplicate groups: {len(duplicates)}")
        print(f"Total records to remove: {total_to_remove}")
        print(f"Keep strategy: {keep_strategy}")
        
        print(f"\n SAMPLE DUPLICATES (showing first 10):")
        for i, action in enumerate(actions[:10]):
            print(f"\n{i+1}. {action['part_number']} - {action['description']}")
            print(f"   Machine Info: {action['machine_info']} | Catalog: {action['catalog']}")
            print(f"   Keep ID: {action['keep_id']} (Reason: {action['keep_reason']})")
            print(f"   Remove IDs: {action['remove_ids']}")
            print(f"   Pages: {action['pages']}")
        
        if dry_run:
            print(f"\n This was a DRY RUN. No changes were made.")
            print(f"   To actually remove duplicates, run with: python app/scripts/deduplicate.py --execute")
            
            # Show total impact
            cursor.execute("SELECT COUNT(*) FROM parts")
            total_parts = cursor.fetchone()[0]
            print(f"\n IMPACT SUMMARY:")
            print(f"   Current total parts: {total_parts:,}")
            print(f"   Duplicate groups: {len(duplicates):,}")
            print(f"   Records to remove: {total_to_remove:,}")
            print(f"   New total after cleanup: {total_parts - total_to_remove:,}")
            print(f"   Reduction: {round((total_to_remove/total_parts)*100, 2)}%")
            
            conn.close()
            return
        
        # Actually perform deletion
        print(f"\n  REMOVING DUPLICATES...")
        removed_count = 0
        
        for action in actions:
            remove_ids = action['remove_ids']
            if remove_ids:
                placeholders = ','.join(['?' for _ in remove_ids])
                delete_query = f"DELETE FROM parts WHERE id IN ({placeholders})"
                cursor.execute(delete_query, remove_ids)
                removed_count += len(remove_ids)
                print(f" Removed {len(remove_ids)} duplicates for {action['part_number']}")
        
        conn.commit()
        
        # Verify cleanup
        cursor.execute("SELECT COUNT(*) FROM parts")
        remaining_count = cursor.fetchone()[0]
        
        print(f"\n CLEANUP COMPLETE!")
        print(f"   Removed records: {removed_count:,}")
        print(f"   Remaining records: {remaining_count:,}")
        if (removed_count + remaining_count) > 0:
            reduction_percent = round((removed_count/(removed_count + remaining_count))*100, 2)
            print(f"   Database size reduced by: {reduction_percent}%")
        
        # Show some sample remaining records
        cursor.execute("SELECT part_number, description FROM parts LIMIT 5")
        sample_records = cursor.fetchall()
        print(f"\n Sample remaining records:")
        for part_num, desc in sample_records:
            print(f"   - {part_num}: {desc[:60]}...")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f" Database error: {e}")
    except Exception as e:
        print(f" Unexpected error: {e}")

def check_duplicate_impact():
    """Check how many duplicates exist and their impact"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print(" Analyzing duplicate impact...")
        
        # Get total parts count
        cursor.execute("SELECT COUNT(*) FROM parts")
        total_parts = cursor.fetchone()[0]
        
        # Find unique parts (based on part_number, description, machine_info, catalog_name)
        cursor.execute("""
            SELECT COUNT(DISTINCT part_number || '|' || description || '|' || machine_info || '|' || catalog_name) 
            FROM parts 
            WHERE description IS NOT NULL
        """)
        unique_parts = cursor.fetchone()[0]
        
        duplicates_count = total_parts - unique_parts
        
        print(f"\n DUPLICATE IMPACT ANALYSIS:")
        print(f"   Total parts in database: {total_parts:,}")
        print(f"   Unique parts: {unique_parts:,}")
        print(f"   Duplicate records: {duplicates_count:,}")
        print(f"   Duplicate percentage: {round((duplicates_count/total_parts)*100, 2)}%")
        
        if duplicates_count > 0:
            print(f"\n💡 You can free up {duplicates_count:,} records ({round((duplicates_count/total_parts)*100, 2)}% of database)")
        
        conn.close()
        
    except Exception as e:
        print(f"Error analyzing impact: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Clean duplicate parts from database')
    parser.add_argument('--execute', action='store_true', 
                       help='Actually perform deletion (default is dry run)')
    parser.add_argument('--strategy', choices=['lowest_id', 'highest_id', 'first'], 
                       default='lowest_id', help='Strategy for which record to keep')
    parser.add_argument('--impact', action='store_true',
                       help='Only show duplicate impact analysis')
    
    args = parser.parse_args()
    
    if args.impact:
        check_duplicate_impact()
    else:
        print("Starting duplicate cleanup...")
        print(f"Database: C:\\Users\\kpecco\\Desktop\\codes\\TESTING\\app\\data\\catalog.db")
        print(f"Mode: {'EXECUTE (will delete duplicates)' if args.execute else 'DRY RUN (read-only)'}")
        print(f"Strategy: Keep {args.strategy} record\n")
        
        cleanup_duplicates(dry_run=not args.execute, keep_strategy=args.strategy)