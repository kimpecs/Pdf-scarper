import pdfplumber
import fitz  # PyMuPDF
import re
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
import sys
from fastapi import File, UploadFile

# EXACT PATH: This file is in app/services/pdf_processing/
script_dir = Path(__file__).parent  # app/services/pdf_processing/
services_dir = script_dir.parent    # app/services/
app_dir = services_dir.parent       # app/
sys.path.insert(0, str(app_dir))

from utils.logger import setup_logging
from utils.constants import PART_NUMBER_PATTERNS, MACHINE_PATTERNS, CATALOG_INDICATORS

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
                                'page_text': text[:10000],  
                                'pdf_path': f"{pdf_name}.pdf",
                                'category': self._infer_category(part['context']),
                                'machine_info': json.dumps(machine_info) if machine_info else None,
                                'image_path': None  # Initialize as None
                            }
                            catalog_data.append(part_data)
                            
                    except Exception as e:
                        logger.warning(f"Error processing page {page_num}: {e}")
                        continue
            
            # Extract images using PyMuPDF - improved to get full part images
            self._extract_part_images(pdf_path, output_image_dir, pdf_name, catalog_data)
            
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
        """Infer category from context using part patterns and text analysis"""
        if not context:
            return 'General'
        
        context_lower = context.lower()
        
        # First, try to infer from part number patterns (most specific)
        category_from_part = self._infer_category_from_part_number(context)
        if category_from_part and category_from_part != 'General':
            return category_from_part
        
        # Fall back to text context analysis
        return self._infer_category_from_context(context_lower)

    def _infer_category_from_part_number(self, context: str) -> str:
        """Infer category by analyzing part number patterns in context"""
        # Extract potential part numbers from context
        part_matches = re.findall(r'\b([A-Z0-9\-]{4,20})\b', context.upper())
        
        for part_number in part_matches:
            # Nelson Exhaust components
            if (part_number.startswith(('CLP', 'TB', 'ES-', 'MUF', 'SAT', 'SAA', 'SAMA', 'BRK')) or
                part_number.startswith('M') and '-' in part_number and part_number[1:4].isdigit() or
                part_number.startswith('491') or part_number.startswith(('RHHR', 'TR', '33165'))):
                return 'Exhaust System'
            
            # Fasteners & Hardware
            if (part_number.startswith(('FL', 'FLG', 'TDF', 'TDG')) or
                'CLAMP' in context.upper() or 'BRACKET' in context.upper()):
                return 'Fasteners & Hardware'
            
            # Pacific Truck Transmission
            if (part_number.startswith(('TA-', 'RTLO', 'FR', 'FS-', 'K-')) or
                'TRANSMISSION' in context.upper() or 'FULLER' in context.upper()):
                return 'Transmission Components'
            
            # Pacific Truck Drivetrain
            if (part_number.startswith(('MU', 'AN', 'NMU', 'TKW')) or
                part_number.endswith('X') or 'U-JOINT' in context.upper() or
                'CLUTCH' in context.upper() or 'YOKE' in context.upper()):
                return 'Drivetrain'
            
            # Pacific Truck Differential
            if (part_number.startswith(('DT', 'DS', 'RS', 'CR0')) or
                '/' in part_number and part_number.replace('/', '').isdigit()):
                return 'Drivetrain'
        
        return None

    def _infer_category_from_context(self, context_lower: str) -> str:
        """Infer category from text context analysis"""
        
        # Enhanced category indicators with priority order
        category_indicators = {
            'Exhaust System': [
            'exhaust', 'muffler', 'catalytic', 'spark arrestor', 'exhaust stack',
            'chrome stack', 'flame proof', 'tanker kit', 'flexible tube',
            'exhaust purifier', 'nelson exhaust', 'diesel exhaust'
        ],
        'Brake System': [
            'brake', 'rotor', 'pad', 'caliper', 'disc', 'brake system',
            'hydraulic brake', 'brake assembly', 'brake kit', 'dayton'
        ],
        'Engine': [
            'engine', 'piston', 'cylinder', 'crankshaft', 'turbocharger',
            'water pump', 'oil cooler', 'fuel injection', 'rocker arm',
            'timing cover', 'cylinder head', 'diesel', 'motor', 'pai'
        ],
        'Drivetrain': [
            'axle', 'differential', 'transmission', 'clutch', 'flywheel',
            'u-joint', 'yoke', 'driveshaft', 'transmission assembly',
            'clutch assembly', 'powertrain'
        ],
        'Transmission Components': [
            'transmission', 'fuller', 'eaton', 'roadranger', 'clutch brake',
            'pilot bearing', 'flywheel', 'pacific truck'
        ],
        'Mirrors & Visibility': [
            'mirror', 'west coast', 'convex', 'hood mount', 'rear cross view',
            '2020 system', '2020xg', 'duraball', 'velvac'
        ],
        'Hydraulic System': [
            'hydraulic', 'pump', 'valve', 'hose', 'hydraulic system',
            'hydraulic pump', 'control valve', 'pressure valve'
        ],
        'Electrical': [
            'electrical', 'sensor', 'switch', 'wire', 'harness', 'actuator',
            'motor', 'switch', 'electrical system', 'wiring', 'connector', 'relay'
        ],
        'Air Intake System': [
            'air intake', 'air filter', 'intake manifold', 'turbo intake',
            'air system', 'air flow'
        ],
        'Cooling System': [
            'radiator', 'coolant', 'thermostat', 'water pump', 'cooling fan',
            'heat exchanger', 'cooling system'
        ],
        'Suspension & Steering': [
            'suspension', 'steering', 'shock', 'strut', 'control arm',
            'ball joint', 'tie rod', 'steering gear'
        ],
        'Fasteners & Hardware': [
            'clamp', 'bracket', 'bolt', 'nut', 'screw', 'fastener',
            'hardware', 'mount', 'bracket assembly'
        ],
        'Filters & Fluids': [
            'filter', 'oil filter', 'fuel filter', 'air filter',
            'lubricant', 'grease', 'fluid'
        ],
        'Lighting': [
            'light', 'headlight', 'taillight', 'marker light',
            'led', 'bulb', 'lighting', 'lamp'
        ],
        'Cab & Interior': [
            'seat', 'dashboard', 'interior', 'cab', 'upholstery',
            'floor mat', 'sun visor'
        ],
        'Wheels & Tires': [
            'wheel', 'tire', 'rim', 'hub', 'bearing', 'wheel bearing', 'tire chain'
        ],
        'Kits & Assemblies': [
            'kit', 'assembly', 'set', 'includes', 'complete'
        ],
        'OEM Parts': [
            'oem', 'oe number', 'original equipment', 'mak', 'amb', 'sch'
        ],
        'Heavy Duty Components': [
            'heavy duty', 'pacific truck', 'powertrain', 'drivetrain experts'
        ]
        }
        
        # Check each category in priority order
        for category, indicators in category_indicators.items():
            if any(indicator in context_lower for indicator in indicators):
                return category
        
        return 'General'

    def _extract_part_images(self, pdf_path: str, output_image_dir: str, pdf_name: str, catalog_data: List[Dict[str, Any]]):
        """Extract part images from PDF using PyMuPDF"""
        try:
            doc = fitz.open(pdf_path)
            
            # Create PDF-specific image directory
            pdf_image_dir = Path(output_image_dir) / pdf_name
            pdf_image_dir.mkdir(parents=True, exist_ok=True)
            
            # Patterns that indicate labels/headers (not part images)
            label_regexes = [
                re.compile(pattern, re.IGNORECASE) for pattern in [
                    r'\b(fig|figure|table|page|section|chapter)\b',
                    r'\b\d+\.\d+\b',  # Decimal numbers like 1.1, 2.3
                    r'^[IVX]+\.?$',   # Roman numerals
                    r'\bcontinued\b',
                    r'\bnote:\b',
                    r'\bwarning:\b',
                    r'\bcaution:\b'
                ]
            ]
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Get all images on the page
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    try:
                        # Extract image
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)
                        
                        if pix.n - pix.alpha < 4:  # Check if image is RGB
                            # Convert image info to rectangle format for analysis
                            img_info = (xref, 0, 0, pix.width, pix.height)  # Simplified rect
                            
                            # Check if this is likely a part image
                            if self._is_part_image(img_info, page, "", label_regexes):
                                # Save the image
                                image_filename = f"{pdf_name}_page{page_num+1}_img{img_index+1}.png"
                                image_path = pdf_image_dir / image_filename
                                
                                # Save as PNG
                                if pix.n - pix.alpha == 3:  # RGB
                                    pix.save(str(image_path))
                                else:  # Convert to RGB
                                    pix_rgb = fitz.Pixmap(fitz.csRGB, pix)
                                    pix_rgb.save(str(image_path))
                                    pix_rgb = None
                                
                                # Update catalog data with image path for parts on this page
                                for part in catalog_data:
                                    if part['page'] == page_num + 1:
                                        part['image_path'] = str(image_path.relative_to(Path(output_image_dir).parent))
                                
                                logger.debug(f"Saved part image: {image_filename}")
                        
                        pix = None  # Free pixmap memory
                        
                    except Exception as e:
                        logger.warning(f"Error processing image {img_index} on page {page_num}: {e}")
                        continue
            
            doc.close()
            logger.info(f"Extracted images for {pdf_name} to {pdf_image_dir}")
            
        except Exception as e:
            logger.error(f"Error extracting images from {pdf_path}: {e}")
    
    def _is_part_image(self, img_info: tuple, page: fitz.Page, page_text: str, label_regexes: list) -> bool:
        """Determine if an image is likely a part image vs label/header"""
        try:
            # Get image rectangle
            img_rect = img_info[1:5]  # x0, y0, x1, y1
            if len(img_rect) >= 4:
                x0, y0, x1, y1 = img_rect[:4]
                img_width = x1 - x0
                img_height = y1 - y0
                
                # Filter criteria for part images:
                
                # 1. Size-based filtering - part images are typically medium to large
                page_width = page.rect.width
                page_height = page.rect.height
                
                # Skip very small images (likely icons, bullets)
                if img_width < 50 or img_height < 50:
                    return False
                
                # Skip full-page images (likely covers or background)
                if img_width > page_width * 0.9 and img_height > page_height * 0.9:
                    return False
                
                # 2. Location-based filtering - part images are usually in content areas
                # Skip images in header/footer regions (top/bottom 15% of page)
                header_threshold = page_height * 0.15
                footer_threshold = page_height * 0.85
                if y0 < header_threshold or y1 > footer_threshold:
                    return False
                
                # 3. Content-based filtering using page text
                # Look for part numbers or technical descriptions near the image
                img_center_x = (x0 + x1) / 2
                img_center_y = (y0 + y1) / 2
                
                # Search for text near the image that might indicate it's a part
                nearby_text = ""
                for block in page.get_text("dict")["blocks"]:
                    if "lines" in block:
                        for line in block["lines"]:
                            for span in line["spans"]:
                                span_bbox = span["bbox"]
                                span_center_x = (span_bbox[0] + span_bbox[2]) / 2
                                span_center_y = (span_bbox[1] + span_bbox[3]) / 2
                                
                                # Check if text is near the image
                                if (abs(span_center_x - img_center_x) < 200 and 
                                    abs(span_center_y - img_center_y) < 100):
                                    nearby_text += span["text"] + " "
                
                nearby_text_lower = nearby_text.lower()
                
                # Check if nearby text matches any label patterns
                for label_regex in label_regexes:
                    if label_regex.search(nearby_text_lower):
                        logger.debug(f"Filtered out image with label text: {nearby_text_lower[:100]}")
                        return False
                
                # If text near image contains part-like patterns, it's likely a part image
                part_indicators = [
                    r'\b\d{4,}[a-z]?\b',  # Numbers with possible letter suffix
                    r'\b[a-z]{2,3}-\d{4}\b',  # Common part patterns from constants
                    r'\b(part|component|assembly|kit|set)\b',
                    r'\b(mm|inch|dimension|size)\b'
                ]
                
                # Check if any part patterns match
                for pattern in part_indicators:
                    if re.search(pattern, nearby_text_lower):
                        return True
                
                # Also check using our part patterns from constants
                for pattern, _ in self.part_patterns:
                    if re.search(pattern, nearby_text_lower, re.IGNORECASE):
                        return True
                
                # Default: be conservative - only save if we're confident it's a part
                return False
                
            return False
            
        except Exception as e:
            logger.warning(f"Error analyzing image type: {e}")
            return False  # Default to skipping if we can't analyze
    
    def extract_table_of_contents(self, pdf_path: str) -> list[dict]:
        """Extract a structured Table of Contents for drill-down navigation"""
        try:
            doc = fitz.open(pdf_path)
            toc = doc.get_toc()
            structured_toc = []
            for entry in toc:
                level, title, page = entry
                structured_toc.append({
                    "level": level,
                    "title": title.strip(),
                    "page": page
                })
            return structured_toc
        except Exception as e:
            logger.error(f"Error extracting TOC from {pdf_path}: {e}")
            return []
        
    def process_and_upload_to_s3(self, pdf_path: str, output_image_dir: str, upload_to_s3: bool = False) -> List[Dict[str, Any]]:
        """Process PDF and optionally upload to S3"""
        catalog_data = self.process_pdf(pdf_path, output_image_dir)
        
        if upload_to_s3:
            try:
                from app.services.storage.storage_service import StorageService
                storage_service = StorageService()
                
                # Upload PDF to S3
                pdf_s3_key = storage_service.upload_pdf(pdf_path, "catalogs")
                if pdf_s3_key:
                    logger.info(f"Uploaded PDF to S3: {pdf_s3_key}")
                    
                    # Update catalog data with S3 URLs
                    for part in catalog_data:
                        if part.get('pdf_path'):
                            part['s3_pdf_url'] = storage_service.get_pdf_url(pdf_s3_key)
                        
                        # Upload and update image URLs
                        if part.get('image_path') and Path(part['image_path']).exists():
                            image_s3_key = storage_service.upload_image(part['image_path'], "images")
                            if image_s3_key:
                                part['s3_image_url'] = storage_service.get_image_url(image_s3_key)
                                logger.info(f"Uploaded image to S3: {image_s3_key}")
                
                # Upload processed data to S3
                processed_data = {
                    'pdf_name': Path(pdf_path).stem,
                    'processed_at': datetime.now().isoformat(),
                    'parts_count': len(catalog_data),
                    'parts_data': catalog_data
                }
                
                data_filename = f"{Path(pdf_path).stem}_processed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                storage_service.upload_processed_data(processed_data, data_filename)
                
            except Exception as e:
                logger.error(f"Error uploading to S3: {e}")
        
        return catalog_data