import os
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import sys
from fastapi import File, UploadFile 



# EXACT PATH: This file is in app/services/db/
script_dir = Path(__file__).parent  # app/services/db/
services_dir = script_dir.parent    # app/services/
app_dir = services_dir.parent       # app/
sys.path.insert(0, str(app_dir))

from utils.config import settings
from utils.logger import setup_logging

logger = setup_logging()

class DatabaseManager:
    def __init__(self):
        # Get DB path string from environment variable
        self.db_path = Path(r"C:\Users\kpecco\Desktop\codes\TESTING\app\data\catalog.db")
        logger.info(f"Using database at: {self.db_path}")

        # Resolve relative to the app directory
        db_path = Path(r"C:\Users\kpecco\Desktop\codes\TESTING\app\data\catalog.db")
        if not db_path.is_absolute():
            db_path = (app_dir / db_path).resolve()

        # Ensure directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        logger.info(f"Using database at: {self.db_path}")

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    
    def search_parts(self, query: str = None, category: str = None, 
                    part_type: str = None, catalog_name: str = None, 
                    limit: int = 100) -> List[Dict[str, Any]]:
        """Search parts with filters"""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        sql = """
            SELECT id, catalog_name, catalog_type, part_type, part_number,
                   description, category, page, image_path, pdf_path
            FROM parts WHERE 1=1
        """
        params = []
        
        if query:
            if query.upper().startswith(('D', '600-', 'CH')):
                sql += " AND part_number LIKE ?"
                params.append(f"{query}%")
            else:
                # FIX: Use proper FTS syntax
                sql += """ AND id IN (
                    SELECT rowid FROM parts_fts WHERE parts_fts MATCH ?
                )"""
                params.append(f"{query}*")
        
        if category:
            sql += " AND category = ?"
            params.append(category)
        
        if part_type:
            sql += " AND part_type = ?"
            params.append(part_type)
        
        if catalog_name:
            sql += " AND catalog_name = ?"
            params.append(catalog_name)
        
        sql += " ORDER BY part_number LIMIT ?"
        params.append(limit)
        
        cur.execute(sql, params)
        rows = cur.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_categories_with_counts(self) -> List[Dict[str, Any]]:
        """Get categories with part counts"""
        conn = self.get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT category, COUNT(*) as count
            FROM parts 
            WHERE category IS NOT NULL AND category != 'General'
            GROUP BY category 
            ORDER BY count DESC
        """)
        
        results = [{"name": row[0], "count": row[1]} for row in cur.fetchall()]
        conn.close()
        return results
    
    def get_part_by_id(self, part_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed part information"""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("""
            SELECT * FROM parts WHERE id = ?
        """, (part_id,))
        
        row = cur.fetchone()
        conn.close()
        
        if row:
            part = dict(row)
            # Parse JSON fields
            if part.get('machine_info'):
                part['machine_info'] = json.loads(part['machine_info'])
            return part
        return None
    
    def insert_part(self, part_data: Dict[str, Any]) -> int:
        """Insert a new part"""
        conn = self.get_connection()
        cur = conn.cursor()
        
        columns = []
        placeholders = []
        values = []
        
        for key, value in part_data.items():
            columns.append(key)
            placeholders.append('?')
            if isinstance(value, (dict, list)):
                values.append(json.dumps(value))
            else:
                values.append(value)
        
        sql = f"INSERT INTO parts ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        cur.execute(sql, values)
        part_id = cur.lastrowid
        conn.commit()
        conn.close()
        
        return part_id
    
    def get_technical_guides(self) -> List[Dict[str, Any]]:
        """Get all technical guides"""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM technical_guides WHERE is_active = 1")
        guides = [dict(row) for row in cur.fetchall()]
        conn.close()
        
        return guides
    def get_guides_for_part(self, part_number: str) -> List[Dict[str, Any]]:
        """Get all technical guides related to a specific part number"""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("""
            SELECT tg.*, gp.confidence_score
            FROM technical_guides tg
            JOIN guide_parts gp ON tg.id = gp.guide_id
            WHERE gp.part_number = ? AND tg.is_active = 1
            ORDER BY gp.confidence_score DESC
        """, (part_number,))
        
        guides = []
        for row in cur.fetchall():
            guide_data = dict(row)
            # Parse JSON fields
            if guide_data.get('template_fields'):
                guide_data['template_fields'] = json.loads(guide_data['template_fields'])
            if guide_data.get('related_parts'):
                guide_data['related_parts'] = json.loads(guide_data['related_parts'])
            guides.append(guide_data)
        
        conn.close()
        return guides

    def insert_technical_guide(self, guide_data: Dict[str, Any]) -> int:
        """Insert a new technical guide"""
        conn = self.get_connection()
        cur = conn.cursor()
        
        # Convert JSON fields to strings
        template_fields = json.dumps(guide_data.get('template_fields', {}))
        related_parts = json.dumps(guide_data.get('related_parts', []))
        
        cur.execute("""
            INSERT OR REPLACE INTO technical_guides 
            (guide_name, display_name, description, category, template_fields, pdf_path, related_parts)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            guide_data['guide_name'],
            guide_data['display_name'],
            guide_data.get('description'),
            guide_data.get('category'),
            template_fields,
            guide_data.get('pdf_path'),
            related_parts
        ))
        
        guide_id = cur.lastrowid
        conn.commit()
        conn.close()
        
        return guide_id

    def create_guide_part_association(self, guide_id: int, part_numbers: List[str]):
        """Create associations between guide and parts"""
        conn = self.get_connection()
        cur = conn.cursor()
        
        for part_number in part_numbers:
            cur.execute("""
                INSERT OR IGNORE INTO guide_parts (guide_id, part_number)
                VALUES (?, ?)
            """, (guide_id, part_number))
        
        conn.commit()
        conn.close()