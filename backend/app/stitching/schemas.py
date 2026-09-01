from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field, model_validator

from app.schemas import AppSchema
from app.stitching.models import FeedbackSeverity, FitArea, FitDirection, StitchRecordStatus


class GarmentTypeDefinitionRead(AppSchema):
    code: str
    display_name: str
    measurement_fields: list[str]
    fit_areas: list[str]
    active: bool


class StitchFeedbackCreate(AppSchema):
    fit_area: FitArea
    direction: FitDirection
    severity: FeedbackSeverity = FeedbackSeverity.MINOR
    adjustment_value: Decimal | None = None
    adjustment_unit: str | None = None
    comment: str | None = None

    @model_validator(mode="after")
    def validate_adjustment_unit(self) -> "StitchFeedbackCreate":
        if self.adjustment_value is not None and not self.adjustment_unit:
            raise ValueError("adjustment_unit is required when adjustment_value is provided")
        return self


class StitchFeedbackPatch(AppSchema):
    severity: FeedbackSeverity | None = None
    adjustment_value: Decimal | None = None
    adjustment_unit: str | None = None
    comment: str | None = None
    resolved: bool | None = None


class StitchFeedbackRead(AppSchema):
    id: int
    stitch_record_id: int
    fit_area: FitArea
    direction: FitDirection
    severity: FeedbackSeverity
    adjustment_value: Decimal | None = None
    adjustment_unit: str | None = None
    comment: str | None = None
    resolved: bool
    created_at: datetime


class StitchRecordCreate(AppSchema):
    merchant_id: int
    customer_id: int
    garment_type_code: str
    order_line_id: int | None = None
    measurement_profile_id: int | None = None
    measurement_version_id: int | None = None
    tailor_name: str | None = None
    style_notes: str | None = None


class StitchRecordPatch(AppSchema):
    status: StitchRecordStatus | None = None
    tailor_name: str | None = None
    style_notes: str | None = None
    fit_notes: str | None = None


class StitchRecordRead(AppSchema):
    id: int
    merchant_id: int
    customer_id: int
    order_line_id: int | None = None
    measurement_profile_id: int | None = None
    measurement_version_id: int | None = None
    garment_type_code: str
    status: StitchRecordStatus
    tailor_name: str | None = None
    style_notes: str | None = None
    fit_notes: str | None = None
    created_at: datetime
    updated_at: datetime
    feedback: list[StitchFeedbackRead] = Field(default_factory=list)


class CustomerFitInsightRead(AppSchema):
    customer_id: int
    garment_type_code: str
    recurring_feedback: list[str] = Field(default_factory=list)
    unresolved_feedback_count: int = 0
    last_stitch_record_id: int | None = None
