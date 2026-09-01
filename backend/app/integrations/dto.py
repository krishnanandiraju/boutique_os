from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field

from app.schemas import AppSchema
from app.models import CommerceChannelType, InventoryType, OrderStatus, MediaType


class ExternalReference(AppSchema):
    system: CommerceChannelType
    resource_type: str
    external_id: str


class CatalogMediaExport(AppSchema):
    media_id: int
    storage_key: str
    mime_type: str
    media_type: MediaType
    is_primary: bool = False
    sort_order: int = 0
    url: str | None = None


class CatalogItemExport(AppSchema):
    item_id: int
    merchant_id: int
    name: str
    description: str | None = None
    category: str
    selling_price: Decimal
    currency: str = "INR"
    media: list[CatalogMediaExport] = Field(default_factory=list)
    availability: str
    attributes: dict[str, str] = Field(default_factory=dict)


class InventoryAvailabilityExport(AppSchema):
    item_id: int
    inventory_type: InventoryType
    available_quantity: Decimal
    sellable: bool
    updated_at: datetime


class OrderImportCustomer(AppSchema):
    external_customer_id: str | None = None
    name: str
    phone: str | None = None
    email: str | None = None


class OrderImportLine(AppSchema):
    external_line_id: str | None = None
    item_id: int
    quantity: Decimal
    unit_price: Decimal
    currency: str = "INR"


class OrderImport(AppSchema):
    source_channel: CommerceChannelType
    external_order_id: str
    customer: OrderImportCustomer
    lines: list[OrderImportLine]
    totals: dict[str, Decimal]
    payment_status: str | None = None


class OrderExportLine(AppSchema):
    item_id: int
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class OrderExport(AppSchema):
    order_id: int
    merchant_id: int
    customer_id: int
    status: OrderStatus
    total_amount: Decimal
    currency: str = "INR"
    lines: list[OrderExportLine]


class InvoiceExport(AppSchema):
    invoice_id: str
    order_id: int
    merchant_id: int
    customer_id: int
    total_amount: Decimal
    currency: str = "INR"


class PaymentExport(AppSchema):
    payment_id: str
    order_id: int
    merchant_id: int
    amount: Decimal
    currency: str = "INR"
    payment_status: str


class RefundExport(AppSchema):
    refund_id: str
    payment_id: str
    merchant_id: int
    amount: Decimal
    currency: str = "INR"
    reason: str | None = None


class ShipmentRequest(AppSchema):
    shipment_id: str
    order_id: int
    merchant_id: int
    customer_id: int
    destination: dict[str, str] = Field(default_factory=dict)
    package: dict[str, Any] = Field(default_factory=dict)


class ShipmentStatus(AppSchema):
    shipment_id: str
    status: str
    carrier_name: str | None = None
    tracking_number: str | None = None


class MessageRequest(AppSchema):
    channel: CommerceChannelType
    recipient: str
    subject: str | None = None
    body: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductMediaAnalysisRequest(AppSchema):
    merchant_id: int
    item_id: int | None = None
    media: list[CatalogMediaExport] = Field(default_factory=list)
    merchant_language: str | None = None
    merchant_tone: str | None = None


class ProductMediaAnalysisResult(AppSchema):
    category: str | None = None
    subcategory: str | None = None
    color_family: str | None = None
    fabric_guess: str | None = None
    work_type: str | None = None
    occasion: str | None = None
    suggested_title: str | None = None
    suggested_description: str | None = None
    confidence_by_field: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
