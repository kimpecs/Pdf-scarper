from .local_storage import LocalStorage
from .s3_storage import S3Storage
from .file_service import FileService
from .storage_service import StorageService

# Create storage instances
local_storage = LocalStorage()
s3_storage = S3Storage()
file_service = FileService()
storage_service = StorageService()

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