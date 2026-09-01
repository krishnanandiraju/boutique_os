from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.stitching.models import GarmentTypeDefinition
from app.stitching.schemas import (
    CustomerFitInsightRead,
    GarmentTypeDefinitionRead,
    StitchFeedbackCreate,
    StitchFeedbackPatch,
    StitchFeedbackRead,
    StitchRecordCreate,
    StitchRecordPatch,
    StitchRecordRead,
)
from app.stitching.service import (
    add_feedback,
    create_stitch_record,
    customer_fit_insights,
    list_customer_stitch_records,
    update_feedback,
    update_stitch_record,
)

router = APIRouter(prefix="/api/stitching", tags=["stitching"])


@router.get("/garment-types", response_model=list[GarmentTypeDefinitionRead])
def garment_types(db: Session = Depends(get_db)) -> list[GarmentTypeDefinitionRead]:
    rows = list(db.scalars(select(GarmentTypeDefinition).where(GarmentTypeDefinition.active.is_(True)).order_by(GarmentTypeDefinition.display_name.asc())))
    return [GarmentTypeDefinitionRead.model_validate(row) for row in rows]


@router.post("/records", response_model=StitchRecordRead)
def post_stitch_record(payload: StitchRecordCreate, db: Session = Depends(get_db)) -> StitchRecordRead:
    return create_stitch_record(db, payload)


@router.patch("/records/{record_id}", response_model=StitchRecordRead)
def patch_stitch_record(record_id: int, payload: StitchRecordPatch, db: Session = Depends(get_db)) -> StitchRecordRead:
    return update_stitch_record(db, record_id, payload)


@router.post("/records/{record_id}/feedback", response_model=StitchFeedbackRead)
def post_stitch_feedback(record_id: int, payload: StitchFeedbackCreate, db: Session = Depends(get_db)) -> StitchFeedbackRead:
    return add_feedback(db, record_id, payload)


@router.patch("/feedback/{feedback_id}", response_model=StitchFeedbackRead)
def patch_stitch_feedback(feedback_id: int, payload: StitchFeedbackPatch, db: Session = Depends(get_db)) -> StitchFeedbackRead:
    return update_feedback(db, feedback_id, payload)


@router.get("/customers/{customer_id}/records", response_model=list[StitchRecordRead])
def customer_stitch_records(customer_id: int, db: Session = Depends(get_db)) -> list[StitchRecordRead]:
    return list_customer_stitch_records(db, customer_id)


@router.get("/customers/{customer_id}/fit-insights/{garment_type_code}", response_model=CustomerFitInsightRead)
def customer_stitch_insights(customer_id: int, garment_type_code: str, db: Session = Depends(get_db)) -> CustomerFitInsightRead:
    return customer_fit_insights(db, customer_id, garment_type_code)
