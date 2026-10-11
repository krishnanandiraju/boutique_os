from __future__ import annotations

import hashlib
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, and_, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.config import settings
from app.customer_crm_v2 import CustomerProfile
from app.db import Base, get_db
from app.models import Customer
from app.utils import utcnow

ServiceId = Literal['standard_preview', 'premium_preview_1', 'design_studio_1']
SegmentName = Literal['New', 'Repeat', 'VIP']
CustomerControl = Literal['follow_segment_policy', 'allow', 'disable']
StaffRole = Literal['owner', 'admin', 'staff', 'platform_ops']

SERVICE_CATALOG: dict[ServiceId, dict[str, str]] = {
    'standard_preview': {
        'name': 'Standard Preview',
        'description': 'Preview supported finished garments on a customer photograph.',
    },
    'premium_preview_1': {
        'name': 'Premium Preview 1',
        'description': 'Higher-quality finished-garment preview where provider connectivity is validated.',
    },
    'design_studio_1': {
        'name': 'Design Studio 1',
        'description': 'Create design concepts from fabric and style input when enabled.',
    },
}

_tenant_semaphore_lock = threading.Lock()
_tenant_semaphores: dict[int, threading.BoundedSemaphore] = {}


class TenantAIPolicy(Base):
    __tablename__ = 'tenant_ai_policies'
    merchant_id: Mapped[int] = mapped_column(ForeignKey('merchants.id'), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    allowed_segments: Mapped[list] = mapped_column(JSON, default=lambda: ['Repeat', 'VIP'])
    enabled_services: Mapped[list] = mapped_column(JSON, default=lambda: ['standard_preview'])
    monthly_request_limit_per_customer: Mapped[int] = mapped_column(Integer, default=3)
    monthly_spending_limit_credits: Mapped[int | None] = mapped_column(Integer, nullable=True)


class CustomerAIPolicy(Base):
    __tablename__ = 'customer_ai_policies'
    customer_id: Mapped[int] = mapped_column(ForeignKey('customers.id'), primary_key=True)
    control: Mapped[str] = mapped_column(String(32), default='follow_segment_policy')
    monthly_request_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)


class TenantAIServiceConfig(Base):
    __tablename__ = 'tenant_ai_service_configs'
    merchant_id: Mapped[int] = mapped_column(ForeignKey('merchants.id'), primary_key=True)
    service_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    credits_per_success: Mapped[int] = mapped_column(Integer, default=1)
    spending_limit_credits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ProductAIConfiguration(Base):
    __tablename__ = 'product_ai_configurations'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey('merchants.id'), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey('items.id'), index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey('item_variants.id'), nullable=True, index=True)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    suitable_photograph_required: Mapped[bool] = mapped_column(Boolean, default=True)
    garment_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    required_photo_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_services: Mapped[list] = mapped_column(JSON, default=lambda: ['standard_preview'])


class TenantAICreditAccount(Base):
    __tablename__ = 'tenant_ai_credit_accounts'
    merchant_id: Mapped[int] = mapped_column(ForeignKey('merchants.id'), primary_key=True)
    available_credits: Mapped[int] = mapped_column(Integer, default=0)
    reserved_credits: Mapped[int] = mapped_column(Integer, default=0)
    spent_credits: Mapped[int] = mapped_column(Integer, default=0)


class TenantAICreditLedger(Base):
    __tablename__ = 'tenant_ai_credit_ledger'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey('merchants.id'), index=True)
    request_key: Mapped[str | None] = mapped_column(String(128), index=True)
    entry_type: Mapped[str] = mapped_column(String(32))
    service_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    credits: Mapped[int] = mapped_column(Integer)
    balance_after: Mapped[int] = mapped_column(Integer)
    reserved_after: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class AIGenerationJob(Base):
    __tablename__ = 'ai_generation_jobs'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey('merchants.id'), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey('customers.id'), index=True)
    service_id: Mapped[str] = mapped_column(String(64), index=True)
    item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    variant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default='reserved')
    reserved_credits: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class AuthContext(BaseModel):
    merchant_id: int
    staff_role: StaffRole
    staff_id: str | None = None


