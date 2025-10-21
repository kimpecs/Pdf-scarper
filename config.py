# config.py
import os
from pathlib import Path

class Config:
    # Base directory
    BASE_DIR = Path(__file__).parent.absolute()
    
    # Database
    DB_PATH = BASE_DIR / "catalog.db"
    IMAGES_DIR = BASE_DIR / "page_images"
    PDF_DIR = BASE_DIR / "pdfs"
    STATIC_DIR = BASE_DIR / "static"
    GUIDES_DIR = BASE_DIR / "technical_guides"
    
    # AWS S3 Configuration (optional - for future use)
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', 'CHANGE_ME')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', 'CHANGE_ME')
    AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
    S3_BUCKET_NAME = os.getenv('S3_BUCKET', 'hydraulic-brakes-technical-guides')
    
    # Check if AWS credentials are actually set
    @classmethod
    def has_aws_credentials(cls):
        return (cls.AWS_ACCESS_KEY_ID not in ['CHANGE_ME', ''] and 
                cls.AWS_SECRET_ACCESS_KEY not in ['CHANGE_ME', ''])