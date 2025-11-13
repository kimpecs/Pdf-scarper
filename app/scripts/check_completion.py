#!/usr/bin/env python3
"""
Check system completion status
"""

'''
import sqlite3
from pathlib import Path

def check_database():
    """Check if database is populated"""
    db_path = Path("catalog.db")
    if not db_path.exists():
        print("[ERROR] Database file not found")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        
        # Check parts table
        cur.execute("SELECT COUNT(*) FROM parts")
        part_count = cur.fetchone()[0]
        
        # Check guides table if exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='technical_guides'")
        has_guides = cur.fetchone() is not None
        
        conn.close()
        
        print(f"[INFO] Parts in database: {part_count}")
        print(f"[INFO] Guides table exists: {has_guides}")
        
        return part_count > 0
        
    except Exception as e:
        print(f"[ERROR] Database check failed: {e}")
        return False

def check_pdfs():
    """Check if PDF directories exist"""
    pdf_dirs = [
        Path("app/data/pdfs"),
        Path("app/data/guides")
    ]
    
    all_exist = True
    for pdf_dir in pdf_dirs:
        if pdf_dir.exists():
            pdf_count = len(list(pdf_dir.glob("*.pdf")))
            print(f"[INFO] PDFs in {pdf_dir}: {pdf_count}")
        else:
            print(f"[WARNING] Directory not found: {pdf_dir}")
            all_exist = False
    
    return all_exist

def main():
    """Run completion checks"""
    print("[CHECK] Running system completion check...")
    
    db_ok = check_database()
    pdfs_ok = check_pdfs()
    
    if db_ok and pdfs_ok:
        print("[SUCCESS] System check completed successfully")
        return True
    else:
        print("[WARNING] System check completed with issues")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) '''
    
"""
Check S3 configuration
"""
'''
import os
from pathlib import Path
import sys

# Add the app directory to Python path
script_dir = Path(__file__).parent
app_dir = script_dir.parent.parent
sys.path.insert(0, str(app_dir))

from app.utils.config import settings

def check_config():
    print("🔍 Checking S3 Configuration:")
    print(f"USE_S3_STORAGE: {settings.USE_S3_STORAGE}")
    print(f"AWS_ACCESS_KEY_ID: {'*' * 8}{settings.AWS_ACCESS_KEY_ID[-4:] if settings.AWS_ACCESS_KEY_ID else 'NOT SET'}")
    print(f"AWS_SECRET_ACCESS_KEY: {'*' * 8}{settings.AWS_SECRET_ACCESS_KEY[-4:] if settings.AWS_SECRET_ACCESS_KEY else 'NOT SET'}")
    print(f"AWS_S3_REGION: {settings.AWS_S3_REGION}")
    print(f"AWS_S3_BUCKET: {settings.AWS_S3_BUCKET}")
    print(f"AWS_S3_ENDPOINT: {settings.AWS_S3_ENDPOINT}")
    
    # Check if required values are set
    missing = []
    if not settings.AWS_ACCESS_KEY_ID:
        missing.append("AWS_ACCESS_KEY_ID")
    if not settings.AWS_SECRET_ACCESS_KEY:
        missing.append("AWS_SECRET_ACCESS_KEY")
    if not settings.AWS_S3_BUCKET:
        missing.append("AWS_S3_BUCKET")
    
    if missing:
        print(f"❌ Missing required configuration: {', '.join(missing)}")
    else:
        print("✅ All required configuration present")

if __name__ == "__main__":
    check_config() '''
    
"""
Debug AWS credentials
"""
import os
import boto3
from botocore.exceptions import ClientError

def test_credentials_directly():
    print("🔧 Testing AWS credentials directly...")
    
    # Get credentials from environment
    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    region = os.getenv('AWS_S3_REGION', 'us-east-1')
    bucket = os.getenv('AWS_S3_BUCKET')
    
    print(f"Access Key: {'*' * 8}{access_key[-4:] if access_key else 'NOT SET'}")
    print(f"Secret Key: {'*' * 8}{secret_key[-4:] if secret_key else 'NOT SET'}")
    print(f"Region: {region}")
    print(f"Bucket: {bucket}")
    
    if not all([access_key, secret_key, bucket]):
        print("❌ Missing one or more required environment variables")
        return False
    
    try:
        # Test with boto3 directly
        s3_client = boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        
        # Try to list buckets (this validates credentials)
        response = s3_client.list_buckets()
        print(f"✅ Credentials valid! Access to {len(response['Buckets'])} buckets")
        
        # Check if our target bucket exists
        buckets = [b['Name'] for b in response['Buckets']]
        if bucket in buckets:
            print(f"✅ Bucket '{bucket}' exists and accessible")
            return True
        else:
            print(f"❌ Bucket '{bucket}' not found. Available buckets: {buckets}")
            return False
            
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        print(f"❌ AWS Error: {error_code} - {error_message}")
        
        if error_code == 'InvalidAccessKeyId':
            print("💡 The Access Key ID is invalid")
        elif error_code == 'SignatureDoesNotMatch':
            print("💡 The Secret Access Key is invalid") 
        elif error_code == 'AccessDenied':
            print("💡 Credentials are valid but don't have S3 access")
        
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    test_credentials_directly()   
    
  