class TenantWrite(BaseModel):
    enabled: bool = False
    allowed_segments: list[SegmentName] = Field(default_factory=lambda: ['Repeat', 'VIP'])
    enabled_services: list[ServiceId] = Field(default_factory=lambda: ['standard_preview'])
    monthly_request_limit_per_customer: int = Field(default=3, ge=0, le=1000)
    monthly_spending_limit_credits: int | None = Field(default=None, ge=1, le=10_000_000)


class CustomerWrite(BaseModel):
    control: CustomerControl = 'follow_segment_policy'
    monthly_request_limit: int | None = Field(default=None, ge=1, le=1000)


class ServiceConfigWrite(BaseModel):
    enabled: bool
    credits_per_success: int = Field(ge=1, le=1000)
    spending_limit_credits: int | None = Field(default=None, ge=1, le=10_000_000)


class ProductConfigWrite(BaseModel):
    ai_enabled: bool
    suitable_photograph_required: bool
    garment_category: str | None = None
    required_photo_type: str | None = None
    approved_services: list[ServiceId] = Field(default_factory=lambda: ['standard_preview'])


class FundTenantCreditsWrite(BaseModel):
    credits: int = Field(ge=1, le=10_000_000)
    note: str | None = Field(default=None, max_length=256)


router = APIRouter(prefix='/api/ai-policy', tags=['AI policy'])


def _default_credits_for_service(service_id: ServiceId) -> int:
    if service_id == 'standard_preview':
        return settings.ai_default_standard_preview_credits
    if service_id == 'premium_preview_1':
        return settings.ai_default_premium_preview_1_credits
    return settings.ai_default_design_studio_1_credits


def get_auth_context(
    request: Request,
    x_boutique_merchant_id: int | None = Header(default=None),
    x_boutique_staff_role: str | None = Header(default=None),
    x_boutique_staff_id: str | None = Header(default=None),
) -> AuthContext:
    if hasattr(request.state, 'auth_context') and request.state.auth_context:
        return request.state.auth_context

    merchant_id = settings.workspace_merchant_id
    staff_role = settings.workspace_staff_role
    staff_id = None
    if settings.environment == 'development' and settings.ai_trust_dev_headers:
        if x_boutique_merchant_id is not None:
            merchant_id = x_boutique_merchant_id
        if x_boutique_staff_role:
            staff_role = x_boutique_staff_role
        staff_id = x_boutique_staff_id

    if staff_role not in {'owner', 'admin', 'staff', 'platform_ops'}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Unauthorized staff role.')
    return AuthContext(merchant_id=merchant_id, staff_role=staff_role, staff_id=staff_id)


def require_admin_context(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if not settings.ai_policy_admin_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, 'AI administration is not enabled.')
    if settings.environment != 'development':
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            'Authenticated AI administration must be connected before production rollout.',
        )
    if auth.staff_role not in {'owner', 'admin', 'platform_ops'}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Staff role cannot manage tenant AI policy.')
    return auth


def _customer_or_404(db: Session, customer_id: int, merchant_id: int) -> Customer:
    customer = db.get(Customer, customer_id)
    if not customer or customer.merchant_id != merchant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Customer was not found.')
    return customer


def _tenant_policy_values(db: Session, merchant_id: int) -> TenantWrite:
    row = db.get(TenantAIPolicy, merchant_id)
    if not row:
        return TenantWrite()
    return TenantWrite(
        enabled=row.enabled,
        allowed_segments=row.allowed_segments,
        enabled_services=row.enabled_services,
        monthly_request_limit_per_customer=row.monthly_request_limit_per_customer,
        monthly_spending_limit_credits=row.monthly_spending_limit_credits,
    )


def _customer_policy_values(db: Session, customer_id: int) -> CustomerWrite:
    row = db.get(CustomerAIPolicy, customer_id)
    if not row:
        return CustomerWrite()
    return CustomerWrite(control=row.control, monthly_request_limit=row.monthly_request_limit)


def _get_or_create_credit_account(db: Session, merchant_id: int) -> TenantAICreditAccount:
    account = db.get(TenantAICreditAccount, merchant_id)
    if not account:
        account = TenantAICreditAccount(merchant_id=merchant_id, available_credits=0, reserved_credits=0, spent_credits=0)
        db.add(account)
        db.flush()
    return account


