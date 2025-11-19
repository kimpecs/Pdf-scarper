# services/storage/__init__.py
from .local_storage import LocalStorage
from .file_service import FileService
from .storage_service import StorageService
from app.utils.config import settings

# Create storage instances
local_storage = LocalStorage()
file_service = FileService()
storage_service = StorageService()

# Only initialize S3 if it's enabled
s3_storage = None
if settings.USE_S3_STORAGE:
    try:
        from .s3_storage import S3Storage
        s3_storage = S3Storage()
    except Exception as e:
        print(f"⚠️ S3 storage disabled: {e}")
        s3_storage = None

__all__ = [
    'LocalStorage', 
    'S3Storage', 
    'FileService', 
    'StorageService',
    'local_storage', 
    's3_storage',
    'file_service',
    'storage_service'
]