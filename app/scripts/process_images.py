import fitz  # PyMuPDF
import re
import os
import sys
import shutil
from pathlib import Path
from typing import List, Dict, Any
import sqlite3
from datetime import datetime

# EXACT PATH: This script is in app/scripts/
script_dir = Path(__file__).parent  # app/scripts/
app_dir = script_dir.parent         # app/
sys.path.insert(0, str(app_dir))

from services.db.queries import DatabaseManager

class DatabaseImageExtractor:
    def __init__(self):
        self.supported_formats = ['.png', '.jpg', '.jpeg', '.webp']
        self.db_manager = DatabaseManager()
    
    def cleanup_existing_images(self):
        """Clean up any existing image data from database"""
        try:
            conn = self.db_manager.get_connection()
            cur = conn.cursor()
            
            # Clear the part_images table
            cur.execute("DELETE FROM part_images")
            
            # Reset image_path in parts table
            cur.execute("UPDATE parts SET image_path = NULL")
            
            conn.commit()
            conn.close()
            print("✅ Cleared existing image data from database")
            
        except Exception as e:
            print(f"❌ Error cleaning database: {e}")
    
    def create_part_images_table(self):
        """Create the part_images table with BLOB storage"""
        try:
            conn = self.db_manager.get_connection()
            cur = conn.cursor()
            
            # Drop the table if it exists (to recreate with correct structure)
            cur.execute("DROP TABLE IF EXISTS part_images")
            
            # Create the table with BLOB storage for images
            cur.execute("""
                CREATE TABLE part_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    part_id INTEGER NOT NULL,
                    image_filename TEXT NOT NULL,
                    image_data BLOB NOT NULL,  -- Store actual image binary data
                    image_type TEXT,
                    image_width INTEGER,
                    image_height INTEGER,
                    file_size INTEGER,
                    page_number INTEGER,
                    confidence REAL DEFAULT 1.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (part_id) REFERENCES parts (id),
                    UNIQUE(part_id, image_filename)
                )
            """)
            
            # Create indexes
            cur.execute("CREATE INDEX IF NOT EXISTS idx_part_images_part_id ON part_images(part_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_part_images_filename ON part_images(image_filename)")
            
            conn.commit()
            conn.close()
            print("✅ Created part_images table with BLOB storage")
            
        except Exception as e:
            print(f"❌ Error creating part_images table: {e}")
            raise
    
    def extract_images_to_database(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Extract images and store directly in database as BLOB
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            print(f"❌ PDF not found: {pdf_path}")
            return []
        
        results = []
        pdf_name = pdf_path.stem
        
        try:
            doc = fitz.open(pdf_path)
            print(f"📄 Processing PDF: {pdf_path.name}")
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images()
                
                print(f"   📄 Page {page_num + 1}: {len(image_list)} images")
                
                for img_index, img in enumerate(image_list):
                    try:
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)
                        
                        # Only process valid images of reasonable size
                        if (pix.n - pix.alpha < 4 and 
                            pix.width >= 50 and pix.height >= 50 and
                            not self._is_full_page_image(pix, page)):
                            
                            # Convert to PNG format in memory
                            if pix.n - pix.alpha == 3:  # RGB
                                # Save as PNG to memory
                                image_data = pix.tobytes("png")
                            else:  # Convert to RGB first
                                pix_rgb = fitz.Pixmap(fitz.csRGB, pix)
                                image_data = pix_rgb.tobytes("png")
                                pix_rgb = None
                            
                            image_filename = f"{pdf_name}_p{page_num+1}_img{img_index+1}.png"
                            
                            result = {
                                'pdf_name': pdf_name,
                                'page_number': page_num + 1,
                                'image_filename': image_filename,
                                'image_data': image_data,  # Binary image data
                                'image_type': 'png',
                                'image_width': pix.width,
                                'image_height': pix.height,
                                'file_size': len(image_data),
                                'created_at': datetime.now().isoformat()
                            }
                            results.append(result)
                            
                            print(f"     💾 Extracted: {image_filename} ({pix.width}x{pix.height}, {len(image_data):,} bytes)")
                            
                        pix = None  # Free memory
                        
                    except Exception as e:
                        print(f"     ❌ Error processing image {img_index}: {e}")
                        continue
            
            doc.close()
            print(f"✅ Completed {pdf_path.name}: {len(results)} images extracted to database")
            
        except Exception as e:
            print(f"❌ Error processing PDF {pdf_path}: {e}")
        
        return results
    
    def _is_full_page_image(self, pix: fitz.Pixmap, page: fitz.Page) -> bool:
        """Check if image is full page (likely background/cover)"""
        page_area = page.rect.width * page.rect.height
        image_area = pix.width * pix.height
        return image_area > page_area * 0.8
    
    def store_images_in_database(self, image_data: List[Dict[str, Any]]):
        """Store extracted images directly in database as BLOB"""
        if not image_data:
            return
        
        try:
            conn = self.db_manager.get_connection()
            cur = conn.cursor()
            
            images_stored = 0
            associations_created = 0
            
            for image_info in image_data:
                pdf_name = image_info['pdf_name']
                page_number = image_info['page_number']
                image_filename = image_info['image_filename']
                
                # Find parts from this PDF and page
                cur.execute("""
                    SELECT id, part_number FROM parts 
                    WHERE catalog_name = ? AND page = ?
                """, (pdf_name, page_number))
                
                parts = cur.fetchall()
                
                # Store image and associate with each part on this page
                for part_id, part_number in parts:
                    try:
                        # Store image in part_images table as BLOB
                        cur.execute("""
                            INSERT OR REPLACE INTO part_images 
                            (part_id, image_filename, image_data, image_type, image_width, image_height, file_size, page_number, confidence)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            part_id,
                            image_filename,
                            image_info['image_data'],  # Binary BLOB data
                            image_info['image_type'],
                            image_info['image_width'],
                            image_info['image_height'],
                            image_info['file_size'],
                            page_number,
                            0.8  # Default confidence
                        ))
                        
                        # Update the part's image reference
                        cur.execute("""
                            UPDATE parts 
                            SET image_path = ?
                            WHERE id = ?
                        """, (image_filename, part_id))
                        
                        images_stored += 1
                        associations_created += 1
                        print(f"     🔗 Stored {image_filename} for part {part_number} ({image_info['file_size']:,} bytes)")
                        
                    except Exception as e:
                        print(f"     ❌ Error storing image for part {part_number}: {e}")
                        continue
            
            conn.commit()
            conn.close()
            print(f"💾 Stored {images_stored} images in database")
            print(f"🔗 Created {associations_created} image-part associations")
            
        except Exception as e:
            print(f"❌ Error storing images in database: {e}")
    
    def get_image_from_database(self, part_id: int, image_filename: str = None):
        """Retrieve image data from database for a specific part"""
        try:
            conn = self.db_manager.get_connection()
            cur = conn.cursor()
            
            if image_filename:
                # Get specific image
                cur.execute("""
                    SELECT image_data, image_type, image_width, image_height 
                    FROM part_images 
                    WHERE part_id = ? AND image_filename = ?
                """, (part_id, image_filename))
            else:
                # Get first image for the part
                cur.execute("""
                    SELECT image_data, image_type, image_width, image_height 
                    FROM part_images 
                    WHERE part_id = ? 
                    ORDER BY confidence DESC, created_at DESC 
                    LIMIT 1
                """, (part_id,))
            
            result = cur.fetchone()
            conn.close()
            
            if result:
                return {
                    'image_data': result[0],
                    'image_type': result[1],
                    'image_width': result[2],
                    'image_height': result[3]
                }
            return None
            
        except Exception as e:
            print(f"❌ Error retrieving image from database: {e}")
            return None
    
    def get_all_images_for_part(self, part_id: int):
        """Get all images for a specific part"""
        try:
            conn = self.db_manager.get_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT image_filename, image_data, image_type, image_width, image_height, file_size
                FROM part_images 
                WHERE part_id = ?
                ORDER BY confidence DESC, created_at DESC
            """, (part_id,))
            
            images = []
            for row in cur.fetchall():
                images.append({
                    'filename': row[0],
                    'image_data': row[1],
                    'image_type': row[2],
                    'width': row[3],
                    'height': row[4],
                    'file_size': row[5]
                })
            
            conn.close()
            return images
            
        except Exception as e:
            print(f"❌ Error retrieving images for part {part_id}: {e}")
            return []
    
    def process_all_pdfs(self, pdf_directory: str):
        """Process all PDFs and store images directly in database"""
        pdf_dir = Path(pdf_directory)
        
        if not pdf_dir.exists():
            print(f"❌ PDF directory not found: {pdf_dir}")
            return
        
        pdf_files = list(pdf_dir.glob("*.pdf"))
        if not pdf_files:
            print(f"❌ No PDF files found in {pdf_dir}")
            return
        
        print(f"📚 Found {len(pdf_files)} PDF files to process")
        
        # Step 1: Clean up existing image data and create table
        print(f"\n{'='*60}")
        print("🧹 DATABASE CLEANUP PHASE")
        print(f"{'='*60}")
        self.cleanup_existing_images()
        self.create_part_images_table()
        
        # Step 2: Process PDFs and store in database
        print(f"\n{'='*60}")
        print("🔄 DATABASE EXTRACTION PHASE")
        print(f"{'='*60}")
        
        total_images = 0
        total_associations = 0
        
        for pdf_path in pdf_files:
            try:
                print(f"\n📄 Processing: {pdf_path.name}")
                
                # Extract images directly to database
                image_data = self.extract_images_to_database(pdf_path)
                
                if image_data:
                    total_images += len(image_data)
                    print(f"✅ Extracted {len(image_data)} images from {pdf_path.name}")
                    
                    # Store images in database
                    self.store_images_in_database(image_data)
                    total_associations += len(image_data)
                    
                else:
                    print(f"⚠️  No images found in {pdf_path.name}")
                    
            except Exception as e:
                print(f"❌ Error processing {pdf_path.name}: {e}")
                continue
        
        print(f"\n{'='*60}")
        print("🎉 FINAL RESULTS")
        print(f"{'='*60}")
        print(f"📊 Total images extracted: {total_images}")
        print(f"💾 Total images stored in database: {total_associations}")
        print(f"🗃️  All images stored as BLOB in database")

def main():
    """Main function to run the database image extraction"""
    # Configuration
    data_dir = app_dir / "data"
    pdf_directory = data_dir / "pdfs"
    
    print("🚀 Starting Database Image Extraction...")
    print(f"📁 PDF Directory: {pdf_directory}")
    print("💾 Storage: Images will be stored as BLOB in database")
    
    # Verify PDF directory exists
    if not pdf_directory.exists():
        print(f"❌ PDF directory not found: {pdf_directory}")
        return
    
    # Create extractor and process
    extractor = DatabaseImageExtractor()
    extractor.process_all_pdfs(pdf_directory)
    
    print(f"\n✅ Image extraction completed! All images stored in database as BLOB data.")

if __name__ == "__main__":
    main()