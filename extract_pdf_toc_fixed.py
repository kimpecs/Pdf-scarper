# extract_pdf_toc_fixed.py
import pdfplumber
from pdf2image import convert_from_path
from pathlib import Path
import sqlite3
import re
from tqdm import tqdm
import argparse

DB_PATH = Path("catalog.db")
IMAGES_DIR = Path("page_images")
PDF_DIR = Path("pdfs")
PDF_DIR.mkdir(exist_ok=True)

# Part number patterns for Dayton catalog
DAYTON_PART_RE = re.compile(r'\b(D\d{2,4}(?:-\d+)?)\b', re.I)
DAYTON_CALIPER_RE = re.compile(r'\b(600-\d{3,4}[A-Z]?)\b', re.I)
DAYTON_KIT_RE = re.compile(r'\b(CH\d{4})\b', re.I)

# Part number patterns for Fort Pro catalog
FORT_PRO_PART_RE = re.compile(r'\b([A-Z]*\d{4,}[A-Z]*(?:-\d+)?)\b', re.I)
FORT_PRO_KIT_RE = re.compile(r'\b(KIT[-_]?\d+|PK[-_]?\d+)\b', re.I)
FORT_PRO_ALPHANUM_RE = re.compile(r'\b([A-Z]{2,}\d{3,}[A-Z]*)\b')

# Caterpillar-specific part number patterns
CAT_PART_RE = re.compile(r'\b(FP-[A-Z0-9-]+)\b')
CAT_NUMERIC_PART_RE = re.compile(r'\b(\d{6,7}[A-Z]?)\b')
CAT_ENGINE_ARR_RE = re.compile(r'\b([A-Z0-9]{4,7})\b')

# Manual TOC structures for each catalog
DAYTON_TOC = [
    ("Introduction", 1),
    ("Hydraulic Brake Components", 2),
    ("Table of Contents", 3),
    ("Disc Brake Pads", 4),
    ("Hydraulic Disc Brakes", 10),
    ("Disc Brake Calipers", 43),
    ("Light Duty Rotors", 50),
    ("Shim Kits Service Instructions", 38),
    ("Caliper Illustrations", 44),
    ("Carrier Specifications", 49)
]

FORT_PRO_TOC = [
    ("Cover Page", 1),
    ("Table of Contents", 2),
    ("Introduction", 3),
    ("Product Categories", 4),
    ("Heavy Duty Parts Overview", 5),
    ("Technical Specifications", 10),
    ("Application Guide", 15),
    ("Installation Instructions", 20),
    ("Maintenance", 25),
    ("Troubleshooting", 30),
    ("Warranty", 35)
]

CATERPILLAR_TOC = [
    ("Cover Page", 1),
    ("Blank Page", 2),
    ("Machine Section Instructions", 3),
    ("Blank Page", 4),
    ("Machine Section Index", 5),
    ("D3 Tractors", 6),
    ("D4 Tractors", 6),
    ("D5 Tractors", 12),
    ("D6 Tractors", 16),
    ("D7 Tractors", 22),
    ("D8 Tractors", 26),
    ("D9 Tractors", 28),
    ("D10-D11 Tractors", 32),
    ("Articulated Dump Trucks", 32),
    ("Backhoe Loaders", 50),
    ("Compactors & Wheel Tractors", 68),
    ("Excavators", 34),
    ("Integrated Tool Carriers", 34),
    ("Lift Trucks", 36),
    ("Motor Graders", 36),
    ("Pipelayers", 52),
    ("Scrapers", 56),
    ("Skidders", 50),
    ("Track Loaders", 74),
    ("Off-Highway Trucks", 66),
    ("Wheel Loaders", 72)
]

