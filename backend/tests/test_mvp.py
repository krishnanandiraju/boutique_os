from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

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


def _create_unique_item(client: TestClient, name: str, price: str = "1000.00") -> int:
    return _create_item(client, name, "UNIQUE", price, "1")


def _create_stocked_item(client: TestClient, name: str, quantity: str, price: str = "100.00") -> int:
    return _create_item(client, name, "STOCKED", price, quantity)


def _create_yardage_item(client: TestClient, name: str, quantity: str, price: str = "10.00") -> int:
    return _create_item(client, name, "YARDAGE", price, quantity)


def test_health_endpoint_works(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unique_item_can_be_held(client: TestClient) -> None:
    item_id = _create_unique_item(client, "Unique Hold Test A")
    response = client.post(f"/api/items/{item_id}/hold", json={"customer_id": 1, "ttl_hours": 24})

    assert response.status_code == 200
    assert response.json()["customer_id"] == 1


def test_same_unique_item_cannot_get_second_active_hold(client: TestClient) -> None:
    item_id = _create_unique_item(client, "Unique Hold Test B")
    first = client.post(f"/api/items/{item_id}/hold", json={"customer_id": 1, "ttl_hours": 24})
    second = client.post(f"/api/items/{item_id}/hold", json={"customer_id": 2, "ttl_hours": 24})

    assert first.status_code == 200
    assert second.status_code == 409


def test_expired_hold_allows_another_hold(client: TestClient) -> None:
    item_id = _create_unique_item(client, "Unique Hold Test C")
    first = client.post(f"/api/items/{item_id}/hold", json={"customer_id": 1, "ttl_hours": 0})
    second = client.post(f"/api/items/{item_id}/hold", json={"customer_id": 2, "ttl_hours": 24})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["customer_id"] == 2


def test_unique_item_can_be_sold(client: TestClient) -> None:
    item_id = _create_unique_item(client, "Unique Sell Test A")
    response = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "lines": [
                {
                    "item_id": item_id,
                    "quantity": "1",
                    "requires_tailoring": False,
                }
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["total_amount"]) == Decimal("1000.00")


def test_sold_unique_item_cannot_be_sold_again(client: TestClient) -> None:
    item_id = _create_unique_item(client, "Unique Sell Test B")
    first = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "lines": [{"item_id": item_id, "quantity": "1", "requires_tailoring": False}],
        },
    )
    second = client.post(
        "/api/orders",
        json={
            "customer_id": 2,
            "lines": [{"item_id": item_id, "quantity": "1", "requires_tailoring": False}],
        },
    )

    assert first.status_code == 200
    assert second.status_code == 409


def test_multi_line_mixed_order_succeeds_and_totals(client: TestClient) -> None:
    unique_id = _create_unique_item(client, "Mixed Unique", "48000.00")
    stocked_id = _create_stocked_item(client, "Mixed Stocked", "5", "4500.00")
    yardage_id = _create_yardage_item(client, "Mixed Yardage", "22.500", "1850.00")

    response = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "lines": [
                {"item_id": unique_id, "quantity": "1", "requires_tailoring": True},
                {"item_id": stocked_id, "quantity": "1", "requires_tailoring": True},
                {"item_id": yardage_id, "quantity": "3.5", "requires_tailoring": False},
            ],
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["lines"]) == 3
    assert Decimal(data["total_amount"]) == Decimal("58975.00")

    by_item = {line["item_id"]: line for line in data["lines"]}
    assert by_item[unique_id]["tailoring_stage"] == "MEASUREMENT_PENDING"
    assert by_item[stocked_id]["tailoring_stage"] == "MEASUREMENT_PENDING"
    assert by_item[yardage_id]["tailoring_stage"] is None


def test_stocked_and_yardage_quantities_decrement(client: TestClient) -> None:
    stocked_id = _create_stocked_item(client, "Stock Decrement", "8", "200.00")
    yardage_id = _create_yardage_item(client, "Yardage Decrement", "22.500", "100.00")

    response = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "lines": [
                {"item_id": stocked_id, "quantity": "3", "requires_tailoring": False},
                {"item_id": yardage_id, "quantity": "3.5", "requires_tailoring": False},
            ],
        },
    )
    assert response.status_code == 200, response.text

    stocked = client.get(f"/api/items/{stocked_id}").json()
    yardage = client.get(f"/api/items/{yardage_id}").json()

    assert Decimal(stocked["quantity_available"]) == Decimal("5")
    assert Decimal(yardage["quantity_available"]) == Decimal("19.000")


