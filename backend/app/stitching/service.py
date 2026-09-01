from __future__ import annotations

from collections import Counter
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer, MeasurementProfile, MeasurementVersion, OrderLine
from app.services.inventory_service import DomainError
from app.stitching.models import GarmentTypeDefinition, StitchFeedback, StitchRecord
from app.stitching.schemas import (
    CustomerFitInsightRead,
    StitchFeedbackCreate,
    StitchFeedbackPatch,
    StitchFeedbackRead,
    StitchRecordCreate,
    StitchRecordPatch,
    StitchRecordRead,
)

logger = logging.getLogger(__name__)


GARMENT_DEFINITIONS = [
    {
        "code": "BLOUSE",
        "display_name": "Blouse",
        "measurement_fields": ["bust", "waist", "shoulder", "blouse_length", "sleeve_length", "armhole", "front_neck_depth", "back_neck_depth"],
        "fit_areas": ["BUST", "WAIST", "SHOULDER", "ARMHOLE", "SLEEVE", "NECKLINE", "LENGTH", "OVERALL"],
    },
    {
        "code": "KURTA",
        "display_name": "Kurta / Kurti",
        "measurement_fields": ["bust", "waist", "hip", "shoulder", "kurta_length", "sleeve_length", "armhole", "neck_depth"],
        "fit_areas": ["BUST", "WAIST", "HIP", "SHOULDER", "ARMHOLE", "SLEEVE", "NECKLINE", "LENGTH", "OVERALL"],
    },
    {
        "code": "BOTTOM",
        "display_name": "Bottom / Trouser / Salwar",
        "measurement_fields": ["waist", "hip", "length", "thigh", "bottom_opening", "crotch"],
        "fit_areas": ["WAIST", "HIP", "LENGTH", "BOTTOM_OPENING", "CROTCH", "OVERALL"],
    },
    {
        "code": "DRESS",
        "display_name": "Dress / Gown",
        "measurement_fields": ["bust", "waist", "hip", "shoulder", "dress_length", "sleeve_length", "armhole", "neck_depth"],
        "fit_areas": ["BUST", "WAIST", "HIP", "SHOULDER", "ARMHOLE", "SLEEVE", "NECKLINE", "LENGTH", "OVERALL"],
    },
    {
        "code": "LEHENGA_BLOUSE",
        "display_name": "Lehenga Blouse",
        "measurement_fields": ["bust", "under_bust", "waist", "shoulder", "blouse_length", "sleeve_length", "armhole", "front_neck_depth", "back_neck_depth"],
        "fit_areas": ["BUST", "WAIST", "SHOULDER", "ARMHOLE", "SLEEVE", "NECKLINE", "LENGTH", "OVERALL"],
    },
]


def seed_garment_definitions(db: Session) -> None:
    existing = set(db.scalars(select(GarmentTypeDefinition.code)))
    changed = False
    for definition in GARMENT_DEFINITIONS:
        if definition["code"] in existing:
            continue
        db.add(GarmentTypeDefinition(**definition))
        changed = True
    if changed:
        db.commit()


def _feedback_read(row: StitchFeedback) -> StitchFeedbackRead:
    return StitchFeedbackRead.model_validate(row)


def _record_read(db: Session, row: StitchRecord) -> StitchRecordRead:
    feedback = list(
        db.scalars(
            select(StitchFeedback)
            .where(StitchFeedback.stitch_record_id == row.id)
            .order_by(StitchFeedback.created_at.asc(), StitchFeedback.id.asc())
        )
    )
    return StitchRecordRead(
        **{key: getattr(row, key) for key in (
            "id", "merchant_id", "customer_id", "order_line_id", "measurement_profile_id",
            "measurement_version_id", "garment_type_code", "status", "tailor_name", "style_notes",
            "fit_notes", "created_at", "updated_at"
        )},
        feedback=[_feedback_read(item) for item in feedback],
    )


