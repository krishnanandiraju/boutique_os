import io
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from PIL import Image

from app import tryon


def fixture(tmp_path, monkeypatch, filename='kurta-front-clean.png'):
    reference = Path(tryon.__file__).parent / 'data' / 'photography' / filename
    target = tmp_path / filename
    target.write_bytes(reference.read_bytes())
    monkeypatch.setattr(tryon.settings, 'media_storage_path', str(tmp_path))
    item = Mock(id=3, merchant_id=1, inventory_type='STOCKED')
    asset = Mock(storage_key=filename, original_filename=filename)
    db = Mock()
    db.query.return_value.filter_by.return_value.first.return_value = asset
    return db, item, target


def test_reviewed_catalog_photo_is_sanitized_and_scoped(tmp_path, monkeypatch):
    db, item, _ = fixture(tmp_path, monkeypatch)
    image = tryon.read_garment(db, item, None, 'catalog', None)
    assert Image.open(io.BytesIO(image)).format == 'JPEG'
    db.query.return_value.filter_by.assert_called_once_with(item_id=3, merchant_id=1, is_primary=True)


@pytest.mark.parametrize('failure', ['variant', 'missing', 'mannequin', 'modified', 'path'])
def test_unsuitable_catalog_photo_rejected(tmp_path, monkeypatch, failure):
    db, item, target = fixture(tmp_path, monkeypatch)
    asset = db.query.return_value.filter_by.return_value.first.return_value
    variant = None
    if failure == 'variant':
        variant = 5
    elif failure == 'missing':
        db.query.return_value.filter_by.return_value.first.return_value = None
    elif failure == 'mannequin':
        asset.original_filename = 'kurta-front.png'
    elif failure == 'modified':
        target.write_bytes(b'unapproved replacement')
    else:
        asset.storage_key = '../outside.png'
    with pytest.raises(HTTPException) as error:
        tryon.read_garment(db, item, variant, 'catalog', None)
    assert error.value.status_code == 422


def test_unknown_source_and_missing_upload_rejected():
    for source in ('upload', 'unknown'):
        with pytest.raises(HTTPException) as error:
            tryon.read_garment(Mock(), Mock(), None, source, None)
        assert error.value.status_code == 422


def test_reviewed_fabric_photo(tmp_path, monkeypatch):
    db, item, _ = fixture(tmp_path, monkeypatch, 'fabric-front.png')
    item.inventory_type = 'YARDAGE'
    assert tryon.read_garment(db, item, None, 'catalog', None).startswith(b'\xff\xd8')


def test_catalog_generation_uses_tenant_credit_lifecycle(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db import SessionLocal
    from app.ai_policy import TenantAICreditAccount
    from test_tryon import enable_ai_for_customer, photo
    monkeypatch.setattr(tryon.settings, 'tryon_enabled', True)
    monkeypatch.setattr(tryon.settings, 'tryon_provider', 'huggingface')
    provider = Mock(return_value={'image': 'data:image/png;base64,test'})
    monkeypatch.setattr(tryon, 'generate_fashn_preview', provider)
    with TestClient(app) as client:
        customer = client.get('/api/customers').json()[0]
        item = next(i for i in client.get('/api/items').json() if i['name'] == 'Cotton Kurta - Blue')
        data = {'customer_id': customer['id'], 'item_id': item['id'], 'consent': 'true', 'garment_source': 'catalog'}
        enable_ai_for_customer(customer['id'])
        with SessionLocal() as db:
            account = db.get(TenantAICreditAccount, 1)
            before = account.available_credits, account.spent_credits
        result = client.post('/api/try-on/generate', data=data, files={'person': ('person.png', photo(), 'image/png')})
        assert result.status_code == 200, result.text
        provider.assert_called_once()
        assert provider.call_args.args[2:] == ('one-pieces', 'flat-lay')
        with SessionLocal() as db:
            account = db.get(TenantAICreditAccount, 1)
            assert account.available_credits == before[0] - 1
            assert account.spent_credits == before[1] + 1
            assert account.reserved_credits == 0