def _service_configs(db: Session, merchant_id: int) -> dict[str, TenantAIServiceConfig]:
    rows = db.scalars(select(TenantAIServiceConfig).where(TenantAIServiceConfig.merchant_id == merchant_id)).all()
    by_service = {row.service_id: row for row in rows}
    for service_id in SERVICE_CATALOG:
        if service_id not in by_service:
            row = TenantAIServiceConfig(
                merchant_id=merchant_id,
                service_id=service_id,
                enabled=False,
                credits_per_success=_default_credits_for_service(service_id),
                spending_limit_credits=None,
                provider_ref=None,
            )
            db.add(row)
            by_service[service_id] = row
    db.flush()
    return by_service


def evaluate_access(tenant: TenantWrite, customer: CustomerWrite, segment: str | None) -> dict:
    segment_name = (segment or '').strip()
    segment_allowed = segment_name.casefold() in {value.casefold() for value in tenant.allowed_segments}
    if not tenant.enabled:
        return {'allow_ai_previews': False, 'reason': 'AI previews are disabled for this tenant.'}
    if customer.control == 'disable':
        return {'allow_ai_previews': False, 'reason': 'AI previews are disabled for this customer.'}
    if customer.control == 'allow':
        return {'allow_ai_previews': True, 'reason': 'Customer override allows AI previews.'}
    if not segment_allowed:
        return {'allow_ai_previews': False, 'reason': f'Segment policy blocks {segment_name or "Unknown"} customers.'}
    return {'allow_ai_previews': True, 'reason': 'Segment policy allows AI previews.'}


def _month_window_start() -> datetime:
    now_local = datetime.now(ZoneInfo(settings.ai_tenant_timezone))
    start_local = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start_local.astimezone(UTC)


def _successful_monthly_requests(db: Session, merchant_id: int, customer_id: int) -> int:
    return len(
        db.scalars(
            select(AIGenerationJob).where(
                and_(
                    AIGenerationJob.merchant_id == merchant_id,
                    AIGenerationJob.customer_id == customer_id,
                    AIGenerationJob.status == 'succeeded',
                    AIGenerationJob.created_at >= _month_window_start(),
                )
            )
        ).all()
    )


def _product_config(
    db: Session,
    merchant_id: int,
    item_id: int | None,
    variant_id: int | None,
) -> ProductAIConfiguration | None:
    if item_id is None:
        return None
    query = select(ProductAIConfiguration).where(
        and_(
            ProductAIConfiguration.merchant_id == merchant_id,
            ProductAIConfiguration.item_id == item_id,
            ProductAIConfiguration.variant_id == variant_id,
        )
    )
    config = db.scalar(query)
    if config or variant_id is None:
        return config
    return db.scalar(
        select(ProductAIConfiguration).where(
            and_(
                ProductAIConfiguration.merchant_id == merchant_id,
                ProductAIConfiguration.item_id == item_id,
                ProductAIConfiguration.variant_id.is_(None),
            )
        )
    )


def _job_request_key(
    service_id: ServiceId,
    customer_id: int,
    item_id: int | None,
    variant_id: int | None,
    person_bytes: bytes | None,
    garment_bytes: bytes | None,
    idempotency_key: str | None,
) -> str:
    if idempotency_key:
        return f'{service_id}:{idempotency_key.strip()}'
    digest = hashlib.sha256()
    digest.update(service_id.encode())
    digest.update(str(customer_id).encode())
    digest.update(str(item_id or '').encode())
    digest.update(str(variant_id or '').encode())
    if person_bytes:
        digest.update(person_bytes[:8192])
    if garment_bytes:
        digest.update(garment_bytes[:8192])
    return f'{service_id}:implicit:{digest.hexdigest()}'


def _credit_ledger_entry(
    db: Session,
    merchant_id: int,
    request_key: str | None,
    entry_type: str,
    service_id: str | None,
    credits: int,
    account: TenantAICreditAccount,
    note: str | None = None,
) -> None:
    db.add(
        TenantAICreditLedger(
            merchant_id=merchant_id,
            request_key=request_key,
            entry_type=entry_type,
            service_id=service_id,
            credits=credits,
            balance_after=account.available_credits,
            reserved_after=account.reserved_credits,
            note=note,
        )
    )


