# guide_manager.py
import os
import json
import sqlite3
from datetime import datetime
from s3_manager import S3Manager
from config import Config

class TechnicalGuideManager:
    def __init__(self):
        self.config = Config()
        self.s3_manager = S3Manager()
        self.guides_dir = self.config.GUIDES_DIR
        
        # Ensure local directories exist
        os.makedirs(self.guides_dir, exist_ok=True)
        
        # Initialize storage
        self.s3_manager.create_bucket_if_not_exists()
        
    def initialize_default_guides(self):
        """Initialize default technical guide templates"""
        default_guides = {
            "installation_guide": {
                "name": "Installation Guide",
                "description": "Standard installation procedures for hydraulic brakes",
                "category": "installation",
                "template_fields": ["product_name", "model", "installation_steps", "torque_specs"]
            },
            "maintenance_manual": {
                "name": "Maintenance Manual", 
                "description": "Routine maintenance and service procedures",
                "category": "maintenance",
                "template_fields": ["product_name", "service_intervals", "lubrication_points", "inspection_checklist"]
            },
            "troubleshooting_guide": {
                "name": "Troubleshooting Guide",
                "description": "Diagnostic procedures and solutions for common issues",
                "category": "troubleshooting", 
                "template_fields": ["symptoms", "possible_causes", "solutions", "preventive_measures"]
            },
            "technical_specification": {
                "name": "Technical Specification",
                "description": "Detailed technical specifications and performance data",
                "category": "specifications",
                "template_fields": ["dimensions", "materials", "performance_data", "environmental_ratings"]
            }
        }
        
        # Store guide metadata in database
        conn = sqlite3.connect(self.config.DB_PATH)
        cur = conn.cursor()
        
        # Insert default guides
        for guide_key, guide_info in default_guides.items():
            cur.execute("""
                INSERT OR REPLACE INTO technical_guides 
                (guide_name, display_name, description, category, template_fields)
                VALUES (?, ?, ?, ?, ?)
            """, (
                guide_key,
                guide_info['name'],
                guide_info['description'],
                guide_info['category'],
                json.dumps(guide_info['template_fields'])
            ))
        
        conn.commit()
        conn.close()
        
        print("Initialized default technical guides metadata")
    
    def get_available_guides(self):
        """Get list of available technical guides"""
        conn = sqlite3.connect(self.config.DB_PATH)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT guide_name, display_name, description, category, template_fields
            FROM technical_guides 
            WHERE is_active = 1
            ORDER BY display_name
        """)
        
        guides = []
        for row in cur.fetchall():
            guides.append({
                'guide_name': row[0],
                'display_name': row[1],
                'description': row[2],
                'category': row[3],
                'template_fields': json.loads(row[4]) if row[4] else []
            })
        
        conn.close()
        return guides
    
    def load_guide(self, guide_name, use_cache=True):
        """Load a technical guide"""
        local_path = os.path.join(self.guides_dir, f"{guide_name}.pdf")
        
        # Return cached version if exists and caching is enabled
        if use_cache and os.path.exists(local_path):
            return local_path
        
        # Download from storage
        downloaded_path = self.s3_manager.download_technical_guide(
            guide_name, 
            local_path
        )
        
        return downloaded_path if downloaded_path else None