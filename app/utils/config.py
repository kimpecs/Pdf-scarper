import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/catalog.db")
    
    # AWS S3
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")
    AWS_S3_REGION = os.getenv("AWS_S3_REGION", "us-east-1")
    AWS_S3_ENDPOINT = os.getenv("AWS_S3_ENDPOINT")
    
    # Application
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "1000"))
    IMAGE_DPI = int(os.getenv("IMAGE_DPI", "150"))
    
    # Paths
    BASE_DIR = Path(__file__).parent.parent.parent
    DATA_DIR = BASE_DIR / "data"
    STATIC_DIR = BASE_DIR / "app" / "static"

settings = Settings()