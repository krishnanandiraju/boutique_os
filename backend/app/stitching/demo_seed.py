from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer, MeasurementProfile, MeasurementVersion, OrderLine
from app.stitching.models import (
    FeedbackSeverity,
    FitArea,
    FitDirection,
    StitchFeedback,
    StitchRecord,
    StitchRecordStatus,
)


DEMO_HISTORY_STYLE = "Classic festive blouse · demo history"
DEMO_ACTIVE_STYLE = "Princess cut · elbow sleeves · boat neck"


def _ensure_feedback(
    db: Session,
    record: StitchRecord,
    *,
    fit_area: FitArea,
    direction: FitDirection,
    severity: FeedbackSeverity,
    adjustment_value: Decimal | None,
    comment: str,
    resolved: bool,
) -> None:
    existing = db.scalar(
        select(StitchFeedback).where(
            StitchFeedback.stitch_record_id == record.id,
            StitchFeedback.fit_area == fit_area,
            StitchFeedback.direction == direction,
            StitchFeedback.comment == comment,
        )
    )
    if existing:
        return
    db.add(
        StitchFeedback(
            stitch_record_id=record.id,
            fit_area=fit_area,
            direction=direction,
            severity=severity,
            adjustment_value=adjustment_value,
            adjustment_unit="INCH" if adjustment_value is not None else None,
            comment=comment,
            resolved=resolved,
        )
    )


def seed_demo_fit_memory(db: Session) -> None:
    """Seed a small, deterministic stitch history for the client demo.

    This data intentionally demonstrates why fit feedback must remain separate from
    immutable body measurements: Anjali's recorded sleeve measurement stays 10 in,
    while repeated trial experience says her blouse sleeve should be reviewed shorter.
    """
    customer = db.scalar(select(Customer).where(Customer.name == "Anjali Rao"))
    if not customer:
        return

    profile = db.scalar(
        select(MeasurementProfile).where(
            MeasurementProfile.customer_id == customer.id,
            MeasurementProfile.name == "Self",
            MeasurementProfile.garment_type == "BLOUSE",
        )
    )
    if not profile:
        return

    version = db.scalar(
        select(MeasurementVersion)
        .where(MeasurementVersion.measurement_profile_id == profile.id)
        .order_by(MeasurementVersion.version_number.desc())
    )
    if not version:
        return

    tailoring_line = db.scalar(
        select(OrderLine).where(
            OrderLine.measurement_profile_id == profile.id,
            OrderLine.requires_tailoring.is_(True),
        )
    )

    historical = db.scalar(
        select(StitchRecord).where(
            StitchRecord.customer_id == customer.id,
            StitchRecord.garment_type_code == "BLOUSE",
            StitchRecord.style_notes == DEMO_HISTORY_STYLE,
        )
    )
    if not historical:
        historical = StitchRecord(
            merchant_id=customer.merchant_id,
            customer_id=customer.id,
            measurement_profile_id=profile.id,
            measurement_version_id=version.id,
            garment_type_code="BLOUSE",
            status=StitchRecordStatus.CLOSED,
            tailor_name="Ritu",
            style_notes=DEMO_HISTORY_STYLE,
            fit_notes="Altered after trial and delivered successfully.",
        )
        db.add(historical)
        db.flush()

    _ensure_feedback(
        db,
        historical,
        fit_area=FitArea.SLEEVE,
        direction=FitDirection.TOO_LONG,
        severity=FeedbackSeverity.MODERATE,
        adjustment_value=Decimal("0.500"),
        comment="Sleeve was half an inch too long at trial; shortened before delivery.",
        resolved=True,
    )
    _ensure_feedback(
        db,
        historical,
        fit_area=FitArea.NECKLINE,
        direction=FitDirection.TOO_DEEP,
        severity=FeedbackSeverity.MINOR,
        adjustment_value=Decimal("0.250"),
        comment="Customer preferred the front neckline slightly higher.",
        resolved=True,
    )

    active = None
    if tailoring_line:
        active = db.scalar(select(StitchRecord).where(StitchRecord.order_line_id == tailoring_line.id))
    if not active:
        active = db.scalar(
            select(StitchRecord).where(
                StitchRecord.customer_id == customer.id,
                StitchRecord.garment_type_code == "BLOUSE",
                StitchRecord.style_notes == DEMO_ACTIVE_STYLE,
            )
        )
    if not active:
        active = StitchRecord(
            merchant_id=customer.merchant_id,
            customer_id=customer.id,
            order_line_id=tailoring_line.id if tailoring_line else None,
            measurement_profile_id=profile.id,
            measurement_version_id=version.id,
            garment_type_code="BLOUSE",
            status=StitchRecordStatus.TRIAL,
            tailor_name="Ritu",
            style_notes=DEMO_ACTIVE_STYLE,
            fit_notes="Trial feedback captured before final alteration.",
        )
        db.add(active)
        db.flush()

    _ensure_feedback(
        db,
        active,
        fit_area=FitArea.SLEEVE,
        direction=FitDirection.TOO_LONG,
        severity=FeedbackSeverity.MINOR,
        adjustment_value=Decimal("0.500"),
        comment="Again felt about half an inch too long at trial; shortened before final finish.",
        resolved=True,
    )

    db.commit()
