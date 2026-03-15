"""
SQLAlchemy ORM models for Larry — LIG Parts Intelligence.

Supports both SQLite (dev) and PostgreSQL (prod) via DATABASE_URL.
Adds governance columns required by the Larry governance framework:
  - confidence_label: 'unverified' | 'ai_extracted' | 'human_verified'
  - review_status:    'pending'    | 'approved'      | 'rejected'
  - published:        bool — only published=True rows shown in UI (future gate)
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Index, Integer, String, Text, UniqueConstraint, event
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ── Parts ──────────────────────────────────────────────────────────────────
class Part(Base):
    __tablename__ = "parts"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    catalog_name     = Column(String(255), nullable=False)
    catalog_type     = Column(String(100))
    part_type        = Column(String(100))
    part_number      = Column(String(100), nullable=False)
    description      = Column(Text)
    category         = Column(String(100))
    page             = Column(Integer)
    image_path       = Column(String(512))
    page_text        = Column(Text)
    pdf_path         = Column(String(512))
    machine_info     = Column(Text)      # JSON string
    specifications   = Column(Text)      # JSON or "Key: Value\n" lines
    oe_numbers       = Column(Text)      # JSON array or comma-separated
    applications     = Column(Text)      # JSON array or comma-separated
    features         = Column(Text)      # JSON array or newline-separated
    created_at       = Column(DateTime(timezone=True), default=_utcnow)

    # ── Governance columns ──────────────────────────────────────────────────
    confidence_label = Column(String(30), nullable=False, default="ai_extracted")
    review_status    = Column(String(20), nullable=False, default="pending")
    published        = Column(Boolean, nullable=False, default=True)
    reviewed_by      = Column(String(100))
    reviewed_at      = Column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("catalog_name", "part_number", "page", name="uq_part_catalog_page"),
        Index("idx_part_number",   "part_number"),
        Index("idx_catalog_name",  "catalog_name"),
        Index("idx_catalog_type",  "catalog_type"),
        Index("idx_part_type",     "part_type"),
        Index("idx_category",      "category"),
        Index("idx_review_status", "review_status"),
        Index("idx_published",     "published"),
    )

    images      = relationship("PartImage",    back_populates="part", cascade="all, delete-orphan")
    part_guides = relationship("PartGuide",    back_populates="part", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Part {self.part_number} [{self.catalog_name}]>"


# ── Technical Guides ───────────────────────────────────────────────────────
class TechnicalGuide(Base):
    __tablename__ = "technical_guides"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    guide_name       = Column(String(255), unique=True, nullable=False)
    display_name     = Column(String(255), nullable=False)
    description      = Column(Text)
    category         = Column(String(100))
    s3_key           = Column(String(512))
    template_fields  = Column(Text)       # JSON
    pdf_path         = Column(String(512))
    related_parts    = Column(Text)       # JSON array
    is_active        = Column(Boolean, default=True)
    created_at       = Column(DateTime(timezone=True), default=_utcnow)

    # Governance
    confidence_label = Column(String(30), nullable=False, default="human_verified")
    review_status    = Column(String(20), nullable=False, default="approved")

    guide_parts = relationship("GuidePart",  back_populates="guide", cascade="all, delete-orphan")
    part_guides = relationship("PartGuide",  back_populates="guide", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<TechnicalGuide {self.guide_name}>"


# ── Guide ↔ Part associations ──────────────────────────────────────────────
class GuidePart(Base):
    """Parts referenced directly from a guide (guide owns the list)."""
    __tablename__ = "guide_parts"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    guide_id         = Column(Integer, ForeignKey("technical_guides.id"), nullable=False)
    part_number      = Column(String(100), nullable=False)
    confidence_score = Column(Float, default=1.0)
    created_at       = Column(DateTime(timezone=True), default=_utcnow)

    guide = relationship("TechnicalGuide", back_populates="guide_parts")

    __table_args__ = (
        UniqueConstraint("guide_id", "part_number", name="uq_guide_part"),
        Index("idx_guide_parts_guide_id",    "guide_id"),
        Index("idx_guide_parts_part_number", "part_number"),
    )


class PartGuide(Base):
    """Parts that have been associated with a guide (part owns the list)."""
    __tablename__ = "part_guides"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    part_id          = Column(Integer, ForeignKey("parts.id"), nullable=False)
    guide_id         = Column(Integer, ForeignKey("technical_guides.id"), nullable=False)
    confidence_score = Column(Float, default=1.0)
    created_at       = Column(DateTime(timezone=True), default=_utcnow)

    part  = relationship("Part",           back_populates="part_guides")
    guide = relationship("TechnicalGuide", back_populates="part_guides")

    __table_args__ = (
        UniqueConstraint("part_id", "guide_id", name="uq_part_guide"),
        Index("idx_part_guides_part_id",  "part_id"),
        Index("idx_part_guides_guide_id", "guide_id"),
    )


# ── Part Images ────────────────────────────────────────────────────────────
class PartImage(Base):
    __tablename__ = "part_images"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    part_id        = Column(Integer, ForeignKey("parts.id"), nullable=False)
    image_filename = Column(String(255), nullable=False)
    image_path     = Column(String(512), nullable=False)
    image_type     = Column(String(10))   # png, jpg, webp
    image_width    = Column(Integer)
    image_height   = Column(Integer)
    page_number    = Column(Integer)
    confidence     = Column(Float, default=1.0)
    created_at     = Column(DateTime(timezone=True), default=_utcnow)

    part = relationship("Part", back_populates="images")

    __table_args__ = (
        UniqueConstraint("part_id", "image_filename", name="uq_part_image"),
        Index("idx_part_images_part_id",  "part_id"),
        Index("idx_part_images_filename", "image_filename"),
    )


# ── Alias (cross-reference / OE number lookup) ─────────────────────────────
class Alias(Base):
    """
    Canonical lookup table for OE numbers and cross-references.
    Lets Larry answer "what LIG part matches OE 1234-5678?"
    """
    __tablename__ = "aliases"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    part_id     = Column(Integer, ForeignKey("parts.id"), nullable=False)
    alias_type  = Column(String(50), nullable=False)   # 'oe', 'competitor', 'superseded'
    alias_value = Column(String(255), nullable=False)
    source      = Column(String(100))
    created_at  = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("idx_aliases_part_id",    "part_id"),
        Index("idx_aliases_alias_value", "alias_value"),
    )


# ── Audit Log ──────────────────────────────────────────────────────────────
class AuditLog(Base):
    """
    Immutable record of every mutating API request.
    Append-only — never update or delete rows.
    """
    __tablename__ = "audit_log"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    timestamp    = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    method       = Column(String(10), nullable=False)
    path         = Column(String(512), nullable=False)
    status_code  = Column(Integer)
    user_agent   = Column(String(512))
    ip_address   = Column(String(64))
    request_body = Column(Text)
    duration_ms  = Column(Float)
    actor        = Column(String(100))

    __table_args__ = (
        Index("idx_audit_timestamp", "timestamp"),
        Index("idx_audit_path",      "path"),
    )


# ── Alias Proposals (Phase 3 governance queue) ─────────────────────────────
class AliasProposal(Base):
    """
    AI-detected near-duplicate part pairs queued for Data Steward review.

    Governance rules:
      - status is ALWAYS 'pending' on creation
      - NEVER auto-approved
      - Data Steward must explicitly approve or reject
    """
    __tablename__ = "alias_proposals"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    source_part_id   = Column(Integer, ForeignKey("parts.id"), nullable=False)
    target_part_id   = Column(Integer, ForeignKey("parts.id"), nullable=False)
    similarity_score = Column(Float, nullable=False)
    proposal_reason  = Column(String(100), default="semantic_similarity")
    status           = Column(String(20), nullable=False, default="pending")
    proposed_at      = Column(DateTime(timezone=True), default=_utcnow)
    reviewed_by      = Column(String(100))
    reviewed_at      = Column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("source_part_id", "target_part_id", name="uq_alias_proposal"),
        Index("idx_alias_proposals_status", "status"),
        Index("idx_alias_proposals_score",  "similarity_score"),
    )