def reserve_generation_credits(
    db: Session,
    auth: AuthContext,
    customer_id: int,
    service_id: ServiceId,
    item_id: int | None,
    variant_id: int | None,
    person_bytes: bytes | None,
    garment_bytes: bytes | None,
    idempotency_key: str | None,
) -> AIGenerationJob:
    if auth.staff_role not in {'owner', 'admin', 'staff', 'platform_ops'}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Staff role cannot request AI previews.')

    _customer_or_404(db, customer_id, auth.merchant_id)
    tenant = _tenant_policy_values(db, auth.merchant_id)
    customer = _customer_policy_values(db, customer_id)
    profile = db.scalar(select(CustomerProfile).where(CustomerProfile.customer_id == customer_id))
    access = evaluate_access(tenant, customer, profile.customer_segment if profile else None)
    if not access['allow_ai_previews']:
        raise HTTPException(status.HTTP_403_FORBIDDEN, access['reason'])

    if service_id not in tenant.enabled_services:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'This AI service is not enabled for the tenant.')

    service_map = _service_configs(db, auth.merchant_id)
    service = service_map[service_id]
    if not service.enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'This AI service is currently unavailable for this tenant.')

    product = _product_config(db, auth.merchant_id, item_id, variant_id)
    if product:
        if not product.ai_enabled:
            raise HTTPException(status.HTTP_403_FORBIDDEN, 'AI preview is disabled for this product.')
        if service_id not in set(product.approved_services or []):
            raise HTTPException(status.HTTP_403_FORBIDDEN, 'This AI service is not approved for this product.')

    monthly_limit = customer.monthly_request_limit or tenant.monthly_request_limit_per_customer
    if monthly_limit > 0:
        used = _successful_monthly_requests(db, auth.merchant_id, customer_id)
        if used >= monthly_limit:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, 'AI request limit reached for this customer.')

    account = _get_or_create_credit_account(db, auth.merchant_id)
    credits = service.credits_per_success
    request_key = _job_request_key(service_id, customer_id, item_id, variant_id, person_bytes, garment_bytes, idempotency_key)
    existing = db.scalar(select(AIGenerationJob).where(AIGenerationJob.request_key == request_key))
    if existing:
        if existing.status == 'succeeded':
            raise HTTPException(status.HTTP_409_CONFLICT, 'Duplicate request already completed.')
        if existing.status == 'reserved':
            raise HTTPException(status.HTTP_409_CONFLICT, 'Preview already preparing. Please check status shortly.')
        raise HTTPException(status.HTTP_409_CONFLICT, 'Duplicate request already processed.')

    if tenant.monthly_spending_limit_credits is not None and account.spent_credits + credits > tenant.monthly_spending_limit_credits:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, 'Tenant spending limit reached.')
    if service.spending_limit_credits is not None:
        service_spent = sum(
            row.credits
            for row in db.scalars(
                select(TenantAICreditLedger).where(
                    and_(
                        TenantAICreditLedger.merchant_id == auth.merchant_id,
                        TenantAICreditLedger.entry_type == 'charge',
                        TenantAICreditLedger.service_id == service_id,
                    )
                )
            ).all()
        )
        if service_spent + credits > service.spending_limit_credits:
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, 'Service spending limit reached.')

    spendable = account.available_credits - account.reserved_credits
    if spendable < credits:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, 'Tenant AI credits are insufficient.')

    account.reserved_credits += credits
    job = AIGenerationJob(
        request_key=request_key,
        merchant_id=auth.merchant_id,
        customer_id=customer_id,
        service_id=service_id,
        item_id=item_id,
        variant_id=variant_id,
        status='reserved',
        reserved_credits=credits,
    )
    db.add(job)
    _credit_ledger_entry(db, auth.merchant_id, request_key, 'reserve', service_id, credits, account, 'Reserved credits for preview request')
    db.flush()
    return job


