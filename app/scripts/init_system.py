#!/usr/bin/env python3
"""
Complete system initialization - database setup + PDF processing
"""
import os
import sys
from pathlib import Path
from fastapi import File, UploadFile

# Add project root to sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from setup import init_database
from app.utils.logger import setup_logging

logger = setup_logging()

def main():
    """Initialize the entire system"""
    try:
        # Step 1: Initialize database
        logger.info("Initializing database...")
        init_database()
        
        # Step 2: Process PDFs (only after DB is ready)
        logger.info("Database ready. Starting PDF processing...")
        
        from detract_pdf import process_pdf_catalogs, process_technical_guides
        
        process_pdf_catalogs()
        process_technical_guides()
        
        logger.info("System initialization completed successfully!")
        
    except Exception as e:
        logger.error(f"System initialization failed: {e}")
        raise

if __name__ == "__main__":
    main()