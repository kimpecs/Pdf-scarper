# run_server.py
import subprocess
import time
import sys
import os

def main():
    print("=== Hydraulic Brakes Catalog Server ===")
    
    # Check if database exists
    if not os.path.exists("catalog.db"):
        print("❌ Database not found. Please run extraction first.")
        print("Run: python extract_pdf_toc_fixed.py Dayton_Hydraulic_Brakes.pdf --skip-images")
        return
    
    # Start the server
    print("Starting server...")
    try:
        subprocess.run([sys.executable, "app_toc.py"])
    except KeyboardInterrupt:
        print("\nServer stopped.")
    except Exception as e:
        print(f"Error starting server: {e}")

if __name__ == "__main__":
    main()