def test_unique_becomes_sold_after_multi_line_order(client: TestClient) -> None:
    unique_id = _create_unique_item(client, "Unique Sold In Cart")
    stocked_id = _create_stocked_item(client, "Stock Helper", "2")

    response = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "lines": [
                {"item_id": unique_id, "quantity": "1", "requires_tailoring": False},
                {"item_id": stocked_id, "quantity": "1", "requires_tailoring": False},
            ],
        },
    )
    assert response.status_code == 200

    unique = client.get(f"/api/items/{unique_id}").json()
    assert unique["availability"] == "SOLD"


def test_insufficient_stocked_rejects_entire_order(client: TestClient) -> None:
    unique_id = _create_unique_item(client, "Atomic Unique A")
    stocked_id = _create_stocked_item(client, "Atomic Stock A", "2")

    before_orders = len(client.get("/api/orders").json())
    before_unique = client.get(f"/api/items/{unique_id}").json()
    before_stocked = client.get(f"/api/items/{stocked_id}").json()

    response = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "lines": [
                {"item_id": unique_id, "quantity": "1", "requires_tailoring": False},
                {"item_id": stocked_id, "quantity": "3", "requires_tailoring": False},
            ],
        },
    )
    assert response.status_code == 409

    after_orders = len(client.get("/api/orders").json())
    after_unique = client.get(f"/api/items/{unique_id}").json()
    after_stocked = client.get(f"/api/items/{stocked_id}").json()

    assert before_orders == after_orders
    assert before_unique["availability"] == "AVAILABLE"
    assert after_unique["availability"] == "AVAILABLE"
    assert Decimal(before_stocked["quantity_available"]) == Decimal("2")
    assert Decimal(after_stocked["quantity_available"]) == Decimal("2")


def test_insufficient_yardage_rejects_entire_order(client: TestClient) -> None:
    unique_id = _create_unique_item(client, "Atomic Unique B")
    yardage_id = _create_yardage_item(client, "Atomic Yardage B", "2.000")

    before_unique = client.get(f"/api/items/{unique_id}").json()
    before_yardage = client.get(f"/api/items/{yardage_id}").json()

    response = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "lines": [
                {"item_id": unique_id, "quantity": "1", "requires_tailoring": False},
                {"item_id": yardage_id, "quantity": "3.5", "requires_tailoring": False},
            ],
        },
    )
    assert response.status_code == 409

    after_unique = client.get(f"/api/items/{unique_id}").json()
    after_yardage = client.get(f"/api/items/{yardage_id}").json()
    assert before_unique["availability"] == "AVAILABLE"
    assert after_unique["availability"] == "AVAILABLE"
    assert Decimal(before_yardage["quantity_available"]) == Decimal("2.000")
    assert Decimal(after_yardage["quantity_available"]) == Decimal("2.000")


def test_unique_held_by_same_customer_can_be_purchased(client: TestClient) -> None:
    unique_id = _create_unique_item(client, "Held Same Customer")
    hold = client.post(f"/api/items/{unique_id}/hold", json={"customer_id": 1, "ttl_hours": 24})
    assert hold.status_code == 200

    response = client.post(
        "/api/orders",
        json={"customer_id": 1, "lines": [{"item_id": unique_id, "quantity": "1", "requires_tailoring": False}]},
    )
    assert response.status_code == 200


def test_unique_held_by_another_customer_is_rejected(client: TestClient) -> None:
    unique_id = _create_unique_item(client, "Held Another Customer")
    hold = client.post(f"/api/items/{unique_id}/hold", json={"customer_id": 1, "ttl_hours": 24})
    assert hold.status_code == 200

    response = client.post(
        "/api/orders",
        json={"customer_id": 2, "lines": [{"item_id": unique_id, "quantity": "1", "requires_tailoring": False}]},
    )
    assert response.status_code == 409


def test_expired_hold_can_be_purchased(client: TestClient) -> None:
    unique_id = _create_unique_item(client, "Expired Hold Purchase")
    hold = client.post(f"/api/items/{unique_id}/hold", json={"customer_id": 1, "ttl_hours": 0})
    assert hold.status_code == 200

    response = client.post(
        "/api/orders",
        json={"customer_id": 2, "lines": [{"item_id": unique_id, "quantity": "1", "requires_tailoring": False}]},
    )
    assert response.status_code == 200


