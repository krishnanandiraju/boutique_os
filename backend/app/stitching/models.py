from __future__ import annotations

import enum
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.utils import utcnow


class StitchRecordStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    MEASURED = "MEASURED"
    CUTTING = "CUTTING"
    STITCHING = "STITCHING"
    TRIAL = "TRIAL"
    ALTERATION = "ALTERATION"
    READY = "READY"
    DELIVERED = "DELIVERED"
    CLOSED = "CLOSED"


class FitArea(str, enum.Enum):
    OVERALL = "OVERALL"
    BUST = "BUST"
    WAIST = "WAIST"
    HIP = "HIP"
    SHOULDER = "SHOULDER"
    ARMHOLE = "ARMHOLE"
    SLEEVE = "SLEEVE"
    NECKLINE = "NECKLINE"
    LENGTH = "LENGTH"
    BOTTOM_OPENING = "BOTTOM_OPENING"
    CROTCH = "CROTCH"
    OTHER = "OTHER"


class FitDirection(str, enum.Enum):
    TOO_LONG = "TOO_LONG"
    TOO_SHORT = "TOO_SHORT"
    TOO_TIGHT = "TOO_TIGHT"
    TOO_LOOSE = "TOO_LOOSE"
    TOO_DEEP = "TOO_DEEP"
    TOO_SHALLOW = "TOO_SHALLOW"
    TOO_HIGH = "TOO_HIGH"
    TOO_LOW = "TOO_LOW"
    OTHER = "OTHER"


class FeedbackSeverity(str, enum.Enum):
    MINOR = "MINOR"
    MODERATE = "MODERATE"
    MAJOR = "MAJOR"


class GarmentTypeDefinition(Base):
    __tablename__ = "garment_type_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    measurement_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    fit_areas: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class StitchRecord(Base):
    __tablename__ = "stitch_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    order_line_id: Mapped[int | None] = mapped_column(ForeignKey("order_lines.id"), nullable=True)
    measurement_profile_id: Mapped[int | None] = mapped_column(ForeignKey("measurement_profiles.id"), nullable=True)
    measurement_version_id: Mapped[int | None] = mapped_column(ForeignKey("measurement_versions.id"), nullable=True)
    garment_type_code: Mapped[str] = mapped_column(ForeignKey("garment_type_definitions.code"), nullable=False)
    status: Mapped[StitchRecordStatus] = mapped_column(Enum(StitchRecordStatus), default=StitchRecordStatus.DRAFT, nullable=False)
    tailor_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    style_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    fit_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("order_line_id", name="uq_stitch_record_order_line"),
        Index("ix_stitch_records_customer_created", "customer_id", "created_at"),
        Index("ix_stitch_records_status", "status"),
    )


class StitchFeedback(Base):
    __tablename__ = "stitch_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stitch_record_id: Mapped[int] = mapped_column(ForeignKey("stitch_records.id"), nullable=False)
    fit_area: Mapped[FitArea] = mapped_column(Enum(FitArea), nullable=False)
    direction: Mapped[FitDirection] = mapped_column(Enum(FitDirection), nullable=False)
    severity: Mapped[FeedbackSeverity] = mapped_column(Enum(FeedbackSeverity), default=FeedbackSeverity.MINOR, nullable=False)
    adjustment_value: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    adjustment_unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (Index("ix_stitch_feedback_record_area", "stitch_record_id", "fit_area"),)
