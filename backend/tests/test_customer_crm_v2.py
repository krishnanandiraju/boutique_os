from fastapi.testclient import TestClient
import pytest

from app.db import Base, SessionLocal, engine
from app.main import app
from app.seed import seed_data


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


def test_customer_profile_can_store_boutique_crm_context(client: TestClient) -> None:
    response = client.put(
        "/api/v2/customers/1/profile",
        json={
            "address_line1": "Miyapur Main Road",
            "city": "Hyderabad",
            "state": "Telangana",
            "postal_code": "500049",
            "country": "India",
            "preferred_language": "Telugu",
            "acquisition_source": "Instagram",
            "acquisition_detail": "Festive saree reel",
            "customer_segment": "VIP",
            "merchant_tags": ["bridal", "silk-lover"],
            "preferences": {"style_notes": "Prefers jewel tones"},
            "marketing_consent": True,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["city"] == "Hyderabad"
    assert data["customer_segment"] == "VIP"
    assert data["merchant_tags"] == ["bridal", "silk-lover"]
    assert "metrics" in data


def test_customer_anniversary_can_carry_offer(client: TestClient) -> None:
    response = client.post(
        "/api/v2/customers/1/occasions",
        json={
            "occasion_type": "WEDDING_ANNIVERSARY",
            "label": "Wedding anniversary",
            "event_date": "2025-11-20",
            "recurring_annually": True,
            "offer_kind": "PERCENTAGE",
            "offer_value": "15",
            "offer_code": "ANNIV15",
            "lead_days": 21,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["offer_kind"] == "PERCENTAGE"
    assert data["offer_code"] == "ANNIV15"
    assert data["anniversary_number"] is not None
    assert data["next_occurrence"]


def test_customer_summary_exposes_crm_metrics_and_next_event(client: TestClient) -> None:
    client.put(
        "/api/v2/customers/1/profile",
        json={
            "city": "Hyderabad",
            "country": "India",
            "customer_segment": "Regular",
            "merchant_tags": ["festive"],
            "preferences": {},
            "marketing_consent": True,
        },
    )
    client.post(
        "/api/v2/customers/1/occasions",
        json={
            "occasion_type": "CUSTOM",
            "label": "First boutique anniversary offer",
            "event_date": "2026-12-01",
            "recurring_annually": True,
            "offer_kind": "FLAT",
            "offer_value": "500",
            "lead_days": 10,
        },
    )
    response = client.get("/api/v2/customers/profiles")
    assert response.status_code == 200, response.text
    row = next(item for item in response.json() if item["customer_id"] == 1)
    assert row["city"] == "Hyderabad"
    assert row["merchant_tags"] == ["festive"]
    assert row["next_event_label"] == "First boutique anniversary offer"
    assert "average_order_value" in row
