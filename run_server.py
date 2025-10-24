#!/usr/bin/env python3
"""
Quick start script for the FastAPI server
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
    
    # Create directories
    directories = [
        data_dir,
        data_dir / "pdfs", 
        data_dir / "page_images",
        data_dir / "guides",
        static_dir
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"Ensured directory exists: {directory}")

def main():
    """Main function to start the server"""
    try:
        # Ensure directories exist first
        ensure_directories()
        
        # Import after creating directories
        from app.main import app
        from app.services.db.setup import init_database
        
        # Initialize database
        print("Initializing database...")
        init_database()
        
        # Start server
        print("Starting FastAPI server on http://0.0.0.0:8000")
        print("API documentation: http://localhost:8000/docs")
        print("Press Ctrl+C to stop the server")
        
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
        
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure you're running from the project root directory")
    except Exception as e:
        print(f"Error starting server: {e}")

if __name__ == "__main__":
    main()