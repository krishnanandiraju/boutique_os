from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.seed import seed_data


def _reset() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()


def test_health_and_status_contracts() -> None:
    _reset()
    with TestClient(app) as client:
        assert client.get('/health/live').json()['status'] == 'ok'
        assert client.get('/health/ready').json()['database'] == 'reachable'
        status = client.get('/api/status')
        assert status.status_code == 200
        catalog = client.get('/api/status/catalog').json()
        assert 'READY' in catalog['order_statuses']
        assert 'MEN' in catalog['audiences']
        assert 'WOMEN' in catalog['audiences']


def test_tenant_can_support_women_men_or_mixed_catalogs() -> None:
    _reset()
    with TestClient(app) as client:
        default_profile = client.get('/api/tenants/1/profile')
        assert default_profile.status_code == 200
        assert default_profile.json()['supported_audiences'] == ['WOMEN']

        mixed = client.put('/api/tenants/1/profile', json={
            'supported_audiences': ['WOMEN', 'MEN', 'UNISEX'],
            'default_audience': 'WOMEN',
            'garment_types': ['BLOUSE', 'KURTA', 'SHIRT', 'TROUSER'],
        })
        assert mixed.status_code == 200
        assert 'MEN' in mixed.json()['supported_audiences']
        assert 'SHIRT' in mixed.json()['garment_types']


def test_item_variants_are_optional_and_sku_is_optional() -> None:
    _reset()
    with TestClient(app) as client:
        item = client.post('/api/items', json={
            'name': 'Classic Shirt',
            'inventory_type': 'STOCKED',
            'category': 'Shirt',
            'selling_price': '1999',
            'quantity': '5',
        }).json()

        assert client.get(f"/api/items/{item['id']}/variants").json() == []

        no_sku = client.post(f"/api/items/{item['id']}/variants", json={
            'name': 'Blue / Medium',
            'option_values': {'color': 'Blue', 'size': 'M'},
        })
        assert no_sku.status_code == 200
        assert no_sku.json()['sku'] is None

        with_sku = client.post(f"/api/items/{item['id']}/variants", json={
            'name': 'Blue / Large',
            'sku': 'SHIRT-BLU-L',
            'option_values': {'color': 'Blue', 'size': 'L'},
        })
        assert with_sku.status_code == 200
        assert with_sku.json()['sku'] == 'SHIRT-BLU-L'


def test_variant_inventory_link_preserves_existing_lot_model() -> None:
    _reset()
    with TestClient(app) as client:
        item = client.post('/api/items', json={
            'name': 'Variant Kurta',
            'inventory_type': 'STOCKED',
            'category': 'Kurta',
            'selling_price': '1200',
            'quantity': '3',
        }).json()
        variant = client.post(f"/api/items/{item['id']}/variants", json={
            'name': 'Green / M',
            'option_values': {'color': 'Green', 'size': 'M'},
        }).json()
        lot = client.get(f"/api/items/{item['id']}/lots").json()[0]
        linked = client.post(f"/api/variants/{variant['id']}/inventory-lots/{lot['id']}")
        assert linked.status_code == 200
        assert linked.json()['lot_ids'] == [lot['id']]
        assert float(linked.json()['quantity_available']) == 3


def test_domain_events_can_be_created_read_filtered_and_statused() -> None:
    _reset()
    with TestClient(app) as client:
        created = client.post('/api/events', json={
            'event_type': 'catalog.item.reviewed',
            'aggregate_type': 'item',
            'aggregate_id': '42',
            'payload': {'source': 'manual'},
        })
        assert created.status_code == 200
        event_id = created.json()['event_id']

        fetched = client.get(f'/api/events/{event_id}')
        assert fetched.status_code == 200
        assert fetched.json()['event_type'] == 'catalog.item.reviewed'

        filtered = client.get('/api/events?event_type=catalog.item.reviewed')
        assert filtered.status_code == 200
        assert any(row['event_id'] == event_id for row in filtered.json())

        processed = client.patch(f'/api/events/{event_id}/status', json={'status': 'PROCESSED'})
        assert processed.status_code == 200
        assert processed.json()['status'] == 'PROCESSED'
        assert processed.json()['processed_at'] is not None
