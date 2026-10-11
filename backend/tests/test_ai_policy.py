import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.ai_policy import CustomerWrite, TenantWrite, evaluate_access, owned_customer, workspace_merchant
from app.core.config import settings


@pytest.mark.parametrize('segment,expected', [('New', False), ('Repeat', True), ('VIP', True), ('vip', True), (None, False), ('Bridal', False)])
def test_segment_policy(segment, expected):
    assert evaluate_access(TenantWrite(enabled=True), CustomerWrite(), segment)['policy_eligible'] == expected


def test_customer_override_cannot_bypass_tenant_disable_and_off_wins():
    assert not evaluate_access(TenantWrite(), CustomerWrite(access='allow'), 'VIP')['policy_eligible']
    assert not evaluate_access(TenantWrite(enabled=True), CustomerWrite(access='off'), 'VIP')['policy_eligible']
    result = evaluate_access(TenantWrite(enabled=True), CustomerWrite(access='allow', monthly_limit=10), 'New')
    assert result['policy_eligible'] and result['monthly_allowance'] == 10
    assert result['credit_balance'] is None and not result['generation_enabled']


def test_zero_allowance_and_invalid_limits():
    assert not evaluate_access(TenantWrite(enabled=True), CustomerWrite(access='allow', monthly_limit=0), 'VIP')['policy_eligible']
    with pytest.raises(ValidationError):
        CustomerWrite(monthly_limit=-1)
    with pytest.raises(ValidationError):
        TenantWrite(enabled_services=['unknown'])


def test_foundation_is_disabled_and_production_cannot_enable_it(monkeypatch):
    monkeypatch.setattr(settings, 'ai_policy_admin_enabled', False)
    with pytest.raises(HTTPException):
        workspace_merchant()
    monkeypatch.setattr(settings, 'ai_policy_admin_enabled', True)
    monkeypatch.setattr(settings, 'environment', 'production')
    with pytest.raises(HTTPException):
        workspace_merchant()


def test_cross_tenant_customer_denied():
    class DB:
        def get(self, model, customer_id):
            return type('Customer', (), {'merchant_id': 2})()
    with pytest.raises(HTTPException) as error:
        owned_customer(DB(), 1, 1)
    assert error.value.status_code == 404


def test_policy_changes_persist_and_other_tenant_cannot_edit_customer():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.db import Base
    from app.models import Merchant, Customer
    from app.ai_policy import get_tenant, put_tenant, get_customer, put_customer
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([Merchant(id=1, name='One'), Merchant(id=2, name='Two')])
        db.flush()
        db.add(Customer(id=1, merchant_id=1, name='VIP', phone='test'))
        db.commit()
        put_tenant(TenantWrite(enabled=True), db, 1)
        put_customer(1, CustomerWrite(access='allow', monthly_limit=10), db, 1)
        assert get_tenant(db, 1)['policy']['enabled']
        assert not get_tenant(db, 2)['policy']['enabled']
        assert get_customer(1, db, 1)['eligibility']['monthly_allowance'] == 10
        with pytest.raises(HTTPException):
            put_customer(1, CustomerWrite(access='off'), db, 2)
        assert get_customer(1, db, 1)['policy']['access'] == 'allow'
    engine.dispose()