def create_stitch_record(db: Session, payload: StitchRecordCreate) -> StitchRecordRead:
    if not db.get(Customer, payload.customer_id):
        raise DomainError(404, "Customer not found", code="RESOURCE_NOT_FOUND")
    garment = db.scalar(select(GarmentTypeDefinition).where(GarmentTypeDefinition.code == payload.garment_type_code, GarmentTypeDefinition.active.is_(True)))
    if not garment:
        raise DomainError(400, "Unknown garment type", code="INVALID_INPUT")
    if payload.order_line_id is not None:
        line = db.get(OrderLine, payload.order_line_id)
        if not line:
            raise DomainError(404, "Order line not found", code="RESOURCE_NOT_FOUND")
        duplicate = db.scalar(select(StitchRecord).where(StitchRecord.order_line_id == payload.order_line_id))
        if duplicate:
            raise DomainError(409, "A stitch record already exists for this order line", code="STITCH_RECORD_EXISTS")
    if payload.measurement_profile_id is not None:
        profile = db.get(MeasurementProfile, payload.measurement_profile_id)
        if not profile or profile.customer_id != payload.customer_id:
            raise DomainError(409, "Measurement profile does not belong to this customer", code="MEASUREMENT_PROFILE_MISMATCH")
    if payload.measurement_version_id is not None:
        version = db.get(MeasurementVersion, payload.measurement_version_id)
        if not version or version.measurement_profile_id != payload.measurement_profile_id:
            raise DomainError(409, "Measurement version does not match the selected profile", code="MEASUREMENT_VERSION_MISMATCH")

    row = StitchRecord(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info("stitch.record.created", extra={"merchant_id": row.merchant_id, "customer_id": row.customer_id, "stitch_record_id": row.id})
    return _record_read(db, row)


def update_stitch_record(db: Session, record_id: int, payload: StitchRecordPatch) -> StitchRecordRead:
    row = db.get(StitchRecord, record_id)
    if not row:
        raise DomainError(404, "Stitch record not found", code="RESOURCE_NOT_FOUND")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    logger.info("stitch.record.updated", extra={"merchant_id": row.merchant_id, "customer_id": row.customer_id, "stitch_record_id": row.id, "status": row.status.value})
    return _record_read(db, row)


def add_feedback(db: Session, record_id: int, payload: StitchFeedbackCreate) -> StitchFeedbackRead:
    record = db.get(StitchRecord, record_id)
    if not record:
        raise DomainError(404, "Stitch record not found", code="RESOURCE_NOT_FOUND")
    garment = db.scalar(select(GarmentTypeDefinition).where(GarmentTypeDefinition.code == record.garment_type_code))
    if garment and payload.fit_area.value not in garment.fit_areas and payload.fit_area.value != "OTHER":
        raise DomainError(400, f"{payload.fit_area.value} is not a standard fit area for {garment.display_name}", code="INVALID_FIT_AREA")
    row = StitchFeedback(stitch_record_id=record_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info("stitch.feedback.created", extra={"merchant_id": record.merchant_id, "customer_id": record.customer_id, "stitch_record_id": record.id, "fit_area": row.fit_area.value, "direction": row.direction.value})
    return _feedback_read(row)


def update_feedback(db: Session, feedback_id: int, payload: StitchFeedbackPatch) -> StitchFeedbackRead:
    row = db.get(StitchFeedback, feedback_id)
    if not row:
        raise DomainError(404, "Stitch feedback not found", code="RESOURCE_NOT_FOUND")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return _feedback_read(row)


def list_customer_stitch_records(db: Session, customer_id: int) -> list[StitchRecordRead]:
    rows = list(db.scalars(select(StitchRecord).where(StitchRecord.customer_id == customer_id).order_by(StitchRecord.created_at.desc())))
    return [_record_read(db, row) for row in rows]


def customer_fit_insights(db: Session, customer_id: int, garment_type_code: str) -> CustomerFitInsightRead:
    records = list(db.scalars(select(StitchRecord).where(StitchRecord.customer_id == customer_id, StitchRecord.garment_type_code == garment_type_code).order_by(StitchRecord.created_at.desc())))
    if not records:
        return CustomerFitInsightRead(customer_id=customer_id, garment_type_code=garment_type_code)
    ids = [row.id for row in records]
    feedback = list(db.scalars(select(StitchFeedback).where(StitchFeedback.stitch_record_id.in_(ids))))
    counts = Counter(f"{row.fit_area.value}:{row.direction.value}" for row in feedback)
    recurring = [key for key, count in counts.most_common() if count >= 2]
    unresolved = sum(1 for row in feedback if not row.resolved)
    return CustomerFitInsightRead(customer_id=customer_id, garment_type_code=garment_type_code, recurring_feedback=recurring, unresolved_feedback_count=unresolved, last_stitch_record_id=records[0].id)
