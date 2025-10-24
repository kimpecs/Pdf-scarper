from pathlib import Path
from typing import Optional
from .config import settings

def get_pdf_url(pdf_path: str, page: int) -> Optional[str]:
    """Generate proper PDF URL with page anchor"""
    if not pdf_path:
        return None
    
    pdf_path = Path(pdf_path)
    pdf_filename = pdf_path.name
    return f"/pdfs/{pdf_filename}#page={page}"

def ensure_directory(path: Path):
    """Ensure directory exists"""
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_static_path(filename: str) -> Path:
    """Get path to static file"""
    return settings.STATIC_DIR / filename

def get_data_path(*subpaths: str) -> Path:
    """Get path in data directory"""
    return settings.DATA_DIR.joinpath(*subpaths)