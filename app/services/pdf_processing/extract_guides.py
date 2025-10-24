import pdfplumber
import fitz  # PyMuPDF
import re
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
import sys

# Add the project root to Python path for absolute imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from app.utils.logger import setup_logging
from app.services.db.queries import DatabaseManager

logger = setup_logging()

class GuideExtractor:
    def __init__(self):
        self.technical_terms = [
            'specification', 'specifications', 'technical', 'manual', 'guide',
            'operation', 'maintenance', 'troubleshooting', 'installation',
            'procedure', 'procedures', 'diagram', 'schematic', 'wiring',
            'hydraulic', 'pneumatic', 'electrical', 'mechanical'
        ]
        
        self.spec_patterns = [
            r'(\w+)\s*[=:]\s*([\d\.]+)\s*(\w+)',  # Key = Value Unit
            r'([\d\.]+)\s*(\w+)\s*([\w\s]+)',     # Value Unit Key
            r'(\w+)\s*[-–]\s*([\d\.]+)\s*(\w+)',  # Key - Value Unit
        ]
    
    def process_guide_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Process technical guide PDF and extract structured information
        
        Args:
            pdf_path: Path to the guide PDF file
            
        Returns:
            Dictionary containing guide metadata and extracted data
        """
        guide_data = {
            'guide_name': Path(pdf_path).stem,
            'display_name': self._generate_display_name(Path(pdf_path).stem),
            'description': '',
            'category': self._detect_category(Path(pdf_path).stem),
            'template_fields': {},
            'sections': [],
            'specifications': {}
        }
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                first_page_text = pdf.pages[0].extract_text() or ""
                
                # Extract guide description from first page
                guide_data['description'] = self._extract_description(first_page_text)
                
                # Process all pages for content
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ""
                    if not text.strip():
                        continue
                    
                    # Extract sections and specifications
                    sections = self._extract_sections(text, page_num)
                    specs = self._extract_specifications(text)
                    
                    guide_data['sections'].extend(sections)
                    guide_data['specifications'].update(specs)
                
                # Generate template fields from extracted data
                guide_data['template_fields'] = self._generate_template_fields(guide_data)
                
            logger.info(f"Processed technical guide: {guide_data['guide_name']}")
            
        except Exception as e:
            logger.error(f"Error processing guide {pdf_path}: {e}")
        
        return guide_data
    
    def _generate_display_name(self, filename: str) -> str:
        """Generate a user-friendly display name from filename"""
        # Remove common file prefixes and clean up
        name = filename.replace('_', ' ').replace('-', ' ')
        
        # Capitalize words
        name = ' '.join(word.capitalize() for word in name.split())
        
        # Add "Technical Guide" if not present
        if not any(term in name.lower() for term in ['guide', 'manual', 'spec']):
            name += ' Technical Guide'
        
        return name
    
    def _detect_category(self, filename: str) -> str:
        """Detect guide category from filename"""
        filename_lower = filename.lower()
        
        if any(term in filename_lower for term in ['engine', 'motor', 'diesel']):
            return 'Engine'
        elif any(term in filename_lower for term in ['brake', 'hydraulic']):
            return 'Brake System'
        elif any(term in filename_lower for term in ['crane', 'lift', 'hoist']):
            return 'Equipment'
        elif any(term in filename_lower for term in ['electrical', 'wiring']):
            return 'Electrical'
        elif any(term in filename_lower for term in ['spec', 'specification']):
            return 'Specifications'
        else:
            return 'Technical Documentation'
    
    def _extract_description(self, first_page_text: str) -> str:
        """Extract description from first page text"""
        lines = first_page_text.split('\n')
        description_lines = []
        
        for line in lines:
            line = line.strip()
            if len(line) > 20 and not line.isupper():  # Skip headers and short lines
                description_lines.append(line)
                if len(description_lines) >= 3:  # Take first 3 meaningful lines
                    break
        
        return ' '.join(description_lines)[:500]  # Limit length
    
    def _extract_sections(self, text: str, page_num: int) -> List[Dict[str, Any]]:
        """Extract document sections from text"""
        sections = []
        lines = text.split('\n')
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            
            # Detect section headers (typically short, capitalized, or numbered)
            if (len(line) < 100 and 
                (line.isupper() or 
                 re.match(r'^\d+\.', line) or
                 re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$', line))):
                
                if current_section:
                    sections.append(current_section)
                
                current_section = {
                    'title': line,
                    'page': page_num,
                    'content': ''
                }
            elif current_section:
                current_section['content'] += line + ' '
        
        if current_section:
            sections.append(current_section)
        
        return sections
    
    def _extract_specifications(self, text: str) -> Dict[str, Any]:
        """Extract technical specifications from text"""
        specs = {}
        
        for pattern in self.spec_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match.groups()) >= 2:
                    key = match.group(1).strip()
                    value = match.group(2).strip()
                    
                    # Clean up the key and value
                    key = self._clean_spec_key(key)
                    if self._is_valid_spec(key, value):
                        specs[key] = value
        
        return specs
    
    def _clean_spec_key(self, key: str) -> str:
        """Clean specification key"""
        key = key.lower().strip()
        
        # Common replacements
        replacements = {
            'max': 'maximum',
            'min': 'minimum',
            'temp': 'temperature',
            'volt': 'voltage',
            'amp': 'amperage',
            'rpm': 'speed',
            'psi': 'pressure',
            'hp': 'horsepower'
        }
        
        for short, full in replacements.items():
            if short in key:
                key = key.replace(short, full)
        
        return key.capitalize()
    
    def _is_valid_spec(self, key: str, value: str) -> bool:
        """Validate if extracted specification is meaningful"""
        # Skip very short keys or numeric-only keys
        if len(key) < 2 or key.isdigit():
            return False
        
        # Skip common false positives
        false_positives = ['page', 'figure', 'table', 'chapter', 'section']
        if key in false_positives:
            return False
        
        return True
    
    def _generate_template_fields(self, guide_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate template fields for guide document generation"""
        template_fields = {
            'guide_title': guide_data['display_name'],
            'description': guide_data['description'],
            'category': guide_data['category'],
            'sections': guide_data['sections'][:5],  # Limit to first 5 sections
            'key_specifications': dict(list(guide_data['specifications'].items())[:10]),  # Top 10 specs
            'created_date': None,  # Will be filled during document generation
            'document_id': None,   # Will be filled during document generation
        }
        
        return template_fields
    
    def save_guide_to_database(self, guide_data: Dict[str, Any]) -> int:
        """Save extracted guide data to database"""
        db_manager = DatabaseManager()
        
        try:
            # Convert template_fields to JSON string for storage
            template_fields_json = json.dumps(guide_data['template_fields'])
            
            # Insert into technical_guides table
            conn = db_manager.get_connection()
            cur = conn.cursor()
            
            cur.execute("""
                INSERT OR REPLACE INTO technical_guides 
                (guide_name, display_name, description, category, template_fields)
                VALUES (?, ?, ?, ?, ?)
            """, (
                guide_data['guide_name'],
                guide_data['display_name'],
                guide_data['description'],
                guide_data['category'],
                template_fields_json
            ))
            
            guide_id = cur.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"Saved guide to database: {guide_data['guide_name']} (ID: {guide_id})")
            return guide_id
            
        except Exception as e:
            logger.error(f"Error saving guide to database: {e}")
            return -1