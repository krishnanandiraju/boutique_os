import base64
from io import BytesIO
from unittest.mock import Mock
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from app import fabric_design, tryon
from app.ai_policy import CustomerAIPolicy, TenantAICreditAccount, TenantAIServiceConfig, TenantAIPolicy
from app.db import SessionLocal
from app.main import app


def photo():
    output = BytesIO()
    Image.new('RGB', (128, 192), 'purple').save(output, 'PNG')
    return output.getvalue()


def files():
    return {name: (f'{name}.png', photo(), 'image/png') for name in ('person', 'garment')}


def enable_design_ai_for_customer(customer_id: int, merchant_id: int = 1):
    with SessionLocal() as db:
        policy = db.get(TenantAIPolicy, merchant_id) or TenantAIPolicy(merchant_id=merchant_id)
        policy.enabled = True
        policy.allowed_segments = ['New', 'Repeat', 'VIP']
        policy.enabled_services = ['standard_preview', 'design_studio_1']
        db.add(policy)

        service = db.get(TenantAIServiceConfig, (merchant_id, 'design_studio_1')) or TenantAIServiceConfig(merchant_id=merchant_id, service_id='design_studio_1')
        service.enabled = True
        service.credits_per_success = 1
        db.add(service)

        customer_policy = db.get(CustomerAIPolicy, customer_id) or CustomerAIPolicy(customer_id=customer_id)
        customer_policy.control = 'allow'
        customer_policy.monthly_request_limit = 20
        db.add(customer_policy)

        account = db.get(TenantAICreditAccount, merchant_id) or TenantAICreditAccount(merchant_id=merchant_id, available_credits=0, reserved_credits=0, spent_credits=0)
        account.available_credits = max(account.available_credits or 0, 50)
        db.add(account)
        db.commit()


def test_fabric_design_contract_and_no_image_response(monkeypatch):
    monkeypatch.setattr(tryon.settings, 'google_cloud_project', 'test-project')
    monkeypatch.setattr(tryon, 'credentials', lambda: Mock(token='test-token'))
    request = Mock(return_value=httpx.Response(200, json={'candidates': [{'content': {'parts': [{'inlineData': {'mimeType': 'image/png', 'data': base64.b64encode(photo()).decode()}}]}}]}))
    monkeypatch.setattr(fabric_design.httpx, 'post', request)
    result = fabric_design.generate_concept(photo(), photo(), 'A straight kurta')
    assert result['preview_type'] == 'DESIGN_CONCEPT'
    assert request.call_args.args[0].endswith('gemini-2.5-flash-image:generateContent')
    body = request.call_args.kwargs['json']
    assert body['generationConfig']['responseModalities'] == ['TEXT', 'IMAGE']
    assert len(body['contents'][0]['parts']) == 3
    request.return_value = httpx.Response(200, json={'candidates': []})
    with pytest.raises(HTTPException) as error:
        fabric_design.generate_concept(photo(), photo(), 'A straight kurta')
    assert error.value.status_code == 422


def test_fabric_design_permissions_type_and_flag(monkeypatch):
    with TestClient(app) as client:
        monkeypatch.setattr(tryon.settings, 'fabric_design_enabled', False)
        data = {'customer_id': client.get('/api/customers').json()[0]['id'], 'item_id': next(i['id'] for i in client.get('/api/items').json() if i['inventory_type'] == 'YARDAGE'), 'consent': 'true', 'brief': 'A straight kurta'}
        generate = Mock(return_value={'image': 'data:image/png;base64,test', 'preview_type': 'DESIGN_CONCEPT'})
        monkeypatch.setattr(fabric_design, 'generate_concept', generate)
        assert client.post('/api/try-on/design', data=data, files=files()).status_code == 503
        generate.assert_not_called()
        monkeypatch.setattr(tryon.settings, 'fabric_design_enabled', True)
        monkeypatch.setattr(tryon.settings, 'google_cloud_project', 'test-project')
        data['consent'] = 'false'
        assert client.post('/api/try-on/design', data=data, files=files()).status_code == 422
        data['consent'] = 'true'
        enable_design_ai_for_customer(data['customer_id'])
        response = client.post('/api/try-on/design', data=data, files=files())
        assert response.status_code == 200
        assert response.headers['cache-control'] == 'no-store'
        data['item_id'] = next(i['id'] for i in client.get('/api/items').json() if i['inventory_type'] != 'YARDAGE')
        assert client.post('/api/try-on/design', data=data, files=files()).status_code == 422


def test_customization_notes_reach_tailoring_task():
    with TestClient(app) as client:
        customer = client.get('/api/customers').json()[0]
        item = client.post('/api/catalog/products', json={'name': 'Notes test kurta', 'inventory_type': 'STOCKED', 'category': 'Kurta', 'selling_price': '100', 'quantity': '3', 'variants': []}).json()
        line = {'item_id': item['id'], 'quantity': '1', 'requires_tailoring': True, 'customization_notes': 'Shorten sleeves after fitting; confirm ease.'}
        response = client.post('/api/orders/variant-aware', json={'customer_id': customer['id'], 'lines': [line]})
        assert response.status_code == 201, response.text
        saved = response.json()['lines'][0]
        assert saved['customization_notes'] == line['customization_notes']
        tasks = client.get('/api/tailoring/tasks').json()
        assert next(task for task in tasks if task['order_line_id'] == saved['id'])['notes'] == line['customization_notes']
        line['requires_tailoring'] = False
        assert client.post('/api/orders/variant-aware', json={'customer_id': customer['id'], 'lines': [line]}).status_code == 422
