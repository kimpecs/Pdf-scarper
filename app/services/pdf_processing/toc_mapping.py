import re
from typing import List, Tuple
from app.utils.logger import setup_logging

logger = setup_logging()

class TOCMapper:
    def extract_toc(self, pdf) -> List[Tuple[str, int]]:
        """Extract table of contents from PDF"""
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
                    logger.info(f"Found TOC on page {i+1}")
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
                            title = re.sub(r'[\.\s]+$', '', title)
                            
                            if title and len(title) > 3 and page_num < 1000:
                                toc_entries.append((title, page_num))
                    break
                    
        except Exception as e:
            logger.error(f"Error extracting TOC: {e}")
        
        # If no TOC found, create basic structure
        if not toc_entries:
            toc_entries = [("Document", 1)]
        
        return toc_entries
    
    def assign_section(self, page_number: int, toc_entries: List[Tuple[str, int]]) -> str:
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