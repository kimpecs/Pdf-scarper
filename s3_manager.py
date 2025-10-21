# s3_manager.py
import os
import logging
from config import Config

class S3Manager:
    def __init__(self):
        self.config = Config()
        self.use_s3 = self.config.has_aws_credentials()
        
        if self.use_s3:
            import boto3
            from botocore.exceptions import ClientError
            self.boto3 = boto3
            self.ClientError = ClientError
            
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.config.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=self.config.AWS_SECRET_ACCESS_KEY,
                region_name=self.config.AWS_REGION
            )
            self.bucket_name = self.config.S3_BUCKET_NAME
        else:
            logging.warning("AWS credentials not found. Using local storage only.")
    
    def create_bucket_if_not_exists(self):
        """Create S3 bucket if it doesn't exist (or ensure local directories)"""
        if self.use_s3:
            try:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
                logging.info(f"Bucket {self.bucket_name} already exists")
                return True
            except self.ClientError:
                try:
                    if self.config.AWS_REGION == 'us-east-1':
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={
                                'LocationConstraint': self.config.AWS_REGION
                            }
                        )
                    logging.info(f"Created bucket {self.bucket_name}")
                    return True
                except self.ClientError as e:
                    logging.error(f"Error creating bucket: {e}")
                    return False
        else:
            # Ensure local directories exist
            os.makedirs(self.config.GUIDES_DIR, exist_ok=True)
            logging.info("Using local storage for technical guides")
            return True
    
    def upload_technical_guide(self, guide_name, file_path, guide_type="template"):
        """Upload a technical guide to S3 or copy to local storage"""
        if self.use_s3:
            try:
                s3_key = f"technical_guides/{guide_type}/{guide_name}.pdf"
                self.s3_client.upload_file(file_path, self.bucket_name, s3_key)
                logging.info(f"Uploaded technical guide {guide_name} to S3")
                return s3_key
            except self.ClientError as e:
                logging.error(f"Error uploading technical guide: {e}")
                return None
        else:
            # Copy to local guides directory
            local_path = os.path.join(self.config.GUIDES_DIR, f"{guide_name}.pdf")
            import shutil
            shutil.copy2(file_path, local_path)
            logging.info(f"Copied technical guide {guide_name} to local storage")
            return local_path
    
    def download_technical_guide(self, guide_name, local_path, guide_type="template"):
        """Download a technical guide from S3 or use local file"""
        if self.use_s3:
            try:
                s3_key = f"technical_guides/{guide_type}/{guide_name}.pdf"
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                self.s3_client.download_file(self.bucket_name, s3_key, local_path)
                logging.info(f"Downloaded technical guide {guide_name} from S3")
                return local_path
            except self.ClientError as e:
                logging.error(f"Error downloading technical guide: {e}")
                return None
        else:
            # Use local file
            local_source = os.path.join(self.config.GUIDES_DIR, f"{guide_name}.pdf")
            if os.path.exists(local_source):
                import shutil
                shutil.copy2(local_source, local_path)
                logging.info(f"Copied technical guide {guide_name} from local storage")
                return local_path
            else:
                logging.error(f"Technical guide {guide_name} not found in local storage")
                return None
    
    def list_technical_guides(self, guide_type="template"):
        """List all available technical guides"""
        if self.use_s3:
            try:
                response = self.s3_client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix=f"technical_guides/{guide_type}/"
                )
                
                guides = []
                if 'Contents' in response:
                    for obj in response['Contents']:
                        if obj['Key'].endswith('.pdf'):
                            guide_name = obj['Key'].split('/')[-1].replace('.pdf', '')
                            guides.append({
                                'name': guide_name,
                                'key': obj['Key'],
                                'size': obj['Size'],
                                'last_modified': obj['LastModified']
                            })
                return guides
            except self.ClientError as e:
                logging.error(f"Error listing technical guides: {e}")
                return []
        else:
            # List local files
            guides = []
            if os.path.exists(self.config.GUIDES_DIR):
                for file in os.listdir(self.config.GUIDES_DIR):
                    if file.endswith('.pdf'):
                        full_path = os.path.join(self.config.GUIDES_DIR, file)
                        guide_name = file.replace('.pdf', '')
                        guides.append({
                            'name': guide_name,
                            'key': full_path,
                            'size': os.path.getsize(full_path),
                            'last_modified': os.path.getmtime(full_path)
                        })
            return guides