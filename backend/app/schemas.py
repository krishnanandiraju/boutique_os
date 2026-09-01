from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    InventoryMovementType,
    InventoryStatus,
    InventoryType,
    MeasurementUnit,
    MediaType,
    OrderStatus,
    TailoringPriority,
    TailoringStage,
)


class AppSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class CustomerCreate(AppSchema):
    merchant_id: int = 1
    name: str
    phone: str
    email: str | None = None
    notes: str | None = None


class CustomerRead(CustomerCreate):
    id: int


class ItemCreate(AppSchema):
    merchant_id: int = 1
    name: str
    sku: str | None = None
    inventory_type: InventoryType
    category: str
    fabric: str | None = None
    color: str | None = None
    selling_price: Decimal
    cost_price: Decimal | None = None
    published: bool = True
    quantity: Decimal = Field(default=Decimal("1"), gt=Decimal("0"))


class ItemRead(AppSchema):
    id: int
    merchant_id: int
    name: str
    sku: str | None
    inventory_type: InventoryType
    category: str
    fabric: str | None
    color: str | None
    selling_price: Decimal
    cost_price: Decimal | None
    published: bool
    created_at: datetime
    availability: str
    hold_expires_at: datetime | None = None
    quantity_available: Decimal = Decimal("0")


class HoldRequest(AppSchema):
    customer_id: int
    ttl_hours: int = 24


class HoldRead(AppSchema):
    id: int
    inventory_lot_id: int
    customer_id: int
    expires_at: datetime
    released_at: datetime | None
    created_at: datetime


class OrderLineAllocationRead(AppSchema):
    id: int
    order_line_id: int
    inventory_lot_id: int
    lot_code: str | None = None
    quantity: Decimal
    created_at: datetime


class OrderLineCreate(AppSchema):
    item_id: int
    quantity: Decimal = Field(gt=Decimal("0"))
    requires_tailoring: bool = False
    measurement_profile_id: int | None = None
    measurement_version_id: int | None = None


class OrderCreate(AppSchema):
    merchant_id: int = 1
    customer_id: int
    status: OrderStatus = OrderStatus.CONFIRMED
    lines: list[OrderLineCreate]


class OrderLineRead(AppSchema):
    id: int
    item_id: int
    item_name: str | None = None
    inventory_lot_id: int | None
    measurement_profile_id: int | None = None
    measurement_version_id: int | None = None
    measurement_profile_name: str | None = None
    measurement_garment_type: str | None = None
    measurement_unit: MeasurementUnit | None = None
    measurement_values: dict[str, Any] | None = None
    measurement_version_number: int | None = None
    allocations: list[OrderLineAllocationRead] = Field(default_factory=list)
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    requires_tailoring: bool
    tailoring_stage: TailoringStage | None


class OrderRead(AppSchema):
    id: int
    merchant_id: int
    customer_id: int
    status: OrderStatus
    total_amount: Decimal
    created_at: datetime
    lines: list[OrderLineRead]


class InventoryStateRead(AppSchema):
    item_id: int
    item_name: str
    inventory_type: InventoryType
    status: InventoryStatus
    quantity_available: Decimal


class OrderDetailRead(OrderRead):
    inventory_state: list[InventoryStateRead]


class OrderStatusPatch(AppSchema):
    status: OrderStatus


class TailoringStagePatch(AppSchema):
    tailoring_stage: TailoringStage


class DashboardRead(AppSchema):
    sales_today: Decimal
    available_items: int
    held_items: int
    orders_pending: int
    tailoring_pending: int
    low_stock_items: int = 0
    remnant_rolls: int = 0


class MeasurementVersionCreate(AppSchema):
    measurements: dict[str, Decimal | int | float]
    notes: str | None = None
    created_by: str | None = None


class MeasurementProfileCreate(AppSchema):
    name: str
    garment_type: str | None = None
    unit: MeasurementUnit = MeasurementUnit.INCH
    is_active: bool = True
    measurements: dict[str, Decimal | int | float]
    notes: str | None = None
    created_by: str | None = None


class MeasurementVersionRead(AppSchema):
    id: int
    measurement_profile_id: int
    version_number: int
    measurements: dict[str, Any]
    notes: str | None
    created_at: datetime
    created_by: str | None


class MeasurementProfileRead(AppSchema):
    id: int
    customer_id: int
    name: str
    garment_type: str | None
    unit: MeasurementUnit
    is_active: bool
    created_at: datetime
    updated_at: datetime
    latest_version: MeasurementVersionRead | None = None


class MeasurementProfileDetailRead(MeasurementProfileRead):
    versions: list[MeasurementVersionRead]


class TailoringTaskRead(AppSchema):
    id: int
    order_line_id: int
    stage: TailoringStage
    assignee: str | None
    due_at: datetime | None
    priority: TailoringPriority
    notes: str | None
    created_at: datetime
    updated_at: datetime
    customer_id: int
    customer_name: str
    order_id: int
    order_status: OrderStatus
    item_id: int
    item_name: str
    measurement_profile_id: int | None
    measurement_profile_name: str | None
    measurement_version_id: int | None
    measurement_version_number: int | None
    measurement_unit: MeasurementUnit | None
    measurement_values: dict[str, Any] | None


class TailoringTaskPatch(AppSchema):
    stage: TailoringStage | None = None
    assignee: str | None = None
    due_at: datetime | None = None
    priority: TailoringPriority | None = None
    notes: str | None = None


class InventoryLotCreate(AppSchema):
    lot_code: str | None = None
    quantity: Decimal = Field(gt=Decimal("0"))
    received_at: datetime | None = None
    cost_price: Decimal | None = None
    notes: str | None = None


class InventoryLotRead(AppSchema):
    id: int
    item_id: int
    lot_code: str | None
    quantity: Decimal
    original_quantity: Decimal
    status: InventoryStatus
    received_at: datetime
    cost_price: Decimal | None
    notes: str | None
    created_at: datetime


class InventoryLotAdjustRequest(AppSchema):
    adjustment_type: InventoryMovementType
    quantity: Decimal = Field(gt=Decimal("0"))
    reason: str | None = None


class InventoryMovementRead(AppSchema):
    id: int
    merchant_id: int
    item_id: int
    inventory_lot_id: int
    movement_type: InventoryMovementType
    quantity: Decimal
    reference_type: str | None
    reference_id: int | None
    reason: str | None
    created_at: datetime


class MediaAssetRead(AppSchema):
    id: int
    merchant_id: int
    item_id: int | None = None
    media_type: MediaType
    storage_key: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    width: int | None = None
    height: int | None = None
    duration_seconds: Decimal | None = None
    sort_order: int = 0
    is_primary: bool = False
    created_at: datetime
    updated_at: datetime


class MediaAssetPatch(AppSchema):
    is_primary: bool | None = None
    sort_order: int | None = None


class MediaUploadResponse(MediaAssetRead):
    url: str | None = None


