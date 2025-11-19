# s3_storage.py
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Optional, List
from app.utils.config import settings
from app.utils.logger import setup_logging
import os

logger = setup_logging()

class S3Storage:
    def __init__(self):
        # Enhanced config validation with better error messages
        config_errors = []
        
        if not settings.AWS_ACCESS_KEY_ID:
            config_errors.append("AWS_ACCESS_KEY_ID is not set")
        if not settings.AWS_SECRET_ACCESS_KEY:
            config_errors.append("AWS_SECRET_ACCESS_KEY is not set") 
        if not settings.AWS_S3_BUCKET:
            config_errors.append("AWS_S3_BUCKET is not set")
            
        if config_errors:
            error_msg = f"S3 configuration errors: {', '.join(config_errors)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION,
                endpoint_url=settings.AWS_S3_ENDPOINT
            )
            self.bucket_name = settings.AWS_S3_BUCKET
            
            # REMOVED: Don't test connection automatically during init
            # This causes import failures if there are permission issues
            # self._test_connection()
            
        except NoCredentialsError:
            logger.error("No AWS credentials found")
            raise
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"AWS ClientError during initialization: {error_code} - {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during S3 initialization: {e}")
            raise
    
    def test_connection(self) -> bool:
        """Test S3 connection and bucket access - call this manually"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"✅ S3 connection successful. Bucket '{self.bucket_name}' is accessible")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.error(f"Bucket '{self.bucket_name}' not found")
            elif error_code == '403':
                logger.error(f"Access denied to bucket '{self.bucket_name}'. Check permissions.")
            else:
                logger.error(f"S3 connection test failed: {error_code} - {e}")
            return False
    
    # ... rest of your methods remain the same ...
    def upload_file(self, file_path: str, s3_key: str) -> bool:
        """Upload file to S3"""
        try:
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return False
                
            self.s3_client.upload_file(file_path, self.bucket_name, s3_key)
            logger.info(f"Uploaded {file_path} to S3 as {s3_key}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"AWS Error uploading {file_path}: {error_code} - {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error uploading {file_path}: {e}")
            return False
    
    def generate_presigned_url(self, s3_key: str, expiration: int = 3600) -> Optional[str]:
        """Generate presigned URL for S3 object"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            logger.error(f"Error generating presigned URL: {e}")
            return None
    
    def list_objects(self, prefix: str = "") -> List[str]:
        """List objects in S3 bucket"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            if 'Contents' in response:
                return [obj['Key'] for obj in response['Contents']]
            return []
        except ClientError as e:
            logger.error(f"Error listing S3 objects: {e}")
            return []
    
    def delete_object(self, s3_key: str) -> bool:
        """Delete object from S3"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"Deleted {s3_key} from S3")
            return True
        except ClientError as e:
            logger.error(f"Error deleting object from S3: {e}")
            return False
    
    def object_exists(self, s3_key: str) -> bool:
        """Check if object exists in S3"""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError:
            return False