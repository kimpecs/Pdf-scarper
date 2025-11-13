# scripts/standalone_resume_migration.py
import sys
import sqlite3
import pyodbc
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional
import logging

# Setup logging without emojis for Windows compatibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('migration_resume.log', encoding='utf-8')
    ]
)
logger = logging.getLogger('migration')

class StandaloneResumeMigration:
    def __init__(self, sqlite_path: str, mssql_connection_string: str):
        self.sqlite_path = sqlite_path
        self.mssql_connection_string = mssql_connection_string
        self.batch_size = 5000
        
    def get_sqlite_connection(self):
        return sqlite3.connect(self.sqlite_path)
    
    def get_mssql_connection(self):
        conn = pyodbc.connect(self.mssql_connection_string)
        conn.autocommit = False
        return conn
    
    def check_existing_data(self):
        """Check how many parts are already in SQL Server"""
        try:
            conn = self.get_mssql_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM parts")
            existing_count = cursor.fetchone()[0]
            
            conn.close()
            
            logger.info(f"Existing parts in SQL Server: {existing_count:,}")
            return existing_count
            
        except Exception as e:
            logger.error(f"Error checking existing data: {e}")
            return 0
    
    def migrate_parts_data_resume(self, start_from_count: int = 70000):
        """Resume migration from specified point"""
        sqlite_conn = self.get_sqlite_connection()
        mssql_conn = self.get_mssql_connection()
        
        try:
            sqlite_cur = sqlite_conn.cursor()
            mssql_cur = mssql_conn.cursor()
            
            # Get total count
            sqlite_cur.execute("SELECT COUNT(*) FROM parts")
            total_parts = sqlite_cur.fetchone()[0]
            
            logger.info(f"RESUMING migration from part {start_from_count:,} of {total_parts:,} total parts...")
            
            # Get the rowid to start from
            start_rowid = self._get_rowid_at_count(sqlite_conn, start_from_count)
            
            if start_rowid is None:
                logger.error(f"Could not find resume point at count {start_from_count}")
                return
            
            logger.info(f"Resuming from rowid: {start_rowid}")
            
            migrated_count = start_from_count
            last_rowid = start_rowid
            
            while True:
                sqlite_cur.execute("""
                    SELECT * FROM parts 
                    WHERE rowid > ? 
                    ORDER BY rowid 
                    LIMIT ?
                """, (last_rowid, self.batch_size))
                
                batch = sqlite_cur.fetchall()
                
                if not batch:
                    logger.info("No more parts to migrate")
                    break
                    
                columns = [desc[0] for desc in sqlite_cur.description]
                
                # Prepare batch insert
                insert_query = """
                    INSERT INTO parts (
                        catalog_name, catalog_type, part_type, part_number,
                        description, category, page, image_path, page_text,
                        pdf_path, machine_info, specifications, oe_numbers,
                        applications, features
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                batch_params = []
                for part in batch:
                    part_dict = dict(zip(columns, part))
                    
                    machine_info = self._safe_json_parse(part_dict.get('machine_info'))
                    specifications = self._safe_json_parse(part_dict.get('specifications'))
                    
                    batch_params.append((
                        part_dict.get('catalog_name'),
                        part_dict.get('catalog_type'),
                        part_dict.get('part_type'),
                        part_dict.get('part_number'),
                        part_dict.get('description'),
                        part_dict.get('category'),
                        part_dict.get('page'),
                        part_dict.get('image_path'),
                        part_dict.get('page_text'),
                        part_dict.get('pdf_path'),
                        json.dumps(machine_info) if machine_info else None,
                        json.dumps(specifications) if specifications else None,
                        part_dict.get('oe_numbers'),
                        part_dict.get('applications'),
                        part_dict.get('features')
                    ))
                    
                    # Update last_rowid for next batch
                    last_rowid = part_dict.get('rowid', last_rowid + 1)
                
                # Execute batch insert
                try:
                    mssql_cur.executemany(insert_query, batch_params)
                    mssql_conn.commit()
                    
                    migrated_count += len(batch)
                    
                    # Progress update
                    progress = (migrated_count / total_parts) * 100
                    logger.info(f"Migrated {migrated_count:,} of {total_parts:,} parts ({progress:.1f}%)...")
                    
                    # Save progress every 10,000 records
                    if migrated_count % 10000 == 0:
                        self._save_progress(migrated_count, last_rowid)
                        
                except Exception as batch_error:
                    mssql_conn.rollback()
                    logger.error(f"Batch insert failed at count {migrated_count}: {batch_error}")
                    
                    # Retry with smaller batch size
                    if self.batch_size > 1000:
                        self.batch_size = 1000
                        logger.info(f"Reducing batch size to {self.batch_size} and retrying...")
                        continue
                    else:
                        logger.error("Failed even with reduced batch size. Aborting.")
                        raise
            
            logger.info(f"Successfully migrated {migrated_count - start_from_count:,} additional parts")
            logger.info(f"Total parts in SQL Server: {migrated_count:,}")
            
        except Exception as e:
            mssql_conn.rollback()
            logger.error(f"Error resuming parts migration: {e}")
            raise
        finally:
            sqlite_conn.close()
            mssql_conn.close()
    
    def _get_rowid_at_count(self, sqlite_conn, target_count):
        """Get the rowid at a specific count position"""
        cursor = sqlite_conn.cursor()
        
        cursor.execute("""
            SELECT rowid FROM parts 
            ORDER BY rowid 
            LIMIT 1 OFFSET ?
        """, (target_count,))
        
        result = cursor.fetchone()
        return result[0] if result else None
    
    def _save_progress(self, count, rowid):
        """Save progress to a file for potential future resumptions"""
        progress_file = Path(__file__).parent / "migration_progress.txt"
        with open(progress_file, 'w', encoding='utf-8') as f:
            f.write(f"count={count}\n")
            f.write(f"rowid={rowid}\n")
            f.write(f"timestamp={time.time()}\n")
        logger.debug(f"Progress saved: count={count}, rowid={rowid}")
    
    def _safe_json_parse(self, json_str):
        """Safely parse JSON string"""
        if not json_str:
            return None
        try:
            return json.loads(json_str)
        except:
            return None
    
    def migrate_technical_guides(self):
        """Migrate technical guides and associations"""
        sqlite_conn = self.get_sqlite_connection()
        mssql_conn = self.get_mssql_connection()
        
        try:
            sqlite_cur = sqlite_conn.cursor()
            mssql_cur = mssql_conn.cursor()
            
            # Check if guides already exist
            mssql_cur.execute("SELECT COUNT(*) FROM technical_guides")
            existing_guides = mssql_cur.fetchone()[0]
            
            if existing_guides > 0:
                logger.info(f"Technical guides already exist: {existing_guides} guides")
                return
            
            logger.info("Migrating technical guides...")
            
            # Migrate technical guides
            sqlite_cur.execute("SELECT * FROM technical_guides")
            guides = sqlite_cur.fetchall()
            columns = [desc[0] for desc in sqlite_cur.description]
            
            insert_guide_query = """
                INSERT INTO technical_guides (
                    guide_name, display_name, description, category,
                    pdf_path, template_fields, related_parts, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            guide_id_map = {}
            
            for guide in guides:
                guide_dict = dict(zip(columns, guide))
                old_guide_id = guide_dict.get('id')
                
                template_fields = self._safe_json_parse(guide_dict.get('template_fields'))
                related_parts = self._safe_json_parse(guide_dict.get('related_parts'))
                
                mssql_cur.execute(insert_guide_query, (
                    guide_dict.get('guide_name'),
                    guide_dict.get('display_name'),
                    guide_dict.get('description'),
                    guide_dict.get('category'),
                    guide_dict.get('pdf_path'),
                    json.dumps(template_fields) if template_fields else None,
                    json.dumps(related_parts) if related_parts else None,
                    bool(guide_dict.get('is_active', True))
                ))
                
                # Get the new ID
                mssql_cur.execute("SELECT @@IDENTITY")
                new_guide_id = mssql_cur.fetchone()[0]
                guide_id_map[old_guide_id] = new_guide_id
            
            mssql_conn.commit()
            logger.info(f"Migrated {len(guides)} technical guides")
            
            # Migrate guide-parts associations
            self._migrate_guide_parts_associations(guide_id_map, sqlite_conn, mssql_conn)
            
        except Exception as e:
            mssql_conn.rollback()
            logger.error(f"Error migrating technical guides: {e}")
            raise
        finally:
            sqlite_conn.close()
            mssql_conn.close()
    
    def _migrate_guide_parts_associations(self, guide_id_map, sqlite_conn, mssql_conn):
        """Migrate guide-parts associations"""
        try:
            sqlite_cur = sqlite_conn.cursor()
            mssql_cur = mssql_conn.cursor()
            
            # Check if associations already exist
            mssql_cur.execute("SELECT COUNT(*) FROM guide_parts")
            existing_associations = mssql_cur.fetchone()[0]
            
            if existing_associations > 0:
                logger.info(f"Guide-parts associations already exist: {existing_associations} associations")
                return
            
            sqlite_cur.execute("SELECT COUNT(*) FROM guide_parts")
            total_associations = sqlite_cur.fetchone()[0]
            
            logger.info(f"Migrating {total_associations} guide-parts associations...")
            
            sqlite_cur.execute("SELECT * FROM guide_parts")
            associations = sqlite_cur.fetchall()
            columns = [desc[0] for desc in sqlite_cur.description]
            
            insert_query = """
                INSERT INTO guide_parts (guide_id, part_number, confidence_score)
                VALUES (?, ?, ?)
            """
            
            batch_params = []
            migrated_count = 0
            
            for association in associations:
                association_dict = dict(zip(columns, association))
                old_guide_id = association_dict.get('guide_id')
                part_number = association_dict.get('part_number')
                confidence_score = association_dict.get('confidence_score', 1.0)
                
                new_guide_id = guide_id_map.get(old_guide_id)
                if new_guide_id:
                    batch_params.append((new_guide_id, part_number, confidence_score))
                    migrated_count += 1
                
                # Insert in batches
                if len(batch_params) >= 1000:
                    mssql_cur.executemany(insert_query, batch_params)
                    mssql_conn.commit()
                    batch_params = []
            
            # Insert any remaining associations
            if batch_params:
                mssql_cur.executemany(insert_query, batch_params)
                mssql_conn.commit()
            
            logger.info(f"Migrated {migrated_count} guide-parts associations")
            
        except Exception as e:
            logger.error(f"Error migrating guide-parts associations: {e}")
            raise
    
    def verify_migration(self):
        """Verify the migration was successful"""
        sqlite_conn = self.get_sqlite_connection()
        mssql_conn = self.get_mssql_connection()
        
        try:
            sqlite_cur = sqlite_conn.cursor()
            mssql_cur = mssql_conn.cursor()
            
            # Count parts
            sqlite_cur.execute("SELECT COUNT(*) FROM parts")
            sqlite_parts = sqlite_cur.fetchone()[0]
            
            mssql_cur.execute("SELECT COUNT(*) FROM parts")
            mssql_parts = mssql_cur.fetchone()[0]
            
            logger.info("Migration Verification:")
            logger.info(f"   Parts: SQLite={sqlite_parts:,}, SQL Server={mssql_parts:,}")
            
            if mssql_parts == sqlite_parts:
                logger.info("Migration verified successfully!")
                return True
            else:
                logger.warning(f"Migration counts don't match - difference: {sqlite_parts - mssql_parts}")
                return False
                
        except Exception as e:
            logger.error(f"Error verifying migration: {e}")
            return False
        finally:
            sqlite_conn.close()
            mssql_conn.close()
    
    def run_resume_migration(self):
        """Run resume migration process"""
        logger.info("RESUMING database migration...")
        
        start_time = time.time()
        
        try:
            # Step 1: Check existing data and determine starting point
            existing_count = self.check_existing_data()
            start_from = max(70000, existing_count)  # Start from 70,000 or current count, whichever is larger
            
            logger.info(f"Starting migration from count: {start_from:,}")
            
            # Step 2: Resume parts migration
            parts_start = time.time()
            self.migrate_parts_data_resume(start_from)
            parts_duration = time.time() - parts_start
            logger.info(f"Parts migration took: {parts_duration:.2f} seconds")
            
            # Step 3: Migrate technical guides (if not already done)
            guides_start = time.time()
            self.migrate_technical_guides()
            guides_duration = time.time() - guides_start
            logger.info(f"Guides migration took: {guides_duration:.2f} seconds")
            
            # Step 4: Verify migration
            self.verify_migration()
            
            total_duration = time.time() - start_time
            logger.info(f"RESUME migration completed in {total_duration:.2f} seconds!")
            
        except Exception as e:
            logger.error(f"Resume migration failed: {e}")
            raise

def main():
    # Configuration - update these paths as needed
    sqlite_path = r"C:\Users\kpecco\Desktop\codes\TESTING\app\data\catalog.db"
    
    # SQL Server connection string - update with your credentials
    mssql_connection_string = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost;"
        "DATABASE=catalog;"
        "Trusted_Connection=yes;"
    )
    
    # Alternative with SQL authentication:
    # mssql_connection_string = (
    #     "DRIVER={ODBC Driver 17 for SQL Server};"
    #     "SERVER=your_server;"
    #     "DATABASE=catalog;"
    #     "UID=your_username;"
    #     "PWD=your_password;"
    # )
    
    # Verify SQLite database exists
    if not Path(sqlite_path).exists():
        logger.error(f"SQLite database not found at: {sqlite_path}")
        return
    
    # Create migration service
    migration_service = StandaloneResumeMigration(sqlite_path, mssql_connection_string)
    
    total_start_time = time.time()
    
    try:
        migration_service.run_resume_migration()
        
        total_duration = time.time() - total_start_time
        logger.info(f"RESUME MIGRATION COMPLETED in {total_duration:.2f} seconds!")
        logger.info(f"Total time: {total_duration/60:.2f} minutes")
        
    except Exception as e:
        logger.error(f"Resume migration failed after {time.time() - total_start_time:.2f} seconds: {e}")

if __name__ == "__main__":
    main()