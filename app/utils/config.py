import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # FIXED: Use the correct database path
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
    
    # Paths - FIXED: Use correct base directory
    BASE_DIR = Path(__file__).parent.parent  # Points to app/ directory
    DATA_DIR = BASE_DIR / "data"
    STATIC_DIR = BASE_DIR / "static"
    
    # Templates
    TEMPLATES_DIR = BASE_DIR / "templates"
    GUIDES_DIR = DATA_DIR / "guides"
    PDFS_DIR = DATA_DIR / "pdfs"
    PAGE_IMAGES_DIR = DATA_DIR / "page_images"
    
    # Frontend Settings
    FRONTEND_TITLE = os.getenv("FRONTEND_TITLE", "Knowledge Base")
    FRONTEND_DESCRIPTION = os.getenv("FRONTEND_DESCRIPTION", "Technical Documentation and Parts Catalog")
    MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", "100"))
    SEARCH_DEBOUNCE_MS = int(os.getenv("SEARCH_DEBOUNCE_MS", "300"))
    
    # Technical Guides Settings
    ENABLE_TECHNICAL_GUIDES = os.getenv("ENABLE_TECHNICAL_GUIDES", "true").lower() == "true"
    MAX_GUIDE_SECTIONS = int(os.getenv("MAX_GUIDE_SECTIONS", "10"))
    MAX_SPECIFICATIONS = int(os.getenv("MAX_SPECIFICATIONS", "20"))
    MAX_RELATED_PARTS = int(os.getenv("MAX_RELATED_PARTS", "6"))
    MAX_RELATED_GUIDES = int(os.getenv("MAX_RELATED_GUIDES", "5"))
    
    # Content Limits (for frontend display)
    MAX_DESCRIPTION_LENGTH = int(os.getenv("MAX_DESCRIPTION_LENGTH", "120"))
    MAX_APPLICATIONS_DISPLAY = int(os.getenv("MAX_APPLICATIONS_DISPLAY", "2"))
    MAX_CARD_CONTENT_LINES = int(os.getenv("MAX_CARD_CONTENT_LINES", "3"))
    
    # Security & Performance
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
    MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", "100"))  # MB
    
    # Feature Flags
    ENABLE_IMAGE_EXTRACTION = os.getenv("ENABLE_IMAGE_EXTRACTION", "true").lower() == "true"
    ENABLE_PDF_DOWNLOAD = os.getenv("ENABLE_PDF_DOWNLOAD", "true").lower() == "true"
    ENABLE_ADVANCED_SEARCH = os.getenv("ENABLE_ADVANCED_SEARCH", "true").lower() == "true"
    ENABLE_RELATED_CONTENT = os.getenv("ENABLE_RELATED_CONTENT", "true").lower() == "true"

settings = Settings()