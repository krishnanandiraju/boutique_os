from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base, get_db
from app.models import Customer, Item, Order, OrderLine, OrderStatus
from app.utils import utcnow

router = APIRouter(prefix="/api/v2", tags=["customer-crm-v2"])


class AppSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, str_strip_whitespace=True)


class OccasionType(str, enum.Enum):
    BIRTHDAY = "BIRTHDAY"
    WEDDING_ANNIVERSARY = "WEDDING_ANNIVERSARY"
    FIRST_PURCHASE_ANNIVERSARY = "FIRST_PURCHASE_ANNIVERSARY"
    CUSTOM = "CUSTOM"


class OfferKind(str, enum.Enum):
    PERCENTAGE = "PERCENTAGE"
    FLAT = "FLAT"
    GIFT = "GIFT"
    NONE = "NONE"


class CustomerProfile(Base):
    __tablename__ = "customer_profiles_v2"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, unique=True)
    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country: Mapped[str] = mapped_column(String(80), default="India", nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    anniversary_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    preferred_language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    acquisition_source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    acquisition_detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_segment: Mapped[str | None] = mapped_column(String(120), nullable=True)
    merchant_tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    marketing_consent: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class CustomerOccasion(Base):
    __tablename__ = "customer_occasions_v2"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    occasion_type: Mapped[OccasionType] = mapped_column(Enum(OccasionType), nullable=False)
    label: Mapped[str] = mapped_column(String(180), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    recurring_annually: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    offer_kind: Mapped[OfferKind] = mapped_column(Enum(OfferKind), default=OfferKind.NONE, nullable=False)
    offer_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    offer_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    lead_days: Mapped[int] = mapped_column(Integer, default=14, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("customer_id", "occasion_type", "label", "event_date", name="uq_customer_occasion_v2"),
    )


class CustomerProfileWrite(AppSchema):
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str = "India"
    date_of_birth: date | None = None
    anniversary_date: date | None = None
    preferred_language: str | None = None
    acquisition_source: str | None = None
    acquisition_detail: str | None = None
    customer_segment: str | None = None
    merchant_tags: list[str] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)
    marketing_consent: bool = True


class CustomerMetrics(AppSchema):
    order_count: int = 0
    total_spend: Decimal = Decimal("0.00")
    average_order_value: Decimal = Decimal("0.00")
    estimated_gross_margin: Decimal = Decimal("0.00")
    last_purchase_at: datetime | None = None


class CustomerProfileRead(CustomerProfileWrite):
    id: int
    customer_id: int
    updated_at: datetime
    metrics: CustomerMetrics


class CustomerProfileSummary(AppSchema):
    customer_id: int
    customer_segment: str | None = None
    merchant_tags: list[str] = Field(default_factory=list)
    acquisition_source: str | None = None
    city: str | None = None
    anniversary_date: date | None = None
    order_count: int = 0
    total_spend: Decimal = Decimal("0.00")
    average_order_value: Decimal = Decimal("0.00")
    last_purchase_at: datetime | None = None
    next_event_label: str | None = None
    next_event_date: date | None = None


class CustomerOccasionCreate(AppSchema):
    occasion_type: OccasionType
    label: str
    event_date: date
    recurring_annually: bool = True
    offer_kind: OfferKind = OfferKind.NONE
    offer_value: Decimal | None = Field(default=None, ge=0)
    offer_code: str | None = None
    lead_days: int = Field(default=14, ge=0, le=365)
    notes: str | None = None
    active: bool = True


class CustomerOccasionRead(CustomerOccasionCreate):
    id: int
    customer_id: int
    created_at: datetime
    next_occurrence: date
    anniversary_number: int | None = None


def _ensure_customer(db: Session, customer_id: int) -> Customer:
    customer = db.scalar(select(Customer).where(Customer.id == customer_id))
    if customer is None:
        raise HTTPException(404, "Customer not found")
    return customer


def _profile(db: Session, customer_id: int) -> CustomerProfile:
    _ensure_customer(db, customer_id)
    profile = db.scalar(select(CustomerProfile).where(CustomerProfile.customer_id == customer_id))
    if profile is None:
        profile = CustomerProfile(customer_id=customer_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def _metrics(db: Session, customer_id: int) -> CustomerMetrics:
    orders = list(
        db.scalars(
            select(Order)
            .where(Order.customer_id == customer_id, Order.status != OrderStatus.CANCELLED)
            .order_by(Order.created_at.desc())
        )
    )
    total = sum((Decimal(order.total_amount) for order in orders), Decimal("0.00"))
    count = len(orders)
    aov = (total / count).quantize(Decimal("0.01")) if count else Decimal("0.00")

    margin = Decimal("0.00")
    if orders:
        order_ids = [order.id for order in orders]
        rows = db.execute(
            select(OrderLine, Item)
            .join(Item, Item.id == OrderLine.item_id)
            .where(OrderLine.order_id.in_(order_ids))
        ).all()
        for line, item in rows:
            if item.cost_price is None:
                continue
            margin += (Decimal(line.unit_price) - Decimal(item.cost_price)) * Decimal(line.quantity)

    return CustomerMetrics(
        order_count=count,
        total_spend=total.quantize(Decimal("0.01")),
        average_order_value=aov,
        estimated_gross_margin=margin.quantize(Decimal("0.01")),
        last_purchase_at=orders[0].created_at if orders else None,
    )


def _next_occurrence(event_date: date, recurring: bool, today: date | None = None) -> date:
    today = today or date.today()
    if not recurring:
        return event_date
    year = today.year
    try:
        candidate = event_date.replace(year=year)
    except ValueError:
        candidate = date(year, 2, 28)
    if candidate < today:
        try:
            candidate = event_date.replace(year=year + 1)
        except ValueError:
            candidate = date(year + 1, 2, 28)
    return candidate


def _occasion_read(occasion: CustomerOccasion) -> CustomerOccasionRead:
    next_date = _next_occurrence(occasion.event_date, occasion.recurring_annually)
    anniversary_number = None
    if occasion.recurring_annually:
        anniversary_number = max(0, next_date.year - occasion.event_date.year)
    return CustomerOccasionRead(
        id=occasion.id,
        customer_id=occasion.customer_id,
        occasion_type=occasion.occasion_type,
        label=occasion.label,
        event_date=occasion.event_date,
        recurring_annually=occasion.recurring_annually,
        offer_kind=occasion.offer_kind,
        offer_value=occasion.offer_value,
        offer_code=occasion.offer_code,
        lead_days=occasion.lead_days,
        notes=occasion.notes,
        active=occasion.active,
        created_at=occasion.created_at,
        next_occurrence=next_date,
        anniversary_number=anniversary_number,
    )


@router.get("/customers/profiles", response_model=list[CustomerProfileSummary])
def list_customer_profiles(merchant_id: int = 1, db: Session = Depends(get_db)) -> list[CustomerProfileSummary]:
    customers = list(db.scalars(select(Customer).where(Customer.merchant_id == merchant_id).order_by(Customer.name)))
    summaries: list[CustomerProfileSummary] = []
    for customer in customers:
        profile = db.scalar(select(CustomerProfile).where(CustomerProfile.customer_id == customer.id))
        metrics = _metrics(db, customer.id)
        occasions = list(db.scalars(select(CustomerOccasion).where(CustomerOccasion.customer_id == customer.id, CustomerOccasion.active.is_(True))))
        next_occasion = min(occasions, key=lambda row: _next_occurrence(row.event_date, row.recurring_annually), default=None)
        summaries.append(
            CustomerProfileSummary(
                customer_id=customer.id,
                customer_segment=profile.customer_segment if profile else None,
                merchant_tags=profile.merchant_tags if profile else [],
                acquisition_source=profile.acquisition_source if profile else None,
                city=profile.city if profile else None,
                anniversary_date=profile.anniversary_date if profile else None,
                order_count=metrics.order_count,
                total_spend=metrics.total_spend,
                average_order_value=metrics.average_order_value,
                last_purchase_at=metrics.last_purchase_at,
                next_event_label=next_occasion.label if next_occasion else None,
                next_event_date=_next_occurrence(next_occasion.event_date, next_occasion.recurring_annually) if next_occasion else None,
            )
        )
    return summaries


@router.get("/customers/{customer_id}/profile", response_model=CustomerProfileRead)
def get_customer_profile(customer_id: int, db: Session = Depends(get_db)) -> CustomerProfileRead:
    profile = _profile(db, customer_id)
    return CustomerProfileRead(**CustomerProfileWrite.model_validate(profile).model_dump(), id=profile.id, customer_id=profile.customer_id, updated_at=profile.updated_at, metrics=_metrics(db, customer_id))


@router.put("/customers/{customer_id}/profile", response_model=CustomerProfileRead)
def put_customer_profile(customer_id: int, payload: CustomerProfileWrite, db: Session = Depends(get_db)) -> CustomerProfileRead:
    profile = _profile(db, customer_id)
    for key, value in payload.model_dump().items():
        setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return CustomerProfileRead(**payload.model_dump(), id=profile.id, customer_id=profile.customer_id, updated_at=profile.updated_at, metrics=_metrics(db, customer_id))


@router.get("/customers/{customer_id}/occasions", response_model=list[CustomerOccasionRead])
def list_customer_occasions(customer_id: int, db: Session = Depends(get_db)) -> list[CustomerOccasionRead]:
    _ensure_customer(db, customer_id)
    rows = list(db.scalars(select(CustomerOccasion).where(CustomerOccasion.customer_id == customer_id, CustomerOccasion.active.is_(True)).order_by(CustomerOccasion.event_date)))
    return sorted((_occasion_read(row) for row in rows), key=lambda row: row.next_occurrence)


@router.post("/customers/{customer_id}/occasions", response_model=CustomerOccasionRead)
def create_customer_occasion(customer_id: int, payload: CustomerOccasionCreate, db: Session = Depends(get_db)) -> CustomerOccasionRead:
    _ensure_customer(db, customer_id)
    occasion = CustomerOccasion(customer_id=customer_id, **payload.model_dump())
    db.add(occasion)
    db.commit()
    db.refresh(occasion)
    return _occasion_read(occasion)
