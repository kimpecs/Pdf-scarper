from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

# Import routes
from app.routes import parts, guides, health
from app.utils.config import settings
from app.utils.logger import setup_logging

# Setup logging
logger = setup_logging()

app = FastAPI(
    title="Knowledge Base API",
    description="Hydraulic Brakes Catalog and Technical Guides",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create data directories BEFORE mounting
data_dir = Path(__file__).parent / "data"
static_dir = Path(__file__).parent / "static"

# Ensure directories exist before mounting
data_dir.mkdir(exist_ok=True)
(data_dir / "pdfs").mkdir(exist_ok=True)
(data_dir / "page_images").mkdir(exist_ok=True)
(data_dir / "guides").mkdir(exist_ok=True)
static_dir.mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Mount data directories
app.mount("/pdfs", StaticFiles(directory=data_dir / "pdfs"), name="pdfs")
app.mount("/images", StaticFiles(directory=data_dir / "page_images"), name="images")
app.mount("/guides", StaticFiles(directory=data_dir / "guides"), name="guides")

# Include routers
app.include_router(parts.router, prefix="/api/v1", tags=["parts"])
app.include_router(guides.router, prefix="/api/v1", tags=["guides"])
app.include_router(health.router, prefix="/api/v1", tags=["health"])

@app.on_event("startup")
async def startup_event():
    logger.info("Starting Knowledge Base API")
    logger.info("Data directories are ready")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)