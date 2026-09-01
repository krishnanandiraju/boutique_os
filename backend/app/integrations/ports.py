from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from fastapi import UploadFile

from app.integrations.dto import (
    CatalogItemExport,
    ExternalReference,
    InventoryAvailabilityExport,
    InvoiceExport,
    MessageRequest,
    PaymentExport,
    ProductMediaAnalysisRequest,
    ProductMediaAnalysisResult,
    RefundExport,
    ShipmentRequest,
    ShipmentStatus,
)


class CommerceChannelPort(Protocol):
    def publish_item(self, item: CatalogItemExport) -> ExternalReference: ...

    def update_inventory(self, availability: InventoryAvailabilityExport) -> None: ...

    def unpublish_item(self, reference: ExternalReference) -> None: ...


class AccountingPort(Protocol):
    def export_invoice(self, invoice: InvoiceExport) -> ExternalReference: ...


class PaymentGatewayPort(Protocol):
    def capture_payment(self, payment: PaymentExport) -> ExternalReference: ...

    def refund_payment(self, refund: RefundExport) -> ExternalReference: ...


class LogisticsPort(Protocol):
    def create_shipment(self, request: ShipmentRequest) -> ExternalReference: ...

    def update_shipment(self, status: ShipmentStatus) -> None: ...


class MessagingPort(Protocol):
    def send_message(self, request: MessageRequest) -> ExternalReference: ...


@runtime_checkable
class MediaStoragePort(Protocol):
    def save(self, file: UploadFile, merchant_id: int, *, item_id: int | None = None) -> tuple[str, Path]: ...

    def delete(self, storage_key: str) -> None: ...

    def exists(self, storage_key: str) -> bool: ...


class AIEnrichmentPort(Protocol):
    def analyze_media(self, request: ProductMediaAnalysisRequest) -> ProductMediaAnalysisResult: ...
