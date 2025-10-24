import pdfplumber
import fitz  # PyMuPDF
import re
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
import sys
import os

# Add the project root to Python path for absolute imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Use absolute imports
from app.utils.logger import setup_logging
from app.utils.constants import PART_NUMBER_PATTERNS, MACHINE_PATTERNS, CATALOG_INDICATORS

logger = setup_logging()

class CatalogExtractor:
    def __init__(self):
        self.part_patterns = [(re.compile(pattern), ptype) for pattern, ptype in PART_NUMBER_PATTERNS]
        self.machine_patterns = [re.compile(pattern) for pattern in MACHINE_PATTERNS]
    
    def process_pdf(self, pdf_path: str, output_image_dir: str) -> List[Dict[str, Any]]:
        """
        Main method to process PDF and extract part data
        """
        catalog_data = []
        pdf_name = Path(pdf_path).stem
        
        try:
            # First, detect catalog type
            catalog_type = self.detect_catalog_type(Path(pdf_path))
            
            # Extract text and parts using pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                first_page_text = pdf.pages[0].extract_text() or ""
                
                for page_num, page in enumerate(pdf.pages, 1):
                    try:
                        text = page.extract_text() or ""
                        if not text.strip():
                            continue
                        
                        # Extract parts from this page
                        parts = self.extract_part_info(text, page_num)
                        
                        # Extract machine info
                        machine_info = self.extract_machine_info(text)
                        
                        # Create part records
                        for part in parts:
                            part_data = {
                                'catalog_name': pdf_name,
                                'catalog_type': catalog_type,
                                'part_number': part['number'],
                                'part_type': part['type'],
                                'description': part.get('context', ''),
                                'page': page_num,
                                'page_text': text[:1000],  # Store first 1000 chars
                                'pdf_path': f"{pdf_name}.pdf",
                                'category': self._infer_category(part['context']),
                                'machine_info': json.dumps(machine_info) if machine_info else None
                            }
                            catalog_data.append(part_data)
                            
                    except Exception as e:
                        logger.warning(f"Error processing page {page_num}: {e}")
                        continue
            
            # Extract images using PyMuPDF
            self._extract_images(pdf_path, output_image_dir, pdf_name, catalog_data)
            
            logger.info(f"Extracted {len(catalog_data)} parts from {pdf_name}")
            
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {e}")
        
        return catalog_data
    
    def detect_catalog_type(self, pdf_path: Path) -> str:
        """Detect catalog type from PDF filename and content"""
        pdf_name = pdf_path.stem.lower()
        
        # First, try to detect from filename
        for catalog_type, indicators in CATALOG_INDICATORS.items():
            if any(indicator in pdf_name for indicator in indicators):
                return catalog_type
        
        # If not detected from filename, check first page content
        try:
            with pdfplumber.open(pdf_path) as pdf:
                first_page_text = pdf.pages[0].extract_text() or ""
                first_page_lower = first_page_text.lower()
                
                for catalog_type, indicators in CATALOG_INDICATORS.items():
                    if any(indicator in first_page_lower for indicator in indicators):
                        return catalog_type
        except:
            pass
        
        return 'general'
    
    def extract_part_info(self, text: str, page_number: int) -> List[Dict[str, Any]]:
        """Extract part numbers and context from text"""
        parts_found = []
        
        for pattern, part_type in self.part_patterns:
            for match in pattern.finditer(text):
                part_num = match.group(1).upper().strip()
                
                # Filter false positives
                if self._is_valid_part(part_num):
                    context = self._extract_context(text, match)
                    parts_found.append({
                        'type': part_type,
                        'number': part_num,
                        'context': context,
                        'page': page_number
                    })
        
        return parts_found
    
    def extract_machine_info(self, text: str) -> Dict[str, Any]:
        """Extract machine models and specifications"""
        machine_info = {}
        models = set()
        
        for pattern in self.machine_patterns:
            matches = pattern.findall(text)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                if len(match) >= 2:
                    models.add(match.upper())
        
        if models:
            machine_info['models'] = sorted(list(models))
        
        return machine_info
    
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
    
    def _extract_context(self, text: str, match) -> str:
        """Extract context around the match"""
        lines = text.split('\n')
        for line in lines:
            if match.group() in line:
                return re.sub(r'\s+', ' ', line.strip())[:250]
        
        # Use surrounding text
        start = max(0, match.start() - 100)
        end = min(len(text), match.end() + 100)
        return text[start:end].strip()
    
    def _infer_category(self, context: str) -> str:
        """Infer category from context"""
        context_lower = context.lower()
        
        if any(word in context_lower for word in ['brake', 'rotor', 'pad', 'caliper', 'disc']):
            return 'Brake System'
        elif any(word in context_lower for word in ['engine', 'piston', 'cylinder', 'crankshaft']):
            return 'Engine'
        elif any(word in context_lower for word in ['hydraulic', 'pump', 'valve', 'hose']):
            return 'Hydraulic System'
        elif any(word in context_lower for word in ['electrical', 'sensor', 'switch', 'wire']):
            return 'Electrical'
        elif any(word in context_lower for word in ['axle', 'differential', 'transmission']):
            return 'Drivetrain'
        else:
            return 'General'
    
    def _extract_images(self, pdf_path: str, output_dir: str, pdf_name: str, catalog_data: List[Dict[str, Any]]):
        """Extract images from PDF and associate with parts"""
        try:
            doc = fitz.open(pdf_path)
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    try:
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)
                        
                        if pix.n - pix.alpha < 4:
                            img_data = pix.tobytes("png")
                        else:
                            pix1 = fitz.Pixmap(fitz.csRGB, pix)
                            img_data = pix1.tobytes("png")
                            pix1 = None
                        
                        # Save image
                        img_filename = f"{pdf_name}_p{page_num+1}_img{img_index}.png"
                        img_path = output_path / img_filename
                        
                        with open(img_path, "wb") as f:
                            f.write(img_data)
                        
                        # Associate image with parts on this page
                        for part in catalog_data:
                            if part['page'] == page_num + 1:
                                part['image_path'] = str(img_path)
                                break
                        
                        pix = None
                        
                    except Exception as e:
                        logger.warning(f"Error extracting image from page {page_num+1}: {e}")
                        continue
            
            doc.close()
            
        except Exception as e:
            logger.error(f"Error extracting images from {pdf_path}: {e}")