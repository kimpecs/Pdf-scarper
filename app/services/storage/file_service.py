# file_service.py
import os
import json
import tempfile
from typing import Optional, Dict, Any
from pathlib import Path
from app.utils.config import settings
from app.utils.logger import setup_logging

logger = setup_logging()

class FileService:
    def __init__(self):
        self.use_s3 = settings.USE_S3_STORAGE
        if self.use_s3:
            try:
                from app.services.storage.s3_storage import S3Storage
                self.s3 = S3Storage()
            except Exception as e:
                logger.error(f"Failed to initialize S3: {e}")
                self.use_s3 = False
                self.s3 = None
        else:
            self.s3 = None
        
        # Always initialize local storage
        from app.services.storage.local_storage import LocalStorage
        self.local = LocalStorage()
    
    async def upload_pdf_to_s3(self, local_pdf_path: str, category: str) -> Optional[str]:
        """Upload PDF to storage (S3 if enabled, otherwise local)"""
        try:
            filename = os.path.basename(local_pdf_path)
            
            if self.use_s3 and self.s3:
                s3_key = f"pdfs/{category}/{filename}" 
                success = self.s3.upload_file(local_pdf_path, s3_key)
                if success:
                    logger.info(f"Successfully uploaded {filename} to S3 as {s3_key}")
                    return s3_key
                else:
                    logger.error(f"Failed to upload {filename} to S3")
                    return None
            else:
                # Use local storage
                local_filename = f"pdfs/{category}/{filename}"
                local_path = self.local.save_file(Path(local_pdf_path), local_filename)
                if local_path:
                    logger.info(f"Successfully saved {filename} to local storage")
                    return local_filename
                return None
                
        except Exception as e:
            logger.error(f"Error in upload_pdf_to_s3: {e}")
            return None
    
    async def upload_image_to_s3(self, local_image_path: str, pdf_filename: str, page_number: int = None) -> Optional[str]:
        """Upload image to storage (S3 if enabled, otherwise local)"""
        try:
            filename = os.path.basename(local_image_path)
            pdf_name = os.path.splitext(pdf_filename)[0]
            
            if self.use_s3 and self.s3:
                if page_number is not None:
                    s3_key = f"part_images/{pdf_name}/page_{page_number:03d}_{filename}"
                else:
                    s3_key = f"part_images/{pdf_name}/{filename}"
                
                success = self.s3.upload_file(local_image_path, s3_key)
                if success:
                    logger.info(f"Successfully uploaded image {filename} to S3 as {s3_key}")
                    return s3_key
                else:
                    return None
            else:
                # Use local storage
                if page_number is not None:
                    local_filename = f"part_images/{pdf_name}/page_{page_number:03d}_{filename}"
                else:
                    local_filename = f"part_images/{pdf_name}/{filename}"
                    
                local_path = self.local.save_file(Path(local_image_path), local_filename)
                if local_path:
                    return local_filename
                return None
                
        except Exception as e:
            logger.error(f"Error in upload_image_to_s3: {e}")
            return None
    
    def get_pdf_url(self, file_key: str) -> Optional[str]:
        """Get PDF URL from storage"""
        if self.use_s3 and self.s3 and file_key.startswith('pdfs/'):
            return self.s3.generate_presigned_url(file_key)
        else:
            return self.local.get_file_url(file_key)
    
    def get_image_url(self, image_key: str) -> Optional[str]:
        """Get image URL from storage"""
        if self.use_s3 and self.s3 and image_key.startswith('part_images/'):
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
            
            if self.use_s3 and self.s3:
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