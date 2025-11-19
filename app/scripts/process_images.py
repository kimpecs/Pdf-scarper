#!/usr/bin/env python3
"""
Smart image extraction that ties images to part numbers AND uploads to database
Uses part patterns from app/utils/constants.py
"""
import fitz  # PyMuPDF
import re
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple
import sqlite3
from datetime import datetime

# EXACT PATH: This script is in app/scripts/
script_dir = Path(__file__).parent  # app/scripts/
app_dir = script_dir.parent         # app/
sys.path.insert(0, str(app_dir))

from services.db.queries import DatabaseManager
from utils.logger import setup_logging
from utils.constants import PART_NUMBER_PATTERNS

logger = setup_logging()

class SmartImageExtractor:
    def __init__(self):
        # Use part patterns from your constants file
        self.part_patterns = [(re.compile(pattern), ptype) for pattern, ptype in PART_NUMBER_PATTERNS]
        self.db_manager = DatabaseManager()
    
    def extract_images_with_parts(self, pdf_path: str, output_dir: str) -> List[Dict[str, Any]]:
        """
        Extract images and associate them with nearby part numbers
        """
        pdf_path = Path(pdf_path)
        output_dir = Path(output_dir)
        
        if not pdf_path.exists():
            logger.error(f"PDF not found: {pdf_path}")
            return []
        
        # Create output directory
        pdf_image_dir = output_dir / pdf_path.stem
        pdf_image_dir.mkdir(parents=True, exist_ok=True)
        
        results = []
        pdf_name = pdf_path.stem
        
        try:
            doc = fitz.open(pdf_path)
            logger.info(f"Processing PDF: {pdf_path.name}")
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Get all text blocks with their positions
                text_blocks = self._extract_text_blocks(page)
                
                # Get all images
                image_list = page.get_images()
                
                logger.info(f"Page {page_num + 1}: {len(image_list)} images, {len(text_blocks)} text blocks")
                
                for img_index, img in enumerate(image_list):
                    try:
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)
                        
                        # Only process valid images of reasonable size
                        if (pix.n - pix.alpha < 4 and 
                            pix.width >= 50 and pix.height >= 50 and
                            not self._is_full_page_image(pix, page)):
                            
                            # Get image position and dimensions
                            img_rect = self._get_image_rect(img, page)
                            
                            # Find part numbers near this image
                            nearby_parts = self._find_nearby_part_numbers(text_blocks, img_rect)
                            
                            if nearby_parts:
                                # Save the image
                                image_filename = f"{pdf_name}_p{page_num+1}_img{img_index+1}.png"
                                image_path = pdf_image_dir / image_filename
                                
                                # Save image
                                if pix.n - pix.alpha == 3:  # RGB
                                    pix.save(str(image_path))
                                else:  # Convert to RGB
                                    pix_rgb = fitz.Pixmap(fitz.csRGB, pix)
                                    pix_rgb.save(str(image_path))
                                    pix_rgb = None
                                
                                # Create result for each associated part
                                for part_data in nearby_parts:
                                    result = {
                                        'pdf_name': pdf_name,
                                        'page_number': page_num + 1,
                                        'image_filename': image_filename,
                                        'image_path': str(image_path),
                                        'image_width': pix.width,
                                        'image_height': pix.height,
                                        'part_number': part_data['part_number'],
                                        'part_type': part_data['part_type'],
                                        'context': part_data['context'],
                                        'confidence': part_data['confidence'],
                                        'created_at': datetime.now().isoformat()
                                    }
                                    results.append(result)
                                
                                logger.info(f"  ✅ Saved image {image_filename} with {len(nearby_parts)} part associations")
                            
                        pix = None  # Free memory
                        
                    except Exception as e:
                        logger.error(f"Error processing image {img_index} on page {page_num}: {e}")
                        continue
            
            doc.close()
            logger.info(f"Completed processing {pdf_path.name}: {len(results)} image-part associations")
            
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {e}")
        
        return results
    
    def _extract_text_blocks(self, page: fitz.Page) -> List[Dict[str, Any]]:
        """Extract text blocks with their positions and content"""
        text_blocks = []
        try:
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text_blocks.append({
                                'text': span["text"],
                                'bbox': span["bbox"],  # [x0, y0, x1, y1]
                                'page_width': page.rect.width,
                                'page_height': page.rect.height
                            })
        except Exception as e:
            logger.error(f"Error extracting text blocks: {e}")
        
        return text_blocks
    
    def _get_image_rect(self, img: tuple, page: fitz.Page) -> tuple:
        """Get image bounding box coordinates"""
        try:
            # Get image rectangle from the page
            xref = img[0]
            image_info = page.get_image_bbox(xref)
            if image_info:
                return image_info
        except:
            pass
        
        # Fallback: return a default rectangle if we can't get exact position
        return (0, 0, 100, 100)
    
    def _is_full_page_image(self, pix: fitz.Pixmap, page: fitz.Page) -> bool:
        """Check if image is full page (likely background/cover)"""
        page_area = page.rect.width * page.rect.height
        image_area = pix.width * pix.height
        return image_area > page_area * 0.8
    
    def _find_nearby_part_numbers(self, text_blocks: List[Dict], img_rect: tuple) -> List[Dict[str, Any]]:
        """Find part numbers near the image position"""
        nearby_parts = []
        
        if not text_blocks:
            return nearby_parts
        
        img_center_x = (img_rect[0] + img_rect[2]) / 2
        img_center_y = (img_rect[1] + img_rect[3]) / 2
        
        for block in text_blocks:
            try:
                block_center_x = (block['bbox'][0] + block['bbox'][2]) / 2
                block_center_y = (block['bbox'][1] + block['bbox'][3]) / 2
                
                # Calculate distance from image center
                distance_x = abs(block_center_x - img_center_x)
                distance_y = abs(block_center_y - img_center_y)
                
                # Consider text "near" if within 200 pixels (adjustable)
                if distance_x < 200 and distance_y < 200:
                    # Search for part numbers in this text block
                    parts_in_block = self._extract_parts_from_text(block['text'])
                    for part_data in parts_in_block:
                        # Calculate confidence based on distance
                        confidence = max(0, 1 - (distance_x + distance_y) / 400)
                        part_data['confidence'] = round(confidence, 2)
                        nearby_parts.append(part_data)
                        
            except Exception as e:
                logger.warning(f"Error processing text block: {e}")
                continue
        
        # Remove duplicates and sort by confidence
        unique_parts = {}
        for part in nearby_parts:
            key = part['part_number']
            if key not in unique_parts or part['confidence'] > unique_parts[key]['confidence']:
                unique_parts[key] = part
        
        return sorted(unique_parts.values(), key=lambda x: x['confidence'], reverse=True)
    
    def _extract_parts_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extract part numbers from text using patterns from constants.py"""
        parts_found = []
        
        for pattern, part_type in self.part_patterns:
            for match in pattern.finditer(text):
                part_num = match.group(1).upper().strip()
                
                # Filter false positives
                if self._is_valid_part(part_num):
                    context = self._extract_context(text, match.start(), match.end())
                    parts_found.append({
                        'part_number': part_num,
                        'part_type': part_type,
                        'context': context,
                        'confidence': 1.0  # Base confidence
                    })
        
        return parts_found
    
    def _is_valid_part(self, part_num: str) -> bool:
        """Validate if extracted part is likely real"""
        false_positives = [
            r'\b(19|20)\d{2}\b',  # Dates
            r'^\d{1,3}$',         # Page numbers
            r'\b(CHAPTER|SECTION|PAGE|FIG|TABLE)\b'  # Common words
        ]
        
        for pattern in false_positives:
            if re.search(pattern, part_num, re.I):
                return False
        
        return len(part_num) >= 4
    
    def _extract_context(self, text: str, start: int, end: int) -> str:
        """Extract context around the match"""
        context_start = max(0, start - 50)
        context_end = min(len(text), end + 50)
        return text[context_start:context_end].strip()
    
    def save_to_database(self, image_part_data: List[Dict[str, Any]]) -> bool:
        """Save image-part associations to database"""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            # Create part_images table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS part_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    part_number TEXT NOT NULL,
                    part_type TEXT,
                    image_filename TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    pdf_name TEXT NOT NULL,
                    page_number INTEGER,
                    image_width INTEGER,
                    image_height INTEGER,
                    context TEXT,
                    confidence REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (part_number) REFERENCES parts (part_number),
                    UNIQUE(part_number, image_filename)
                )
            """)
            
            # Create index for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_part_images_part_number 
                ON part_images (part_number)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_part_images_pdf_name 
                ON part_images (pdf_name)
            """)
            
            # Insert image-part associations
            success_count = 0
            for data in image_part_data:
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO part_images 
                        (part_number, part_type, image_filename, image_path, pdf_name, 
                         page_number, image_width, image_height, context, confidence, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        data['part_number'],
                        data['part_type'],
                        data['image_filename'],
                        data['image_path'],
                        data['pdf_name'],
                        data['page_number'],
                        data['image_width'],
                        data['image_height'],
                        data['context'],
                        data['confidence'],
                        data['created_at']
                    ))
                    success_count += 1
                except Exception as e:
                    logger.error(f"Error inserting image-part data for {data['part_number']}: {e}")
                    continue
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Successfully saved {success_count}/{len(image_part_data)} image-part associations to database")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error saving to database: {e}")
            return False
    
    def get_images_for_part(self, part_number: str) -> List[Dict[str, Any]]:
        """Get all images associated with a part number"""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM part_images 
                WHERE part_number = ? 
                ORDER BY confidence DESC, created_at DESC
            """, (part_number,))
            
            results = []
            for row in cursor.fetchall():
                results.append(dict(row))
            
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Error getting images for part {part_number}: {e}")
            return []
    
    def process_pdf_directory(self, pdf_directory: str, output_base_dir: str):
        """Process all PDFs in a directory"""
        pdf_dir = Path(pdf_directory)
        output_dir = Path(output_base_dir)
        
        if not pdf_dir.exists():
            logger.error(f"PDF directory not found: {pdf_dir}")
            return
        
        pdf_files = list(pdf_dir.glob("*.pdf"))
        if not pdf_files:
            logger.error(f"No PDF files found in {pdf_dir}")
            return
        
        logger.info(f"Found {len(pdf_files)} PDF files to process")
        
        total_associations = 0
        
        for pdf_path in pdf_files:
            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing: {pdf_path.name}")
                logger.info(f"{'='*60}")
                
                # Extract images with part associations
                image_part_data = self.extract_images_with_parts(pdf_path, output_dir)
                
                if image_part_data:
                    # Save to database
                    if self.save_to_database(image_part_data):
                        total_associations += len(image_part_data)
                        logger.info(f"✅ Successfully processed {pdf_path.name}: {len(image_part_data)} associations")
                    else:
                        logger.error(f"❌ Failed to save associations for {pdf_path.name}")
                else:
                    logger.warning(f"⚠️  No image-part associations found in {pdf_path.name}")
                    
            except Exception as e:
                logger.error(f"❌ Error processing {pdf_path.name}: {e}")
                continue
        
        logger.info(f"\n🎉 Processing completed! Total image-part associations: {total_associations}")

def main():
    """Main function to run the image extraction"""
    # Configuration
    data_dir = app_dir / "data"
    pdf_directory = data_dir / "pdfs"
    output_image_dir = data_dir / "part_images"
    
    print("🚀 Starting Smart Image-Part Extraction...")
    print(f"📁 PDF Directory: {pdf_directory}")
    print(f"💾 Output Directory: {output_image_dir}")
    print(f"🗄️  Database: {data_dir / 'catalog.db'}")
    
    # Verify PDF directory exists
    if not pdf_directory.exists():
        print(f"❌ PDF directory not found: {pdf_directory}")
        return
    
    # Create extractor and process
    extractor = SmartImageExtractor()
    extractor.process_pdf_directory(pdf_directory, output_image_dir)
    
    print(f"\n✅ Image extraction completed! Check database for results.")

if __name__ == "__main__":
    main()