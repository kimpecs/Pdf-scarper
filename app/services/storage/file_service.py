import os
import json
import tempfile
from typing import Optional, Dict, Any
from pathlib import Path
from app.services.storage.s3_storage import S3Storage
from app.utils.logger import setup_logging

logger = setup_logging()

class FileService:
    def __init__(self):
        self.s3 = S3Storage()  
    
    async def upload_pdf_to_s3(self, local_pdf_path: str, category: str) -> Optional[str]:
        """Upload PDF to S3 and return S3 key"""
        try:
            filename = os.path.basename(local_pdf_path)
            s3_key = f"pdfs/{category}/{filename}" 
            
            success = self.s3.upload_file(local_pdf_path, s3_key)
            if success:
                logger.info(f"Successfully uploaded {filename} to S3 as {s3_key}")
                return s3_key
            else:
                logger.error(f"Failed to upload {filename} to S3")
                return None
                
        except Exception as e:
            logger.error(f"Error in upload_pdf_to_s3: {e}")
            return None
    
    async def upload_image_to_s3(self, local_image_path: str, pdf_filename: str, page_number: int = None) -> Optional[str]:
        """Upload image to S3 and return S3 key"""
        try:
            filename = os.path.basename(local_image_path)
            pdf_name = os.path.splitext(pdf_filename)[0]
            
            if page_number is not None:
                s3_key = f"page_images/{pdf_name}/page_{page_number:03d}_{filename}"
            else:
                s3_key = f"page_images/{pdf_name}/{filename}"
            
            success = self.s3.upload_file(local_image_path, s3_key)
            if success:
                logger.info(f"Successfully uploaded image {filename} to S3 as {s3_key}")
                return s3_key
            else:
                logger.error(f"Failed to upload image {filename} to S3")
                return None
                
        except Exception as e:
            logger.error(f"Error in upload_image_to_s3: {e}")
            return None
    
    def get_pdf_url(self, s3_key: str) -> Optional[str]:
        """Generate presigned URL for PDF"""
        return self.s3.generate_presigned_url(s3_key)
    
    def get_image_url(self, s3_key: str) -> Optional[str]:
        """Generate presigned URL for image"""
        return self.s3.generate_presigned_url(s3_key)
    
    def upload_processed_data(self, data: dict, filename: str) -> bool:
        """Upload processed data (JSON) to S3"""
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, delete_on_close=False) as f:
                json.dump(data, f, indent=2)
                temp_path = f.name
            
            s3_key = f"processed_data/{filename}"
            success = self.s3.upload_file(temp_path, s3_key)
            
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except:
                pass
            
            return success
            
        except Exception as e:
            logger.error(f"Error uploading processed data: {e}")
            return False