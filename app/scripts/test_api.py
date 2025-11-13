'''#!/usr/bin/env python3
"""
Simple API test - uses the correct endpoints
"""
import requests

def test_simple():
    """Test the actual API endpoints"""
    base = "http://localhost:8000"
    
    endpoints = [
        "/api/debug/status",
        "/catalogs", 
        "/categories",
        "/part_types",
        "/search?q=test&limit=5"
    ]
    
    print("Testing API Endpoints:\n")
    
    for endpoint in endpoints:
        try:
            url = base + endpoint
            print(f"Testing: {url}")
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "catalogs" in data:
                    print(f"  {endpoint}: {len(data['catalogs'])} catalogs")
                elif "categories" in data:
                    print(f"  {endpoint}: {len(data['categories'])} categories") 
                elif "results" in data:
                    print(f"  {endpoint}: {len(data['results'])} results")
                elif "status" in data:
                    print(f"  {endpoint}: {data['status']} - {data['parts_count']} parts")
                else:
                    print(f"  {endpoint}: Success")
            else:
                print(f"  {endpoint}: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"  {endpoint}: {e}")
        
        print()

if __name__ == "__main__":
    test_simple()
    '''
    # scripts/setup_migration.py
'''# scripts/test_api.py
import sys
import os
from pathlib import Path

def setup_environment():
    """Setup Python environment correctly"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    app_root = project_root.parent
    
    print(f"Script directory: {script_dir}")
    print(f"Project root (app): {project_root}")
    print(f"App root (TESTING): {app_root}")
    
    paths_to_add = [str(app_root), str(project_root)]
    for path in paths_to_add:
        if path not in sys.path:
            sys.path.insert(0, path)
    
    return app_root, project_root

def check_prerequisites():
    """Check if everything is ready for migration"""
    app_root, project_root = setup_environment()
    
    try:
        print("Attempting to import app modules...")
        from app.utils.config import settings
        from app.utils.logger import setup_logging
        
        print("SUCCESS: Imported app modules!")
        
        logger = setup_logging()
        logger.info("Checking migration prerequisites...")
        
        # Check SQLite database
        sqlite_path = settings.DB_PATH
        if sqlite_path.exists():
            logger.info(f"SQLite database found: {sqlite_path}")
            
            import sqlite3
            try:
                conn = sqlite3.connect(sqlite_path)
                cur = conn.cursor()
                
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cur.fetchall()]
                
                logger.info(f"Found tables: {', '.join(tables)}")
                
                for table in ['parts', 'technical_guides']:
                    if table in tables:
                        cur.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cur.fetchone()[0]
                        logger.info(f"   {table}: {count} records")
                
                conn.close()
                
            except Exception as e:
                logger.error(f"Error checking SQLite: {e}")
                return False
        else:
            logger.error(f"SQLite database not found: {sqlite_path}")
            return False
        
        # Check SQL Server connection string
        if hasattr(settings, 'MSSQL_CONNECTION_STRING') and settings.MSSQL_CONNECTION_STRING:
            logger.info("SQL Server connection string configured")
            
            # Test connection
            try:
                import pyodbc
                conn = pyodbc.connect(settings.MSSQL_CONNECTION_STRING)
                conn.close()
                logger.info("SQL Server connection test successful")
            except Exception as e:
                logger.error(f"SQL Server connection failed: {e}")
                return False
        else:
            logger.error("SQL Server connection string not configured")
            return False
        
        # Check pyodbc installation
        try:
            import pyodbc
            logger.info("pyodbc installed")
        except ImportError:
            logger.error("pyodbc not installed. Run: pip install pyodbc")
            return False
        
        logger.info("All prerequisites met! Ready for migration.")
        return True
        
    except ImportError as e:
        print(f"Import failed: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

if __name__ == "__main__":
    if check_prerequisites():
        print("\nSUCCESS: You're ready to run: python scripts/migrate_to_mssql.py")
    else:
        print("\nFAILED: Please fix the issues above before running migration.")
    '''
# test_setup.py
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent  # This should be the TESTING directory
sys.path.insert(0, str(project_root))

print(f"Project root: {project_root}")
print(f"Python path: {sys.path}")

# Try basic imports
try:
    print("Testing basic imports...")
    import sqlite3
    import pyodbc
    print("✅ Basic imports successful")
except ImportError as e:
    print(f"❌ Basic imports failed: {e}")

# Try app imports
try:
    print("Testing app imports...")
    from app.utils.logger import setup_logging
    logger = setup_logging('test')
    print("✅ Logger import successful")
    
    from app.utils.config import settings
    print(f"✅ Config import successful - MSSQL: {'Yes' if hasattr(settings, 'MSSQL_CONNECTION_STRING') else 'No'}")
except ImportError as e:
    print(f"❌ App imports failed: {e}")