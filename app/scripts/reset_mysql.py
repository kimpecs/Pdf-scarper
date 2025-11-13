# scripts/reset_mssql.py
import sys
from pathlib import Path

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
app_root = project_root.parent
sys.path.insert(0, str(app_root))
sys.path.insert(0, str(project_root))

from app.utils.config import settings
from app.utils.logger import setup_logging

logger = setup_logging()

def reset_mssql_database():
    """Reset SQL Server database by dropping and recreating tables"""
    try:
        import pyodbc
        conn = pyodbc.connect(settings.MSSQL_CONNECTION_STRING)
        cursor = conn.cursor()
        
        logger.info("🔄 Resetting SQL Server database...")
        
        # Drop tables in correct order (due to foreign keys)
        tables = ['guide_parts', 'technical_guides', 'parts']
        
        for table in tables:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                logger.info(f"✅ Dropped table: {table}")
            except Exception as e:
                logger.warning(f"Could not drop {table}: {e}")
        
        conn.commit()
        conn.close()
        logger.info("✅ SQL Server database reset successfully")
        
    except Exception as e:
        logger.error(f"❌ Error resetting database: {e}")

if __name__ == "__main__":
    reset_mssql_database()# scripts/reset_mssql.py
import sys
from pathlib import Path

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
app_root = project_root.parent
sys.path.insert(0, str(app_root))
sys.path.insert(0, str(project_root))

from app.utils.config import settings
from app.utils.logger import setup_logging

logger = setup_logging()

def reset_mssql_database():
    """Reset SQL Server database by dropping and recreating tables"""
    try:
        import pyodbc
        conn = pyodbc.connect(settings.MSSQL_CONNECTION_STRING)
        cursor = conn.cursor()
        
        logger.info("🔄 Resetting SQL Server database...")
        
        # Drop tables in correct order (due to foreign keys)
        tables = ['guide_parts', 'technical_guides', 'parts']
        
        for table in tables:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                logger.info(f"✅ Dropped table: {table}")
            except Exception as e:
                logger.warning(f"Could not drop {table}: {e}")
        
        conn.commit()
        conn.close()
        logger.info("✅ SQL Server database reset successfully")
        
    except Exception as e:
        logger.error(f"❌ Error resetting database: {e}")

if __name__ == "__main__":
    reset_mssql_database()