def test_duplicate_unique_item_in_same_cart_rejected(client: TestClient) -> None:
    unique_id = _create_unique_item(client, "Duplicate Unique")
    response = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "lines": [
                {"item_id": unique_id, "quantity": "1", "requires_tailoring": False},
                {"item_id": unique_id, "quantity": "1", "requires_tailoring": False},
            ],
        },
    )
    assert response.status_code == 400


def test_empty_cart_rejected(client: TestClient) -> None:
    response = client.post("/api/orders", json={"customer_id": 1, "lines": []})
    assert response.status_code == 400


def test_fractional_stocked_quantity_rejected(client: TestClient) -> None:
    stocked_id = _create_stocked_item(client, "Stock Fraction", "4")
    response = client.post(
        "/api/orders",
        json={"customer_id": 1, "lines": [{"item_id": stocked_id, "quantity": "1.5", "requires_tailoring": False}]},
    )
    assert response.status_code == 400


def test_unique_quantity_not_one_rejected(client: TestClient) -> None:
    unique_id = _create_unique_item(client, "Unique Qty Rule")
    response = client.post(
        "/api/orders",
        json={"customer_id": 1, "lines": [{"item_id": unique_id, "quantity": "2", "requires_tailoring": False}]},
    )
    assert response.status_code == 400


def test_mandatory_atomic_regression_valid_plus_invalid_line_rollback(client: TestClient) -> None:
    lehenga_id = _create_unique_item(client, "Regression Lehenga", "48000.00")
    kurta_id = _create_stocked_item(client, "Regression Kurta", "2", "2499.00")

    before_order_count = len(client.get("/api/orders").json())
    before_lehenga = client.get(f"/api/items/{lehenga_id}").json()
    before_kurta = client.get(f"/api/items/{kurta_id}").json()

    response = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "lines": [
                {"item_id": lehenga_id, "quantity": "1", "requires_tailoring": False},
                {"item_id": kurta_id, "quantity": "3", "requires_tailoring": False},
            ],
        },
    )

    assert response.status_code == 409

    after_order_count = len(client.get("/api/orders").json())
    after_lehenga = client.get(f"/api/items/{lehenga_id}").json()
    after_kurta = client.get(f"/api/items/{kurta_id}").json()

    assert before_order_count == after_order_count
    assert before_lehenga["availability"] == "AVAILABLE"
    assert after_lehenga["availability"] == "AVAILABLE"
    assert Decimal(before_kurta["quantity_available"]) == Decimal("2")
    assert Decimal(after_kurta["quantity_available"]) == Decimal("2")


