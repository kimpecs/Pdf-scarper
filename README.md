```markdown
# PDF Parts Catalog Scraper & Search API

A complete system for extracting, organizing, and searching hydraulic brake parts from PDF catalogs with a web-based interface.

## 🎯 What This Project Does

This system transforms unstructured PDF parts catalogs into a searchable database with a web interface. It's specifically designed for hydraulic brake components, Fort-pro and Fp Caterpiller but it will be adapted for other part catalogs.

### Core Workflow:
1. **PDF Processing** → Extract part numbers, descriptions, and pages from catalog PDFs
2. **Data Organization** → Categorize parts using table of contents and intelligent pattern matching
3. **Web Interface** → Provide searchable API and web interface for part lookup
4. **PDF Integration** → Link parts directly to their source PDF pages

## 📁 Project Structure

```
TESTING/
├── app_toc.py              # FastAPI web server & search API
├── db_setup.py             # Database schema creation
├── extract_pdf_toc_fixed.py # PDF processing & data extraction
├── run_server.py           # Server startup script
├── catalog.db              # SQLite database (generated)
├── requirements.txt        # Python dependencies
├── static/                 # Web interface files
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── pdfs/                   # Source PDF files (not tracked in Git)
├── page_images/           # Extracted page images (not tracked)
└── venv/                  # Python virtual environment (not tracked)
```

Here's the updated section with the direct Poppler download link:

```markdown
## 🚀 Quick Start

### 1. Installation
```bash
# Clone repository
git clone https://github.com/kimpecs/Pdf-scarper.git
cd Pdf-scarper

# Install dependencies
pip install -r requirements.txt

# Install Poppler for image(page) conversion (REQUIRED for PDF processing)
# Download from: https://github.com/oschwartz10612/poppler-windows/releases/
# Download the latest release (e.g., poppler-25.07.0-Linux-x86_64.zip)
# Extract to C:\Users\YourUsername\Desktop\codes\poppler-25.07.0
# The extract_pdf_toc_fixed.py already points to: C:\Users\kpecco\Desktop\codes\poppler-25.07.0\Library\bin
```

### Direct Poppler Download:
**Windows Users:** Download from:  
📦 **https://github.com/oschwartz10612/poppler-windows/releases/download/v25.07.0/poppler-25.07.0_Linux-x86_64.zip**

**Installation Steps:**
1. Download the zip file from the link above
2. Extract it to: `C:\Users\YourUsername\Desktop\codes\poppler-25.07.0`
3. Update the path in `extract_pdf_toc_fixed.py` if needed:
   ```python
   pages_imgs = convert_from_path(
       str(pdf_path),
       dpi=dpi,
       poppler_path=r"C:\Users\YourUsername\Desktop\codes\poppler-25.07.0\Library\bin"
   )
   ```

**Alternative Locations:**
- You can extract Poppler anywhere and update the path in the code
- Or add the Poppler `bin` folder to your system PATH

**Without Poppler:** Use `--skip-images` flag to process without page images:
```bash
python extract_pdf_toc_fixed.py --skip-images "your_catalog.pdf"
```

### 2. Database Setup
```bash
# Create database schema
python db_setup.py
```

### 3. Process PDF Catalogs
```bash
# Extract parts from PDFs (supports multiple files)
python extract_pdf_toc_fixed.py "Dayton_Hydraulic_Brakes.pdf" "FP_Caterpillar.pdf"

# Options:
python extract_pdf_toc_fixed.py --dpi 150 --skip-images --max-pages 50 "your_catalog.pdf"
```

### 4. Start Web Server
```bash
# Start the search API and web interface
python run_server.py
# or
python app_toc.py
```

Visit: http://localhost:8000

## 🔧 How It Works

### PDF Processing Pipeline:
1. **Catalog Detection** - Automatically detects catalog type (Dayton, Fort Pro, Caterpillar)
2. **TOC Analysis** - Uses manual table of contents structures to categorize pages
3. **Part Extraction** - Regex patterns identify part numbers in context:
   - Dayton: `D50`, `600-123A`, `CH1234`
   - Fort Pro: `KIT-100`, `PK200`, alphanumeric codes
   - Caterpillar: `FP-123456`, engine arrangements, numeric parts
4. **Image Generation** - Converts PDF pages to PNG for visual reference
5. **Database Storage** - Stores parts with categories, page numbers, and PDF links

### Supported Catalog Types:
- **Dayton Hydraulic Brakes**: Disc brakes, calipers, rotors, kits
- **Fort Pro Heavy Duty**: Heavy-duty components and kits  
- **Caterpillar Equipment**: Machine-specific parts and arrangements

## 🌐 Web API Endpoints

### Search & Browse:
- `GET /` - Web interface
- `GET /search?q=D50` - Search parts
- `GET /categories` - List all categories
- `GET /part_types` - List part types
- `GET /catalogs` - List catalog types

### System Info:
- `GET /health` - Server status
- `GET /test` - Detailed system diagnostics

### File Access:
- `GET /pdfs/{filename}#page=123` - View PDF at specific page
- `GET /images/{filename}` - View page images

## 💾 Data Model

```sql
parts:
- id (PK)
- catalog_type ('dayton', 'fort_pro', 'caterpillar')  
- part_type ('part', 'caliper', 'kit', 'other')
- part_number (D50, 600-123, FP-123456)
- description (context from PDF)
- category (from TOC)
- page (PDF page number)
- image_path (page screenshot)
- pdf_path (source PDF file)
- page_text (OCR text content)
```

## 🛠️ Advanced Usage

### Custom Catalog Support:
Modify `extract_pdf_toc_fixed.py` to add:
- New TOC structures in `*_TOC` constants
- Part number patterns in `*_PART_RE` regexes
- Catalog detection logic in `detect_catalog_type()`

### Search Features:
- **Full-text search** across part numbers, descriptions, and page text
- **Filter by category**, part type, or catalog
- **PDF deep linking** - click results to open PDF at correct page

### Database Inspection:
```bash
python check_db.py  # Simple database query tool
sqlite3 catalog.db  # Direct database access
```

## 📊 Example Queries

```bash
# Web interface
http://localhost:8000/search?q=D50
http://localhost:8000/search?category="Disc Brake Calipers"
http://localhost:8000/search?catalog_type=dayton&part_type=caliper

# API responses
{
  "query": "D50",
  "count": 15,
  "results": [
    {
      "part_number": "D50",
      "description": "D50 Disc Brake Pad Set",
      "category": "Disc Brake Pads", 
      "page": 45,
      "pdf_url": "/pdfs/Dayton_Hydraulic_Brakes.pdf#page=45",
      "image_url": "/images/dayton_Dayton_Hydraulic_page_0045.png"
    }
  ]
}
```

## ⚠️ Important Notes

- **Large files** (PDFs, images, database) are excluded from Git via `.gitignore`
- **Poppler required** for PDF-to-image conversion on Windows
- **Process PDFs locally** then deploy database and code to production
- **Catalog-specific patterns** may need tuning for new PDF formats

## 🔍 Troubleshooting

See `GET /test` endpoint for system diagnostics including:
- Database connectivity
- File locations
- Sample parts data
- Static file availability

## 👥 Contributing

1. Process PDFs locally (keep large files out of Git)
2. Test with `python run_server.py` 
3. Verify all API endpoints work
4. Submit pull request with code changes only
```