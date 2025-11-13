#  process_guides.py

#!/usr/bin/env python3
"""
Process technical guide PDFs
"""
import os
import sys
import json
from pathlib import Path

# EXACT PATH: This script is in app/scripts/
script_dir = Path(__file__).parent  # app/scripts/
app_dir = script_dir.parent         # app/
sys.path.insert(0, str(app_dir))

from services.pdf_processing.extract_guides import GuideExtractor
from services.db.queries import DatabaseManager
from utils.logger import setup_logging

logger = setup_logging()

def save_guide_with_fallback(guide_data: dict, db_manager: DatabaseManager) -> int:
    """Save guide data with fallback for missing columns"""
    try:
        # Try the extractor's method first
        extractor = GuideExtractor()
        guide_id = extractor.save_guide_to_database(guide_data)
        return guide_id
    except Exception as e:
        if "no column named" in str(e).lower():
            logger.warning(f"Database schema issue detected, using fallback method: {e}")
            return save_guide_fallback(guide_data, db_manager)
        else:
            raise

def save_guide_fallback(guide_data: dict, db_manager: DatabaseManager) -> int:
    """Fallback method to save guide without the new columns"""
    try:
        conn = db_manager.get_connection()
        cur = conn.cursor()
        
        # Convert template_fields to JSON string for storage
        template_fields_json = guide_data.get('template_fields')
        if template_fields_json and isinstance(template_fields_json, dict):
            template_fields_json = json.dumps(template_fields_json)
        
        # Try INSERT with basic columns (matching current schema)
        cur.execute("""
            INSERT OR REPLACE INTO technical_guides 
            (guide_name, display_name, description, category, template_fields)
            VALUES (?, ?, ?, ?, ?)
        """, (
            guide_data['guide_name'],
            guide_data['display_name'],
            guide_data.get('description', ''),
            guide_data.get('category', 'Technical Documentation'),
            template_fields_json
        ))
        
        guide_id = cur.lastrowid
        
        # Try to create guide-part associations if possible
        try:
            related_parts = guide_data.get('related_parts', [])
            if related_parts:
                # Create guide_parts table if it doesn't exist
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS guide_parts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guide_id INTEGER,
                        part_number TEXT,
                        confidence_score REAL DEFAULT 1.0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (guide_id) REFERENCES technical_guides (id),
                        UNIQUE(guide_id, part_number)
                    )
                """)
                
                # Insert associations
                for part_number in related_parts:
                    cur.execute("""
                        INSERT OR IGNORE INTO guide_parts (guide_id, part_number)
                        VALUES (?, ?)
                    """, (guide_id, part_number))
                
                logger.info(f"Created {len(related_parts)} guide-part associations")
        except Exception as assoc_error:
            logger.warning(f"Could not create guide-part associations: {assoc_error}")
            # Continue without associations
        
        conn.commit()
        conn.close()
        
        logger.info(f"Saved guide to database (fallback): {guide_data['guide_name']} (ID: {guide_id})")
        return guide_id
        
    except Exception as e:
        logger.error(f"Error in fallback save: {e}")
        return -1

def process_technical_guides():
    """Process all technical guide PDFs"""
    data_dir = app_dir / "data"
    guides_directory = data_dir / "guides"
    
    if not guides_directory.exists():
        logger.error(f"Guides directory not found: {guides_directory}")
        logger.info("Please place guide PDFs in the app/data/guides directory")
        return
    
    guide_files = list(guides_directory.glob("*.pdf"))
    if not guide_files:
        logger.info(f"No guide PDFs found in {guides_directory}")
        return
    
    logger.info(f"Found {len(guide_files)} technical guides to process")
    
    # Initialize extractor and database manager
    extractor = GuideExtractor()
    db_manager = DatabaseManager()
    
    processed_count = 0
    failed_count = 0
    
    for i, guide_path in enumerate(guide_files, 1):
        try:
            logger.info(f"[{i}/{len(guide_files)}] Processing technical guide: {guide_path.name}")
            
            # Extract guide data
            guide_data = extractor.process_guide_pdf(str(guide_path))
            
            # Save to database with fallback
            guide_id = save_guide_with_fallback(guide_data, db_manager)
            
            if guide_id > 0:
                part_count = len(guide_data.get('related_parts', []))
                logger.info(f"SUCCESS: Processed {guide_path.name} (ID: {guide_id}) with {part_count} related parts")
                processed_count += 1
            else:
                logger.error(f"FAILED: Could not save {guide_path.name} to database")
                failed_count += 1
            
        except Exception as e:
            logger.error(f"ERROR processing {guide_path.name}: {e}")
            failed_count += 1
            continue
    
    logger.info(f"Guide processing completed! Processed: {processed_count}, Failed: {failed_count}, Total: {len(guide_files)}")

def main():
    logger.info("Starting technical guide processing...")
    process_technical_guides()
    logger.info("Technical guide processing completed!")

if __name__ == "__main__":
    main()
