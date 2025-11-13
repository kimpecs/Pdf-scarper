# app/services/db/migration_service.py
import sqlite3
import pyodbc
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
import os
import time
from app.utils.logger import setup_logging
from app.services.storage.storage_service import StorageService
from app.utils.config import settings

logger = setup_logging()

class MSSQLMigrationService:
    def __init__(self, sqlite_path: str, mssql_connection_string: str):
        self.sqlite_path = sqlite_path
        self.mssql_connection_string = mssql_connection_string
        self.storage_service = StorageService()
        self.batch_size = 5000  # Optimal batch size for performance
        
    def get_sqlite_connection(self):
        return sqlite3.connect(self.sqlite_path)
    
    def get_mssql_connection(self):
        conn = pyodbc.connect(self.mssql_connection_string)
        conn.autocommit = False
        return conn
    
    def reset_mssql_database(self):
        """Reset SQL Server database"""
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
            cursor.execute("SET IMPLICIT_TRANSACTIONS OFF")
            
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
                    s3_pdf_url NVARCHAR(MAX),
                    s3_image_url NVARCHAR(MAX),
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
                    s3_key NVARCHAR(MAX),
                    template_fields NVARCHAR(MAX),
                    pdf_path NVARCHAR(MAX),
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
                
            # Create essential indexes
            self._create_essential_indexes(conn)
            
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Error creating SQL Server schema: {e}")
            raise
        finally:
            conn.close()

    def _create_essential_indexes(self, conn):
        """Create only essential indexes for performance"""
        cursor = conn.cursor()
        
        essential_indexes = [
            ("idx_parts_part_number", "parts", "part_number"),
            ("idx_parts_catalog_name", "parts", "catalog_name"),
            ("idx_parts_category", "parts", "category"),
            ("idx_guides_name", "technical_guides", "guide_name"),
            ("idx_guide_parts_guide", "guide_parts", "guide_id"),
            ("idx_guide_parts_part", "guide_parts", "part_number"),
        ]
        
        for index_name, table_name, columns in essential_indexes:
            try:
                cursor.execute(f"CREATE INDEX {index_name} ON {table_name}({columns})")
                logger.debug(f"Created index: {index_name}")
            except Exception as e:
                logger.warning(f"Could not create index {index_name}: {e}")
        
        conn.commit()
        logger.info("✅ Essential indexes created successfully")

    def migrate_parts_data_optimized(self):
        """Optimized batch migration for parts data"""
        sqlite_conn = self.get_sqlite_connection()
        mssql_conn = self.get_mssql_connection()
        
        try:
            sqlite_cur = sqlite_conn.cursor()
            mssql_cur = mssql_conn.cursor()
            
            # Get total count
            sqlite_cur.execute("SELECT COUNT(*) FROM parts")
            total_parts = sqlite_cur.fetchone()[0]
            
            logger.info(f"🔄 Migrating {total_parts:,} parts (optimized batch)...")
            
            # Use more efficient pagination with rowid
            migrated_count = 0
            last_rowid = 0
            
            while True:
                sqlite_cur.execute("""
                    SELECT * FROM parts 
                    WHERE rowid > ? 
                    ORDER BY rowid 
                    LIMIT ?
                """, (last_rowid, self.batch_size))
                
                batch = sqlite_cur.fetchall()
                
                if not batch:
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
                mssql_cur.executemany(insert_query, batch_params)
                mssql_conn.commit()
                
                migrated_count += len(batch)
                
                # Progress update
                if migrated_count % 10000 == 0:
                    progress = (migrated_count / total_parts) * 100
                    logger.info(f"📦 Migrated {migrated_count:,} of {total_parts:,} parts ({progress:.1f}%)...")
            
            logger.info(f"✅ Successfully migrated {migrated_count:,} parts to SQL Server")
            
        except Exception as e:
            mssql_conn.rollback()
            logger.error(f"❌ Error migrating parts data: {e}")
            raise
        finally:
            sqlite_conn.close()
            mssql_conn.close()

    def migrate_technical_guides_optimized(self):
        """Optimized technical guides migration"""
        sqlite_conn = self.get_sqlite_connection()
        mssql_conn = self.get_mssql_connection()
        
        try:
            sqlite_cur = sqlite_conn.cursor()
            mssql_cur = mssql_conn.cursor()
            
            # Get guides count
            sqlite_cur.execute("SELECT COUNT(*) FROM technical_guides")
            total_guides = sqlite_cur.fetchone()[0]
            
            logger.info(f"🔄 Migrating {total_guides} technical guides...")
            
            sqlite_cur.execute("SELECT * FROM technical_guides")
            guides = sqlite_cur.fetchall()
            columns = [desc[0] for desc in sqlite_cur.description]
            
            insert_query = """
                INSERT INTO technical_guides (
                    guide_name, display_name, description, category,
                    pdf_path, template_fields, related_parts, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            batch_params = []
            guide_id_map = {}  # Map old IDs to new IDs
            
            for guide in guides:
                guide_dict = dict(zip(columns, guide))
                old_guide_id = guide_dict.get('id')
                
                template_fields = self._safe_json_parse(guide_dict.get('template_fields'))
                related_parts = self._safe_json_parse(guide_dict.get('related_parts'))
                
                batch_params.append((
                    guide_dict.get('guide_name'),
                    guide_dict.get('display_name'),
                    guide_dict.get('description'),
                    guide_dict.get('category'),
                    guide_dict.get('pdf_path'),
                    json.dumps(template_fields) if template_fields else None,
                    json.dumps(related_parts) if related_parts else None,
                    bool(guide_dict.get('is_active', True))
                ))
            
            # Execute all guides in one batch
            mssql_cur.executemany(insert_query, batch_params)
            mssql_conn.commit()
            
            logger.info(f"✅ Migrated {len(batch_params)} technical guides")
            
            # Get the mapping between old and new guide IDs
            guide_id_map = self._get_guide_id_mapping(sqlite_conn, mssql_conn)
            
            # Migrate associations
            self._migrate_guide_parts_associations(guide_id_map, mssql_conn)
            
        except Exception as e:
            mssql_conn.rollback()
            logger.error(f"❌ Error migrating technical guides: {e}")
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

    def _migrate_guide_parts_associations(self, guide_id_map, mssql_conn):
        """Migrate guide-parts associations"""
        sqlite_conn = self.get_sqlite_connection()
        
        try:
            sqlite_cur = sqlite_conn.cursor()
            mssql_cur = mssql_conn.cursor()
            
            # Get associations count
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
                association_dict = dict(zip(columns, association))
                old_guide_id = association_dict.get('guide_id')
                part_number = association_dict.get('part_number')
                confidence_score = association_dict.get('confidence_score', 1.0)
                
                new_guide_id = guide_id_map.get(old_guide_id)
                if new_guide_id:
                    batch_params.append((new_guide_id, part_number, confidence_score))
                    migrated_count += 1
                
                # Insert in batches to avoid memory issues
                if len(batch_params) >= 1000:
                    mssql_cur.executemany(insert_query, batch_params)
                    mssql_conn.commit()
                    batch_params = []
            
            # Insert any remaining associations
            if batch_params:
                mssql_cur.executemany(insert_query, batch_params)
                mssql_conn.commit()
            
            logger.info(f"✅ Migrated {migrated_count} guide-parts associations")
            
        except Exception as e:
            logger.error(f"❌ Error migrating guide-parts associations: {e}")
            raise
        finally:
            sqlite_conn.close()

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

    def run_optimized_migration(self):
        """Run optimized migration process"""
        logger.info("🚀 Starting OPTIMIZED database migration...")
        
        start_time = time.time()
        
        try:
            # Step 1: Reset database
            self.reset_mssql_database()
            
            # Step 2: Create schema
            self.create_mssql_schema()
            
            # Step 3: Migrate parts data (using optimized batch)
            parts_start = time.time()
            self.migrate_parts_data_optimized()
            parts_duration = time.time() - parts_start
            logger.info(f"⏱️ Parts migration took: {parts_duration:.2f} seconds")
            
            # Step 4: Migrate technical guides
            guides_start = time.time()
            self.migrate_technical_guides_optimized()
            guides_duration = time.time() - guides_start
            logger.info(f"⏱️ Guides migration took: {guides_duration:.2f} seconds")
            
            # Step 5: Verify migration
            self.verify_migration()
            
            total_duration = time.time() - start_time
            logger.info(f"🎉 OPTIMIZED migration completed in {total_duration:.2f} seconds!")
            
        except Exception as e:
            logger.error(f"❌ Optimized migration failed: {e}")
            raise

