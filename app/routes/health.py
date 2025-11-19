from fastapi import APIRouter

# Import from app modules
from app.services.db.queries import DatabaseManager
from app.utils.logger import setup_logging

logger = setup_logging()
router = APIRouter()
db_manager = DatabaseManager()

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        conn = db_manager.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        conn.close()
        
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": "2024-01-01T00:00:00Z"  # Add actual timestamp
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }

@router.get("/status")
async def status():
    """Detailed system status"""
    try:
        conn = db_manager.get_connection()
        cur = conn.cursor()
        
        # Get counts
        cur.execute("SELECT COUNT(*) FROM parts")
        part_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM technical_guides WHERE is_active = 1")
        guide_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(DISTINCT catalog_name) FROM parts")
        catalog_count = cur.fetchone()[0]
        
        conn.close()
        
        return {
            "parts": part_count,
            "guides": guide_count,
            "catalogs": catalog_count,
            "status": "operational"
        }
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }
@router.get("/")
async def health_check():
    return {
        "status": "healthy", 
        "service": "parts-catalog",
        "timestamp": datetime.utcnow().isoformat()
    }