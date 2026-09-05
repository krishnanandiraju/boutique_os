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


def test_product_without_sku_or_variants_is_valid() -> None:
    _reset()
    with TestClient(app) as client:
        response = client.post('/api/catalog/products', json={
            'name': 'One-off Handwoven Saree',
            'inventory_type': 'UNIQUE',
            'category': 'Saree',
            'selling_price': '18500',
            'quantity': '1',
            'audience': 'WOMEN',
            'variants': [],
        })
        assert response.status_code == 201, response.text
        product = response.json()
        assert product['sku'] is None
        assert product['variants'] == []
        assert float(product['quantity_available']) == 1
        assert product['audience'] == 'WOMEN'


def test_variant_stock_is_created_separately_and_sku_remains_optional() -> None:
    _reset()
    with TestClient(app) as client:
        response = client.post('/api/catalog/products', json={
            'name': 'Oxford Shirt',
            'inventory_type': 'STOCKED',
            'category': 'Shirt',
            'selling_price': '2499',
            'quantity': '0',
            'audience': 'MEN',
            'variants': [
                {'name': 'Blue / M', 'sku': 'OX-BLU-M', 'option_values': {'size': 'M', 'colour': 'Blue'}, 'quantity': '3'},
                {'name': 'Blue / L', 'option_values': {'size': 'L', 'colour': 'Blue'}, 'quantity': '5'},
            ],
        })
        assert response.status_code == 201, response.text
        product = response.json()
        assert len(product['variants']) == 2
        assert product['variants'][0]['sku'] == 'OX-BLU-M'
        assert product['variants'][1]['sku'] is None
        assert float(product['variants'][0]['quantity_available']) == 3
        assert float(product['variants'][1]['quantity_available']) == 5
        assert float(product['quantity_available']) == 8


def test_variant_aware_order_only_consumes_selected_variant_inventory() -> None:
    _reset()
    with TestClient(app) as client:
        customer_id = client.get('/api/customers').json()[0]['id']
        product = client.post('/api/catalog/products', json={
            'name': 'Variant Kurta',
            'inventory_type': 'STOCKED',
            'category': 'Kurta',
            'selling_price': '1500',
            'quantity': '0',
            'audience': 'UNISEX',
            'variants': [
                {'name': 'Green / M', 'sku': 'K-GRN-M', 'option_values': {'size': 'M', 'colour': 'Green'}, 'selling_price': '1600', 'quantity': '3'},
                {'name': 'Red / M', 'sku': 'K-RED-M', 'option_values': {'size': 'M', 'colour': 'Red'}, 'selling_price': '1700', 'quantity': '4'},
            ],
        }).json()
        green = product['variants'][0]
        red = product['variants'][1]

        ordered = client.post('/api/orders/variant-aware', json={
            'customer_id': customer_id,
            'lines': [{'item_id': product['id'], 'variant_id': green['id'], 'quantity': '2', 'requires_tailoring': False}],
        })
        assert ordered.status_code == 201, ordered.text
        body = ordered.json()
        assert body['lines'][0]['variant_id'] == green['id']
        assert body['lines'][0]['variant_sku'] == 'K-GRN-M'
        assert float(body['lines'][0]['unit_price']) == 1600

        refreshed = client.get(f"/api/catalog/products/{product['id']}").json()
        by_id = {row['id']: row for row in refreshed['variants']}
        assert float(by_id[green['id']]['quantity_available']) == 1
        assert float(by_id[red['id']]['quantity_available']) == 4


def test_variant_is_required_when_product_has_variants() -> None:
    _reset()
    with TestClient(app) as client:
        customer_id = client.get('/api/customers').json()[0]['id']
        product = client.post('/api/catalog/products', json={
            'name': 'Sized Shirt',
            'inventory_type': 'STOCKED',
            'category': 'Shirt',
            'selling_price': '2000',
            'quantity': '0',
            'variants': [{'name': 'M', 'option_values': {'size': 'M'}, 'quantity': '2'}],
        }).json()
        response = client.post('/api/orders/variant-aware', json={
            'customer_id': customer_id,
            'lines': [{'item_id': product['id'], 'quantity': '1', 'requires_tailoring': False}],
        })
        assert response.status_code == 400
        assert response.json()['error']['code'] == 'VARIANT_REQUIRED'


def test_product_media_can_be_uploaded_and_becomes_catalog_primary() -> None:
    _reset()
    with TestClient(app) as client:
        product = client.post('/api/catalog/products', json={
            'name': 'Photo Dress',
            'inventory_type': 'UNIQUE',
            'category': 'Dress',
            'selling_price': '5000',
            'quantity': '1',
            'variants': [],
        }).json()
        png = b'\x89PNG\r\n\x1a\n' + b'0' * 64
        uploaded = client.post(f"/api/media/upload?item_id={product['id']}", files={'file': ('dress.png', png, 'image/png')})
        assert uploaded.status_code == 200, uploaded.text
        media_id = uploaded.json()['id']
        primary = client.patch(f"/api/items/{product['id']}/media/{media_id}", json={'is_primary': True, 'sort_order': 0})
        assert primary.status_code == 200
        refreshed = client.get(f"/api/catalog/products/{product['id']}").json()
        assert refreshed['media_count'] == 1
        assert refreshed['primary_media_url'].startswith('/media/')


def test_men_can_be_enabled_at_tenant_level_and_use_shirt_measurements() -> None:
    _reset()
    with TestClient(app) as client:
        saved = client.put('/api/tenants/1/profile', json={
            'supported_audiences': ['WOMEN', 'MEN'],
            'default_audience': 'WOMEN',
            'garment_types': ['BLOUSE', 'KURTA', 'SHIRT', 'TROUSER', 'SUIT'],
        })
        assert saved.status_code == 200
        assert 'MEN' in saved.json()['supported_audiences']
        assert 'SHIRT' in saved.json()['garment_types']

        customer_id = client.get('/api/customers').json()[0]['id']
        profile = client.post(f'/api/customers/{customer_id}/measurement-profiles', json={
            'name': 'Self',
            'garment_type': 'SHIRT',
            'unit': 'INCH',
            'measurements': {'chest': 40, 'waist': 36, 'shoulder': 18, 'sleeve_length': 25},
        })
        assert profile.status_code == 200, profile.text
        assert profile.json()['garment_type'] == 'SHIRT'
        assert float(profile.json()['latest_version']['measurements']['chest']) == 40