def _create_measurement_profile(client: TestClient, customer_id: int = 1, bust: str = "36") -> int:
    response = client.post(
        f"/api/customers/{customer_id}/measurement-profiles",
        json={
            "name": "Self",
            "garment_type": "BLOUSE",
            "unit": "INCH",
            "measurements": {
                "bust": bust,
                "waist": "30",
                "shoulder": "14",
                "blouse_length": "14.5",
                "sleeve_length": "10",
                "armhole": "16",
            },
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_measurement_profile_creation_creates_version_one(client: TestClient) -> None:
    profile_id = _create_measurement_profile(client)
    profile = client.get(f"/api/measurement-profiles/{profile_id}")
    assert profile.status_code == 200
    versions = profile.json()["versions"]
    assert len(versions) == 1
    assert versions[0]["version_number"] == 1


def test_editing_measurements_creates_new_version_and_preserves_old(client: TestClient) -> None:
    profile_id = _create_measurement_profile(client)
    v1 = client.get(f"/api/measurement-profiles/{profile_id}/versions").json()[0]

    v2_res = client.post(
        f"/api/measurement-profiles/{profile_id}/versions",
        json={
            "measurements": {
                "bust": "37",
                "waist": "30",
                "shoulder": "14",
                "blouse_length": "14.5",
                "sleeve_length": "10",
                "armhole": "16",
            }
        },
    )
    assert v2_res.status_code == 200
    assert v2_res.json()["version_number"] == 2

    v1_check = client.get(f"/api/measurement-profiles/{profile_id}/versions/{v1['id']}")
    assert v1_check.status_code == 200
    assert Decimal(str(v1_check.json()["measurements"]["bust"])) == Decimal("36")


def test_latest_profile_response_identifies_newest_version(client: TestClient) -> None:
    profile_id = _create_measurement_profile(client)
    client.post(
        f"/api/measurement-profiles/{profile_id}/versions",
        json={"measurements": {"bust": "38", "waist": "31", "shoulder": "14", "blouse_length": "14", "sleeve_length": "10", "armhole": "16"}},
    )

    response = client.get("/api/customers/1/measurement-profiles")
    assert response.status_code == 200
    profile = next(p for p in response.json() if p["id"] == profile_id)
    assert profile["latest_version"]["version_number"] == 2


def test_general_measurement_fields_can_be_stored(client: TestClient) -> None:
    response = client.post(
        "/api/customers/1/measurement-profiles",
        json={
            "name": "General Set",
            "garment_type": "GENERAL",
            "unit": "CM",
            "measurements": {"custom_drop": "11", "neck_round": "42.5"},
        },
    )
    assert response.status_code == 200
    measurements = response.json()["versions"][0]["measurements"]
    assert Decimal(str(measurements["custom_drop"])) == Decimal("11")
    assert Decimal(str(measurements["neck_round"])) == Decimal("42.5")


def test_zero_or_negative_measurements_rejected(client: TestClient) -> None:
    zero = client.post(
        "/api/customers/1/measurement-profiles",
        json={"name": "Bad", "unit": "INCH", "measurements": {"bust": "0"}},
    )
    negative = client.post(
        "/api/customers/1/measurement-profiles",
        json={"name": "Bad2", "unit": "INCH", "measurements": {"bust": "-1"}},
    )
    assert zero.status_code == 400
    assert negative.status_code == 400


def test_tailoring_required_line_creates_task_and_non_tailoring_does_not(client: TestClient) -> None:
    unique_id = _create_unique_item(client, "Task Unique")
    stocked_id = _create_stocked_item(client, "Task Stock", "2")
    response = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "lines": [
                {"item_id": unique_id, "quantity": "1", "requires_tailoring": True},
                {"item_id": stocked_id, "quantity": "1", "requires_tailoring": False},
            ],
        },
    )
    assert response.status_code == 200

    tasks = client.get("/api/tailoring/tasks")
    assert tasks.status_code == 200
    relevant = [t for t in tasks.json() if t["order_id"] == response.json()["id"]]
    assert len(relevant) == 1
    assert relevant[0]["item_id"] == unique_id


def test_order_line_stores_exact_measurement_version_and_is_historical(client: TestClient) -> None:
    profile_id = _create_measurement_profile(client, bust="36")
    v1 = client.get(f"/api/measurement-profiles/{profile_id}/versions").json()[0]
    item_id = _create_stocked_item(client, "Measured Blouse", "3", "4500.00")

    order = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "lines": [
                {
                    "item_id": item_id,
                    "quantity": "1",
                    "requires_tailoring": True,
                    "measurement_profile_id": profile_id,
                    "measurement_version_id": v1["id"],
                }
            ],
        },
    )
    assert order.status_code == 200
    line = order.json()["lines"][0]
    assert line["measurement_version_id"] == v1["id"]
    assert Decimal(str(line["measurement_values"]["bust"])) == Decimal("36")

    v2 = client.post(
        f"/api/measurement-profiles/{profile_id}/versions",
        json={"measurements": {"bust": "37", "waist": "30", "shoulder": "14", "blouse_length": "14.5", "sleeve_length": "10", "armhole": "16"}},
    )
    assert v2.status_code == 200

    old_order = client.get(f"/api/orders/{order.json()['id']}")
    assert old_order.status_code == 200
    old_line = old_order.json()["lines"][0]
    assert old_line["measurement_version_id"] == v1["id"]
    assert Decimal(str(old_line["measurement_values"]["bust"])) == Decimal("36")


def test_tailoring_task_stage_and_due_date_updates(client: TestClient) -> None:
    task = client.get("/api/tailoring/tasks").json()[0]
    update = client.patch(
        f"/api/tailoring/tasks/{task['id']}",
        json={"stage": "QC", "due_at": "2030-01-01T10:00:00Z"},
    )
    assert update.status_code == 200
    data = update.json()
    assert data["stage"] == "QC"
    assert data["due_at"] is not None


