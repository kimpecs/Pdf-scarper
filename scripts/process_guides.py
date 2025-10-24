#!/usr/bin/env python3
"""
Process technical guide PDFs
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.pdf_processing.extract_guides import GuideExtractor
from app.utils.logger import setup_logging

logger = setup_logging()

def process_technical_guides():
    """Process all technical guide PDFs"""
    guides_directory = Path("app/data/guides")
    
    if not guides_directory.exists():
        logger.error(f"Guides directory not found: {guides_directory}")
        logger.info("Please place guide PDFs in the app/data/guides directory")
        return
    
    guide_files = list(guides_directory.glob("*.pdf"))
    if not guide_files:
        logger.info(f"No guide PDFs found in {guides_directory}")
        return
    
    logger.info(f"Found {len(guide_files)} technical guides to process")
    
    # Initialize extractor
    extractor = GuideExtractor()
    
    processed_count = 0
    
    for guide_path in guide_files:
        try:
            logger.info(f"Processing technical guide: {guide_path.name}")
            
            # Extract guide data
            guide_data = extractor.process_guide_pdf(str(guide_path))
            
            # Save to database
            guide_id = extractor.save_guide_to_database(guide_data)
            
            if guide_id > 0:
                logger.info(f"Successfully processed {guide_path.name} (ID: {guide_id})")
                processed_count += 1
            else:
                logger.error(f"Failed to save {guide_path.name} to database")
            
        except Exception as e:
            logger.error(f"Error processing {guide_path.name}: {e}")
            continue
    
    logger.info(f"Guide processing completed! Processed {processed_count}/{len(guide_files)} guides")

def main():
    logger.info("Starting technical guide processing...")
    process_technical_guides()
    logger.info("Technical guide processing completed!")

if __name__ == "__main__":
    main()