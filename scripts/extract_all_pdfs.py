#!/usr/bin/env python3
"""
Batch process all PDFs in a directory
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.pdf_processing.extract_catalog import CatalogExtractor
from app.services.pdf_processing.extract_guides import GuideExtractor
from app.services.db.queries import DatabaseManager
from app.utils.logger import setup_logging

logger = setup_logging()

def process_pdf_catalogs():
    """Process all catalog PDFs"""
    pdf_directory = Path("app/data/pdfs")
    output_image_dir = Path("app/data/page_images")
    
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
    
    for pdf_path in pdf_files:
        try:
            logger.info(f"Processing catalog PDF: {pdf_path.name}")
            
            # Extract catalog data from PDF
            catalog_data = extractor.process_pdf(str(pdf_path), str(output_image_dir))
            
            # Insert into database
            for part_data in catalog_data:
                db_manager.insert_part(part_data)
            
            logger.info(f"Successfully processed {pdf_path.name} - extracted {len(catalog_data)} parts")
            total_parts += len(catalog_data)
            
        except Exception as e:
            logger.error(f"Error processing {pdf_path.name}: {e}")
            continue
    
    logger.info(f"PDF processing completed! Total parts extracted: {total_parts}")

def process_technical_guides():
    """Process technical guides"""
    guides_directory = Path("app/data/guides")
    
    if not guides_directory.exists():
        logger.info(f"Guides directory not found: {guides_directory}")
        return
    
    guide_files = list(guides_directory.glob("*.pdf"))
    if guide_files:
        logger.info(f"Found {len(guide_files)} technical guides")
        
        guide_extractor = GuideExtractor()
        processed_count = 0
        
        for guide_path in guide_files:
            try:
                logger.info(f"Processing technical guide: {guide_path.name}")
                guide_data = guide_extractor.process_guide_pdf(str(guide_path))
                guide_id = guide_extractor.save_guide_to_database(guide_data)
                
                if guide_id > 0:
                    processed_count += 1
                    logger.info(f"Saved guide: {guide_data['display_name']} (ID: {guide_id})")
            except Exception as e:
                logger.error(f"Error processing guide {guide_path.name}: {e}")
                continue
        
        logger.info(f"Processed {processed_count} technical guides")

def main():
    logger.info("Starting batch PDF processing...")
    
    # Process catalog PDFs
    process_pdf_catalogs()
    
    # Process technical guides
    process_technical_guides()
    
    logger.info("PDF processing completed!")

if __name__ == "__main__":
    main()