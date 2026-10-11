import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.main import app  # registers all model tables
from app.db import Base
from app import demo_ai
from app.ai_policy import CustomerAIPolicy, TenantAICreditAccount, TenantAICreditLedger, TenantAIPolicy, TenantAIServiceConfig
from app.models import Merchant, Customer


@pytest.fixture()
def db(monkeypatch):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    monkeypatch.setattr(demo_ai.settings, 'ai_demo_bootstrap_enabled', True)
    monkeypatch.setattr(demo_ai.settings, 'tryon_enabled', True)
    monkeypatch.setattr(demo_ai.settings, 'tryon_provider', 'huggingface')
    with Session(engine) as session:
        session.add_all([Merchant(id=1, name='Meera Boutique'), Merchant(id=2, name='Other Boutique')])
        session.add_all([Customer(id=1, merchant_id=1, name='Neha Reddy', phone='123'),
                         Customer(id=2, merchant_id=2, name='Neha Reddy', phone='234')])
        session.commit()
        yield session
    engine.dispose()


def test_provisions_only_demo_tenant_once_and_preserves_later_controls(db):
    demo_ai.provision_demo_ai(db)
    assert db.get(TenantAIPolicy, 1).enabled
    assert db.get(TenantAIServiceConfig, (1, 'standard_preview')).enabled
    assert db.get(CustomerAIPolicy, 1).control == 'allow'
    assert db.get(CustomerAIPolicy, 2) is None
    assert db.get(TenantAICreditAccount, 2) is None
    account = db.get(TenantAICreditAccount, 1)
    assert account.available_credits == 100
    account.available_credits = 91
    db.get(TenantAIPolicy, 1).enabled = False
    db.commit()
    demo_ai.provision_demo_ai(db)
    assert account.available_credits == 91
    assert not db.get(TenantAIPolicy, 1).enabled
    assert len(db.scalars(select(TenantAICreditLedger)).all()) == 1


@pytest.mark.parametrize('flag,value', [('ai_demo_bootstrap_enabled',False), ('tryon_enabled',False), ('tryon_provider','google')])
def test_explicit_free_demo_configuration_required(db, monkeypatch, flag, value):
    monkeypatch.setattr(demo_ai.settings, flag, value)
    demo_ai.provision_demo_ai(db)
    assert db.get(TenantAICreditAccount,1) is None


def test_merchant_identity_must_match(db):
    db.get(Merchant,1).name = 'Real customer tenant'
    db.commit()
    demo_ai.provision_demo_ai(db)
    assert db.get(TenantAICreditAccount,1) is None


def test_existing_kurta_category_is_repaired_without_refunding_or_enabling(db):
    from app.ai_policy import ProductAIConfiguration
    from app.models import Item, InventoryType
    db.add(Item(id=3, merchant_id=1, name='Cotton Kurta - Blue', inventory_type=InventoryType.STOCKED, category='Kurta', selling_price=2499))
    db.commit()
    demo_ai.provision_demo_ai(db)
    product = db.scalar(select(ProductAIConfiguration))
    assert product.garment_category == 'one-pieces'
    product.garment_category = 'tops'
    product.ai_enabled = False
    account = db.get(TenantAICreditAccount, 1)
    account.available_credits = 87
    db.commit()
    demo_ai.provision_demo_ai(db)
    assert product.garment_category == 'one-pieces'
    assert not product.ai_enabled
    assert account.available_credits == 87
    assert len(db.scalars(select(TenantAICreditLedger)).all()) == 1
