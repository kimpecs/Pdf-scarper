#!/usr/bin/env python3
"""
Batch process all PDFs in a directory - FIXED VERSION
"""
import os
import sys
import re
from pathlib import Path
from fastapi import File, UploadFile

# EXACT PATH: This script is in app/scripts/
script_dir = Path(__file__).parent  # app/scripts/
app_dir = script_dir.parent         # app/
sys.path.insert(0, str(app_dir))

from services.pdf_processing.extract_catalog import CatalogExtractor
from services.pdf_processing.extract_guides import GuideExtractor
from services.db.queries import DatabaseManager
from utils.logger import setup_logging

logger = setup_logging()

def clean_text(text: str) -> str:
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

def process_pdf_catalogs():
    """Process all catalog PDFs with duplicate prevention"""
    # Use correct paths relative to app directory
    data_dir = app_dir / "data"
    pdf_directory = data_dir / "pdfs"
    output_image_dir = data_dir / "part_images"
    
    if not pdf_directory.exists():
        logger.error(f"PDF directory not found: {pdf_directory}")
        logger.info("Please place PDF files in the app/data/pdfs directory")
        return
    
    pdf_files = list(pdf_directory.glob("*.pdf"))
    if not pdf_files:
        logger.info(f"No PDF files found in {pdf_directory}")
        return
    
    logger.info(f"Found {len(pdf_files)} PDF files to process")
    
    # Initialize extractor and database
    extractor = CatalogExtractor()
    db_manager = DatabaseManager()
    
    total_parts = 0
    skipped_duplicates = 0
    
    for pdf_path in pdf_files:
        try:
            logger.info(f"🔄 Processing catalog PDF: {pdf_path.name}")
            
            # Extract catalog data from PDF
            catalog_data = extractor.process_pdf(str(pdf_path), str(output_image_dir))
            
            # Clean and insert into database with duplicate checking
            inserted_count = 0
            for part_data in catalog_data:
                # Clean the data before insertion
                part_data = clean_part_data(part_data)
                
                # Check for existing part to prevent duplicates
                if not part_exists(db_manager, part_data):
                    try:
                        db_manager.insert_part(part_data)
                        inserted_count += 1
                    except Exception as insert_error:
                        # This might be a duplicate due to race condition
                        if "UNIQUE constraint" in str(insert_error):
                            skipped_duplicates += 1
                            logger.debug(f"Skipped duplicate: {part_data.get('part_number')}")
                        else:
                            logger.error(f"Error inserting part {part_data.get('part_number')}: {insert_error}")
                else:
                    skipped_duplicates += 1
            
            logger.info(f"✅ Successfully processed {pdf_path.name} - {inserted_count} parts inserted, {skipped_duplicates} duplicates skipped")
            total_parts += inserted_count
            
        except Exception as e:
            logger.error(f"❌ Error processing {pdf_path.name}: {e}")
            continue
    
    logger.info(f"🎉 PDF processing completed! Total parts inserted: {total_parts}, Duplicates skipped: {skipped_duplicates}")

def clean_part_data(part_data: dict) -> dict:
    """Clean part data by removing excessive dots and whitespace"""
    text_fields = ['description', 'features', 'specifications', 'machine_info', 'applications']
    
    for field in text_fields:
        if field in part_data and part_data[field]:
            part_data[field] = clean_text(part_data[field])
    
    # Clean page_text if it exists (limit length to prevent database issues)
    if 'page_text' in part_data and part_data['page_text']:
        part_data['page_text'] = clean_text(part_data['page_text'])[:10000]  # Limit to 10k chars
    
    return part_data

def part_exists(db_manager, part_data: dict) -> bool:
    """Check if a part already exists in the database"""
    try:
        conn = db_manager.get_connection()
        cur = conn.cursor()
        
        # Check for existing part with same catalog, part_number, and page
        cur.execute("""
            SELECT id FROM parts 
            WHERE catalog_name = ? AND part_number = ? AND page = ?
        """, (
            part_data.get('catalog_name'),
            part_data.get('part_number'),
            part_data.get('page')
        ))
        
        exists = cur.fetchone() is not None
        conn.close()
        return exists
        
    except Exception as e:
        logger.error(f"Error checking if part exists: {e}")
        return False

