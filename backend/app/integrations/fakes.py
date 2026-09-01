from __future__ import annotations

from dataclasses import dataclass, field

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
from app.integrations.ports import (
    AccountingPort,
    AIEnrichmentPort,
    CommerceChannelPort,
    LogisticsPort,
    MediaStoragePort,
    MessagingPort,
    PaymentGatewayPort,
)
from app.models import CommerceChannelType


@dataclass
class FakeCommerceChannelAdapter(CommerceChannelPort):
    published_items: list[CatalogItemExport] = field(default_factory=list)
    inventory_updates: list[InventoryAvailabilityExport] = field(default_factory=list)
    unpublished: list[ExternalReference] = field(default_factory=list)

    def publish_item(self, item: CatalogItemExport) -> ExternalReference:
        self.published_items.append(item)
        return ExternalReference(system=CommerceChannelType.SHOPIFY, resource_type="ITEM", external_id=f"fake-{item.item_id}")

    def update_inventory(self, availability: InventoryAvailabilityExport) -> None:
        self.inventory_updates.append(availability)

    def unpublish_item(self, reference: ExternalReference) -> None:
        self.unpublished.append(reference)


@dataclass
class FakeAccountingAdapter(AccountingPort):
    exported_invoices: list[InvoiceExport] = field(default_factory=list)

    def export_invoice(self, invoice: InvoiceExport) -> ExternalReference:
        self.exported_invoices.append(invoice)
        return ExternalReference(system=CommerceChannelType.MANUAL, resource_type="INVOICE", external_id=invoice.invoice_id)


@dataclass
class FakePaymentAdapter(PaymentGatewayPort):
    captured_payments: list[PaymentExport] = field(default_factory=list)
    refunded_payments: list[RefundExport] = field(default_factory=list)

    def capture_payment(self, payment: PaymentExport) -> ExternalReference:
        self.captured_payments.append(payment)
        return ExternalReference(system=CommerceChannelType.MANUAL, resource_type="PAYMENT", external_id=payment.payment_id)

    def refund_payment(self, refund: RefundExport) -> ExternalReference:
        self.refunded_payments.append(refund)
        return ExternalReference(system=CommerceChannelType.MANUAL, resource_type="REFUND", external_id=refund.refund_id)


@dataclass
class FakeLogisticsAdapter(LogisticsPort):
    created_shipments: list[ShipmentRequest] = field(default_factory=list)
    updated_shipments: list[ShipmentStatus] = field(default_factory=list)

    def create_shipment(self, request: ShipmentRequest) -> ExternalReference:
        self.created_shipments.append(request)
        return ExternalReference(system=CommerceChannelType.MANUAL, resource_type="SHIPMENT", external_id=request.shipment_id)

    def update_shipment(self, status: ShipmentStatus) -> None:
        self.updated_shipments.append(status)


@dataclass
class FakeMessagingAdapter(MessagingPort):
    sent_messages: list[MessageRequest] = field(default_factory=list)

    def send_message(self, request: MessageRequest) -> ExternalReference:
        self.sent_messages.append(request)
        return ExternalReference(system=CommerceChannelType.WHATSAPP, resource_type="MESSAGE", external_id=f"msg-{len(self.sent_messages)}")


@dataclass
class FakeAIEnrichmentAdapter(AIEnrichmentPort):
    requests: list[ProductMediaAnalysisRequest] = field(default_factory=list)

    def analyze_media(self, request: ProductMediaAnalysisRequest) -> ProductMediaAnalysisResult:
        self.requests.append(request)
        return ProductMediaAnalysisResult(
            category="Ethnic Wear",
            subcategory="Kurta",
            color_family="Red",
            fabric_guess="Silk",
            work_type="Embroidery",
            occasion="Festive",
            suggested_title="Elegant Festive Kurta",
            suggested_description="A deterministic AI-free suggestion for testing.",
            confidence_by_field={"category": 1.0, "subcategory": 1.0},
            warnings=[],
        )
