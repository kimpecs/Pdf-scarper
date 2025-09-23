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
IMAGES_DIR.mkdir(exist_ok=True)

# Part number patterns for Dayton catalog
DAYTON_PART_RE = re.compile(r'\b(D\d{2,4}(?:-\d+)?)\b', re.I)  # Matches D50, D52, D120, etc.
DAYTON_CALIPER_RE = re.compile(r'\b(600-\d{3,4}[A-Z]?)\b', re.I)  # Matches 600-216, 600-905F, etc.
DAYTON_KIT_RE = re.compile(r'\b(CH\d{4})\b', re.I)  # Matches CH5500, CH5584, etc.

# Part number patterns for Fort Pro catalog (based on heavy duty parts)
FORT_PRO_PART_RE = re.compile(r'\b([A-Z]*\d{4,}[A-Z]*(?:-\d+)?)\b', re.I)  # Matches 4+ digit numbers with optional prefix/suffix
FORT_PRO_KIT_RE = re.compile(r'\b(KIT[-_]?\d+|PK[-_]?\d+)\b', re.I)  # Matches KIT-123, PK_456, etc.
FORT_PRO_ALPHANUM_RE = re.compile(r'\b([A-Z]{2,}\d{3,}[A-Z]*)\b')  # Matches alphanumeric codes like ABC1234

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

# Generic TOC for Fort Pro Heavy Duty Parts catalog
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

def detect_catalog_type(pdf_path, first_page_text):
    """Detect whether this is a Dayton or Fort Pro catalog"""
    pdf_name = Path(pdf_path).name.lower()
    first_page_lower = first_page_text.lower()
    
    # Check for Dayton indicators
    if 'dayton' in first_page_lower or 'hydraulic brake' in first_page_lower:
        return 'dayton'
    # Check for Fort Pro indicators
    elif 'fort pro' in first_page_lower or 'fortpro' in first_page_lower or 'heavy duty parts' in first_page_lower:
        return 'fort_pro'
    # Default based on filename
    elif 'dayton' in pdf_name:
        return 'dayton'
    elif 'fort' in pdf_name or 'heavy_duty' in pdf_name:
        return 'fort_pro'
    else:
        # Try to detect based on content patterns
        if re.search(r'\b(D\d{2,4}|600-\d{3,4}|CH\d{4})\b', first_page_text):
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
    else:  # fort_pro
        return {
            'patterns': [
                (FORT_PRO_PART_RE, 'part'),
                (FORT_PRO_KIT_RE, 'kit'),
                (FORT_PRO_ALPHANUM_RE, 'part')
            ],
            'toc': FORT_PRO_TOC,
            'name': 'Fort Pro'
        }

def extract_toc(pdf, catalog_type):
    """Use manual TOC based on catalog type"""
    specs = get_catalog_specs(catalog_type)
    print(f"Using manual TOC structure for {specs['name']} catalog")
    
    # Try to extract from actual TOC page if available
    try:
        # Look for a table of contents page (usually early in document)
        for i, page in enumerate(pdf.pages[:5]):  # Check first 5 pages
            toc_text = page.extract_text() or ""
            if 'table of contents' in toc_text.lower() or 'contents' in toc_text.lower():
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
    
    # Default to first section
    current_section = toc_entries[0][0]
    current_start = toc_entries[0][1]
    
    # Find the section that starts before or equal to this page
    for section_name, start_page in toc_entries:
        if page_number >= start_page and start_page >= current_start:
            current_section = section_name
            current_start = start_page
    
    return current_section

def extract_part_info(text, page_number, catalog_type):
    """Extract part numbers and their context from page text."""
    specs = get_catalog_specs(catalog_type)
    parts_found = []
    
    for pattern, part_type in specs['patterns']:
        for match in pattern.finditer(text):
            part_num = match.group(1).upper()
            
            # Filter out obvious non-part numbers (page numbers, years, etc.)
            if len(part_num) < 3:  # Too short to be a part number
                continue
            if part_num.isdigit() and len(part_num) > 6:  # Probably a long number like a phone number
                continue
            if part_num.isdigit() and int(part_num) < 1000:  # Probably a page number or small number
                continue
                
            # Find context line (the line containing the part number)
            lines = text.split('\n')
            context = ""
            for line in lines:
                if part_num in line:
                    context = re.sub(r'\s+', ' ', line.strip())[:200]  # Clean up whitespace and limit length
                    break
            
            if not context:
                context = text[:100]  # Fallback context
                
            parts_found.append((part_type, part_num, context))
    
    return parts_found

def insert_part(conn, catalog_type, part_type, part_number, description, page, image_path, page_text, category=None):
    cur = conn.cursor()
    
    # Check if part already exists (more specific check including catalog type)
    cur.execute("SELECT id FROM parts WHERE part_number=? AND page=? AND part_type=? AND catalog_type=?", 
                (part_number, page, part_type, catalog_type))
    if cur.fetchone():
        return
    
    # Insert into parts table
    cur.execute("""
        INSERT INTO parts (catalog_type, part_type, part_number, description, category, page, image_path, page_text)
        VALUES (?,?,?,?,?,?,?,?)""",
        (catalog_type, part_type, part_number, description, category, page, str(image_path) if image_path else None, page_text))
    
    return cur.lastrowid

def extract(pdf_path, dpi=150, skip_image=False, max_pages=None):
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

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
                        continue  # Skip empty pages
                except:
                    print(f"Could not extract text from page {page_index}")
                    continue

                # Assign category from TOC
                category = assign_section(page_index, toc_entries)

                # Save page image with catalog-specific naming
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
                
                if parts_info:
                    print(f"Page {page_index} -> Category: {category} - Found {len(parts_info)} parts")
                    for part_type, part_num, context in parts_info:
                        insert_part(conn, catalog_type, part_type, part_num, context, page_index, 
                                   image_path, text[:2000], category)
                else:
                    print(f"Page {page_index} -> Category: {category} - No parts found")

        conn.commit()
    print(f"Extraction complete for {specs['name']} catalog. TOC-based categories applied.")

def process_multiple_pdfs(pdf_paths, dpi=150, skip_images=False, max_pages=None):
    """Process multiple PDF files"""
    for pdf_path in pdf_paths:
        try:
            extract(pdf_path, dpi=dpi, skip_image=skip_images, max_pages=max_pages)
        except Exception as e:
            print(f"Error processing {pdf_path}: {e}")
            continue

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract parts from PDF with TOC categories")
    parser.add_argument("pdf", nargs="+", help="path to PDF file(s)")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--skip-images", action="store_true")
    parser.add_argument("--max-pages", type=int, default=None)
    args = parser.parse_args()
    
    # Process all PDFs
    process_multiple_pdfs(args.pdf, dpi=args.dpi, skip_images=args.skip_images, max_pages=args.max_pages)