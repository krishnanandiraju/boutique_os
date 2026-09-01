from __future__ import annotations

import enum
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.utils import utcnow


class InventoryType(str, enum.Enum):
    UNIQUE = "UNIQUE"
    STOCKED = "STOCKED"
    YARDAGE = "YARDAGE"


class InventoryStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    HELD = "HELD"
    SOLD = "SOLD"
    DEPLETED = "DEPLETED"
    REMNANT = "REMNANT"


class InventoryMovementType(str, enum.Enum):
    RECEIPT = "RECEIPT"
    SALE = "SALE"
    ADJUSTMENT_IN = "ADJUSTMENT_IN"
    ADJUSTMENT_OUT = "ADJUSTMENT_OUT"
    DAMAGE = "DAMAGE"
    GIFT = "GIFT"
    RETURN = "RETURN"
    YARDAGE_CUT = "YARDAGE_CUT"
    HOLD = "HOLD"
    HOLD_RELEASE = "HOLD_RELEASE"
    HOLD_EXPIRE = "HOLD_EXPIRE"


class OrderStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    TAILORING = "TAILORING"
    READY = "READY"
    PACKED = "PACKED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class TailoringStage(str, enum.Enum):
    MEASUREMENT_PENDING = "MEASUREMENT_PENDING"
    CUTTING = "CUTTING"
    STITCHING = "STITCHING"
    QC = "QC"
    TRIAL_SCHEDULED = "TRIAL_SCHEDULED"
    ALTERATION = "ALTERATION"
    READY = "READY"


class MeasurementUnit(str, enum.Enum):
    INCH = "INCH"
    CM = "CM"


class TailoringPriority(str, enum.Enum):
    NORMAL = "NORMAL"
    URGENT = "URGENT"


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    measurement_profiles: Mapped[list[MeasurementProfile]] = relationship(back_populates="customer")


class MediaType(str, enum.Enum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"


class CommerceChannelType(str, enum.Enum):
    BOUTIQUEOS = "BOUTIQUEOS"
    LABHA = "LABHA"
    SHOPIFY = "SHOPIFY"
    WHATSAPP = "WHATSAPP"
    INSTAGRAM = "INSTAGRAM"
    MANUAL = "MANUAL"
    POS = "POS"


class ChannelConnectionStatus(str, enum.Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


class ExternalResourceType(str, enum.Enum):
    ITEM = "ITEM"
    ORDER = "ORDER"
    INVOICE = "INVOICE"
    PAYMENT = "PAYMENT"
    REFUND = "REFUND"
    SHIPMENT = "SHIPMENT"
    MESSAGE = "MESSAGE"
    MEDIA = "MEDIA"


class MappingSyncStatus(str, enum.Enum):
    PENDING = "PENDING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"


class IntegrationOutboxStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    inventory_type: Mapped[InventoryType] = mapped_column(Enum(InventoryType), nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    fabric: Mapped[str | None] = mapped_column(String(120), nullable=True)
    color: Mapped[str | None] = mapped_column(String(120), nullable=True)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cost_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    lots: Mapped[list[InventoryLot]] = relationship(back_populates="item")
    movements: Mapped[list[InventoryMovement]] = relationship(back_populates="item")
    media_assets: Mapped[list[MediaAsset]] = relationship(back_populates="item", cascade="all, delete-orphan")


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    media_type: Mapped[MediaType] = mapped_column(Enum(MediaType), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    item: Mapped[Item | None] = relationship(back_populates="media_assets")


class ChannelConnection(Base):
    __tablename__ = "channel_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    channel_type: Mapped[CommerceChannelType] = mapped_column(Enum(CommerceChannelType), nullable=False)
    status: Mapped[ChannelConnectionStatus] = mapped_column(Enum(ChannelConnectionStatus), default=ChannelConnectionStatus.NOT_CONFIGURED, nullable=False)
    external_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    configuration_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("merchant_id", "channel_type", "external_account_id", name="uq_channel_connections_lookup"),)


class ExternalResourceMapping(Base):
    __tablename__ = "external_resource_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    system: Mapped[CommerceChannelType] = mapped_column(Enum(CommerceChannelType), nullable=False)
    resource_type: Mapped[ExternalResourceType] = mapped_column(Enum(ExternalResourceType), nullable=False)
    internal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    sync_status: Mapped[MappingSyncStatus] = mapped_column(Enum(MappingSyncStatus), default=MappingSyncStatus.PENDING, nullable=False)
    last_synced_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("merchant_id", "system", "resource_type", "internal_id", name="uq_resource_mapping_internal"),
        Index("ix_external_resource_mappings_external", "merchant_id", "system", "resource_type", "external_id"),
    )


class IntegrationOutbox(Base):
    __tablename__ = "integration_outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(120), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(120), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[IntegrationOutboxStatus] = mapped_column(Enum(IntegrationOutboxStatus), default=IntegrationOutboxStatus.PENDING, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    processed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_integration_outbox_status_created", "status", "created_at"),
        Index("ix_integration_outbox_next_attempt", "status", "next_attempt_at"),
    )


