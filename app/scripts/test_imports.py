#!/usr/bin/env python3
"""
Test script to verify imports work correctly
"""
import sys
from pathlib import Path

# EXACT PATH: This script is in app/scripts/
script_dir = Path(__file__).parent  # app/scripts/
app_dir = script_dir.parent         # app/
sys.path.insert(0, str(app_dir))

try:
    from services.pdf_processing.extract_catalog import CatalogExtractor
    print("✓ CatalogExtractor imported successfully")
    
    from services.pdf_processing.extract_guides import GuideExtractor
    print("✓ GuideExtractor imported successfully")
    
    from services.db.queries import DatabaseManager
    print("✓ DatabaseManager imported successfully")
    
    from utils.logger import setup_logging
    print("✓ setup_logging imported successfully")
    
    print("All imports successful!")
    
except ImportError as e:
    print(f"✗ Import failed: {e}")