def test_overdue_filter_returns_only_overdue_non_ready(client: TestClient) -> None:
    tasks = client.get("/api/tailoring/tasks?due=overdue")
    assert tasks.status_code == 200
    assert all(task["stage"] != "READY" for task in tasks.json())


def test_ready_task_not_considered_overdue(client: TestClient) -> None:
    all_tasks = client.get("/api/tailoring/tasks").json()
    task = all_tasks[0]
    client.patch(f"/api/tailoring/tasks/{task['id']}", json={"stage": "READY", "due_at": "2020-01-01T10:00:00Z"})
    overdue = client.get("/api/tailoring/tasks?due=overdue").json()
    assert all(t["id"] != task["id"] for t in overdue)


def test_customer_measurement_profiles_scope(client: TestClient) -> None:
    _create_measurement_profile(client, customer_id=1)
    _create_measurement_profile(client, customer_id=2)
    c1 = client.get("/api/customers/1/measurement-profiles")
    c2 = client.get("/api/customers/2/measurement-profiles")
    assert c1.status_code == 200
    assert c2.status_code == 200
    assert all(p["customer_id"] == 1 for p in c1.json())
    assert all(p["customer_id"] == 2 for p in c2.json())


def _add_lot(
    client: TestClient,
    item_id: int,
    quantity: str,
    lot_code: str,
    received_at: str,
    cost_price: str = "100.00",
) -> dict:
    response = client.post(
        f"/api/items/{item_id}/lots",
        json={
            "lot_code": lot_code,
            "quantity": quantity,
            "received_at": received_at,
            "cost_price": cost_price,
            "notes": "seeded test lot",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _movements(client: TestClient, query: str = "") -> list[dict]:
    url = "/api/inventory/movements"
    if query:
        url = f"{url}?{query}"
    response = client.get(url)
    assert response.status_code == 200, response.text
    return response.json()


def test_receive_stock_creates_lot_and_receipt_movement(client: TestClient) -> None:
    item_id = _create_stocked_item(client, "Receipt Stocked", "2")
    lot = _add_lot(client, item_id, "5", "LOT-REC-1", "2024-01-01T00:00:00Z")

    assert lot["item_id"] == item_id
    assert lot["lot_code"] == "LOT-REC-1"
    assert Decimal(lot["quantity"]) == Decimal("5")
    assert Decimal(lot["original_quantity"]) == Decimal("5")

    moves = _movements(client, f"lot_id={lot['id']}&movement_type=RECEIPT")
    assert len(moves) >= 1
    assert moves[0]["movement_type"] == "RECEIPT"
    assert Decimal(str(moves[0]["quantity"])) == Decimal("5")


def test_item_lots_list_is_ordered_by_received_at(client: TestClient) -> None:
    item_id = _create_stocked_item(client, "Lot Order Item", "1")
    _add_lot(client, item_id, "2", "LOT-ORDER-NEW", "2024-05-01T00:00:00Z")
    _add_lot(client, item_id, "3", "LOT-ORDER-OLD", "2024-01-01T00:00:00Z")

    response = client.get(f"/api/items/{item_id}/lots")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["lot_code"] == "LOT-ORDER-OLD"


def test_get_inventory_lot_detail_returns_lot(client: TestClient) -> None:
    item_id = _create_stocked_item(client, "Lot Detail Item", "1")
    lot = _add_lot(client, item_id, "4", "LOT-DETAIL-1", "2024-01-01T00:00:00Z")

    response = client.get(f"/api/inventory/lots/{lot['id']}")
    assert response.status_code == 200
    assert response.json()["lot_code"] == "LOT-DETAIL-1"


def test_lot_adjustment_in_increases_quantity_and_logs_movement(client: TestClient) -> None:
    item_id = _create_stocked_item(client, "Adjust In Item", "1")
    lot = _add_lot(client, item_id, "4", "LOT-ADJIN-1", "2024-01-01T00:00:00Z")

    adjust = client.post(
        f"/api/inventory/lots/{lot['id']}/adjust",
        json={"adjustment_type": "ADJUSTMENT_IN", "quantity": "2", "reason": "cycle count"},
    )
    assert adjust.status_code == 200
    assert Decimal(adjust.json()["quantity"]) == Decimal("6")

    moves = _movements(client, f"lot_id={lot['id']}&movement_type=ADJUSTMENT_IN")
    assert len(moves) == 1
    assert Decimal(str(moves[0]["quantity"])) == Decimal("2")


def test_lot_adjustment_out_decreases_quantity_and_logs_movement(client: TestClient) -> None:
    item_id = _create_stocked_item(client, "Adjust Out Item", "1")
    lot = _add_lot(client, item_id, "4", "LOT-ADJOUT-1", "2024-01-01T00:00:00Z")

    adjust = client.post(
        f"/api/inventory/lots/{lot['id']}/adjust",
        json={"adjustment_type": "ADJUSTMENT_OUT", "quantity": "1.5", "reason": "damage"},
    )
    assert adjust.status_code == 200
    assert Decimal(adjust.json()["quantity"]) == Decimal("2.5")

    moves = _movements(client, f"lot_id={lot['id']}&movement_type=ADJUSTMENT_OUT")
    assert len(moves) == 1
    assert Decimal(str(moves[0]["quantity"])) == Decimal("-1.5")


def test_lot_adjustment_out_cannot_exceed_available_quantity(client: TestClient) -> None:
    item_id = _create_stocked_item(client, "Adjust Bound Item", "1")
    lot = _add_lot(client, item_id, "1", "LOT-BOUND-1", "2024-01-01T00:00:00Z")

    adjust = client.post(
        f"/api/inventory/lots/{lot['id']}/adjust",
        json={"adjustment_type": "ADJUSTMENT_OUT", "quantity": "2", "reason": "bad"},
    )
    assert adjust.status_code == 409


def test_lot_adjustment_rejects_unsupported_movement_type(client: TestClient) -> None:
    item_id = _create_stocked_item(client, "Adjust Unsupported", "1")
    lot = _add_lot(client, item_id, "2", "LOT-UNSUP-1", "2024-01-01T00:00:00Z")

    adjust = client.post(
        f"/api/inventory/lots/{lot['id']}/adjust",
        json={"adjustment_type": "HOLD", "quantity": "1", "reason": "bad"},
    )
    assert adjust.status_code == 409


def test_stocked_order_allocates_oldest_lots_first(client: TestClient) -> None:
    item_id = _create_stocked_item(client, "Multi Lot Stocked", "1", "100.00")
    old_lot = _add_lot(client, item_id, "2", "LOT-OLD", "2024-01-01T00:00:00Z")
    newer_lot = _add_lot(client, item_id, "5", "LOT-NEW", "2024-06-01T00:00:00Z")

    order = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "lines": [{"item_id": item_id, "quantity": "3", "requires_tailoring": False}],
        },
    )
    assert order.status_code == 200, order.text
    allocations = order.json()["lines"][0]["allocations"]
    assert len(allocations) == 2
    assert allocations[0]["inventory_lot_id"] == old_lot["id"]
    assert Decimal(allocations[0]["quantity"]) == Decimal("2")
    assert allocations[1]["inventory_lot_id"] in {newer_lot["id"], order.json()["lines"][0]["inventory_lot_id"]}
    assert Decimal(allocations[1]["quantity"]) == Decimal("1")