def complete_generation_success(db: Session, job: AIGenerationJob) -> None:
    account = _get_or_create_credit_account(db, job.merchant_id)
    account.reserved_credits -= job.reserved_credits
    account.available_credits -= job.reserved_credits
    account.spent_credits += job.reserved_credits
    job.status = 'succeeded'
    job.error_code = None
    job.completed_at = utcnow()
    _credit_ledger_entry(
        db,
        merchant_id=job.merchant_id,
        request_key=job.request_key,
        entry_type='charge',
        service_id=job.service_id,
        credits=job.reserved_credits,
        account=account,
        note='Charged credits after successful preview delivery',
    )


def complete_generation_failure(db: Session, job: AIGenerationJob, error_code: str) -> None:
    account = _get_or_create_credit_account(db, job.merchant_id)
    account.reserved_credits -= job.reserved_credits
    job.status = 'failed'
    job.error_code = error_code
    job.completed_at = utcnow()
    _credit_ledger_entry(
        db,
        merchant_id=job.merchant_id,
        request_key=job.request_key,
        entry_type='release',
        service_id=job.service_id,
        credits=job.reserved_credits,
        account=account,
        note='Released reserved credits after preview failure',
    )


@contextmanager
def tenant_generation_slot(merchant_id: int):
    with _tenant_semaphore_lock:
        semaphore = _tenant_semaphores.get(merchant_id)
        if semaphore is None:
            semaphore = threading.BoundedSemaphore(settings.ai_max_concurrent_jobs_per_tenant)
            _tenant_semaphores[merchant_id] = semaphore

    attempts = max(1, settings.ai_generation_retry_limit)
    backoff = max(0, settings.ai_generation_retry_backoff_ms) / 1000
    acquired = False
    for _ in range(attempts):
        if semaphore.acquire(blocking=False):
            acquired = True
            break
        if backoff:
            time.sleep(backoff)
    if not acquired:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, 'Preparing your preview. Please retry in a moment.')
    try:
        yield
    finally:
        semaphore.release()


def run_generation_with_retries(job_callable):
    attempts = max(1, settings.ai_generation_retry_limit)
    backoff = max(0, settings.ai_generation_retry_backoff_ms) / 1000
    last_error: HTTPException | None = None
    for attempt in range(attempts):
        try:
            return job_callable()
        except HTTPException as exc:
            last_error = exc
            if exc.status_code not in {429, 502, 503, 504} or attempt == attempts - 1:
                raise
            if backoff:
                time.sleep(backoff * (attempt + 1))
    if last_error:
        raise last_error
    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, 'Preview generation failed.')


@router.get('/tenant')
def get_tenant(db: Session = Depends(get_db), auth: AuthContext = Depends(require_admin_context)):
    tenant = _tenant_policy_values(db, auth.merchant_id)
    account = _get_or_create_credit_account(db, auth.merchant_id)
    services = _service_configs(db, auth.merchant_id)
    usage_history = [
        {
            'created_at': row.created_at.isoformat(),
            'entry_type': row.entry_type,
            'service_id': row.service_id,
            'credits': row.credits,
            'note': row.note,
        }
        for row in db.scalars(
            select(TenantAICreditLedger)
            .where(TenantAICreditLedger.merchant_id == auth.merchant_id)
            .order_by(TenantAICreditLedger.id.desc())
            .limit(50)
        ).all()
    ]
    return {
        'policy': tenant.model_dump(),
        'credit_balance': {
            'available_credits': account.available_credits,
            'reserved_credits': account.reserved_credits,
            'spent_credits': account.spent_credits,
        },
        'services': [
            {
                'id': service_id,
                'name': SERVICE_CATALOG[service_id]['name'],
                'description': SERVICE_CATALOG[service_id]['description'],
                'enabled': services[service_id].enabled,
                'credits_per_success': services[service_id].credits_per_success,
                'spending_limit_credits': services[service_id].spending_limit_credits,
            }
            for service_id in SERVICE_CATALOG
        ],
        'usage_history': usage_history,
    }


@router.put('/tenant')
def put_tenant(payload: TenantWrite, db: Session = Depends(get_db), auth: AuthContext = Depends(require_admin_context)):
    row = db.get(TenantAIPolicy, auth.merchant_id)
    if not row:
        row = TenantAIPolicy(merchant_id=auth.merchant_id)
        db.add(row)
    values = payload.model_dump()
    for key, value in values.items():
        setattr(row, key, value)
    db.commit()
    return values


