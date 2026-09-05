from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.catalog_models import AudienceSegment
from app.db import get_db
from app.integrations.service import IntegrationEventService
from app.models import IntegrationOutbox, IntegrationOutboxStatus, InventoryStatus, Order, OrderStatus, TailoringStage, TailoringTask

router = APIRouter()
events = IntegrationEventService()


class ApiSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class EventCreate(ApiSchema):
    merchant_id: int = 1
    event_type: str = Field(min_length=3, max_length=120)
    aggregate_type: str = Field(min_length=2, max_length=120)
    aggregate_id: str = Field(min_length=1, max_length=120)
    payload: dict[str, Any] = Field(default_factory=dict)


class EventStatusPatch(ApiSchema):
    status: IntegrationOutboxStatus
    last_error: str | None = None


class EventRead(ApiSchema):
    id: int
    event_id: str
    merchant_id: int
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload_json: dict[str, Any]
    status: IntegrationOutboxStatus
    attempt_count: int
    last_error: str | None
    created_at: datetime
    processed_at: datetime | None
    next_attempt_at: datetime | None


@router.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok", "check": "live"}


@router.get("/health/ready")
def health_ready(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "check": "ready", "database": "reachable"}


@router.get("/api/status")
def application_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    open_orders = db.scalar(select(func.count(Order.id)).where(Order.status.not_in([OrderStatus.DELIVERED, OrderStatus.CANCELLED]))) or 0
    ready_orders = db.scalar(select(func.count(Order.id)).where(Order.status == OrderStatus.READY)) or 0
    tailoring_open = db.scalar(select(func.count(TailoringTask.id)).where(TailoringTask.stage != TailoringStage.READY)) or 0
    pending_events = db.scalar(select(func.count(IntegrationOutbox.id)).where(IntegrationOutbox.status.in_([IntegrationOutboxStatus.PENDING, IntegrationOutboxStatus.PROCESSING]))) or 0
    failed_events = db.scalar(select(func.count(IntegrationOutbox.id)).where(IntegrationOutbox.status == IntegrationOutboxStatus.FAILED)) or 0
    return {
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
        "orders": {"open": int(open_orders), "ready": int(ready_orders)},
        "tailoring": {"open": int(tailoring_open)},
        "events": {"pending": int(pending_events), "failed": int(failed_events)},
    }


@router.get("/api/status/catalog")
def status_catalog() -> dict[str, list[str]]:
    return {
        "order_statuses": [value.value for value in OrderStatus],
        "tailoring_stages": [value.value for value in TailoringStage],
        "inventory_statuses": [value.value for value in InventoryStatus],
        "event_statuses": [value.value for value in IntegrationOutboxStatus],
        "audiences": [value.value for value in AudienceSegment],
    }


@router.post("/api/events", response_model=EventRead)
def create_event(payload: EventCreate, db: Session = Depends(get_db)) -> EventRead:
    row = events.enqueue(
        db,
        merchant_id=payload.merchant_id,
        event_type=payload.event_type,
        aggregate_type=payload.aggregate_type,
        aggregate_id=payload.aggregate_id,
        payload=payload.payload,
    )
    db.commit()
    db.refresh(row)
    return EventRead.model_validate(row)


@router.get("/api/events", response_model=list[EventRead])
def list_events(
    status: IntegrationOutboxStatus | None = None,
    event_type: str | None = None,
    aggregate_type: str | None = None,
    aggregate_id: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[EventRead]:
    query = select(IntegrationOutbox).order_by(IntegrationOutbox.created_at.desc(), IntegrationOutbox.id.desc())
    if status is not None:
        query = query.where(IntegrationOutbox.status == status)
    if event_type:
        query = query.where(IntegrationOutbox.event_type == event_type)
    if aggregate_type:
        query = query.where(IntegrationOutbox.aggregate_type == aggregate_type)
    if aggregate_id:
        query = query.where(IntegrationOutbox.aggregate_id == aggregate_id)
    rows = list(db.scalars(query.limit(max(1, min(limit, 500)))))
    return [EventRead.model_validate(row) for row in rows]


@router.get("/api/events/{event_id}", response_model=EventRead)
def get_event(event_id: str, db: Session = Depends(get_db)) -> EventRead:
    row = db.scalar(select(IntegrationOutbox).where(IntegrationOutbox.event_id == event_id))
    if not row:
        raise HTTPException(404, "Event not found")
    return EventRead.model_validate(row)


@router.patch("/api/events/{event_id}/status", response_model=EventRead)
def patch_event_status(event_id: str, payload: EventStatusPatch, db: Session = Depends(get_db)) -> EventRead:
    row = db.scalar(select(IntegrationOutbox).where(IntegrationOutbox.event_id == event_id))
    if not row:
        raise HTTPException(404, "Event not found")
    row.status = payload.status
    row.last_error = payload.last_error
    if payload.status == IntegrationOutboxStatus.PROCESSED:
        row.processed_at = datetime.now(UTC)
    elif payload.status in {IntegrationOutboxStatus.PENDING, IntegrationOutboxStatus.PROCESSING}:
        row.processed_at = None
    db.commit()
    db.refresh(row)
    return EventRead.model_validate(row)
