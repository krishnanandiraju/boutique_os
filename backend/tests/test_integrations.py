from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.integrations.dto import CatalogItemExport, InvoiceExport, ProductMediaAnalysisRequest
from app.integrations.fakes import FakeAIEnrichmentAdapter, FakeAccountingAdapter, FakeCommerceChannelAdapter
from app.integrations.ports import MediaStoragePort
from app.integrations.service import IntegrationEventService, IntegrationProcessor
from app.main import app
from app.models import CommerceChannelType, ExternalResourceMapping, ExternalResourceType, IntegrationOutboxStatus, Item, MappingSyncStatus
from app.seed import seed_data
from app.services.media_service import LocalMediaStorage


@pytest.fixture(autouse=True)
def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _create_item(client: TestClient, name: str, inventory_type: str, price: str, quantity: str) -> int:
    response = client.post(
        "/api/items",
        json={
            "name": name,
            "inventory_type": inventory_type,
            "category": "Test",
            "fabric": "Silk",
            "color": "Red",
            "selling_price": price,
            "quantity": quantity,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_commerce_channels_support_labha_and_shopify() -> None:
    assert CommerceChannelType.LABHA.value == "LABHA"
    assert CommerceChannelType.SHOPIFY.value == "SHOPIFY"


def test_external_resource_mapping_supports_multiple_channels(db_session) -> None:
    service = IntegrationEventService()
    item = db_session.query(Item).first()
    assert item is not None

    service.record_mapping(
        db_session,
        merchant_id=item.merchant_id,
        system=CommerceChannelType.SHOPIFY,
        resource_type=ExternalResourceType.ITEM,
        internal_id=item.id,
        external_id="shopify-item-1",
        sync_status=MappingSyncStatus.SYNCED,
    )
    service.record_mapping(
        db_session,
        merchant_id=item.merchant_id,
        system=CommerceChannelType.LABHA,
        resource_type=ExternalResourceType.ITEM,
        internal_id=item.id,
        external_id="labha-item-1",
    )
    db_session.commit()

    rows = db_session.query(ExternalResourceMapping).filter(ExternalResourceMapping.internal_id == item.id).all()
    assert len(rows) == 2
    assert {row.system for row in rows} == {CommerceChannelType.SHOPIFY, CommerceChannelType.LABHA}
    assert "shopify_product_id" not in Item.__table__.columns


def test_order_creation_emits_outbox_events(client: TestClient) -> None:
    item_id = _create_item(client, "Outbox Stock Item", "STOCKED", "500.00", "3")
    response = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "lines": [{"item_id": item_id, "quantity": "1", "requires_tailoring": False}],
        },
    )
    assert response.status_code == 200, response.text

    outbox = client.get("/api/integrations/outbox")
    assert outbox.status_code == 200
    payload = outbox.json()
    assert {entry["event_type"] for entry in payload} == {"order.created", "inventory.changed"}
    assert all(entry["status"] == "PENDING" for entry in payload)


def test_failed_order_transaction_emits_no_outbox_events(client: TestClient) -> None:
    item_id = _create_item(client, "Rollback Item", "STOCKED", "500.00", "1")
    response = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "lines": [{"item_id": item_id, "quantity": "2", "requires_tailoring": False}],
        },
    )
    assert response.status_code == 409
    assert client.get("/api/integrations/outbox").json() == []


def test_successful_order_commits_business_data_and_outbox_together(client: TestClient) -> None:
    item_id = _create_item(client, "Atomic Outbox Item", "STOCKED", "750.00", "2")
    response = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "lines": [{"item_id": item_id, "quantity": "1", "requires_tailoring": False}],
        },
    )
    assert response.status_code == 200, response.text
    assert client.get(f"/api/orders/{response.json()['id']}").status_code == 200
    assert len(client.get("/api/integrations/outbox").json()) == 2


def test_integration_outbox_starts_pending(db_session) -> None:
    service = IntegrationEventService()
    event = service.enqueue(
        db_session,
        merchant_id=1,
        event_type="order.created",
        aggregate_type="Order",
        aggregate_id="1",
        payload={"order_id": 1},
    )
    db_session.commit()
    assert event.status == IntegrationOutboxStatus.PENDING


