"""Explicit, one-time provisioning for the existing Meera Boutique demo."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_policy import (
    CustomerAIPolicy, ProductAIConfiguration, TenantAICreditAccount,
    TenantAICreditLedger, TenantAIPolicy, TenantAIServiceConfig,
)
from app.core.config import settings
from app.models import Customer, Item, Merchant

MARKER = 'Meera Boutique demo AI activation v1'
DEMO_CUSTOMERS = {'Anjali Rao', 'Priya Sharma', 'Neha Reddy'}


def provision_demo_ai(db: Session) -> None:
    if not (settings.ai_demo_bootstrap_enabled and settings.tryon_enabled
            and settings.tryon_provider == 'huggingface'):
        return
    merchant = db.get(Merchant, 1)
    if not merchant or merchant.name != 'Meera Boutique':
        return
    if db.scalar(select(TenantAICreditLedger.id).where(
            TenantAICreditLedger.merchant_id == merchant.id,
            TenantAICreditLedger.note == MARKER)) is not None:
        # Repair the old bundled kurta category without funding or re-enabling anyone.
        product = db.scalar(select(ProductAIConfiguration).join(Item, Item.id == ProductAIConfiguration.item_id).where(
            ProductAIConfiguration.merchant_id == merchant.id,
            Item.name == 'Cotton Kurta - Blue', ProductAIConfiguration.variant_id.is_(None)))
        if product and product.garment_category == 'tops':
            product.garment_category = 'one-pieces'
            db.commit()
        return
    policy = db.get(TenantAIPolicy, merchant.id) or TenantAIPolicy(merchant_id=merchant.id)
    policy.enabled = True
    policy.allowed_segments = ['Repeat', 'VIP']
    policy.enabled_services = ['standard_preview']
    policy.monthly_request_limit_per_customer = 0
    policy.monthly_spending_limit_credits = None
    db.add(policy)
    service = db.get(TenantAIServiceConfig, (merchant.id, 'standard_preview')) or TenantAIServiceConfig(
        merchant_id=merchant.id, service_id='standard_preview')
    service.enabled = True
    service.credits_per_success = 1
    service.spending_limit_credits = None
    db.add(service)
    for customer in db.scalars(select(Customer).where(
            Customer.merchant_id == merchant.id, Customer.name.in_(DEMO_CUSTOMERS))):
        access = db.get(CustomerAIPolicy, customer.id) or CustomerAIPolicy(customer_id=customer.id)
        access.control = 'allow'
        access.monthly_request_limit = None
        db.add(access)
    item = db.scalar(select(Item).where(Item.merchant_id == merchant.id, Item.name == 'Cotton Kurta - Blue'))
    if item:
        product = db.scalar(select(ProductAIConfiguration).where(
            ProductAIConfiguration.merchant_id == merchant.id,
            ProductAIConfiguration.item_id == item.id,
            ProductAIConfiguration.variant_id.is_(None))) or ProductAIConfiguration(
                merchant_id=merchant.id, item_id=item.id)
        product.ai_enabled = True
        product.suitable_photograph_required = True
        product.garment_category = 'one-pieces'
        product.required_photo_type = 'flat-lay'
        product.approved_services = ['standard_preview']
        db.add(product)
    account = db.get(TenantAICreditAccount, merchant.id) or TenantAICreditAccount(
        merchant_id=merchant.id, available_credits=0, reserved_credits=0, spent_credits=0)
    account.available_credits += 100
    db.add(account)
    db.add(TenantAICreditLedger(merchant_id=merchant.id, entry_type='fund', credits=100,
        balance_after=account.available_credits, reserved_after=account.reserved_credits, note=MARKER))
    db.commit()