def process_technical_guides():
    """Process technical guides with improved error handling"""
    data_dir = app_dir / "data"
    guides_directory = data_dir / "guides"
    
    if not guides_directory.exists():
        logger.info(f"Guides directory not found: {guides_directory}")
        return
    
    guide_files = list(guides_directory.glob("*.pdf"))
    if guide_files:
        logger.info(f"Found {len(guide_files)} technical guides")
        
        guide_extractor = GuideExtractor()
        processed_count = 0
        failed_count = 0
        
        for guide_path in guide_files:
            try:
                logger.info(f"📚 Processing technical guide: {guide_path.name}")
                guide_data = guide_extractor.process_guide_pdf(str(guide_path))
                
                # Clean guide data
                guide_data = clean_guide_data(guide_data)
                
                guide_id = guide_extractor.save_guide_to_database(guide_data)
                
                if guide_id > 0:
                    processed_count += 1
                    logger.info(f"✅ Saved guide: {guide_data['display_name']} (ID: {guide_id})")
                else:
                    failed_count += 1
                    logger.error(f"❌ Failed to save guide: {guide_data['display_name']}")
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"❌ Error processing guide {guide_path.name}: {e}")
                continue
        
        logger.info(f"📊 Technical guides processing: {processed_count} successful, {failed_count} failed")
    else:
        logger.info("No technical guide PDFs found")

def clean_guide_data(guide_data: dict) -> dict:
    """Clean technical guide data"""
    if 'description' in guide_data and guide_data['description']:
        guide_data['description'] = clean_text(guide_data['description'])[:500]  # Limit description length
    
    # Clean template fields if they exist
    if 'template_fields' in guide_data and guide_data['template_fields']:
        if isinstance(guide_data['template_fields'], dict):
            # Clean text fields in template
            text_fields = ['description', 'guide_title']
            for field in text_fields:
                if field in guide_data['template_fields'] and guide_data['template_fields'][field]:
                    guide_data['template_fields'][field] = clean_text(guide_data['template_fields'][field])
    
    return guide_data

def create_associations():
    """Create associations between parts and guides based on part numbers"""
    try:
        db_manager = DatabaseManager()
        conn = db_manager.get_connection()
        cur = conn.cursor()
        
        logger.info("🔗 Creating part-guide associations...")
        
        # Get all guide-part associations from guide_parts table
        cur.execute("""
            SELECT gp.guide_id, gp.part_number, gp.confidence_score
            FROM guide_parts gp
            JOIN technical_guides tg ON gp.guide_id = tg.id
            WHERE tg.is_active = 1
        """)
        
        associations = cur.fetchall()
        logger.info(f"Found {len(associations)} guide-part associations to process")
        
        created_count = 0
        for guide_id, part_number, confidence_score in associations:
            try:
                # Find parts with this part_number
                cur.execute("""
                    SELECT id FROM parts WHERE part_number = ?
                """, (part_number,))
                
                parts = cur.fetchall()
                
                # Create part_guide associations for each matching part
                for (part_id,) in parts:
                    try:
                        cur.execute("""
                            INSERT OR IGNORE INTO part_guides (part_id, guide_id, confidence_score)
                            VALUES (?, ?, ?)
                        """, (part_id, guide_id, confidence_score))
                        created_count += 1
                    except Exception as e:
                        logger.debug(f"Could not create association for part {part_id} with guide {guide_id}: {e}")
                        
            except Exception as e:
                logger.error(f"Error processing part_number {part_number}: {e}")
                continue
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Created {created_count} part-guide associations")
        
    except Exception as e:
        logger.error(f"❌ Error creating associations: {e}")

def cleanup_duplicates():
    """Clean up any duplicate parts that might have been created"""
    try:
        db_manager = DatabaseManager()
        conn = db_manager.get_connection()
        cur = conn.cursor()
        
        logger.info("🧹 Cleaning up duplicate parts...")
        
        # Find and delete duplicates (keeping the one with the lowest ID)
        cur.execute("""
            DELETE FROM parts 
            WHERE id NOT IN (
                SELECT MIN(id) 
                FROM parts 
                GROUP BY catalog_name, part_number, page
            )
        """)
        
        duplicates_removed = cur.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Removed {duplicates_removed} duplicate parts")
        
    except Exception as e:
        logger.error(f"❌ Error cleaning duplicates: {e}")

def main():
    logger.info("🚀 Starting batch PDF processing...")
    
    try:
        # Process catalog PDFs
        process_pdf_catalogs()
        
        # Process technical guides
        process_technical_guides()
        
        # Create associations between parts and guides
        create_associations()
        
        # Final cleanup of any duplicates
        cleanup_duplicates()
        
        logger.info("🎉 All PDF processing completed successfully!")
        
    except Exception as e:
        logger.error(f"💥 Critical error in batch processing: {e}")
        raise

if __name__ == "__main__":
    main()