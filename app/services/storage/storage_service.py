import os
import json
import tempfile
from typing import Optional, List, BinaryIO
from pathlib import Path
from app.services.storage.local_storage import LocalStorage
from app.services.storage.s3_storage import S3Storage
from app.utils.config import settings
from app.utils.logger import setup_logging

logger = setup_logging()

class StorageService:
    def __init__(self):
        self.local = LocalStorage()
        self.s3 = S3Storage()
        self.use_s3 = settings.USE_S3_STORAGE
    
    async def upload_pdf(self, file_path: str, category: str = "catalogs") -> Optional[str]:
        """Upload PDF to storage (local or S3)"""
        try:
            filename = os.path.basename(file_path)
            
            if self.use_s3:
                s3_key = f"pdfs/{category}/{filename}"
                success = self.s3.upload_file(file_path, s3_key)
                if success:
                    logger.info(f"Uploaded {filename} to S3 as {s3_key}")
                    return s3_key
            else:
                
                local_path = self.local.save_file(Path(file_path), f"pdfs/{category}/{filename}")
                if local_path:
                    logger.info(f"Saved {filename} to local storage")
                    return f"pdfs/{category}/{filename}"
            
            return None
                
        except Exception as e:
            logger.error(f"Error uploading PDF: {e}")
            return None
    
    async def upload_image(self, image_path: str, pdf_filename: str = None, page_number: int = None) -> Optional[str]:
        """Upload image to storage"""
        try:
            filename = os.path.basename(image_path)
            
            if self.use_s3:
                
                if pdf_filename:
                    pdf_name = os.path.splitext(pdf_filename)[0]
                    if page_number is not None:
                        s3_key = f"page_images/{pdf_name}/page_{page_number:03d}_{filename}"
                    else:
                        s3_key = f"page_images/{pdf_name}/{filename}"
                else:
                    s3_key = f"page_images/{filename}"
                
                success = self.s3.upload_file(image_path, s3_key)
                if success:
                    logger.info(f"Uploaded image {filename} to S3 as {s3_key}")
                    return s3_key
            else:
                # Local storage
                if pdf_filename:
                    pdf_name = os.path.splitext(pdf_filename)[0]
                    local_filename = f"page_images/{pdf_name}/{filename}"
                else:
                    local_filename = f"page_images/{filename}"
                    
                local_path = self.local.save_file(Path(image_path), local_filename)
                if local_path:
                    return local_filename
            
            return None
                
        except Exception as e:
            logger.error(f"Error uploading image: {e}")
            return None
    
    def get_pdf_url(self, file_key: str) -> Optional[str]:
        """Get PDF URL from storage"""
        if self.use_s3 and file_key.startswith('pdfs/'):
            return self.s3.generate_presigned_url(file_key)
        else:
            return self.local.get_file_url(file_key)
    
    def get_image_url(self, image_key: str) -> Optional[str]:
        """Get image URL from storage"""
        if self.use_s3 and image_key.startswith('page_images/'):
            return self.s3.generate_presigned_url(image_key)
        else:
            return self.local.get_file_url(image_key)
    
    def upload_processed_data(self, data: dict, filename: str) -> bool:
        """Upload processed data to storage"""
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, delete_on_close=False) as f:
                json.dump(data, f, indent=2)
                temp_path = f.name
            
            if self.use_s3:
                s3_key = f"processed_data/{filename}"
                success = self.s3.upload_file(temp_path, s3_key)
            else:
                local_path = self.local.save_file(Path(temp_path), f"data/{filename}")
                success = local_path is not None
            
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except:
                pass
            
            return success
            
        except Exception as e:
            logger.error(f"Error uploading processed data: {e}")
            return False
    
    def file_exists(self, file_key: str) -> bool:
        """Check if file exists in storage"""
        if self.use_s3 and file_key.startswith(('pdfs/', 'page_images/', 'processed_data/')):
            return self.s3.object_exists(file_key)
        else:
            return self.local.file_exists(file_key)
    
    def delete_file(self, file_key: str) -> bool:
        """Delete file from storage"""
        if self.use_s3 and file_key.startswith(('pdfs/', 'page_images/', 'processed_data/')):
            return self.s3.delete_object(file_key)
        else:
            return self.local.delete_file(file_key)