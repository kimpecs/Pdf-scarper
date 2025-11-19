# check_storage_mode.py
from app.utils.config import settings

print("🔍 Checking Storage Configuration")
print("=" * 35)
print(f"USE_S3_STORAGE: {settings.USE_S3_STORAGE}")
print(f"DATA_DIR: {settings.DATA_DIR}")

if settings.USE_S3_STORAGE:
    print("🎯 Storage Mode: S3 (DigitalOcean Spaces)")
else:
    print("🎯 Storage Mode: LOCAL FILESYSTEM")
    print(f"📁 Files will be stored in: {settings.DATA_DIR}")

# Check if data directory exists
if not settings.DATA_DIR.exists():
    print("⚠️ Data directory doesn't exist, but will be created automatically")
else:
    print(f"✅ Data directory exists: {settings.DATA_DIR}")