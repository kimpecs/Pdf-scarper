from typing import Optional, Dict, Any, List
from pydantic import BaseModel

class Part(BaseModel):
    id: Optional[int] = None
    catalog_name: str
    catalog_type: Optional[str] = None
    part_type: Optional[str] = None
    part_number: str
    description: Optional[str] = None
    category: Optional[str] = None
    page: Optional[int] = None
    image_path: Optional[str] = None
    page_text: Optional[str] = None
    pdf_path: Optional[str] = None
    machine_info: Optional[Dict[str, Any]] = None
    specifications: Optional[str] = None
    oe_numbers: Optional[str] = None
    applications: Optional[str] = None
    features: Optional[str] = None

class TechnicalGuide(BaseModel):
    id: Optional[int] = None
    guide_name: str
    display_name: str
    description: Optional[str] = None
    category: Optional[str] = None
    s3_key: Optional[str] = None
    template_fields: Optional[Dict[str, Any]] = None
    is_active: bool = True