def detect_catalog_type(pdf_path, first_page_text):
    """Detect the type of catalog based on content and filename"""
    pdf_name = Path(pdf_path).name.lower()
    first_page_lower = first_page_text.lower()
    
    # Check for Caterpillar indicators
    if any(indicator in first_page_lower for indicator in ['caterpillar', 'cat ', 'fp-']):
        return 'caterpillar'
    elif 'caterpillar' in pdf_name or 'cat_' in pdf_name:
        return 'caterpillar'
    
    # Check for Dayton indicators
    elif any(indicator in first_page_lower for indicator in ['dayton', 'hydraulic brake']):
        return 'dayton'
    elif 'dayton' in pdf_name:
        return 'dayton'
    
    # Check for Fort Pro indicators
    elif any(indicator in first_page_lower for indicator in ['fort pro', 'fortpro', 'heavy duty parts']):
        return 'fort_pro'
    elif any(indicator in pdf_name for indicator in ['fort', 'heavy_duty', 'heavy-duty']):
        return 'fort_pro'
    
    else:
        # Try to detect based on content patterns
        if re.search(r'\b(FP-[A-Z0-9]+|\d{6,7}[A-Z]?)\b', first_page_text):
            return 'caterpillar'
        elif re.search(r'\b(D\d{2,4}|600-\d{3,4}|CH\d{4})\b', first_page_text):
            return 'dayton'
        elif re.search(r'\b([A-Z]*\d{4,}[A-Z]*|KIT[-_]?\d+)\b', first_page_text):
            return 'fort_pro'
        else:
            print(f"Warning: Could not auto-detect catalog type for {pdf_path}. Defaulting to Dayton.")
            return 'dayton'

def get_catalog_specs(catalog_type):
    """Return the appropriate patterns and TOC for the catalog type"""
    if catalog_type == 'dayton':
        return {
            'patterns': [
                (DAYTON_PART_RE, 'part'),
                (DAYTON_CALIPER_RE, 'caliper'),
                (DAYTON_KIT_RE, 'kit')
            ],
            'toc': DAYTON_TOC,
            'name': 'Dayton'
        }
    elif catalog_type == 'fort_pro':
        return {
            'patterns': [
                (FORT_PRO_PART_RE, 'part'),
                (FORT_PRO_KIT_RE, 'kit'),
                (FORT_PRO_ALPHANUM_RE, 'part')
            ],
            'toc': FORT_PRO_TOC,
            'name': 'Fort Pro'
        }
    elif catalog_type == 'caterpillar':
        return {
            'patterns': [
                (CAT_PART_RE, 'part'),  # Using 'part' instead of 'fp_part' to match db constraints
                (CAT_NUMERIC_PART_RE, 'part'),  # Using 'part' instead of 'numeric_part'
                (CAT_ENGINE_ARR_RE, 'part')  # Using 'part' instead of 'engine_arrangement'
            ],
            'toc': CATERPILLAR_TOC,
            'name': 'Caterpillar'
        }
    else:
        return get_catalog_specs('dayton')  # Default fallback

def extract_toc(pdf, catalog_type):
    """Use manual TOC based on catalog type"""
    specs = get_catalog_specs(catalog_type)
    print(f"Using manual TOC structure for {specs['name']} catalog")
    
    # Try to extract from actual TOC page if available
    try:
        for i, page in enumerate(pdf.pages[:5]):
            toc_text = page.extract_text() or ""
            toc_lower = toc_text.lower()
            
            if catalog_type == 'caterpillar':
                if 'machine section index' in toc_lower:
                    print(f"Found Machine Section Index on page {i+1}")
                    models_found = re.findall(r'\b(D[0-9]+|9[0-9]{2})\b', toc_text)
                    if models_found:
                        print(f"Sample models found: {list(set(models_found))[:10]}")
                    break
            else:
                if 'table of contents' in toc_lower or 'contents' in toc_lower:
                    print(f"Found TOC on page {i+1}:")
                    for line in toc_text.split('\n')[:8]:
                        cleaned_line = re.sub(r'\s+', ' ', line.strip())
                        print(f"  {cleaned_line}")
                    break
    except Exception as e:
        print(f"Could not read TOC pages: {e}")
    
    return specs['toc']

