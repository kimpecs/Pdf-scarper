import sys
from pathlib import Path

app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))

from app.services.pdf_processing.extract_catalog import CatalogExtractor
from app.utils.logger import setup_logging

logger = setup_logging()

def process_pdf_to_s3(pdf_path: str):
    """Simple: Process PDF -> SQLite -> Upload to S3"""
    print(f" Processing: {pdf_path}")
    
    extractor = CatalogExtractor()
    
    try:
        # This does everything:
        # 1. Extract data from PDF
        # 2. Save to SQLite database  
        # 3. Upload PDF + images to S3
        catalog_data = extractor.process_pdf_and_upload_to_s3(
            pdf_path=pdf_path,
            output_image_dir="data/page_images"
        )
        
        print(f"[OK] Completed: {len(catalog_data)} parts extracted")
        print("[OK] Data saved to SQLite database")
        print("[OK] Files uploaded to S3 bucket")
        
    except Exception as e:
        print(f"[ERROR] Error: {e}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python process_to_s3.py <pdf_path>")
        return
    
    pdf_path = sys.argv[1]
    
    if not Path(pdf_path).exists():
        print(f"[ERROR] PDF not found: {pdf_path}")
        return
    
    process_pdf_to_s3(pdf_path)

if __name__ == "__main__":
    main()