# process_all_to_s3.py
"""
Batch process all PDFs and upload to S3
"""
import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime

script_dir = Path(__file__).parent  
app_dir = script_dir.parent        
sys.path.insert(0, str(app_dir))

from services.pdf_processing.extract_catalog import CatalogExtractor
from services.db.queries import DatabaseManager
from app.utils.logger import setup_logging

logger = setup_logging()

async def process_all_pdfs_to_s3():
    """Process all PDFs and upload to S3"""
    data_dir = app_dir / "data"
    pdf_directory = data_dir / "pdfs"
    output_image_dir = data_dir / "part_images"
    
    if not pdf_directory.exists():
        logger.error(f"PDF directory not found: {pdf_directory}")
        return
    
    pdf_files = list(pdf_directory.glob("*.pdf"))
    if not pdf_files:
        logger.info(f"No PDF files found in {pdf_directory}")
        return
    
    logger.info(f"Found {len(pdf_files)} PDF files to process and upload to S3")
    
    extractor = CatalogExtractor()
    db_manager = DatabaseManager()
    
    total_parts = 0
    successful_uploads = 0
    
    for pdf_path in pdf_files:
        try:
            logger.info(f"Processing and uploading to S3: {pdf_path.name}")
            
            # Extract catalog data and upload to S3
            catalog_data = await extractor.process_and_upload_to_s3(  # FIXED: Added await
                str(pdf_path), 
                str(output_image_dir), 
                upload_to_s3=True
            )
            
            # Insert into database
            for part_data in catalog_data:
                db_manager.insert_part(part_data)
            
            logger.info(f"Successfully processed {pdf_path.name} - extracted {len(catalog_data)} parts")
            total_parts += len(catalog_data)
            successful_uploads += 1
            
        except Exception as e:
            logger.error(f"Error processing {pdf_path.name}: {e}")
            continue
    
    logger.info(f"S3 processing completed! {successful_uploads}/{len(pdf_files)} PDFs uploaded, {total_parts} total parts extracted")

def main():
    logger.info("Starting batch PDF processing with S3 upload...")
    asyncio.run(process_all_pdfs_to_s3())
    logger.info("PDF processing with S3 upload completed!")

if __name__ == "__main__":
    main()