def test_stocked_insufficient_rolls_back_without_movements(client: TestClient) -> None:
    item_id = _create_stocked_item(client, "Stocked Atomic", "1", "100.00")
    _add_lot(client, item_id, "2", "LOT-A1", "2024-01-01T00:00:00Z")
    before = _movements(client, f"item_id={item_id}")

    order = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "lines": [{"item_id": item_id, "quantity": "5", "requires_tailoring": False}],
        },
    )
    assert order.status_code == 409

    after = _movements(client, f"item_id={item_id}")
    assert len(before) == len(after)


def test_yardage_uses_smallest_sufficient_single_roll(client: TestClient) -> None:
    item_id = _create_yardage_item(client, "Yardage Smallest", "1.000", "200.00")
    small = _add_lot(client, item_id, "4.000", "ROLL-4", "2024-01-01T00:00:00Z")
    _add_lot(client, item_id, "6.000", "ROLL-6", "2024-01-02T00:00:00Z")

    order = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "lines": [{"item_id": item_id, "quantity": "3.500", "requires_tailoring": False}],
        },
    )
    assert order.status_code == 200
    alloc = order.json()["lines"][0]["allocations"]
    assert len(alloc) == 1
    assert alloc[0]["inventory_lot_id"] == small["id"]


def test_yardage_does_not_split_across_multiple_rolls(client: TestClient) -> None:
    item_id = _create_yardage_item(client, "Yardage No Split", "1.000", "200.00")
    _add_lot(client, item_id, "2.000", "ROLL-2A", "2024-01-01T00:00:00Z")
    _add_lot(client, item_id, "2.000", "ROLL-2B", "2024-01-02T00:00:00Z")

    order = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "lines": [{"item_id": item_id, "quantity": "3.000", "requires_tailoring": False}],
        },
    )
    assert order.status_code == 409


