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


def create_stocked(client: TestClient, name: str) -> int:
    response = client.post('/api/items', json={
        'name': name,
        'inventory_type': 'STOCKED',
        'category': 'Blouse',
        'selling_price': '1500',
        'quantity': '3',
    })
    assert response.status_code == 200, response.text
    return response.json()['id']


def create_tailoring_order(client: TestClient, item_count: int = 1) -> tuple[int, list[dict]]:
    item_ids = [create_stocked(client, f'Ready lifecycle {index}') for index in range(item_count)]
    response = client.post('/api/orders', json={
        'customer_id': 1,
        'lines': [{'item_id': item_id, 'quantity': '1', 'requires_tailoring': True} for item_id in item_ids],
    })
    assert response.status_code == 200, response.text
    order_id = response.json()['id']
    tasks = [task for task in client.get('/api/tailoring/tasks').json() if task['order_id'] == order_id]
    assert len(tasks) == item_count
    return order_id, tasks


def advance_to_qc(client: TestClient, task_id: int) -> None:
    for stage in ('CUTTING', 'STITCHING', 'QC'):
        response = client.post(f'/api/tailoring/tasks/{task_id}/transition', json={'stage': stage})
        assert response.status_code == 200, response.text


def test_ready_requires_quality_check(client: TestClient) -> None:
    _, tasks = create_tailoring_order(client)
    response = client.post(f"/api/tailoring/tasks/{tasks[0]['id']}/transition", json={'stage': 'READY'})
    assert response.status_code == 409
    assert 'quality check' in response.json()['error']['message'].lower()


def test_last_ready_tailoring_item_marks_order_ready_and_emits_event(client: TestClient) -> None:
    order_id, tasks = create_tailoring_order(client, item_count=2)
    for task in tasks:
        advance_to_qc(client, task['id'])

    first = client.post(f"/api/tailoring/tasks/{tasks[0]['id']}/transition", json={'stage': 'READY'})
    assert first.status_code == 200
    assert first.json()['order_became_ready'] is False
    assert first.json()['remaining_tailoring_items'] == 1

    second = client.post(f"/api/tailoring/tasks/{tasks[1]['id']}/transition", json={'stage': 'READY'})
    assert second.status_code == 200
    assert second.json()['order_became_ready'] is True
    assert second.json()['remaining_tailoring_items'] == 0
    assert second.json()['order_status'] == 'READY'

    order = client.get(f'/api/orders/{order_id}')
    assert order.status_code == 200
    assert order.json()['status'] == 'READY'

    events = client.get('/api/integrations/outbox?event_type=order.ready')
    assert events.status_code == 200
    matching = [event for event in events.json() if event['aggregate_id'] == str(order_id)]
    assert len(matching) == 1
    assert matching[0]['payload_json']['reason'] == 'all_tailoring_items_ready'


def test_ready_order_can_be_completed_as_delivered(client: TestClient) -> None:
    order_id, tasks = create_tailoring_order(client)
    advance_to_qc(client, tasks[0]['id'])
    ready = client.post(f"/api/tailoring/tasks/{tasks[0]['id']}/transition", json={'stage': 'READY'})
    assert ready.status_code == 200

    delivered = client.patch(f'/api/orders/{order_id}/status', json={'status': 'DELIVERED'})
    assert delivered.status_code == 200
    assert delivered.json()['status'] == 'DELIVERED'
