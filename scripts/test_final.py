#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from app.services.pdf_processing.extract_catalog import CatalogExtractor
    print("✓ CatalogExtractor import: SUCCESS")
    
    from app.services.db.queries import DatabaseManager
    print("✓ DatabaseManager import: SUCCESS")
    
    from app.utils.logger import setup_logging
    print("✓ Logger import: SUCCESS")
    
    from app.utils.constants import PART_NUMBER_PATTERNS
    print("✓ Constants import: SUCCESS")
    
    # Test instantiation
    logger = setup_logging()
    extractor = CatalogExtractor()
    db_manager = DatabaseManager()
    print("✓ All components instantiated successfully!")
    print("✓ Your PDF extraction system is ready to use!")
    
except ImportError as e:
    print(f"✗ Import failed: {e}")
except Exception as e:
    print(f"✗ Instantiation failed: {e}")