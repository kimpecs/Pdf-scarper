# extract_pdf_flexible.py
import pdfplumber
from pdf2image import convert_from_path
from pathlib import Path
import sqlite3
import re
from tqdm import tqdm
import argparse
import json
import requests
import os

DB_PATH = Path("catalog.db")
IMAGES_DIR = Path("page_images")
PDF_DIR = Path("pdfs")
IMAGES_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)

# Set poppler path
POPPLER_PATH = r"C:\Users\kpecco\Desktop\codes\poppler-25.07.0\Library\bin"

# Comprehensive part number patterns
PART_NUMBER_PATTERNS = [
    # Standard formats: D50, D50-100, 600-123A, CH1234
    (re.compile(r'\b([A-Z]{1,4}\d{2,4}(?:-\d+)?[A-Z]?)\b'), 'part'),
    
    # Numeric formats: 123456, 1234567A
    (re.compile(r'\b(\d{5,7}[A-Z]?)\b'), 'part'),
    
    # Alphanumeric with dash: FP-1234-ABC, KIT-123, PK-456
    (re.compile(r'\b([A-Z]{2,}-[A-Z0-9]+(?:-[A-Z0-9]+)?)\b'), 'part'),
    
    # KIT/PK formats: KIT123, PK456, KIT-789
    (re.compile(r'\b(?:KIT|PK)[-_]?(\d+[A-Z]?)\b', re.I), 'kit'),
    
    # Engine/Model numbers: D6H, 3406B, C15
    (re.compile(r'\b([A-Z]?\d+[A-Z]+|[A-Z]+\d+[A-Z]*)\b'), 'model'),
    
    # Caliper formats: 600-123, 600-456A
    (re.compile(r'\b(600-\d{3,4}[A-Z]?)\b', re.I), 'caliper'),
    
    # CH formats: CH1234
    (re.compile(r'\b(CH\d{4})\b', re.I), 'kit'),
    
    # International formats with slashes: 123/456, ABC/123
    (re.compile(r'\b([A-Z0-9]+/[A-Z0-9]+)\b'), 'part'),
]

# Machine/vehicle patterns
MACHINE_PATTERNS = [
    re.compile(r'\b(D[3-9]|D1[0-1]|[0-9]{3}[A-Z]?)\b'),  # Caterpillar models
    re.compile(r'\b([0-9]{1,2}[A-Z]*\s*Series?)\b', re.I),  # Series
    re.compile(r'\b([A-Z]+\s*[0-9]+[A-Z]*)\b'),  # General models
]

# Specification patterns
SPEC_PATTERNS = [
    re.compile(r'(\d+\.?\d*)\s*(?:mm|in|inch|lb|kg|psi|bar|rpm|ft|lbs?)\b', re.I),
    re.compile(r'\b(Torque|Weight|Capacity|Pressure|Size|Length|Width|Height):?\s*([^\n]+)', re.I),
]

def download_pdf(url, local_name):
    """Download PDF from URL if it doesn't exist locally"""
    local_path = PDF_DIR / local_name
    
    if local_path.exists():
        print(f"PDF already exists: {local_path}")
        return local_path
    
    try:
        print(f"Downloading PDF from {url}")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"Downloaded PDF to: {local_path}")
        return local_path
    except Exception as e:
        print(f"Error downloading PDF: {e}")
        return None