@router.put('/tenant/services/{service_id}')
def put_tenant_service(
    service_id: ServiceId,
    payload: ServiceConfigWrite,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_admin_context),
):
    services = _service_configs(db, auth.merchant_id)
    row = services[service_id]
    row.enabled = payload.enabled
    row.credits_per_success = payload.credits_per_success
    row.spending_limit_credits = payload.spending_limit_credits
    db.commit()
    return {
        'id': service_id,
        'name': SERVICE_CATALOG[service_id]['name'],
        'description': SERVICE_CATALOG[service_id]['description'],
        **payload.model_dump(),
    }


@router.post('/tenant/fund')
def fund_tenant_credits(
    payload: FundTenantCreditsWrite,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_admin_context),
):
    if auth.staff_role != 'platform_ops':
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Only platform operations can fund tenant credits.')
    account = _get_or_create_credit_account(db, auth.merchant_id)
    account.available_credits += payload.credits
    _credit_ledger_entry(
        db,
        merchant_id=auth.merchant_id,
        request_key=None,
        entry_type='fund',
        service_id=None,
        credits=payload.credits,
        account=account,
        note=payload.note or 'Tenant credits funded by platform operations',
    )
    db.commit()
    return {
        'merchant_id': auth.merchant_id,
        'available_credits': account.available_credits,
        'reserved_credits': account.reserved_credits,
        'spent_credits': account.spent_credits,
    }


@router.get('/customers/{customer_id}')
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_admin_context),
):
    _customer_or_404(db, customer_id, auth.merchant_id)
    policy = _customer_policy_values(db, customer_id)
    profile = db.scalar(select(CustomerProfile).where(CustomerProfile.customer_id == customer_id))
    eligibility = evaluate_access(_tenant_policy_values(db, auth.merchant_id), policy, profile.customer_segment if profile else None)
    return {'policy': policy.model_dump(), 'eligibility': eligibility}


@router.put('/customers/{customer_id}')
def put_customer(
    customer_id: int,
    payload: CustomerWrite,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_admin_context),
):
    _customer_or_404(db, customer_id, auth.merchant_id)
    row = db.get(CustomerAIPolicy, customer_id)
    if not row:
        row = CustomerAIPolicy(customer_id=customer_id)
        db.add(row)
    row.control = payload.control
    row.monthly_request_limit = payload.monthly_request_limit
    db.commit()
    return payload.model_dump()


@router.get('/products/{item_id}')
def get_product_ai_config(
    item_id: int,
    variant_id: int | None = None,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_admin_context),
):
    row = _product_config(db, auth.merchant_id, item_id, variant_id)
    if not row:
        return {
            'item_id': item_id,
            'variant_id': variant_id,
            'ai_enabled': True,
            'suitable_photograph_required': True,
            'garment_category': None,
            'required_photo_type': None,
            'approved_services': ['standard_preview'],
        }
    return {
        'item_id': row.item_id,
        'variant_id': row.variant_id,
        'ai_enabled': row.ai_enabled,
        'suitable_photograph_required': row.suitable_photograph_required,
        'garment_category': row.garment_category,
        'required_photo_type': row.required_photo_type,
        'approved_services': row.approved_services,
    }


@router.put('/products/{item_id}')
def put_product_ai_config(
    item_id: int,
    payload: ProductConfigWrite,
    variant_id: int | None = None,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_admin_context),
):
    row = _product_config(db, auth.merchant_id, item_id, variant_id)
    if not row:
        row = ProductAIConfiguration(merchant_id=auth.merchant_id, item_id=item_id, variant_id=variant_id)
        db.add(row)
    row.ai_enabled = payload.ai_enabled
    row.suitable_photograph_required = payload.suitable_photograph_required
    row.garment_category = payload.garment_category
    row.required_photo_type = payload.required_photo_type
    row.approved_services = payload.approved_services
    db.commit()
    return {
        'item_id': item_id,
        'variant_id': variant_id,
        **payload.model_dump(),
    }