def assign_section(page_number, toc_entries):
    """Assign a page to a section based on TOC page ranges."""
    if not toc_entries:
        return "Uncategorized"
    
    current_section = toc_entries[0][0]
    current_start = toc_entries[0][1]
    
    for section_name, start_page in toc_entries:
        if page_number >= start_page and start_page >= current_start:
            current_section = section_name
            current_start = start_page
    
    return current_section

def extract_machine_info(text):
    """Extract machine model and serial number information from page text (Caterpillar specific)."""
    machine_info = {}
    
    model_matches = re.findall(r'\b(D[0-9]+|[0-9]{3}[A-Z]?)\b', text)
    if model_matches:
        machine_info['models'] = list(set(model_matches))
    
    serial_ranges = re.findall(r'(\d+[A-Z]*)\s+(\d+[A-Z]*)', text)
    if serial_ranges:
        machine_info['serial_ranges'] = serial_ranges[:5]
    
    engine_arrangements = re.findall(r'\b([A-Z0-9]{4,7})\b', text)
    if engine_arrangements:
        machine_info['engine_arrangements'] = list(set(engine_arrangements))[:10]
    
    return machine_info

def extract_part_info(text, page_number, catalog_type):
    """Extract part numbers and their context from page text."""
    specs = get_catalog_specs(catalog_type)
    parts_found = []
    
    for pattern, part_type in specs['patterns']:
        for match in pattern.finditer(text):
            part_num = match.group(1).upper()
            
            # Catalog-specific filtering
            if catalog_type == 'caterpillar':
                if len(part_num) < 4:
                    continue
                if part_num.isdigit():
                    part_num_int = int(part_num)
                    if part_num_int < 100000 or part_num_int > 9999999:
                        continue
            else:  # Dayton and Fort Pro
                if len(part_num) < 3:
                    continue
                if part_num.isdigit() and len(part_num) > 6:
                    continue
                if part_num.isdigit() and int(part_num) < 1000:
                    continue
            
            # Find context line
            lines = text.split('\n')
            context = ""
            for line in lines:
                if part_num in line:
                    context = re.sub(r'\s+', ' ', line.strip())[:200]
                    break
            
            if not context:
                context = text[:100]
                
            parts_found.append((part_type, part_num, context))
    
    return parts_found

