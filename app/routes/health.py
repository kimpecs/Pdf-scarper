from datetime import datetime, timezone

from fastapi import APIRouter

from app.services.db.queries import DatabaseManager
from app.utils.logger import setup_logging

logger = setup_logging()
router = APIRouter()
db_manager = DatabaseManager()


@router.get("/health")
async def health_check():
    """Basic health check — confirms the service and database are reachable."""
    if db_manager.ping():
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    return {
        "status": "unhealthy",
        "database": "disconnected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/status")
async def status():
    """Detailed system status with row counts for key tables."""
    try:
        counts = db_manager.get_counts()
        return {**counts, "status": "operational"}
    except Exception as e:
        logger.error("Status check failed: %s", e)
        return {"status": "error", "error": str(e)}
