from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.seed import seed_data


def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()


def setup_function() -> None:
    _reset_db()


def test_merchant_policy_is_configurable() -> None:
    with TestClient(app) as client:
        current = client.get("/api/v2/merchant-policy")
        assert current.status_code == 200
        saved = client.put(
            "/api/v2/merchant-policy",
            json={
                "measurement_edit_mode": "STAGE_AND_TIME",
                "measurement_grace_hours": 12,
                "measurement_lock_stage": "CUTTING",
                "post_lock_requires_approval": True,
                "dashboard_config": {"default": "ADMIN", "widgets": ["sales_today", "tailoring_due"]},
            },
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["measurement_grace_hours"] == 12
        assert saved.json()["measurement_lock_stage"] == "CUTTING"


def test_item_profile_keeps_material_and_tags_separate_from_inventory_behavior() -> None:
    with TestClient(app) as client:
        item = client.post(
            "/api/items",
            json={"name": "Silk Blouse A", "inventory_type": "STOCKED", "category": "Blouse", "fabric": "Silk", "selling_price": "2200", "quantity": "2"},
        ).json()
        response = client.put(
            f"/api/v2/items/{item['id']}/profile",
            json={
                "system_code": "BLO-2609-0001",
                "boutique_code": "B-101",
                "audience": "WOMEN",
                "purpose": "SELLABLE",
                "material_name": "Raw silk",
                "material_details": {"weave": "raw silk", "lining": "cotton"},
                "system_tags": ["BLOUSE"],
                "merchant_tags": ["Bridal", "High touch"],
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["material_name"] == "Raw silk"
        assert body["merchant_tags"] == ["Bridal", "High touch"]


def test_finished_garment_spec_is_stored_on_order_line() -> None:
    with TestClient(app) as client:
        item = client.post(
            "/api/items",
            json={"name": "Custom Blouse", "inventory_type": "UNIQUE", "category": "Blouse", "selling_price": "1800", "quantity": "1"},
        ).json()
        order = client.post(
            "/api/orders",
            json={"customer_id": 1, "lines": [{"item_id": item["id"], "quantity": "1", "requires_tailoring": True}]},
        ).json()
        line_id = order["lines"][0]["id"]
        response = client.put(
            f"/api/v2/order-lines/{line_id}/garment-spec",
            json={"garment_type": "BLOUSE", "finished_values": {"bust": "38", "sleeve_length": "10.5"}, "style_attributes": {"neck": "boat"}},
        )
        assert response.status_code == 200, response.text
        assert response.json()["finished_values"]["bust"] == "38"


def test_required_material_blocks_cutting_until_sourced() -> None:
    with TestClient(app) as client:
        item = client.post(
            "/api/items",
            json={"name": "Tailored Kurta", "inventory_type": "UNIQUE", "category": "Kurta", "selling_price": "3000", "quantity": "1"},
        ).json()
        order = client.post(
            "/api/orders",
            json={"customer_id": 1, "lines": [{"item_id": item["id"], "quantity": "1", "requires_tailoring": True}]},
        ).json()
        line_id = order["lines"][0]["id"]
        tasks = client.get("/api/tailoring/tasks").json()
        task = next(task for task in tasks if task["order_line_id"] == line_id)
        material = client.post(
            f"/api/v2/order-lines/{line_id}/materials",
            json={"name": "Lining", "quantity": "0.8", "unit": "m", "source": "TO_PURCHASE", "status": "NEEDED", "required": True},
        )
        assert material.status_code == 200
        blocked = client.post(f"/api/tailoring/tasks/{task['id']}/transition", json={"stage": "CUTTING"})
        assert blocked.status_code == 409
        patched = client.patch(f"/api/v2/materials/{material.json()['id']}", json={"status": "SOURCED"})
        assert patched.status_code == 200
        allowed = client.post(f"/api/tailoring/tasks/{task['id']}/transition", json={"stage": "CUTTING"})
        assert allowed.status_code == 200, allowed.text


def test_discount_rules_validate_percentage_and_store_governance() -> None:
    with TestClient(app) as client:
        invalid = client.post("/api/v2/discount-rules", json={"name": "Too much", "kind": "PERCENTAGE", "value": "120"})
        assert invalid.status_code == 422
        valid = client.post(
            "/api/v2/discount-rules",
            json={"name": "Sales discretionary", "kind": "PERCENTAGE", "scope": "ORDER", "value": "10", "requires_reason": True, "approval_above_value": "8", "stackable": False},
        )
        assert valid.status_code == 200, valid.text
        assert valid.json()["approval_above_value"] == "8.00"