def detect_catalog_type(pdf_path, first_page_text):
    """Flexible catalog type detection"""
    pdf_name = Path(pdf_path).stem.lower()
    first_page_lower = first_page_text.lower()
    
    catalog_indicators = {
        'dayton': ['dayton', 'hydraulic brake'],
        'caterpillar': ['caterpillar', 'cat ', 'fp-'],
        'fort_pro': ['fort pro', 'fortpro', 'heavy duty'],
        'dana_spicer': ['dana', 'spicer', 'axle'],
        'cummins': ['cummins', 'engine'],
        'detroit': ['detroit diesel'],
        'international': ['international', 'navistar'],
        'exhaust': ['exhaust', 'nelson'],
        'lighting': ['lighting', 'fortpro'],
        'springs': ['spring', 'suspension'],
        'brakes': ['brake', 'caliper', 'rotor'],
    }
    
    for catalog_type, indicators in catalog_indicators.items():
        if any(indicator in pdf_name for indicator in indicators):
            return catalog_type
        if any(indicator in first_page_lower for indicator in indicators):
            return catalog_type
    
    # Try filename-based detection
    if 'dayton' in pdf_name:
        return 'dayton'
    elif 'caterpillar' in pdf_name or 'cat' in pdf_name:
        return 'caterpillar'
    elif 'fort' in pdf_name:
        return 'fort_pro'
    elif 'dana' in pdf_name:
        return 'dana_spicer'
    elif 'cummins' in pdf_name:
        return 'cummins'
    elif 'detroit' in pdf_name:
        return 'detroit'
    elif 'international' in pdf_name:
        return 'international'
    elif 'exhaust' in pdf_name:
        return 'exhaust'
    elif 'lighting' in pdf_name:
        return 'lighting'
    elif 'spring' in pdf_name:
        return 'springs'
    else:
        return 'general'

def extract_smart_toc(pdf, catalog_type):
    """Extract TOC intelligently based on content"""
    toc_entries = []
    
    try:
        # Look for TOC pages in first 20 pages
        for i, page in enumerate(pdf.pages[:20]):
            text = page.extract_text() or ""
            text_lower = text.lower()
            
            # Check if this is a TOC page
            is_toc_page = any(indicator in text_lower for indicator in 
                            ['contents', 'table of contents', 'index', 'chapter'])
            
            if is_toc_page:
                print(f"Found TOC on page {i+1}")
                
                # Extract potential TOC entries
                lines = text.split('\n')
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Look for page numbers at the end
                    page_match = re.search(r'(\d+)$', line)
                    if page_match:
                        page_num = int(page_match.group(1))
                        title = line[:page_match.start()].strip()
                        # Clean up title
                        title = re.sub(r'[\.\s]+$', '', title)
                        
                        if title and len(title) > 3 and page_num < 1000:  # Reasonable page number
                            toc_entries.append((title, page_num))
                
                break
                
    except Exception as e:
        print(f"Error extracting TOC: {e}")
    
    # If no TOC found, create basic structure
    if not toc_entries:
        toc_entries = [("Document", 1)]
    
    return toc_entries

def assign_section(page_number, toc_entries):
    """Assign page to appropriate section based on TOC"""
    if not toc_entries:
        return "General"
    
    current_section = toc_entries[0][0]
    for section, start_page in toc_entries:
        if page_number >= start_page:
            current_section = section
        else:
            break
    
    return current_section

def extract_machine_info(text):
    """Extract machine models and specifications"""
    machine_info = {}
    
    # Extract machine models
    models = set()
    for pattern in MACHINE_PATTERNS:
        matches = pattern.findall(text)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]  # Handle capture groups
            if len(match) >= 2:  # Reasonable length
                models.add(match.upper())
    
    if models:
        machine_info['models'] = sorted(list(models))
    
    # Extract specifications
    specs = {}
    for pattern in SPEC_PATTERNS:
        matches = pattern.findall(text)
        for match in matches:
            if isinstance(match, tuple):
                key, value = match[0], match[1]
                specs[key.lower()] = value.strip()
            else:
                specs['measurement'] = match
    
    if specs:
        machine_info['specifications'] = specs
    
    return machine_info

def extract_part_info(text, page_number):
    """Extract part numbers and context using comprehensive patterns"""
    parts_found = []
    
    for pattern, part_type in PART_NUMBER_PATTERNS:
        for match in pattern.finditer(text):
            part_num = match.group(1).upper().strip()
            
            # Filter out obvious non-part numbers
            if (len(part_num) < 3 or 
                part_num.isdigit() and (int(part_num) < 1000 or int(part_num) > 99999999) or
                part_num in ['CONTENTS', 'CHAPTER', 'SECTION', 'PAGE']):
                continue
            
            # Extract context
            lines = text.split('\n')
            context = ""
            for line in lines:
                if part_num in line:
                    context = re.sub(r'\s+', ' ', line.strip())[:250]
                    break
            
            if not context:
                # Use surrounding text
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                context = text[start:end].strip()
            
            parts_found.append({
                'type': part_type,
                'number': part_num,
                'context': context
            })
    
    return parts_found