def test_mixed_order_rolls_back_when_yardage_has_no_single_sufficient_roll(client: TestClient) -> None:
    unique_id = _create_unique_item(client, "Atomic Mix Unique", "1000.00")
    stocked_id = _create_stocked_item(client, "Atomic Mix Stock", "4", "100.00")
    yardage_id = _create_yardage_item(client, "Atomic Mix Yardage", "1.000", "200.00")
    _add_lot(client, yardage_id, "2.000", "ROLL-MIX-2A", "2024-01-01T00:00:00Z")
    _add_lot(client, yardage_id, "2.000", "ROLL-MIX-2B", "2024-01-02T00:00:00Z")

    before_orders = len(client.get("/api/orders").json())
    before_unique = client.get(f"/api/items/{unique_id}").json()
    before_stocked = client.get(f"/api/items/{stocked_id}").json()

    response = client.post(
        "/api/orders",
        json={
            "customer_id": 1,
            "lines": [
                {"item_id": unique_id, "quantity": "1", "requires_tailoring": False},
                {"item_id": stocked_id, "quantity": "2", "requires_tailoring": False},
                {"item_id": yardage_id, "quantity": "3.000", "requires_tailoring": False},
            ],
        },
    )
    assert response.status_code == 409

    after_orders = len(client.get("/api/orders").json())
    after_unique = client.get(f"/api/items/{unique_id}").json()
    after_stocked = client.get(f"/api/items/{stocked_id}").json()

    assert before_orders == after_orders
    assert before_unique["availability"] == "AVAILABLE"
    assert after_unique["availability"] == "AVAILABLE"
    assert Decimal(before_stocked["quantity_available"]) == Decimal(after_stocked["quantity_available"])


def test_yardage_remainder_at_threshold_becomes_remnant(client: TestClient) -> None:
    item_id = _create_yardage_item(client, "Remnant Threshold", "1.000", "200.00")
    lot = _add_lot(client, item_id, "2.500", "ROLL-REM-1", "2024-01-01T00:00:00Z")

    order = client.post(
        "/api/orders",
        json={"customer_id": 1, "lines": [{"item_id": item_id, "quantity": "2.000", "requires_tailoring": False}]},
    )
    assert order.status_code == 200

    lot_read = client.get(f"/api/inventory/lots/{lot['id']}")
    assert lot_read.status_code == 200
    assert lot_read.json()["status"] == "REMNANT"
    assert Decimal(lot_read.json()["quantity"]) == Decimal("0.500")


def test_yardage_exact_cut_sets_depleted(client: TestClient) -> None:
    item_id = _create_yardage_item(client, "Yardage Depleted", "1.000", "200.00")
    lot = _add_lot(client, item_id, "3.000", "ROLL-DEP-1", "2024-01-01T00:00:00Z")

    order = client.post(
        "/api/orders",
        json={"customer_id": 1, "lines": [{"item_id": item_id, "quantity": "3.000", "requires_tailoring": False}]},
    )
    assert order.status_code == 200

    lot_read = client.get(f"/api/inventory/lots/{lot['id']}")
    assert lot_read.status_code == 200
    assert lot_read.json()["status"] == "DEPLETED"
    assert Decimal(lot_read.json()["quantity"]) == Decimal("0")


