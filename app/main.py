from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path

# Internal imports
from app.utils.config import settings
from app.utils.logger import setup_logging
from app.routes import parts, guides, health

# ------------------------------------------------------------------------------
# [OK] Initialize FastAPI app
# ------------------------------------------------------------------------------
app = FastAPI(
    title=settings.FRONTEND_TITLE,
    description=settings.FRONTEND_DESCRIPTION,
    version="1.0.0"
)

# ------------------------------------------------------------------------------
# [OK] Setup logging and CORS
# ------------------------------------------------------------------------------
logger = setup_logging()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------------------
# [OK] Define base paths and ensure directories exist
# ------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = settings.TEMPLATES_DIR  # ensure this points to app/templates

for folder in [DATA_DIR, STATIC_DIR, DATA_DIR / "pdfs", DATA_DIR / "page_images", DATA_DIR / "guides"]:
    folder.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------------------
# [OK] Mount static and data directories
# ------------------------------------------------------------------------------
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/pdfs", StaticFiles(directory=DATA_DIR / "pdfs"), name="pdfs")
app.mount("/images", StaticFiles(directory=DATA_DIR / "page_images"), name="images")
app.mount("/guides", StaticFiles(directory=DATA_DIR / "guides"), name="guides")

# ------------------------------------------------------------------------------
# [OK] Template configuration (for base.html + index.html via Jinja2)
# ------------------------------------------------------------------------------
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# ------------------------------------------------------------------------------
# [OK] Include routers
# ------------------------------------------------------------------------------
app.include_router(guides.router, prefix="/api/guides", tags=["guides"])
app.include_router(parts.router, prefix="/api/parts", tags=["parts"])
app.include_router(health.router, prefix="/api/health", tags=["health"])

# ------------------------------------------------------------------------------
# [OK] Frontend serving routes
# ------------------------------------------------------------------------------
@app.get("/")
async def serve_frontend():
    """Serve main SPA index file."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        logger.error(f"Index file not found at {index_path}")
        return {"error": "Frontend not built or missing index.html"}
    return FileResponse(index_path)


@app.get("/search")
async def serve_search():
    """Allow direct URL access to /search (SPA route)."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/guides/{path:path}")
async def serve_guide_routes(path: str):
    """SPA catch-all for guide routes."""
    return FileResponse(STATIC_DIR / "index.html")


# ------------------------------------------------------------------------------
# [OK] Startup event logging
# ------------------------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    logger.info(" Knowledge Base API starting...")
    logger.info(f"Static directory: {STATIC_DIR}")
    logger.info(f"Templates directory: {TEMPLATES_DIR}")
    logger.info("Data directories ready and mounted successfully.")

# ------------------------------------------------------------------------------
# [OK] Local development entrypoint
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