def insert_part(conn, catalog_type, part_type, part_number, description, page, image_path, page_text, pdf_path, category=None):
    """Insert part into database with proper constraints"""
    cur = conn.cursor()
    
    # Check if part already exists
    cur.execute("SELECT id FROM parts WHERE part_number=? AND page=? AND part_type=? AND catalog_type=?", 
                (part_number, page, part_type, catalog_type))
    if cur.fetchone():
        return
    
    # Ensure part_type is valid according to database constraints
    valid_part_types = ['part', 'caliper', 'kit', 'other']
    if part_type not in valid_part_types:
        part_type = 'part'  # Default to 'part' if invalid
    
    # Insert into parts table
    cur.execute("""
        INSERT INTO parts (catalog_type, part_type, part_number, description, category, page, image_path, page_text, pdf_path)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (catalog_type, part_type, part_number, description, category, page, 
         str(image_path) if image_path else None, page_text, str(pdf_path) if pdf_path else None))
    
    return cur.lastrowid

def copy_pdf_to_pdfs_dir(pdf_path):
    """Copy PDF to PDFs directory for web server access"""
    try:
        target_path = PDF_DIR / pdf_path.name
        import shutil
        shutil.copy2(pdf_path, target_path)
        print(f"Copied PDF to: {target_path}")
        return target_path
    except Exception as e:
        print(f"Warning: Could not copy PDF to PDFs directory: {e}")
        return pdf_path

def extract(pdf_path, dpi=150, skip_image=False, max_pages=None):
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    # Copy PDF to PDFs directory for web access
    pdf_copy_path = copy_pdf_to_pdfs_dir(pdf_path)

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
            specs = get_catalog_specs(catalog_type)
            
            print(f"Processing {specs['name']} catalog: {pdf_path.name}")

            toc_entries = extract_toc(pdf, catalog_type)

            pages_imgs = None
            if not skip_image:
                try:
                    pages_imgs = convert_from_path(
                        str(pdf_path),
                        dpi=dpi,
                        poppler_path=r"C:\Users\kpecco\Desktop\codes\poppler-25.07.0\Library\bin"
                    )
                except Exception as e:
                    print(f"Image conversion failed: {e}. Continuing without images.")
                    pages_imgs = None

            # Process each page
            for i in tqdm(range(total_pages), desc="Pages"):
                page_index = i + 1
                page = pdf.pages[i]
                
                try:
                    text = page.extract_text() or ""
                    if not text.strip():
                        continue
                except:
                    print(f"Could not extract text from page {page_index}")
                    continue

                # Assign category from TOC
                category = assign_section(page_index, toc_entries)

                # Save page image
                image_path = None
                if pages_imgs and i < len(pages_imgs):
                    try:
                        pil_img = pages_imgs[i]
                        image_filename = f"{catalog_type}_{pdf_path.stem}_page_{page_index:04d}.png"
                        image_path = IMAGES_DIR / image_filename
                        pil_img.save(image_path, format="PNG")
                    except Exception as e:
                        print(f"Failed to save image for page {page_index}: {e}")

                # Extract parts from this page
                parts_info = extract_part_info(text, page_index, catalog_type)
                
                # For Caterpillar, also extract machine info
                if catalog_type == 'caterpillar':
                    machine_info = extract_machine_info(text)
                    if machine_info.get('models'):
                        print(f"Page {page_index} -> Category: {category} - Models: {machine_info['models']}")

                if parts_info:
                    print(f"Page {page_index} -> Category: {category} - Found {len(parts_info)} parts")
                    for part_type, part_num, context in parts_info:
                        insert_part(conn, catalog_type, part_type, part_num, context, page_index, 
                                   image_path, text[:2000], pdf_copy_path, category)
                else:
                    print(f"Page {page_index} -> Category: {category} - No parts found")

        conn.commit()
    print(f"Extraction complete for {specs['name']} catalog.")

def process_multiple_pdfs(pdf_paths, dpi=150, skip_images=False, max_pages=None):
    """Process multiple PDF files"""
    for pdf_path in pdf_paths:
        try:
            extract(pdf_path, dpi=dpi, skip_image=skip_images, max_pages=max_pages)
        except Exception as e:
            print(f"Error processing {pdf_path}: {e}")
            continue

def check_database_schema():
    """Verify that the database schema matches expectations"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Check if parts table exists and has required columns
        cur.execute("PRAGMA table_info(parts)")
        columns = {column[1]: column for column in cur.fetchall()}
        
        required_columns = ['catalog_type', 'part_type', 'part_number', 'pdf_path']
        missing_columns = [col for col in required_columns if col not in columns]
        
        if missing_columns:
            print(f"Error: Database missing required columns: {missing_columns}")
            print("Please run db_setup.py first to create the database schema.")
            return False
            
        # Check if FTS table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='parts_fts'")
        if not cur.fetchone():
            print("Error: FTS table 'parts_fts' does not exist.")
            print("Please run db_setup.py first to create the database schema.")
            return False
            
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error checking database schema: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract parts from PDF with TOC categories")
    parser.add_argument("pdf", nargs="+", help="path to PDF file(s)")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--skip-images", action="store_true")
    parser.add_argument("--max-pages", type=int, default=None)
    args = parser.parse_args()
    
    # Check database schema before processing
    if not check_database_schema():
        print("\nTo set up the database, run: python db_setup.py")
        exit(1)
    
    process_multiple_pdfs(args.pdf, dpi=args.dpi, skip_images=args.skip_images, max_pages=args.max_pages)