def test_inventory_movements_support_filters(client: TestClient) -> None:
    item_id = _create_stocked_item(client, "Move Filter Item", "2", "100.00")
    lot = _add_lot(client, item_id, "3", "LOT-MOVE-1", "2024-01-01T00:00:00Z")

    client.post(
        "/api/orders",
        json={"customer_id": 1, "lines": [{"item_id": item_id, "quantity": "1", "requires_tailoring": False}]},
    )

    by_item = _movements(client, f"item_id={item_id}")
    assert all(row["item_id"] == item_id for row in by_item)

    by_lot = _movements(client, f"lot_id={lot['id']}")
    assert all(row["inventory_lot_id"] == lot["id"] for row in by_lot)

    by_type = _movements(client, "movement_type=RECEIPT")
    assert all(row["movement_type"] == "RECEIPT" for row in by_type)


def test_inventory_movements_respect_limit_parameter(client: TestClient) -> None:
    item_id = _create_stocked_item(client, "Move Limit Item", "1", "100.00")
    lot = _add_lot(client, item_id, "5", "LOT-LIMIT-1", "2024-01-01T00:00:00Z")

    client.post(f"/api/inventory/lots/{lot['id']}/adjust", json={"adjustment_type": "ADJUSTMENT_IN", "quantity": "1"})
    client.post(f"/api/inventory/lots/{lot['id']}/adjust", json={"adjustment_type": "ADJUSTMENT_OUT", "quantity": "1"})

    moves = _movements(client, f"item_id={item_id}&limit=1")
    assert len(moves) == 1


def test_unique_sale_creates_allocation_and_sale_movement(client: TestClient) -> None:
    item_id = _create_unique_item(client, "Unique Move", "1000.00")
    order = client.post(
        "/api/orders",
        json={"customer_id": 1, "lines": [{"item_id": item_id, "quantity": "1", "requires_tailoring": False}]},
    )
    assert order.status_code == 200

    line = order.json()["lines"][0]
    assert len(line["allocations"]) == 1
    assert Decimal(line["allocations"][0]["quantity"]) == Decimal("1")

    moves = _movements(client, f"item_id={item_id}&movement_type=SALE")
    assert len(moves) >= 1
    assert Decimal(str(moves[0]["quantity"])) == Decimal("-1")


def test_hold_and_release_create_movements(client: TestClient) -> None:
    item_id = _create_unique_item(client, "Hold Move Item", "1000.00")
    hold = client.post(f"/api/items/{item_id}/hold", json={"customer_id": 1, "ttl_hours": 24})
    assert hold.status_code == 200
    release = client.delete(f"/api/items/{item_id}/hold")
    assert release.status_code == 200

    moves = _movements(client, f"item_id={item_id}")
    kinds = {m["movement_type"] for m in moves}
    assert "HOLD" in kinds
    assert "HOLD_RELEASE" in kinds


def test_expired_hold_creates_hold_expire_movement(client: TestClient) -> None:
    item_id = _create_unique_item(client, "Expire Move Item", "1000.00")
    first = client.post(f"/api/items/{item_id}/hold", json={"customer_id": 1, "ttl_hours": 0})
    assert first.status_code == 200
    second = client.post(f"/api/items/{item_id}/hold", json={"customer_id": 2, "ttl_hours": 24})
    assert second.status_code == 200

    moves = _movements(client, f"item_id={item_id}")
    assert any(m["movement_type"] == "HOLD_EXPIRE" for m in moves)


def test_dashboard_contains_low_stock_and_remnant_roll_metrics(client: TestClient) -> None:
    stocked_id = _create_stocked_item(client, "Dashboard Low Stock", "1", "100.00")
    yardage_id = _create_yardage_item(client, "Dashboard Remnant", "1.000", "100.00")
    rem_lot = _add_lot(client, yardage_id, "2.500", "ROLL-DASH-1", "2024-01-01T00:00:00Z")

    client.post(
        "/api/orders",
        json={"customer_id": 1, "lines": [{"item_id": yardage_id, "quantity": "2.000", "requires_tailoring": False}]},
    )

    # Keep stocked item in low stock state with positive quantity <= 2.
    stocked = client.get(f"/api/items/{stocked_id}")
    assert stocked.status_code == 200
    assert Decimal(stocked.json()["quantity_available"]) <= Decimal("2")

    lot_read = client.get(f"/api/inventory/lots/{rem_lot['id']}")
    assert lot_read.status_code == 200
    assert lot_read.json()["status"] == "REMNANT"

    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200
    data = dashboard.json()
    assert "low_stock_items" in data
    assert "remnant_rolls" in data
    assert isinstance(data["low_stock_items"], int)
    assert isinstance(data["remnant_rolls"], int)