class InventoryLot(Base):
    __tablename__ = "inventory_lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    lot_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    original_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=Decimal("0"))
    status: Mapped[InventoryStatus] = mapped_column(Enum(InventoryStatus), default=InventoryStatus.AVAILABLE, nullable=False)
    received_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    cost_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    item: Mapped[Item] = relationship(back_populates="lots")
    holds: Mapped[list[Hold]] = relationship(back_populates="lot")
    movements: Mapped[list[InventoryMovement]] = relationship(back_populates="lot")
    allocations: Mapped[list[OrderLineAllocation]] = relationship(back_populates="lot")


class Hold(Base):
    __tablename__ = "holds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inventory_lot_id: Mapped[int] = mapped_column(ForeignKey("inventory_lots.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    expires_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    lot: Mapped[InventoryLot] = relationship(back_populates="holds")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.CONFIRMED, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    lines: Mapped[list[OrderLine]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderLine(Base):
    __tablename__ = "order_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    inventory_lot_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_lots.id"), nullable=True)
    measurement_profile_id: Mapped[int | None] = mapped_column(ForeignKey("measurement_profiles.id"), nullable=True)
    measurement_version_id: Mapped[int | None] = mapped_column(ForeignKey("measurement_versions.id"), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    requires_tailoring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tailoring_stage: Mapped[TailoringStage | None] = mapped_column(Enum(TailoringStage), nullable=True)

    order: Mapped[Order] = relationship(back_populates="lines")
    tailoring_task: Mapped[TailoringTask | None] = relationship(back_populates="order_line", uselist=False)
    allocations: Mapped[list[OrderLineAllocation]] = relationship(back_populates="order_line", cascade="all, delete-orphan")


class MeasurementProfile(Base):
    __tablename__ = "measurement_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    garment_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unit: Mapped[MeasurementUnit] = mapped_column(Enum(MeasurementUnit), default=MeasurementUnit.INCH, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    customer: Mapped[Customer] = relationship(back_populates="measurement_profiles")
    versions: Mapped[list[MeasurementVersion]] = relationship(back_populates="profile", cascade="all, delete-orphan")


class MeasurementVersion(Base):
    __tablename__ = "measurement_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    measurement_profile_id: Mapped[int] = mapped_column(ForeignKey("measurement_profiles.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    measurements: Mapped[dict] = mapped_column(JSON, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)

    profile: Mapped[MeasurementProfile] = relationship(back_populates="versions")


class TailoringTask(Base):
    __tablename__ = "tailoring_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_line_id: Mapped[int] = mapped_column(ForeignKey("order_lines.id"), nullable=False, unique=True)
    stage: Mapped[TailoringStage] = mapped_column(Enum(TailoringStage), default=TailoringStage.MEASUREMENT_PENDING, nullable=False)
    assignee: Mapped[str | None] = mapped_column(String(120), nullable=True)
    due_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    priority: Mapped[TailoringPriority] = mapped_column(Enum(TailoringPriority), default=TailoringPriority.NORMAL, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    order_line: Mapped[OrderLine] = relationship(back_populates="tailoring_task")


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    inventory_lot_id: Mapped[int] = mapped_column(ForeignKey("inventory_lots.id"), nullable=False)
    movement_type: Mapped[InventoryMovementType] = mapped_column(Enum(InventoryMovementType), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    item: Mapped[Item] = relationship(back_populates="movements")
    lot: Mapped[InventoryLot] = relationship(back_populates="movements")


class OrderLineAllocation(Base):
    __tablename__ = "order_line_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_line_id: Mapped[int] = mapped_column(ForeignKey("order_lines.id"), nullable=False)
    inventory_lot_id: Mapped[int] = mapped_column(ForeignKey("inventory_lots.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    order_line: Mapped[OrderLine] = relationship(back_populates="allocations")
    lot: Mapped[InventoryLot] = relationship(back_populates="allocations")
