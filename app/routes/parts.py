import json
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.db.queries import DatabaseManager
from app.utils.file_utils import get_pdf_url
from app.utils.logger import setup_logging

router = APIRouter(prefix="/api", tags=["Search"])

logger = setup_logging()
db = DatabaseManager()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def row_to_dict(row) -> dict:
    """Convert sqlite3.Row (or similar) to a plain dict."""
    if row is None:
        return {}
    try:
        return dict(row)
    except Exception:
        return {key: row[key] for key in row.keys()}


def get_image_url(image_path: Optional[str]) -> Optional[str]:
    """Return the URL path for a part image stored under /images/."""
    if not image_path:
        return None
    filename = Path(image_path.replace("\\", "/")).name
    return f"/images/{filename}"


def _extract_specifications_from_text(text: str) -> Dict:
    """Extract key-value specifications from free-form text."""
    specs: Dict[str, str] = {}
    patterns = [
        r'(\w+)\s*[=:]\s*([^,\n]+)',
        r'([^:]+):\s*([^\n]+)',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            key = match.group(1).strip()
            value = match.group(2).strip()
            if key and value and len(key) > 2:
                specs[key] = value
    return specs


def _format_cross_references(part: dict) -> List[Dict]:
    """Build a cross-reference list from part data."""
    cross_refs: List[Dict] = [
        {
            "oem": "Primary",
            "part_number": part.get("part_number", ""),
            "alias": "Main Part",
            "compatible_vehicles": "All compatible applications",
        }
    ]
    oe_numbers = part.get("oe_numbers", "")
    if oe_numbers:
        for oe in (o.strip() for o in oe_numbers.split(";") if o.strip()):
            cross_refs.append(
                {
                    "oem": "OEM",
                    "part_number": oe,
                    "alias": "Alternate",
                    "compatible_vehicles": "OE specification",
                }
            )
    return cross_refs


def _merge_template_data(enhanced: dict, template_data: dict) -> None:
    """Merge guide template fields into the enhanced part dict (in-place)."""
    if not enhanced["introduction"] and template_data.get("description"):
        enhanced["introduction"] = template_data["description"]

    for section in template_data.get("sections", []):
        title = section.get("title", "").lower()
        if "usage" in title or "application" in title:
            enhanced["usage_info"].append(section.get("content", ""))
        if "specification" in title:
            specs = _extract_specifications_from_text(section.get("content", ""))
            enhanced["specifications"].update(specs)

    if template_data.get("key_specifications"):
        enhanced["specifications"].update(template_data["key_specifications"])


def _merge_with_technical_guides(part: dict, guides: List[dict]) -> dict:
    """Merge part data with associated technical guide information."""
    enhanced = part.copy()
    enhanced["introduction"] = part.get("description", "")
    enhanced["usage_info"] = list(part.get("applications") or [])
    enhanced["specifications"] = {}
    enhanced["cross_references"] = []
    enhanced["technical_guides"] = []

    for guide in guides:
        enhanced["technical_guides"].append(
            {
                "id": guide["id"],
                "display_name": guide.get("display_name", guide.get("guide_name", "")),
                "description": guide.get("description", ""),
                "confidence_score": guide.get("confidence_score", 0.5),
            }
        )
        template_fields = guide.get("template_fields")
        if template_fields and isinstance(template_fields, str):
            try:
                _merge_template_data(enhanced, json.loads(template_fields))
            except (json.JSONDecodeError, TypeError):
                pass

    enhanced["cross_references"] = _format_cross_references(part)
    return enhanced


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@router.get("/search")
async def search_parts(
    q: Optional[str] = Query(None, description="Search term for part number or description"),
    category: Optional[str] = Query(None),
    part_type: Optional[str] = Query(None),
    catalog_type: Optional[str] = Query(None),
    content_type: str = Query("all"),
    limit: int = Query(50, ge=1, le=1000),
):
    if content_type == "guides":
        return {
            "query": q or "",
            "filters": {"category": category, "part_type": part_type,
                        "catalog_type": catalog_type, "content_type": content_type},
            "count": 0,
            "results": [],
        }

    try:
        results = db.search_parts(
            query=q,
            category=category,
            part_type=part_type,
            catalog_name=catalog_type,
            limit=limit,
        )

        formatted = []
        for row in results:
            part = row_to_dict(row)
            formatted.append(
                {
                    "id": part.get("id"),
                    "part_number": part.get("part_number"),
                    "description": part.get("description"),
                    "category": part.get("category"),
                    "part_type": part.get("part_type"),
                    "catalog_type": part.get("catalog_type"),
                    "page": part.get("page"),
                    "image_url": get_image_url(part.get("image_path")),
                    "pdf_url": get_pdf_url(part.get("pdf_path"), part.get("page", 1)),
                    "applications": [
                        a.strip()
                        for a in (part.get("applications") or "").split(";")
                        if a.strip()
                    ],
                }
            )

        return {
            "query": q or "",
            "filters": {"category": category, "part_type": part_type,
                        "catalog_type": catalog_type, "content_type": content_type},
            "count": len(formatted),
            "results": formatted,
        }

    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(500, f"Search failed: {str(e)}")


@router.get("/parts/{part_id}/enhanced")
async def get_enhanced_part_detail(part_id: int):
    """Get part details merged with technical guide information."""
    try:
        with db.connection() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            cur.execute("SELECT * FROM parts WHERE id = ?", (part_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Part not found")

            part = row_to_dict(row)

            cur.execute(
                """
                SELECT tg.*, pg.confidence_score
                FROM technical_guides tg
                JOIN part_guides pg ON tg.id = pg.guide_id
                WHERE pg.part_id = ? AND tg.is_active = 1
                ORDER BY pg.confidence_score DESC
                """,
                (part_id,),
            )
            guides = [row_to_dict(r) for r in cur.fetchall()]

        part["image_url"] = get_image_url(part.get("image_path"))
        part["applications"] = [
            a.strip()
            for a in (part.get("applications") or "").split(";")
            if a.strip()
        ]

        return _merge_with_technical_guides(part, guides)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching enhanced part {part_id}: {e}")
        raise HTTPException(500, f"Failed to fetch enhanced part: {str(e)}")


@router.get("/parts/{part_id}")
async def get_part_detail(part_id: int):
    try:
        with db.connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM parts WHERE id = ?", (part_id,)).fetchone()

        if not row:
            raise HTTPException(404, "Part not found")

        part = row_to_dict(row)
        part["image_url"] = get_image_url(part.get("image_path"))
        part["applications"] = [
            a.strip()
            for a in (part.get("applications") or "").split(";")
            if a.strip()
        ]
        return part

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching part {part_id}: {e}")
        raise HTTPException(500, f"Failed to fetch part: {str(e)}")


@router.get("/catalogs")
async def get_catalogs():
    try:
        catalog_types = db.get_distinct_catalog_types()
        return {"catalogs": [{"name": ct} for ct in catalog_types]}
    except Exception as e:
        logger.error(f"Error fetching catalogs: {e}")
        raise HTTPException(500, "Failed to fetch catalogs")


@router.get("/categories")
async def get_categories():
    try:
        return {"categories": db.get_distinct_categories()}
    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        raise HTTPException(500, "Failed to fetch categories")


@router.get("/part_types")
async def get_part_types():
    try:
        return {"part_types": db.get_distinct_part_types()}
    except Exception as e:
        logger.error(f"Error fetching part types: {e}")
        raise HTTPException(500, "Failed to fetch part types")


@router.get("/config")
async def get_config():
    return {
        "maxDescriptionLength": 120,
        "maxApplicationsDisplay": 2,
        "searchDebounceMs": 300,
        "enableTechnicalGuides": True,
        "maxSearchResults": 50,
    }
