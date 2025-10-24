import shutil
from pathlib import Path
from typing import Optional
from app.utils.config import settings
from app.utils.logger import setup_logging

logger = setup_logging()

class LocalStorage:
    def __init__(self):
        self.data_dir = settings.DATA_DIR
    
    def save_file(self, source_path: Path, target_filename: str) -> Optional[Path]:
        """Save file to local storage"""
        try:
            target_path = self.data_dir / target_filename
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
            logger.info(f"Saved file: {target_path}")
            return target_path
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            return None
    
    def get_file_url(self, filename: str) -> Optional[str]:
        """Get URL for local file"""
        file_path = self.data_dir / filename
        if file_path.exists():
            return f"/{filename}"
        return None
    
    def list_files(self, directory: str = "") -> List[Path]:
        """List files in directory"""
        dir_path = self.data_dir / directory
        if dir_path.exists():
            return list(dir_path.iterdir())
        return []