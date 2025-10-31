
```markdown
# Poppler Setup Instructions

## Windows Installation:

1. **Download Poppler:**
   - Go to: https://github.com/oschwartz10612/poppler-windows/releases
   - Download the latest release: `poppler-25.07.0_Linux-x86_64.zip`

2. **Extract Files:**
   - Create folder: `C:\Users\YourUsername\Desktop\codes\poppler-25.07.0`
   - Extract the zip contents to this folder

3. **Verify Structure:**
   ```
   poppler-25.07.0/
   ├── Library/
   │   └── bin/
   │       ├── pdftoppm.exe
   │       ├── pdfimages.exe
   │       └── ... (other PDF tools)
   ```

4. **Update Path (if needed):**
   - Open `extract_pdf_toc_fixed.py`
   - Find the `poppler_path` line (around line 390)
   - Update the path if you installed Poppler elsewhere:
   ```python
   poppler_path=r"C:\Users\YourUsername\Desktop\codes\poppler-25.07.0\Library\bin"
   ```

## Testing Poppler Installation:

```bash
# Test if Poppler works
python -c "
from pdf2image import convert_from_path
try:
    images = convert_from_path('test.pdf', poppler_path=r'C:\Users\YourUsername\Desktop\codes\poppler-25.07.0\Library\bin')
    print('[OK] Poppler working correctly!')
except Exception as e:
    print(f'[ERROR] Poppler error: {e}')
"
```

## Alternative: Skip Images

If Poppler setup fails, you can still use the system without images:

```bash
python extract_pdf_toc_fixed.py --skip-images "your_catalog.pdf"
```

This will still extract all part numbers and text, just without page screenshots.
```

The direct link I provided is for the specific version that my code is configured for. This will give users the best chance of first-try success!