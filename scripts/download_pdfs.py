#!/usr/bin/env python3
"""
Download all PDFs from the provided URLs
"""
import requests
from pathlib import Path
import sys
from urllib.parse import urlparse
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.logger import setup_logging

logger = setup_logging()

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

def download_pdf(url: str, filename: str, download_dir: Path) -> bool:
    """Download a PDF from URL"""
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        filepath = download_dir / f"{filename}.pdf"
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Downloaded: {filename}.pdf ({filepath.stat().st_size / 1024 / 1024:.1f} MB)")
        return True
        
    except Exception as e:
        logger.error(f"Failed to download {filename}: {e}")
        return False

def main():
    """Download all PDFs"""
    download_dir = Path("app/data/pdfs")
    download_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Downloading PDFs to: {download_dir}")
    
    success_count = 0
    for name, url in PDF_URLS.items():
        if download_pdf(url, name, download_dir):
            success_count += 1
        time.sleep(1)  # Be nice to servers
    
    logger.info(f"Download completed: {success_count}/{len(PDF_URLS)} PDFs downloaded")

if __name__ == "__main__":
    main()