# scripts/migrate_.py
import sys
from pathlib import Path
import time

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
app_root = project_root.parent
sys.path.insert(0, str(app_root))
sys.path.insert(0, str(project_root))

try:
    from app.services.db.migration_service import MSSQLMigrationService
    from app.utils.config import settings
    from app.utils.logger import setup_logging
    print("✅ Successfully imported migration modules!")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

logger = setup_logging()

def main():
    logger.info("🚀 Starting FAST SQL Server Migration...")
    
    sqlite_path = r"C:\Users\kpecco\Desktop\codes\TESTING\app\data\catalog.db"
    mssql_connection_string = getattr(settings, 'MSSQL_CONNECTION_STRING', '')
    
    if not mssql_connection_string:
        logger.error("❌ SQL Server connection string not found")
        return
    
    # Verify SQLite database exists
    if not Path(sqlite_path).exists():
        logger.error(f"❌ SQLite database not found at: {sqlite_path}")
        return
    
    migration_service = MSSQLMigrationService(sqlite_path, mssql_connection_string)
    
    total_start_time = time.time()
    
    try:
        migration_service.run_optimized_migration()
        
        total_duration = time.time() - total_start_time
        
        logger.info(f"🎉 MIGRATION COMPLETED in {total_duration:.2f} seconds!")
        logger.info(f"⏱️ Total time: {total_duration/60:.2f} minutes")
        
    except Exception as e:
        logger.error(f"❌ Migration failed after {time.time() - total_start_time:.2f} seconds: {e}")

if __name__ == "__main__":
    main()