# init_system.py
from guide_manager import TechnicalGuideManager
from db_setup import add_technical_guides_table

def initialize_system():
    """Initialize the complete system with S3 and technical guides"""
    print("Initializing Knowledge Base...")
    
    # Add technical guides table to database
    add_technical_guides_table()
    
    # Initialize technical guides
    guide_manager = TechnicalGuideManager()
    guide_manager.initialize_default_guides()
    
    print("System initialization complete!")
    print("Available technical guides:")
    for guide in guide_manager.get_available_guides():
        print(f"  - {guide['display_name']} ({guide['category']})")

if __name__ == "__main__":
    initialize_system()