def is_valid_part(part_data, catalog_type):
    """Validate if extracted part is likely real"""
    part_num = part_data['number']
    
    # Common false positives
    false_positives = {
        'dates': re.compile(r'\b(19|20)\d{2}\b'),
        'page_numbers': re.compile(r'^\d{1,3}$'),
        'common_words': re.compile(r'\b(CHAPTER|SECTION|PAGE|FIG|TABLE)\b', re.I)
    }
    
    for pattern in false_positives.values():
        if pattern.search(part_num):
            return False
    
    # Catalog-specific validation
    if catalog_type == 'caterpillar':
        return len(part_num) >= 4 and not part_num.isdigit()
    elif catalog_type == 'dayton':
        return any(prefix in part_num for prefix in ['D', '600-', 'CH'])
    else:
        return len(part_num) >= 4

def insert_part(conn, catalog_name, catalog_type, part_data, page, image_path, page_text, pdf_path, category, machine_info):
    """Insert part into database"""
    cur = conn.cursor()
    
    # Check for duplicates
    cur.execute("""
        SELECT id FROM parts 
        WHERE part_number=? AND page=? AND catalog_name=?
    """, (part_data['number'], page, catalog_name))
    
    if cur.fetchone():
        return
    
    # Insert part
    cur.execute("""
        INSERT INTO parts (
            catalog_name, catalog_type, part_type, part_number, 
            description, category, page, image_path, page_text, 
            pdf_path, machine_info
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        catalog_name, catalog_type, part_data['type'], part_data['number'],
        part_data['context'], category, page, 
        str(image_path) if image_path else None,
        page_text[:5000] if page_text else None,
        str(pdf_path),
        json.dumps(machine_info) if machine_info else None
    ))

def process_pdf(pdf_path, catalog_name, dpi=150, skip_images=False, max_pages=None):
    """Process a single PDF file"""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        return
    
    # Copy PDF to PDFs directory for web access
    try:
        target_pdf = PDF_DIR / pdf_path.name
        import shutil
        shutil.copy2(pdf_path, target_pdf)
        pdf_path = target_pdf
    except Exception as e:
        print(f"Warning: Could not copy PDF: {e}")
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.isolation_level = None
        conn.execute("BEGIN")
        
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            if max_pages:
                total_pages = min(total_pages, max_pages)
            
            # Detect catalog type
            first_page_text = pdf.pages[0].extract_text() or ""
            catalog_type = detect_catalog_type(pdf_path, first_page_text)
            
            print(f"Processing: {catalog_name} ({catalog_type}) - {total_pages} pages")
            
            # Extract TOC
            toc_entries = extract_smart_toc(pdf, catalog_type)
            print(f"Found {len(toc_entries)} TOC entries")
            
            # Convert to images if needed
            pages_imgs = None
            if not skip_images:
                try:
                    pages_imgs = convert_from_path(
                        str(pdf_path),
                        dpi=dpi,
                        first_page=1,
                        last_page=total_pages
                    )
                except Exception as e:
                    print(f"Image conversion failed: {e}")
                    pages_imgs = None
            
            # Process pages
            for i in tqdm(range(total_pages), desc=f"Processing {catalog_name}"):
                page_num = i + 1
                page = pdf.pages[i]
                
                try:
                    text = page.extract_text() or ""
                    if not text.strip():
                        continue
                except Exception as e:
                    print(f"Error extracting text from page {page_num}: {e}")
                    continue
                
                # Assign category
                category = assign_section(page_num, toc_entries)
                
                # Save page image
                image_path = None
                if pages_imgs and i < len(pages_imgs):
                    try:
                        image_filename = f"{catalog_name}_page_{page_num:04d}.png"
                        image_path = IMAGES_DIR / image_filename
                        pages_imgs[i].save(image_path, "PNG")
                    except Exception as e:
                        print(f"Error saving image for page {page_num}: {e}")
                
                # Extract machine info
                machine_info = extract_machine_info(text)
                
                # Extract parts
                parts_data = extract_part_info(text, page_num)
                valid_parts = [p for p in parts_data if is_valid_part(p, catalog_type)]
                
                if valid_parts:
                    print(f"Page {page_num}: Found {len(valid_parts)} parts in category: {category}")
                    
                    for part in valid_parts:
                        insert_part(
                            conn, catalog_name, catalog_type, part, 
                            page_num, image_path, text, pdf_path, 
                            category, machine_info
                        )
            
            conn.commit()
            print(f"Completed processing {catalog_name}")

def process_all_catalogs(pdf_urls, dpi=150, skip_images=False, max_pages=None):
    """Process all catalogs from the URL dictionary"""
    for catalog_name, url in pdf_urls.items():
        print(f"\n{'='*60}")
        print(f"Processing: {catalog_name}")
        print(f"URL: {url}")
        print('='*60)
        
        # Download PDF
        local_name = f"{catalog_name.replace(' ', '_')}.pdf"
        pdf_path = download_pdf(url, local_name)
        
        if pdf_path:
            try:
                process_pdf(pdf_path, catalog_name, dpi, skip_images, max_pages)
            except Exception as e:
                print(f"Error processing {catalog_name}: {e}")
        else:
            print(f"Failed to download {catalog_name}")

# Catalog URLs
PDF_URLS = {
    "Dayton_Hydraulic_Brakes": "https://lascotruckparts.com/wp-content/uploads/2023/09/Dayton-Parts-Frenos-Hidraulicos-Parte-1-ENG-Dayton-Parts-Hydraulic-Brakes-Part-1.pdf",
    "Dana_Spicer": "https://www.canadawideparts.com/downloads/catalogs/dana_spicer_tandemAxles_461-462-463-521-581_AXIP-0085A.pdf",
    "PAI_Drivetrain": "https://barringtondieselclub.co.za/mack/general/mack/pai-mack-volvo-parts.pdf",
    "FP_Cummins": "https://www.drivparts.com/content/dam/marketing/North-America/catalogs/fp-diesel/pdf/fp-diesel-cummins-engines.pdf",
    "FP_Caterpillar": "https://www.drivparts.com/content/dam/marketing/North-America/catalogs/fp-diesel/pdf/fp-diesel-caterpillar-engines.pdf",
    "FP_Detroit": "https://www.dieselduck.info/historical/01%20diesel%20engine/detroit%20diesel/_docs/Detroit%20Diesel%20%28all%29%20FP%20Parts%20manual.pdf",
    "FP_International": "https://www.drivparts.com/content/dam/marketing/emea/fmmp/brands/catalogues/fp-diesel-international-navistar-engines.pdf",
    "Nelson_Exhaust": "https://nelsonexhaust.com.au/files/File/Nelson%20old%20catalogue.pdf",
    "FortPro_HeavyDuty": "https://www.fortpro.com/images/uploaded/HEAVY_DUTY_PARTS.pdf",
    "FortPro_Lighting": "https://www.fortpro.com/images/uploaded/LIGHTING_2020.pdf",
    "Velvac": "https://www.velvac.com/sites/default/files/velvac_catalog_2016.pdf"
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract parts from multiple PDF catalogs")
    parser.add_argument("--dpi", type=int, default=150, help="Image DPI")
    parser.add_argument("--skip-images", action="store_true", help="Skip image extraction")
    parser.add_argument("--max-pages", type=int, default=None, help="Max pages per PDF")
    parser.add_argument("--catalog", type=str, help="Process specific catalog")
    
    args = parser.parse_args()
    
    # Process specific catalog or all
    if args.catalog:
        if args.catalog in PDF_URLS:
            urls = {args.catalog: PDF_URLS[args.catalog]}
            process_all_catalogs(urls, args.dpi, args.skip_images, args.max_pages)
        else:
            print(f"Catalog '{args.catalog}' not found. Available catalogs: {list(PDF_URLS.keys())}")
    else:
        process_all_catalogs(PDF_URLS, args.dpi, args.skip_images, args.max_pages)