# standalone_migrate_fixed.py
import sys
import os
import time
import sqlite3
import pyodbc
import json
from datetime import datetime
from pathlib import Path
import signal
import threading

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

# Disable S3 completely for migration
os.environ['USE_S3_STORAGE'] = 'false'

# Global flag to control migration
migration_active = True

def signal_handler(signum, frame):
    """Handle interrupt signals (Ctrl+C)"""
    global migration_active
    print(f"\n🛑 Received interrupt signal. Stopping migration gracefully...")
    migration_active = False

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

class MigrationController:
    """Controller to manage migration stop/start"""
    def __init__(self):
        self.is_running = True
        self.current_operation = None
        
    def stop(self):
        """Stop the migration"""
        self.is_running = False
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🛑 Migration stop requested...")
        
    def check_continue(self):
        """Check if migration should continue"""
        return self.is_running and migration_active
        
    def set_current_operation(self, operation):
        """Set the current operation for status reporting"""
        self.current_operation = operation

class StandaloneMSSQLMigrationService:
    def __init__(self, sqlite_path: str, mssql_connection_string: str):
        self.sqlite_path = sqlite_path
        self.mssql_connection_string = mssql_connection_string
        self.batch_size = 5000
        self.controller = MigrationController()
        
        if not self.mssql_connection_string:
            raise ValueError("MSSQL_CONNECTION_STRING not provided")
    
    def set_controller(self, controller: MigrationController):
        """Set an external migration controller"""
        self.controller = controller
    
    def get_sqlite_connection(self):
        """Get SQLite database connection"""
        return sqlite3.connect(self.sqlite_path)
    
    def get_mssql_connection(self):
        """Get MSSQL database connection"""
        conn = pyodbc.connect(self.mssql_connection_string)
        conn.autocommit = False
        return conn
    
    def cleanup_duplicates(self):
        """Remove duplicate parts data beyond the actual count"""
        conn = self.get_mssql_connection()
        cursor = conn.cursor()
        
        try:
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔍 Checking for duplicate data...")
            
            # Get current count from MSSQL
            cursor.execute("SELECT COUNT(*) FROM parts")
            current_count = cursor.fetchone()[0]
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📊 Current MSSQL parts count: {current_count:,}")
            
            # Get expected count from SQLite
            sqlite_conn = self.get_sqlite_connection()
            sqlite_cur = sqlite_conn.cursor()
            sqlite_cur.execute("SELECT COUNT(*) FROM parts")
            expected_count = sqlite_cur.fetchone()[0]
            sqlite_conn.close()
            
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📊 Expected SQLite parts count: {expected_count:,}")
            
            if current_count > expected_count:
                # Delete records beyond expected count
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🗑️ Deleting duplicate records beyond {expected_count:,}...")
                cursor.execute("DELETE FROM parts WHERE id > ?", (expected_count,))
                deleted_count = cursor.rowcount
                conn.commit()
                
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ Deleted {deleted_count:,} duplicate records")
                
                # Reset identity seed
                cursor.execute("DBCC CHECKIDENT ('parts', RESEED, ?)", (expected_count,))
                conn.commit()
                
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔄 Reset identity seed to {expected_count:,}")
            else:
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ No duplicates found")
            
        except Exception as e:
            conn.rollback()
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ Error during cleanup: {e}")
            raise
        finally:
            conn.close()
    
    def check_existing_data(self):
        """Check what data already exists in SQL Server"""
        try:
            conn = self.get_mssql_connection()
            cursor = conn.cursor()
            
            tables = ['parts', 'technical_guides', 'guide_parts', 'part_images']
            existing_data = {}
            
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    existing_data[table] = count
                    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📊 {table}: {count:,} existing records")
                except Exception as e:
                    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📊 {table}: Does not exist or error: {e}")
                    existing_data[table] = 0
            
            conn.close()
            return existing_data
            
        except Exception as e:
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ Error checking existing data: {e}")
            return {}
    
    def migrate_parts_data(self):
        """Migrate parts data with progress tracking and stop functionality"""
        sqlite_conn = self.get_sqlite_connection()
        mssql_conn = self.get_mssql_connection()
        
        try:
            sqlite_cur = sqlite_conn.cursor()
            mssql_cur = mssql_conn.cursor()
            
            # Get total count from SQLite
            sqlite_cur.execute("SELECT COUNT(*) FROM parts")
            total_parts = sqlite_cur.fetchone()[0]
            
            # Get current count from MSSQL to resume from correct position
            mssql_cur.execute("SELECT COUNT(*) FROM parts")
            current_mssql_count = mssql_cur.fetchone()[0]
            
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔄 Migrating parts: {current_mssql_count:,} → {total_parts:,}")
            
            migrated_count = current_mssql_count
            
            # If we already have all parts, return
            if migrated_count >= total_parts:
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ All parts already migrated!")
                return migrated_count
            
            # Find starting rowid based on current progress
            start_rowid = self._find_start_rowid(sqlite_conn, migrated_count)
            if start_rowid is None:
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ Could not find resume point")
                return migrated_count
                
            last_rowid = start_rowid
            batch_number = 0
            
            while self.controller.check_continue():
                batch_number += 1
                batch_start_time = time.time()
                
                sqlite_cur.execute("""
                    SELECT * FROM parts 
                    WHERE rowid > ? 
                    ORDER BY rowid 
                    LIMIT ?
                """, (last_rowid, self.batch_size))
                
                batch = sqlite_cur.fetchall()
                
                if not batch:
                    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ All parts migrated successfully!")
                    break
                    
                columns = [desc[0] for desc in sqlite_cur.description]
                
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
                    
                    last_rowid = part_dict.get('rowid', last_rowid + 1)
                
                # Execute batch insert
                mssql_cur.executemany(insert_query, batch_params)
                mssql_conn.commit()
                
                migrated_count += len(batch)
                batch_duration = time.time() - batch_start_time
                
                progress = (migrated_count / total_parts) * 100
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📦 Batch {batch_number}: Migrated {len(batch):,} parts "
                      f"(Total: {migrated_count:,}/{total_parts:,}, {progress:.1f}%) "
                      f"in {batch_duration:.2f}s")
                
                # Stop condition check
                if not self.controller.check_continue():
                    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⏹️ Parts migration stopped by user")
                    return migrated_count
            
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ Successfully migrated {migrated_count:,} parts")
            return migrated_count
            
        except Exception as e:
            mssql_conn.rollback()
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ Error migrating parts data: {e}")
            raise
        finally:
            sqlite_conn.close()
            mssql_conn.close()

    def _find_start_rowid(self, sqlite_conn, target_count):
        """Find the rowid to start from based on the count we want to resume from"""
        cursor = sqlite_conn.cursor()
        
        cursor.execute("""
            SELECT rowid FROM parts 
            ORDER BY rowid 
            LIMIT 1 OFFSET ?
        """, (target_count,))
        
        result = cursor.fetchone()
        return result[0] if result else None

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
        if not self.controller.check_continue():
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⏹️ Skipping guides migration - migration stopped")
            return
            
        sqlite_conn = self.get_sqlite_connection()
        mssql_conn = self.get_mssql_connection()
        
        try:
            sqlite_cur = sqlite_conn.cursor()
            mssql_cur = mssql_conn.cursor()
            
            # Create technical_guides table if it doesn't exist
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔄 Creating technical_guides table...")
            mssql_cur.execute("""
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='technical_guides' AND xtype='U')
                CREATE TABLE technical_guides (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    guide_name NVARCHAR(255) UNIQUE NOT NULL,
                    display_name NVARCHAR(255) NOT NULL,
                    description NVARCHAR(MAX),
                    category NVARCHAR(100),
                    pdf_path NVARCHAR(MAX),
                    template_fields NVARCHAR(MAX),
                    related_parts NVARCHAR(MAX),
                    is_active BIT DEFAULT 1,
                    created_at DATETIME2 DEFAULT GETDATE()
                )
            """)
            
            # Migrate technical guides
            sqlite_cur.execute("SELECT COUNT(*) FROM technical_guides")
            total_guides = sqlite_cur.fetchone()[0]
            
            mssql_cur.execute("SELECT COUNT(*) FROM technical_guides")
            existing_guides = mssql_cur.fetchone()[0]
            
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📊 Technical guides: SQLite={total_guides}, MSSQL={existing_guides}")
            
            if existing_guides >= total_guides:
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ Technical guides already migrated!")
                guide_id_map = self._get_guide_id_mapping(sqlite_conn, mssql_conn)
            else:
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔄 Migrating {total_guides} technical guides...")
                
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
                    if not self.controller.check_continue():
                        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⏹️ Stopping guides migration")
                        break
                        
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
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ Migrated {len(guides)} technical guides")
            
            # Migrate guide-parts associations if not stopped
            if self.controller.check_continue():
                self._migrate_guide_parts_associations(guide_id_map, sqlite_conn, mssql_conn)
            
        except Exception as e:
            mssql_conn.rollback()
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ Error migrating technical guides: {e}")
            raise
        finally:
            sqlite_conn.close()
            mssql_conn.close()

    def _get_guide_id_mapping(self, sqlite_conn, mssql_conn):
        """Get mapping between old SQLite IDs and new SQL Server IDs"""
        sqlite_cur = sqlite_conn.cursor()
        mssql_cur = mssql_conn.cursor()
        
        # Get old guide IDs and names
        sqlite_cur.execute("SELECT id, guide_name FROM technical_guides")
        old_guides = {name: id for id, name in sqlite_cur.fetchall()}
        
        # Get new guide IDs and names
        mssql_cur.execute("SELECT id, guide_name FROM technical_guides")
        new_guides = {name: id for id, name in mssql_cur.fetchall()}
        
        # Create mapping
        guide_id_map = {}
        for guide_name, old_id in old_guides.items():
            if guide_name in new_guides:
                guide_id_map[old_id] = new_guides[guide_name]
        
        return guide_id_map

    def _migrate_guide_parts_associations(self, guide_id_map, sqlite_conn, mssql_conn):
        """Migrate guide-parts associations with duplicate handling"""
        try:
            sqlite_cur = sqlite_conn.cursor()
            mssql_cur = mssql_conn.cursor()
            
            # Create guide_parts table if it doesn't exist
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔄 Creating guide_parts table...")
            mssql_cur.execute("""
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='guide_parts' AND xtype='U')
                CREATE TABLE guide_parts (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    guide_id INT,
                    part_number NVARCHAR(100),
                    confidence_score FLOAT DEFAULT 1.0,
                    created_at DATETIME2 DEFAULT GETDATE(),
                    CONSTRAINT FK_guide_parts_guide FOREIGN KEY (guide_id) REFERENCES technical_guides(id),
                    CONSTRAINT UQ_guide_part UNIQUE (guide_id, part_number)
                )
            """)
            
            # Get all associations from SQLite
            sqlite_cur.execute("SELECT * FROM guide_parts")
            all_associations = sqlite_cur.fetchall()
            columns = [desc[0] for desc in sqlite_cur.description]
            
            # Get existing associations from MSSQL to avoid duplicates
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔍 Checking existing associations...")
            mssql_cur.execute("SELECT guide_id, part_number FROM guide_parts")
            existing_associations = set((row[0], row[1]) for row in mssql_cur.fetchall())
            
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📊 Found {len(existing_associations):,} existing associations")
            
            insert_query = """
                INSERT INTO guide_parts (guide_id, part_number, confidence_score)
                VALUES (?, ?, ?)
            """
            
            batch_params = []
            skipped_count = 0
            migrated_count = len(existing_associations)
            batch_number = 0
            
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔄 Processing {len(all_associations):,} associations from SQLite...")
            
            for association in all_associations:
                if not self.controller.check_continue():
                    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⏹️ Stopping associations migration")
                    break
                    
                association_dict = dict(zip(columns, association))
                old_guide_id = association_dict.get('guide_id')
                part_number = association_dict.get('part_number')
                confidence_score = association_dict.get('confidence_score', 1.0)
                
                new_guide_id = guide_id_map.get(old_guide_id)
                if new_guide_id:
                    # Check if this association already exists
                    association_key = (new_guide_id, part_number)
                    if association_key not in existing_associations:
                        batch_params.append((new_guide_id, part_number, confidence_score))
                        migrated_count += 1
                    else:
                        skipped_count += 1
                
                # Insert in batches of 1000
                if len(batch_params) >= 1000:
                    batch_number += 1
                    try:
                        mssql_cur.executemany(insert_query, batch_params)
                        mssql_conn.commit()
                        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔗 Batch {batch_number}: Migrated {len(batch_params):,} associations (Total: {migrated_count:,}, Skipped: {skipped_count:,})")
                        batch_params = []
                    except Exception as batch_error:
                        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ Batch {batch_number} failed: {batch_error}")
                        # Try individual inserts for the failed batch to identify the problematic record
                        successful_in_batch = 0
                        for params in batch_params:
                            try:
                                mssql_cur.execute(insert_query, params)
                                successful_in_batch += 1
                            except Exception as single_error:
                                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ Failed to insert: guide_id={params[0]}, part_number={params[1]}, error: {single_error}")
                        mssql_conn.commit()
                        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔄 Batch {batch_number} recovered: {successful_in_batch}/{len(batch_params)} inserted")
                        batch_params = []
            
            # Insert any remaining associations
            if batch_params and self.controller.check_continue():
                try:
                    mssql_cur.executemany(insert_query, batch_params)
                    mssql_conn.commit()
                    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔗 Final batch: Migrated {len(batch_params):,} associations")
                except Exception as final_batch_error:
                    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ Final batch failed: {final_batch_error}")
            
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ Guide-parts associations completed: {migrated_count:,} total, {skipped_count:,} duplicates skipped")
            
        except Exception as e:
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ Error migrating associations: {e}")
            raise

    def migrate_part_images_table(self):
        """Migrate the part_images table from SQLite to MSSQL"""
        if not self.controller.check_continue():
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⏹️ Skipping part_images migration - migration stopped")
            return
        
        sqlite_conn = self.get_sqlite_connection()
        mssql_conn = self.get_mssql_connection()
        
        try:
            sqlite_cur = sqlite_conn.cursor()
            mssql_cur = mssql_conn.cursor()
            
            # Check if part_images table exists in SQLite
            sqlite_cur.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='part_images'
            """)
            table_exists = sqlite_cur.fetchone() is not None
            
            if not table_exists:
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ℹ️ part_images table does not exist in SQLite")
                return
            
            # Create part_images table in MSSQL if it doesn't exist
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔄 Creating part_images table in MSSQL...")
            mssql_cur.execute("""
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='part_images' AND xtype='U')
                CREATE TABLE part_images (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    part_number NVARCHAR(100) NOT NULL,
                    part_type NVARCHAR(100),
                    image_filename NVARCHAR(255) NOT NULL,
                    image_path NVARCHAR(MAX) NOT NULL,
                    pdf_name NVARCHAR(255) NOT NULL,
                    page_number INT,
                    image_width INT,
                    image_height INT,
                    context NVARCHAR(MAX),
                    confidence FLOAT,
                    created_at DATETIME2 DEFAULT GETDATE()
                )
            """)
            
            # Create indexes
            mssql_cur.execute("""
                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_part_images_part_number')
                CREATE INDEX idx_part_images_part_number ON part_images (part_number)
            """)
            mssql_cur.execute("""
                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_part_images_pdf_name')
                CREATE INDEX idx_part_images_pdf_name ON part_images (pdf_name)
            """)
            
            mssql_conn.commit()
            
            # Get count from SQLite
            sqlite_cur.execute("SELECT COUNT(*) FROM part_images")
            total_images = sqlite_cur.fetchone()[0]
            
            # Get current count from MSSQL
            mssql_cur.execute("SELECT COUNT(*) FROM part_images")
            current_count = mssql_cur.fetchone()[0]
            
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📊 part_images: SQLite={total_images:,}, MSSQL={current_count:,}")
            
            if current_count >= total_images:
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ part_images already migrated!")
                return
            
            # Migrate data
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔄 Migrating {total_images - current_count:,} part_images records...")
            
            sqlite_cur.execute("SELECT * FROM part_images")
            columns = [desc[0] for desc in sqlite_cur.description]
            
            insert_query = """
                INSERT INTO part_images (
                    part_number, part_type, image_filename, image_path, pdf_name,
                    page_number, image_width, image_height, context, confidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            batch_params = []
            migrated_count = current_count
            batch_number = 0
            
            for record in sqlite_cur.fetchall():
                if not self.controller.check_continue():
                    break
                    
                record_dict = dict(zip(columns, record))
                
                batch_params.append((
                    record_dict.get('part_number'),
                    record_dict.get('part_type'),
                    record_dict.get('image_filename'),
                    record_dict.get('image_path'),
                    record_dict.get('pdf_name'),
                    record_dict.get('page_number'),
                    record_dict.get('image_width'),
                    record_dict.get('image_height'),
                    record_dict.get('context'),
                    record_dict.get('confidence'),
                    record_dict.get('created_at')
                ))
                
                # Insert in batches of 1000
                if len(batch_params) >= 1000:
                    batch_number += 1
                    mssql_cur.executemany(insert_query, batch_params)
                    mssql_conn.commit()
                    migrated_count += len(batch_params)
                    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📸 Batch {batch_number}: Migrated {migrated_count:,} part_images...")
                    batch_params = []
            
            # Insert remaining records
            if batch_params and self.controller.check_continue():
                mssql_cur.executemany(insert_query, batch_params)
                mssql_conn.commit()
                migrated_count += len(batch_params)
            
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ Successfully migrated {migrated_count:,} part_images")
            
        except Exception as e:
            mssql_conn.rollback()
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ Error migrating part_images: {e}")
            raise
        finally:
            sqlite_conn.close()
            mssql_conn.close()

    def verify_migration(self):
        """Verify the migration was successful"""
        if not self.controller.check_continue():
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⏹️ Skipping verification - migration stopped")
            return False
            
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
            
            # Count guides
            sqlite_cur.execute("SELECT COUNT(*) FROM technical_guides")
            sqlite_guides = sqlite_cur.fetchone()[0]
            
            mssql_cur.execute("SELECT COUNT(*) FROM technical_guides")
            mssql_guides = mssql_cur.fetchone()[0]
            
            # Count associations
            sqlite_cur.execute("SELECT COUNT(*) FROM guide_parts")
            sqlite_associations = sqlite_cur.fetchone()[0]
            
            mssql_cur.execute("SELECT COUNT(*) FROM guide_parts")
            mssql_associations = mssql_cur.fetchone()[0]
            
            # Count part_images
            sqlite_cur.execute("SELECT COUNT(*) FROM part_images")
            sqlite_images = sqlite_cur.fetchone()[0]
            
            mssql_cur.execute("SELECT COUNT(*) FROM part_images")
            mssql_images = mssql_cur.fetchone()[0]
            
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📊 Migration Verification:")
            print(f"   Parts: SQLite={sqlite_parts:,}, SQL Server={mssql_parts:,}")
            print(f"   Guides: SQLite={sqlite_guides}, SQL Server={mssql_guides}")
            print(f"   Associations: SQLite={sqlite_associations:,}, SQL Server={mssql_associations:,}")
            print(f"   Part Images: SQLite={sqlite_images:,}, SQL Server={mssql_images:,}")
            
            if (mssql_parts == sqlite_parts and 
                mssql_guides == sqlite_guides and 
                mssql_associations == sqlite_associations and
                mssql_images == sqlite_images):
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ Migration verified successfully!")
                return True
            else:
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⚠️ Migration counts don't match - please check")
                return False
                
        except Exception as e:
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ Error verifying migration: {e}")
            return False
        finally:
            sqlite_conn.close()
            mssql_conn.close()

def monitor_user_input(controller):
    """Monitor for user input to stop migration"""
    while controller.is_running and migration_active:
        try:
            user_input = input()
            if user_input.strip().lower() in ['stop', 'quit', 'exit', 's', 'q']:
                controller.stop()
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🛑 Stop command received. Stopping migration...")
                break
        except (EOFError, KeyboardInterrupt):
            break
        

def main():
    global migration_active
    
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🚀 Starting STANDALONE SQL Server Migration...")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 💡 Press Ctrl+C or type 'stop' to abort migration")
    
    # Your configuration
    sqlite_path = r"C:\Users\kpecco\Desktop\codes\TESTING\app\data\catalog.db"
    mssql_connection_string = (
        "Driver={ODBC Driver 17 for SQL Server};"
        "Server=192.96.222.38,30002;"
        "Database=ApelloKbDev;"
        "Uid=ligapp;"
        "Pwd=MySysDb2026#;"
        "TrustServerCertificate=yes;"
        "Connection Timeout=30;"
    )
    
    # Verify SQLite database exists
    if not Path(sqlite_path).exists():
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ SQLite database not found at: {sqlite_path}")
        return
    
    # Create migration controller
    controller = MigrationController()
    
    # Start input monitoring in separate thread
    input_thread = threading.Thread(target=monitor_user_input, args=(controller,), daemon=True)
    input_thread.start()
    
    migration_service = StandaloneMSSQLMigrationService(sqlite_path, mssql_connection_string)
    migration_service.set_controller(controller)
    
    total_start_time = time.time()
    
    try:
        # Step 1: Clean up duplicates
        migration_service.cleanup_duplicates()
        
        if not controller.check_continue():
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⏹️ Migration stopped after cleanup")
            return
        
        # Step 2: Check existing data
        existing_data = migration_service.check_existing_data()
        
        # Step 3: Migrate parts
        parts_start = time.time()
        migrated_parts = migration_service.migrate_parts_data()
        parts_duration = time.time() - parts_start
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⏱️ Parts migration took: {parts_duration:.2f} seconds")
        
        if not controller.check_continue():
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⏹️ Migration stopped after parts")
            return
        
        # Step 4: Migrate technical guides
        guides_start = time.time()
        migration_service.migrate_technical_guides()
        guides_duration = time.time() - guides_start
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⏱️ Guides migration took: {guides_duration:.2f} seconds")
        
        if not controller.check_continue():
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⏹️ Migration stopped after guides")
            return
        
        # Step 5: Migrate part_images
        images_start = time.time()
        migration_service.migrate_part_images_table()
        images_duration = time.time() - images_start
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⏱️ Part images migration took: {images_duration:.2f} seconds")
        
        # Step 6: Verify migration
        if controller.check_continue():
            migration_service.verify_migration()
        
        if controller.check_continue():
            total_duration = time.time() - total_start_time
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🎉 MIGRATION COMPLETED in {total_duration:.2f} seconds!")
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⏱️ Total time: {total_duration/60:.2f} minutes")
        else:
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⏹️ Migration was stopped by user")
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⏱️ Ran for {time.time() - total_start_time:.2f} seconds")
        
    except KeyboardInterrupt:
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⏹️ Migration interrupted by user")
    except Exception as e:
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ Migration failed after {time.time() - total_start_time:.2f} seconds: {e}")
    finally:
        controller.stop()
        migration_active = False

if __name__ == "__main__":
    main()