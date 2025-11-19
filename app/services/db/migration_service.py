# app/services/db/migration_service.py
from datetime import datetime
import sqlite3
import pyodbc
import json
import time
import os
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

from app.utils.logger import setup_logging
from app.utils.config import settings

# Load environment variables
load_dotenv()

logger = setup_logging()

class MigrationController:
    """Controller to manage migration stop/start"""
    def __init__(self):
        self.is_running = True
        self.current_operation = None
        
    def stop(self):
        """Stop the migration"""
        self.is_running = False
        logger.info("🛑 Migration stop requested...")
        
    def check_continue(self):
        """Check if migration should continue"""
        return self.is_running
        
    def set_current_operation(self, operation):
        """Set the current operation for status reporting"""
        self.current_operation = operation

class MSSQLMigrationService:
    def __init__(self, sqlite_path: Optional[str] = None, mssql_connection_string: Optional[str] = None):
        self.sqlite_path = sqlite_path or r"C:\Users\kpecco\Desktop\codes\TESTING\app\data\catalog.db"
        self.mssql_connection_string = mssql_connection_string or os.getenv('MSSQL_CONNECTION_STRING')
        self.batch_size = 5000
        self.controller = MigrationController()  # Default controller
        
        if not self.mssql_connection_string:
            raise ValueError("MSSQL_CONNECTION_STRING not found in environment")
    
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
    
    def check_existing_data(self) -> Dict[str, int]:
        """Check what data already exists in SQL Server"""
        try:
            conn = self.get_mssql_connection()
            cursor = conn.cursor()
            
            tables = ['parts', 'technical_guides', 'guide_parts']
            existing_data = {}
            
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    existing_data[table] = count
                    logger.info(f"📊 {table}: {count:,} existing records")
                except Exception as e:
                    logger.info(f"📊 {table}: Does not exist or error: {e}")
                    existing_data[table] = 0
            
            conn.close()
            return existing_data
            
        except Exception as e:
            logger.error(f"❌ Error checking existing data: {e}")
            return {}
    
    def reset_mssql_database(self):
        """Reset SQL Server database by dropping existing tables"""
        try:
            conn = self.get_mssql_connection()
            cursor = conn.cursor()
            
            logger.info("🔄 Resetting SQL Server database...")
            
            # Drop tables in correct order (due to foreign keys)
            tables = ['guide_parts', 'technical_guides', 'parts']
            
            for table in tables:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {table}")
                    logger.info(f"✅ Dropped table: {table}")
                except Exception as e:
                    logger.warning(f"Could not drop {table}: {e}")
            
            conn.commit()
            conn.close()
            logger.info("✅ Database reset successfully")
            
        except Exception as e:
            logger.error(f"❌ Error resetting database: {e}")
            raise

    def create_mssql_schema(self):
        """Create SQL Server schema matching SQLite structure"""
        conn = self.get_mssql_connection()
        cursor = conn.cursor()
    
        try:
            # Parts table
            cursor.execute("""
                CREATE TABLE parts (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    catalog_name NVARCHAR(255) NOT NULL,
                    catalog_type NVARCHAR(100),
                    part_type NVARCHAR(100),
                    part_number NVARCHAR(100) NOT NULL,
                    description NVARCHAR(MAX),
                    category NVARCHAR(100),
                    page INT,
                    image_path NVARCHAR(MAX),
                    page_text NVARCHAR(MAX),
                    pdf_path NVARCHAR(MAX),
                    machine_info NVARCHAR(MAX),
                    specifications NVARCHAR(MAX),
                    oe_numbers NVARCHAR(MAX),
                    applications NVARCHAR(MAX),
                    features NVARCHAR(MAX),
                    created_at DATETIME2 DEFAULT GETDATE()
                )
            """)
            
            # Technical guides table
            cursor.execute("""
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
            
            # Guide-Parts association table
            cursor.execute("""
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
            
            conn.commit()
            logger.info("✅ Tables created successfully")
            
            # Create indexes
            self._create_indexes(conn)
                
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Error creating SQL Server schema: {e}")
            raise
        finally:
            conn.close()

    def _create_indexes(self, conn):
        """Create performance indexes"""
        cursor = conn.cursor()
        
        indexes = [
            ("CREATE INDEX idx_parts_part_number ON parts(part_number)", "parts part_number"),
            ("CREATE INDEX idx_parts_catalog_name ON parts(catalog_name)", "parts catalog_name"),
            ("CREATE INDEX idx_parts_category ON parts(category)", "parts category"),
            ("CREATE INDEX idx_guides_name ON technical_guides(guide_name)", "guides name"),
            ("CREATE INDEX idx_guide_parts_guide ON guide_parts(guide_id)", "guide_parts guide"),
            ("CREATE INDEX idx_guide_parts_part ON guide_parts(part_number)", "guide_parts part"),
        ]
        
        for index_sql, desc in indexes:
            try:
                cursor.execute(index_sql)
                logger.debug(f"Created index: {desc}")
            except Exception as e:
                logger.warning(f"Could not create index for {desc}: {e}")
        
        conn.commit()
        logger.info("✅ Indexes created successfully")

    def migrate_all_data(self):
        """Complete migration of all data (reset and migrate)"""
        logger.info("🚀 Starting complete database migration...")
        
        start_time = time.time()
        
        try:
            # Step 1: Reset database
            self.reset_mssql_database()
            
            # Step 2: Create schema
            self.create_mssql_schema()
            
            # Step 3: Migrate parts data
            parts_start = time.time()
            self.migrate_parts_data()
            parts_duration = time.time() - parts_start
            logger.info(f"⏱️ Parts migration took: {parts_duration:.2f} seconds")
            
            # Step 4: Migrate technical guides
            guides_start = time.time()
            self.migrate_technical_guides()
            guides_duration = time.time() - guides_start
            logger.info(f"⏱️ Guides migration took: {guides_duration:.2f} seconds")
            
            # Step 5: Verify migration
            self.verify_migration()
            
            total_duration = time.time() - start_time
            logger.info(f"🎉 Complete migration completed in {total_duration:.2f} seconds!")
            
        except Exception as e:
            logger.error(f"❌ Complete migration failed: {e}")
            raise

        
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
            
            logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔄 Migrating parts: {current_mssql_count:,} → {total_parts:,}")
            
            migrated_count = current_mssql_count
            
            # If we already have all parts, return
            if migrated_count >= total_parts:
                logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ All parts already migrated!")
                return migrated_count
            
            # Find starting rowid based on current progress
            start_rowid = self._find_start_rowid(sqlite_conn, migrated_count)
            if start_rowid is None:
                logger.error(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ Could not find resume point")
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
                    logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ All parts migrated successfully!")
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
                logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📦 Batch {batch_number}: Migrated {len(batch):,} parts "
                        f"(Total: {migrated_count:,}/{total_parts:,}, {progress:.1f}%) "
                        f"in {batch_duration:.2f}s")
                
                # Stop condition check
                if not self.controller.check_continue():
                    logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⏹️ Parts migration stopped by user")
                    return migrated_count
            
            logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ Successfully migrated {migrated_count:,} parts")
            return migrated_count
            
        except Exception as e:
            mssql_conn.rollback()
            logger.error(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ Error migrating parts data: {e}")
            raise
        finally:
            sqlite_conn.close()
            mssql_conn.close()

    def migrate_remaining_parts(self):
        """Migrate only the remaining parts that haven't been migrated yet"""
        sqlite_conn = self.get_sqlite_connection()
        mssql_conn = self.get_mssql_connection()
        
        try:
            sqlite_cur = sqlite_conn.cursor()
            mssql_cur = mssql_conn.cursor()
            
            # Get counts
            mssql_cur.execute("SELECT COUNT(*) FROM parts")
            current_mssql_count = mssql_cur.fetchone()[0]
            
            sqlite_cur.execute("SELECT COUNT(*) FROM parts")
            total_sqlite_parts = sqlite_cur.fetchone()[0]
            
            remaining_parts = total_sqlite_parts - current_mssql_count
            
            if remaining_parts <= 0:
                logger.info("✅ All parts already migrated!")
                return 0
            
            logger.info(f"🔄 Resuming migration: {current_mssql_count:,} → {total_sqlite_parts:,} parts")
            logger.info(f"📊 Remaining to migrate: {remaining_parts:,} parts")
            
            # Find the starting rowid in SQLite
            start_rowid = self._find_start_rowid(sqlite_conn, current_mssql_count)
            
            if start_rowid is None:
                logger.error("❌ Could not find resume point")
                return 0
            
            logger.info(f"📍 Starting from rowid: {start_rowid}")
            
            migrated_count = current_mssql_count
            last_rowid = start_rowid
            
            while self.controller.check_continue():  # Check if should continue
                sqlite_cur.execute("""
                    SELECT * FROM parts 
                    WHERE rowid > ? 
                    ORDER BY rowid 
                    LIMIT ?
                """, (last_rowid, self.batch_size))
                
                batch = sqlite_cur.fetchall()
                
                if not batch:
                    logger.info("✅ No more parts to migrate")
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
                
                # Progress update
                progress = (migrated_count / total_sqlite_parts) * 100
                logger.info(f"📦 Progress: {migrated_count:,} of {total_sqlite_parts:,} parts ({progress:.1f}%)")
                
                # Check if we should stop
                if not self.controller.check_continue():
                    logger.info("⏹️ Migration stopped by user")
                    break
            
            if self.controller.check_continue():
                logger.info(f"✅ Successfully migrated {remaining_parts:,} additional parts")
                logger.info(f"📊 Total parts in SQL Server: {migrated_count:,}")
            else:
                logger.info(f"⏹️ Migration stopped. Migrated {migrated_count - current_mssql_count:,} additional parts")
                logger.info(f"📊 Total parts in SQL Server: {migrated_count:,}")
            
            return migrated_count - current_mssql_count
            
        except Exception as e:
            mssql_conn.rollback()
            logger.error(f"❌ Error resuming migration: {e}")
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

    def migrate_technical_guides(self):
        """Migrate technical guides and associations with stop functionality"""
        if not self.controller.check_continue():
            logger.info("⏹️ Skipping guides migration - migration stopped")
            return
            
        sqlite_conn = self.get_sqlite_connection()
        mssql_conn = self.get_mssql_connection()
        
        try:
            sqlite_cur = sqlite_conn.cursor()
            mssql_cur = mssql_conn.cursor()
            
            # Check if guides already exist
            mssql_cur.execute("SELECT COUNT(*) FROM technical_guides")
            existing_guides = mssql_cur.fetchone()[0]
            
            if existing_guides > 0:
                logger.info(f"📊 Technical guides already exist: {existing_guides} guides")
                # Still need to get ID mapping for associations
                guide_id_map = self._get_guide_id_mapping(sqlite_conn, mssql_conn)
            else:
                logger.info("🔄 Migrating technical guides...")
                
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
                    if not self.controller.check_continue():
                        logger.info("⏹️ Stopping guides migration")
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
                logger.info(f"✅ Migrated {len(guides)} technical guides")
            
            # Migrate guide-parts associations if not stopped
            if self.controller.check_continue():
                self._migrate_guide_parts_associations(guide_id_map, sqlite_conn, mssql_conn)
            
        except Exception as e:
            mssql_conn.rollback()
            logger.error(f"❌ Error migrating technical guides: {e}")
            raise
        finally:
            sqlite_conn.close()
            mssql_conn.close()
    def migrate_part_images_table(self):
        """Migrate the part_images table from SQLite to MSSQL"""
        if not self.controller.check_continue():
            logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ⏹️ Skipping part_images migration - migration stopped")
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
                logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ℹ️ part_images table does not exist in SQLite")
                return
            
            # Create part_images table in MSSQL if it doesn't exist
            logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔄 Creating part_images table in MSSQL...")
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
                CREATE INDEX IF NOT EXISTS idx_part_images_part_number 
                ON part_images (part_number)
            """)
            mssql_cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_part_images_pdf_name 
                ON part_images (pdf_name)
            """)
            
            mssql_conn.commit()
            
            # Get count from SQLite
            sqlite_cur.execute("SELECT COUNT(*) FROM part_images")
            total_images = sqlite_cur.fetchone()[0]
            
            # Get current count from MSSQL
            mssql_cur.execute("SELECT COUNT(*) FROM part_images")
            current_count = mssql_cur.fetchone()[0]
            
            logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📊 part_images: SQLite={total_images:,}, MSSQL={current_count:,}")
            
            if current_count >= total_images:
                logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ part_images already migrated!")
                return
            
            # Migrate data
            logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 🔄 Migrating {total_images - current_count:,} part_images records...")
            
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
                    mssql_cur.executemany(insert_query, batch_params)
                    mssql_conn.commit()
                    migrated_count += len(batch_params)
                    batch_params = []
                    logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 📸 Migrated {migrated_count:,} part_images...")
            
            # Insert remaining records
            if batch_params and self.controller.check_continue():
                mssql_cur.executemany(insert_query, batch_params)
                mssql_conn.commit()
                migrated_count += len(batch_params)
            
            logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ✅ Successfully migrated {migrated_count:,} part_images")
            
        except Exception as e:
            mssql_conn.rollback()
            logger.error(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ❌ Error migrating part_images: {e}")
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
        """Migrate guide-parts associations with stop functionality"""
        try:
            sqlite_cur = sqlite_conn.cursor()
            mssql_cur = mssql_conn.cursor()
            
            # Check if associations already exist
            mssql_cur.execute("SELECT COUNT(*) FROM guide_parts")
            existing_associations = mssql_cur.fetchone()[0]
            
            if existing_associations > 0:
                logger.info(f"📊 Guide-parts associations already exist: {existing_associations} associations")
                return
            
            sqlite_cur.execute("SELECT COUNT(*) FROM guide_parts")
            total_associations = sqlite_cur.fetchone()[0]
            
            logger.info(f"🔄 Migrating {total_associations} guide-parts associations...")
            
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
                if not self.controller.check_continue():
                    logger.info("⏹️ Stopping associations migration")
                    break
                    
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
                    logger.info(f"   ...migrated {migrated_count} associations")
            
            # Insert any remaining associations
            if batch_params and self.controller.check_continue():
                mssql_cur.executemany(insert_query, batch_params)
                mssql_conn.commit()
            
            logger.info(f"✅ Migrated {migrated_count} guide-parts associations")
            
        except Exception as e:
            logger.error(f"❌ Error migrating associations: {e}")
            raise

    def _safe_json_parse(self, json_str):
        """Safely parse JSON string"""
        if not json_str:
            return None
        try:
            return json.loads(json_str)
        except:
            return None

    def verify_migration(self):
        """Verify the migration was successful"""
        if not self.controller.check_continue():
            logger.info("⏹️ Skipping verification - migration stopped")
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
            
            logger.info("📊 Migration Verification:")
            logger.info(f"   Parts: SQLite={sqlite_parts:,}, SQL Server={mssql_parts:,}")
            logger.info(f"   Guides: SQLite={sqlite_guides}, SQL Server={mssql_guides}")
            logger.info(f"   Associations: SQLite={sqlite_associations:,}, SQL Server={mssql_associations:,}")
            
            if (mssql_parts == sqlite_parts and 
                mssql_guides == sqlite_guides and 
                mssql_associations == sqlite_associations):
                logger.info("✅ Migration verified successfully!")
                return True
            else:
                logger.warning("⚠️ Migration counts don't match - please check")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error verifying migration: {e}")
            return False
        finally:
            sqlite_conn.close()
            mssql_conn.close()

    def run_resume_migration(self):
        """Run resume migration process (continue from existing data)"""
        logger.info("🚀 RESUMING database migration...")
        
        start_time = time.time()
        
        try:
            # Step 1: Check existing data
            existing_data = self.check_existing_data()
            
            # Step 2: Resume parts migration
            parts_start = time.time()
            self.migrate_remaining_parts()
            parts_duration = time.time() - parts_start
            logger.info(f"⏱️ Parts migration took: {parts_duration:.2f} seconds")
            
            # Step 3: Migrate technical guides
            guides_start = time.time()
            self.migrate_technical_guides()
            guides_duration = time.time() - guides_start
            logger.info(f"⏱️ Guides migration took: {guides_duration:.2f} seconds")
            
            # Step 4: Verify migration
            self.verify_migration()
            
            total_duration = time.time() - start_time
            logger.info(f"🎉 RESUME migration completed in {total_duration:.2f} seconds!")
            
        except Exception as e:
            logger.error(f"❌ Resume migration failed: {e}")
            raise

    def run_optimized_migration(self):
        """Run optimized migration with stop functionality"""
        logger.info("🚀 Starting OPTIMIZED database migration...")
        
        start_time = time.time()
        
        try:
            # Check if we should reset or resume
            existing_data = self.check_existing_data()
            total_parts = existing_data.get('parts', 0)
            
            if total_parts == 0:
                # Fresh migration
                logger.info("🔄 Starting fresh migration...")
                self.reset_mssql_database()
                self.create_mssql_schema()
                self.migrate_parts_data()
            else:
                # Resume migration
                logger.info("🔄 Resuming existing migration...")
                self.migrate_remaining_parts()
            
            # Only migrate guides if not stopped
            if self.controller.check_continue():
                self.migrate_technical_guides()
            
            # Only verify if not stopped
            if self.controller.check_continue():
                self.verify_migration()
                total_duration = time.time() - start_time
                logger.info(f"🎉 OPTIMIZED migration completed in {total_duration:.2f} seconds!")
            else:
                logger.info("⏹️ Migration stopped before completion")
                
        except Exception as e:
            logger.error(f"❌ Optimized migration failed: {e}")
            raise