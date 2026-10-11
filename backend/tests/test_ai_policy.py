import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ai_policy import (
    AIGenerationJob,
    AuthContext,
    CustomerAIPolicy,
    CustomerWrite,
    TenantAICreditAccount,
    TenantAICreditLedger,
    TenantAIServiceConfig,
    TenantAIPolicy,
    TenantWrite,
    complete_generation_failure,
    complete_generation_success,
    evaluate_access,
    reserve_generation_credits,
)
from app.db import Base
from app.models import Customer, Merchant


@pytest.mark.parametrize('segment,expected', [('New', False), ('Repeat', True), ('VIP', True), ('vip', True), (None, False), ('Bridal', False)])
def test_segment_policy(segment, expected):
    result = evaluate_access(TenantWrite(enabled=True), CustomerWrite(), segment)
    assert result['allow_ai_previews'] is expected


def _seed(db: Session):
    db.add(Merchant(id=1, name='One'))
    db.add(Merchant(id=2, name='Two'))
    db.add(Customer(id=1, merchant_id=1, name='VIP', phone='1111111111'))
    db.add(Customer(id=2, merchant_id=2, name='Other', phone='2222222222'))
    db.add(TenantAIPolicy(merchant_id=1, enabled=True, allowed_segments=['New', 'Repeat', 'VIP'], enabled_services=['standard_preview'], monthly_request_limit_per_customer=5))
    db.add(CustomerAIPolicy(customer_id=1, control='allow', monthly_request_limit=10))
    db.add(TenantAIServiceConfig(merchant_id=1, service_id='standard_preview', enabled=True, credits_per_success=2, spending_limit_credits=None))
    db.add(TenantAICreditAccount(merchant_id=1, available_credits=20, reserved_credits=0, spent_credits=0))
    db.commit()


def test_reservations_charge_once_and_release_on_failure():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed(db)
        auth = AuthContext(merchant_id=1, staff_role='staff')
        first = reserve_generation_credits(
            db=db,
            auth=auth,
            customer_id=1,
            service_id='standard_preview',
            item_id=101,
            variant_id=None,
            person_bytes=b'person',
            garment_bytes=b'garment',
            idempotency_key='req-1',
        )
        complete_generation_failure(db, first, 'http_503')
        db.commit()

        account = db.get(TenantAICreditAccount, 1)
        assert account.available_credits == 20
        assert account.reserved_credits == 0
        assert db.get(AIGenerationJob, first.id).status == 'failed'
        assert len(db.query(TenantAICreditLedger).all()) == 2

        second = reserve_generation_credits(
            db=db,
            auth=auth,
            customer_id=1,
            service_id='standard_preview',
            item_id=101,
            variant_id=None,
            person_bytes=b'person2',
            garment_bytes=b'garment2',
            idempotency_key='req-2',
        )
        complete_generation_success(db, second)
        db.commit()

        account = db.get(TenantAICreditAccount, 1)
        assert account.available_credits == 18
        assert account.reserved_credits == 0
        assert account.spent_credits == 2
        assert db.get(AIGenerationJob, second.id).status == 'succeeded'

    engine.dispose()


def test_duplicate_idempotency_key_is_blocked():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed(db)
        auth = AuthContext(merchant_id=1, staff_role='staff')
        reserve_generation_credits(
            db=db,
            auth=auth,
            customer_id=1,
            service_id='standard_preview',
            item_id=99,
            variant_id=None,
            person_bytes=b'person',
            garment_bytes=b'garment',
            idempotency_key='dup-key',
        )
        with pytest.raises(HTTPException) as error:
            reserve_generation_credits(
                db=db,
                auth=auth,
                customer_id=1,
                service_id='standard_preview',
                item_id=99,
                variant_id=None,
                person_bytes=b'person',
                garment_bytes=b'garment',
                idempotency_key='dup-key',
            )
        assert error.value.status_code == 409

    engine.dispose()


def test_cross_tenant_customer_isolation():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed(db)
        with pytest.raises(HTTPException) as error:
            reserve_generation_credits(
                db=db,
                auth=AuthContext(merchant_id=2, staff_role='staff'),
                customer_id=1,
                service_id='standard_preview',
                item_id=1,
                variant_id=None,
                person_bytes=b'person',
                garment_bytes=b'garment',
                idempotency_key='isolation-check',
            )
        assert error.value.status_code == 404

    engine.dispose()