def test_successful_processor_marks_processed(db_session) -> None:
    service = IntegrationEventService()
    event = service.enqueue(
        db_session,
        merchant_id=1,
        event_type="order.created",
        aggregate_type="Order",
        aggregate_id="1",
        payload={"order_id": 1},
    )
    db_session.commit()

    processor = IntegrationProcessor(handlers={"order.created": lambda payload: None})
    assert processor.process_event(db_session, event.event_id) == "processed"
    refreshed = db_session.get(type(event), event.id)
    assert refreshed is not None
    assert refreshed.status == IntegrationOutboxStatus.PROCESSED


def test_adapter_failure_marks_failed_and_increments_attempt_count(db_session) -> None:
    service = IntegrationEventService()
    event = service.enqueue(
        db_session,
        merchant_id=1,
        event_type="order.created",
        aggregate_type="Order",
        aggregate_id="1",
        payload={"order_id": 1},
    )
    db_session.commit()

    processor = IntegrationProcessor(handlers={"order.created": lambda payload: (_ for _ in ()).throw(RuntimeError("boom"))})
    assert processor.process_event(db_session, event.event_id) == "failed"
    refreshed = db_session.get(type(event), event.id)
    assert refreshed is not None
    assert refreshed.status == IntegrationOutboxStatus.FAILED
    assert refreshed.attempt_count == 1


def test_failed_event_can_be_retried(db_session) -> None:
    service = IntegrationEventService()
    event = service.enqueue(
        db_session,
        merchant_id=1,
        event_type="order.created",
        aggregate_type="Order",
        aggregate_id="1",
        payload={"order_id": 1},
    )
    db_session.commit()
    processor = IntegrationProcessor(handlers={"order.created": lambda payload: (_ for _ in ()).throw(RuntimeError("boom"))})
    assert processor.process_event(db_session, event.event_id) == "failed"
    retry = service.retry(db_session, event.event_id)
    db_session.commit()
    assert retry is not None
    assert retry.status == IntegrationOutboxStatus.PENDING


def test_processed_event_is_idempotent(db_session) -> None:
    service = IntegrationEventService()
    event = service.enqueue(
        db_session,
        merchant_id=1,
        event_type="order.created",
        aggregate_type="Order",
        aggregate_id="1",
        payload={"order_id": 1},
    )
    db_session.commit()
    calls: list[dict] = []
    processor = IntegrationProcessor(handlers={"order.created": lambda payload: calls.append(payload)})
    assert processor.process_event(db_session, event.event_id) == "processed"
    assert processor.process_event(db_session, event.event_id) == "already_processed"
    assert len(calls) == 1


def test_external_adapter_failure_does_not_roll_back_internal_order(client: TestClient) -> None:
    item_id = _create_item(client, "External Failure Item", "STOCKED", "650.00", "2")
    response = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "lines": [{"item_id": item_id, "quantity": "1", "requires_tailoring": False}],
        },
    )
    assert response.status_code == 200, response.text
    outbox_id = client.get("/api/integrations/outbox").json()[0]["id"]
    retry = client.post(f"/api/integrations/outbox/{outbox_id}/retry")
    assert retry.status_code == 200


def test_fake_adapters_receive_canonical_dtos() -> None:
    commerce = FakeCommerceChannelAdapter()
    accounting = FakeAccountingAdapter()
    ai = FakeAIEnrichmentAdapter()

    commerce.publish_item(
        CatalogItemExport(
            item_id=1,
            merchant_id=1,
            name="Sample Item",
            category="Category",
            selling_price=Decimal("100.00"),
            availability="AVAILABLE",
        )
    )
    accounting.export_invoice(
        InvoiceExport(invoice_id="inv-1", order_id=1, merchant_id=1, customer_id=1, total_amount=Decimal("100.00"))
    )
    ai.analyze_media(ProductMediaAnalysisRequest(merchant_id=1))

    assert commerce.published_items[0].name == "Sample Item"
    assert accounting.exported_invoices[0].invoice_id == "inv-1"
    assert ai.requests[0].merchant_id == 1


def test_local_media_storage_satisfies_port_contract(tmp_path: Path) -> None:
    storage = LocalMediaStorage(tmp_path)
    assert isinstance(storage, MediaStoragePort)


def test_core_modules_have_no_vendor_dependency() -> None:
    forbidden = ("shopify", "labha", "razorpay", "cashfree", "shiprocket")
    for path in Path("app/services").rglob("*.py"):
        if "integrations" in path.parts or "adapters" in path.parts:
            continue
        text = path.read_text(encoding="utf-8").lower()
        assert not any(word in text for word in forbidden), path
