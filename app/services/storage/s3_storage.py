import boto3
from botocore.exceptions import ClientError
from typing import Optional, List
from app.utils.config import settings
from app.utils.logger import setup_logging

logger = setup_logging()

class S3Storage:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION,
            endpoint_url=settings.AWS_S3_ENDPOINT
        )
        self.bucket_name = settings.AWS_S3_BUCKET
    
    def upload_file(self, file_path: str, s3_key: str) -> bool:
        """Upload file to S3"""
        try:
            self.s3_client.upload_file(file_path, self.bucket_name, s3_key)
            logger.info(f"Uploaded {file_path} to S3 as {s3_key}")
            return True
        except ClientError as e:
            logger.error(f"Error uploading to S3: {e}")
            return False
    
    def download_file(self, s3_key: str, local_path: str) -> bool:
        """Download file from S3"""
        try:
            self.s3_client.download_file(self.bucket_name, s3_key, local_path)
            logger.info(f"Downloaded {s3_key} from S3 to {local_path}")
            return True
        except ClientError as e:
            logger.error(f"Error downloading from S3: {e}")
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