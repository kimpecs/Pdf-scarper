from pdf2image import convert_from_path
from pathlib import Path
from typing import List, Optional
from app.utils.config import settings
from app.utils.logger import setup_logging

logger = setup_logging()

class PDFImageConverter:
    def __init__(self, poppler_path: Optional[str] = None):
        self.poppler_path = poppler_path
    
    def convert_to_images(self, pdf_path: Path, dpi: int = None, 
                         first_page: int = 1, last_page: int = None) -> List[Path]:
        """Convert PDF pages to images"""
        if dpi is None:
            dpi = settings.IMAGE_DPI
        
        try:
            images = convert_from_path(
                str(pdf_path),
                dpi=dpi,
                first_page=first_page,
                last_page=last_page,
                poppler_path=self.poppler_path
            )
            
            output_paths = []
            images_dir = settings.DATA_DIR / "page_images"
            images_dir.mkdir(exist_ok=True)
            
            for i, image in enumerate(images):
                page_num = first_page + i
                output_path = images_dir / f"{pdf_path.stem}_page_{page_num:04d}.png"
                image.save(output_path, "PNG")
                output_paths.append(output_path)
            
            logger.info(f"Converted {len(images)} pages to images")
            return output_paths
            
        except Exception as e:
            logger.error(f"Image conversion failed: {e}")
            return []