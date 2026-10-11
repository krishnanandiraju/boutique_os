"""AI entitlement foundation. Disabled until authenticated admin access and ledger ship."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, ForeignKey, Integer, JSON, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.config import settings
from app.db import Base, get_db
from app.models import Customer
from app.customer_crm_v2 import CustomerProfile


class TenantAIPolicy(Base):
    __tablename__ = 'tenant_ai_policies'
    merchant_id: Mapped[int] = mapped_column(ForeignKey('merchants.id'), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    monthly_customer_limit: Mapped[int] = mapped_column(Integer, default=3)
    allowed_segments: Mapped[list] = mapped_column(JSON, default=lambda: ['Repeat', 'VIP'])
    enabled_services: Mapped[list] = mapped_column(JSON, default=lambda: ['standard_preview'])


class CustomerAIPolicy(Base):
    __tablename__ = 'customer_ai_policies'
    customer_id: Mapped[int] = mapped_column(ForeignKey('customers.id'), primary_key=True)
    access: Mapped[str] = mapped_column(default='inherit')
    monthly_limit: Mapped[int] = mapped_column(Integer, default=3)


class TenantWrite(BaseModel):
    enabled: bool = False
    monthly_customer_limit: int = Field(default=3, ge=0, le=1000)
    allowed_segments: list[Literal['New', 'Repeat', 'VIP']] = Field(default_factory=lambda: ['Repeat', 'VIP'])
    enabled_services: list[Literal['standard_preview', 'premium_preview_1', 'design_studio_1']] = Field(default_factory=lambda: ['standard_preview'])


class CustomerWrite(BaseModel):
    access: Literal['off', 'inherit', 'allow'] = 'inherit'
    monthly_limit: int = Field(default=3, ge=0, le=1000)


# Prices here are configuration placeholders, not funded credits or provider costs.
SERVICES = [
    {'id': 'standard_preview', 'name': 'Standard Preview', 'description': 'Preview supported finished garments on the customer.', 'credits_per_request': 1},
    {'id': 'premium_preview_1', 'name': 'Premium Preview 1', 'description': 'Additional preview options when connected and validated.', 'credits_per_request': None},
    {'id': 'design_studio_1', 'name': 'Design Studio 1', 'description': 'Create a garment concept from fabric and chosen style.', 'credits_per_request': None},
]
router = APIRouter(prefix='/api/ai-policy', tags=['AI policy'])


def workspace_merchant() -> int:
    if not settings.ai_policy_admin_enabled:
        raise HTTPException(503, 'AI administration is not enabled.')
    # Development workspace only. Replace with authenticated owner/staff context.
    if settings.environment != 'development':
        raise HTTPException(503, 'Authenticated AI administration must be connected before rollout.')
    return 1


def owned_customer(db: Session, customer_id: int, merchant_id: int) -> Customer:
    customer = db.get(Customer, customer_id)
    if not customer or customer.merchant_id != merchant_id:
        raise HTTPException(404, 'Customer was not found.')
    return customer


def tenant_values(db: Session, merchant_id: int) -> TenantWrite:
    row = db.get(TenantAIPolicy, merchant_id)
    return TenantWrite(**{key: getattr(row, key) for key in TenantWrite.model_fields}) if row else TenantWrite()


def customer_values(db: Session, customer_id: int) -> CustomerWrite:
    row = db.get(CustomerAIPolicy, customer_id)
    return CustomerWrite(access=row.access, monthly_limit=row.monthly_limit) if row else CustomerWrite()


def evaluate_access(tenant: TenantWrite, customer: CustomerWrite, segment: str | None) -> dict:
    normalized = (segment or '').strip().casefold()
    segment_allowed = normalized in {s.casefold() for s in tenant.allowed_segments}
    eligible = tenant.enabled and customer.access != 'off' and (customer.access == 'allow' or segment_allowed)
    limit = customer.monthly_limit if customer.access == 'allow' else tenant.monthly_customer_limit
    return {'policy_eligible': eligible and limit > 0, 'monthly_allowance': limit if eligible else 0,
            'generation_enabled': False, 'credit_balance': None,
            'reason': 'Credit accounting and authenticated request enforcement are pending.'}


@router.get('/tenant')
def get_tenant(db: Session = Depends(get_db), merchant_id: int = Depends(workspace_merchant)):
    return {'policy': tenant_values(db, merchant_id).model_dump(), 'services': SERVICES,
            'credit_balance': None, 'generation_enabled': False}


@router.put('/tenant')
def put_tenant(payload: TenantWrite, db: Session = Depends(get_db), merchant_id: int = Depends(workspace_merchant)):
    row = db.get(TenantAIPolicy, merchant_id)
    if not row:
        row = TenantAIPolicy(merchant_id=merchant_id)
        db.add(row)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()
    return payload.model_dump()


@router.get('/customers/{customer_id}')
def get_customer(customer_id: int, db: Session = Depends(get_db), merchant_id: int = Depends(workspace_merchant)):
    owned_customer(db, customer_id, merchant_id)
    profile = db.scalar(select(CustomerProfile).where(CustomerProfile.customer_id == customer_id))
    policy = customer_values(db, customer_id)
    return {'policy': policy.model_dump(), 'eligibility': evaluate_access(tenant_values(db, merchant_id), policy, profile.customer_segment if profile else None)}


@router.put('/customers/{customer_id}')
def put_customer(customer_id: int, payload: CustomerWrite, db: Session = Depends(get_db), merchant_id: int = Depends(workspace_merchant)):
    owned_customer(db, customer_id, merchant_id)
    row = db.get(CustomerAIPolicy, customer_id)
    if not row:
        row = CustomerAIPolicy(customer_id=customer_id)
        db.add(row)
    row.access, row.monthly_limit = payload.access, payload.monthly_limit
    db.commit()
    return payload.model_dump()
