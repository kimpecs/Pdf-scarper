"""
Test S3 upload functionality
"""
import os
import sys
from pathlib import Path

# Add the app directory to Python path
script_dir = Path(__file__).parent
app_dir = script_dir.parent.parent
sys.path.insert(0, str(app_dir))

from app.services.storage.s3_storage import S3Storage
from app.services.storage.storage_service import StorageService
from app.utils.logger import setup_logging

logger = setup_logging()

def test_s3_connection():
    """Test basic S3 connection"""
    try:
        s3 = S3Storage()
        print("✅ S3 Storage initialized successfully")
        
        # Test bucket access by listing objects
        objects = s3.list_objects(prefix="")
        print(f"✅ S3 bucket accessible. Found {len(objects)} objects")
        return True
        
    except Exception as e:
        print(f"❌ S3 connection failed: {e}")
        return False

async def test_pdf_upload():
    """Test PDF upload to S3"""
    try:
        storage_service = StorageService()
        
        # Create a test file
        test_pdf_path = Path("test_upload.pdf")
        with open(test_pdf_path, 'w') as f:
            f.write("This is a test PDF content")
        
        # Upload test file
        s3_key = await storage_service.upload_pdf(str(test_pdf_path), "test")
        
        if s3_key:
            print(f"✅ PDF upload successful: {s3_key}")
            
            # Test URL generation
            url = storage_service.get_pdf_url(s3_key)
            print(f"✅ Presigned URL: {url}")
            
            # Clean up test file
            test_pdf_path.unlink()
            return True
        else:
            print("❌ PDF upload failed")
            return False
            
    except Exception as e:
        print(f"❌ PDF upload test failed: {e}")
        return False

async def test_image_upload():
    """Test image upload to S3"""
    try:
        storage_service = StorageService()
        
        # Create a test image file
        test_image_path = Path("test_image.png")
        with open(test_image_path, 'w') as f:
            f.write("Fake image content")
        
        # Upload test image
        s3_key = await storage_service.upload_image(
            str(test_image_path), 
            pdf_filename="test_catalog.pdf", 
            page_number=1
        )
        
        if s3_key:
            print(f"✅ Image upload successful: {s3_key}")
            
            # Test URL generation
            url = storage_service.get_image_url(s3_key)
            print(f"✅ Image URL: {url}")
            
            # Clean up
            test_image_path.unlink()
            return True
        else:
            print("❌ Image upload failed")
            return False
            
    except Exception as e:
        print(f"❌ Image upload test failed: {e}")
        return False

async def main():
    print("🧪 Testing S3 Upload Functionality...")
    
    # Test 1: S3 Connection
    print("\n1. Testing S3 Connection...")
    connection_ok = test_s3_connection()
    
    if connection_ok:
        # Test 2: PDF Upload
        print("\n2. Testing PDF Upload...")
        pdf_ok = await test_pdf_upload()
        
        # Test 3: Image Upload  
        print("\n3. Testing Image Upload...")
        image_ok = await test_image_upload()
        
        if pdf_ok and image_ok:
            print("\n🎉 All tests passed! S3 upload is working correctly.")
        else:
            print("\n⚠️ Some tests failed. Check the errors above.")
    else:
        print("\n❌ S3 connection failed. Check your credentials and configuration.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())