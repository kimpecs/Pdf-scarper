#!/usr/bin/env python3
"""
Check if all required files and __init__.py files exist
"""
from pathlib import Path

required_files = [
    "app/__init__.py",
    "app/pdf_processing/__init__.py",
    "app/pdf_processing/extract_catalog.py",
    "app/utils/__init__.py",
    "app/utils/constants.py",
    "app/utils/logger.py",
    "app/services/__init__.py",
    "app/services/db/__init__.py",
    "app/services/db/queries.py",
]

project_root = Path(__file__).parent.parent

print("Checking project structure...")
for file_path in required_files:
    full_path = project_root / file_path
    if full_path.exists():
        print(f"[OK] {file_path}")
    else:
        print(f"[ERROR] {file_path} - MISSING")

print(f"\nProject root: {project_root}")