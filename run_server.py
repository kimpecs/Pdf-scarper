#!/usr/bin/env python3
"""
Unified launcher for the FastAPI Knowledge Base server
Ensures all directories exist, initializes the database,
and launches Uvicorn.
"""
import uvicorn
import sys
from pathlib import Path

def ensure_directories():
    """Ensure all required directories exist before starting the server"""
    project_root = Path(__file__).parent
    app_dir = project_root / "app"
    data_dir = app_dir / "data"
    static_dir = app_dir / "static"
    templates_dir = app_dir / "templates"

    # List of required directories
    directories = [
        data_dir,
        data_dir / "pdfs",
        data_dir / "page_images",
        data_dir / "guides",
        static_dir,
        templates_dir
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"[OK] Ensured directory exists: {directory}")

def main():
    """Main entrypoint for the FastAPI application"""
    try:
        # Step 1 — Ensure required directories
        ensure_directories()

        # Step 2 — Import after directories exist
        from app.main import app
        from app.utils.config import settings

        # Step 3 — Display startup diagnostics
        print("\n Starting Knowledge Base API server")
        print("────────────────────────────────────────────")
        print(f"Frontend URL:        http://localhost:8000")
        print(f"API Docs:            http://localhost:8000/docs")
        print(f"Static Directory:    {settings.STATIC_DIR}")
        print(f"Templates Directory: {settings.TEMPLATES_DIR}")
        print("────────────────────────────────────────────")
        print("Press Ctrl+C to stop the server\n")

        # Step 4 — Start Uvicorn
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=False,
            log_level="info"
        )

    except ImportError as e:
        print(f"[ERROR] Import error: {e}")
        print("Hint: Run this script from your project root (where 'app/' resides).")
        sys.exit(1)

    except Exception as e:
        print(f"[ERROR] Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()