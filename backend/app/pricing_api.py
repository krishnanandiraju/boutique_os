"""Audited discounts on immutable order-line prices."""
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain_v2 import DiscountKind, DiscountRule, DiscountScope, OrderAdjustment
from app.integrations.service import IntegrationEventService
from app.models import Order, OrderLine, OrderStatus

router = APIRouter(prefix='/api/v2/orders', tags=['order-pricing'])
events = IntegrationEventService()
CENT = Decimal('0.01')


class ApplyDiscount(BaseModel):
    rule_id: int
    order_line_id: int | None = None
    reason: str = Field(default='', max_length=1000)


class ReverseDiscount(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


def _order(db, order_id, merchant_id, *, editing=False):
    if editing and db.bind.dialect.name == 'sqlite':
        db.execute(text('BEGIN IMMEDIATE'))
    order = db.scalar(select(Order).where(Order.id == order_id, Order.merchant_id == merchant_id).with_for_update())
    if order is None:
        raise HTTPException(404, 'Order not found')
    if editing and order.status not in {OrderStatus.DRAFT, OrderStatus.CONFIRMED, OrderStatus.TAILORING, OrderStatus.READY}:
        raise HTTPException(409, 'Pricing is locked after packing, shipping, delivery or cancellation')
    return order


def _adjustments(db, order_id):
    return list(db.scalars(select(OrderAdjustment).where(OrderAdjustment.order_id == order_id).order_by(OrderAdjustment.id)))


def _active(rows):
    reversed_ids = {int(row.source.split(':')[1]) for row in rows if row.source.startswith('REVERSAL:')}
    return [row for row in rows if not row.source.startswith('REVERSAL:') and row.id not in reversed_ids]


def _pricing(db, order):
    lines = list(db.scalars(select(OrderLine).where(OrderLine.order_id == order.id)))
    subtotal = sum((line.quantity * line.unit_price for line in lines), Decimal('0')).quantize(CENT, rounding=ROUND_HALF_UP)
    adjustments = _adjustments(db, order.id)
    discount = sum((row.amount for row in adjustments), Decimal('0')).quantize(CENT)
    active_ids = {row.id for row in _active(adjustments)}
    return {
        'order_id': order.id, 'subtotal': str(subtotal), 'discount_total': str(discount), 'total': str(subtotal - discount),
        'adjustments': [{'id': row.id, 'order_line_id': row.order_line_id, 'rule_id': row.rule_id,
            'kind': row.kind.value, 'value': str(row.value), 'amount': str(row.amount), 'reason': row.reason,
            'source': row.source, 'active': row.id in active_ids, 'created_at': row.created_at.isoformat()} for row in adjustments],
    }


def _commit(db, order, event_type):
    db.flush()
    pricing = _pricing(db, order)
    order.total_amount = Decimal(pricing['total'])
    events.enqueue(db, merchant_id=order.merchant_id, event_type=event_type, aggregate_type='Order', aggregate_id=str(order.id), payload=pricing)
    db.commit()
    return pricing


@router.get('/{order_id}/pricing')
def get_pricing(order_id: int, merchant_id: int = 1, db: Session = Depends(get_db)):
    return _pricing(db, _order(db, order_id, merchant_id))


@router.post('/{order_id}/discounts', status_code=201)
def apply_discount(order_id: int, payload: ApplyDiscount, merchant_id: int = 1, db: Session = Depends(get_db)):
    order = _order(db, order_id, merchant_id, editing=True)
    rule = db.scalar(select(DiscountRule).where(DiscountRule.id == payload.rule_id, DiscountRule.merchant_id == merchant_id, DiscountRule.active.is_(True)))
    if rule is None:
        raise HTTPException(404, 'Active discount rule not found')
    if rule.requires_reason and not payload.reason.strip():
        raise HTTPException(422, 'Enter a reason for this discount')
    existing = _active(_adjustments(db, order.id))
    if any(row.rule_id == rule.id and row.order_line_id == payload.order_line_id for row in existing):
        raise HTTPException(409, 'This discount is already applied')
    if existing and (not rule.stackable or any((db.get(DiscountRule, row.rule_id) is None or not db.get(DiscountRule, row.rule_id).stackable) for row in existing)):
        raise HTTPException(409, 'These discount rules cannot be combined')
    if rule.scope == DiscountScope.LINE:
        line = db.scalar(select(OrderLine).where(OrderLine.id == payload.order_line_id, OrderLine.order_id == order.id))
        if line is None:
            raise HTTPException(422, 'Select a line belonging to this order')
        if any(row.order_line_id is None for row in existing):
            raise HTTPException(409, 'Apply line discounts before order discounts')
        base = line.quantity * line.unit_price - sum((row.amount for row in existing if row.order_line_id == line.id), Decimal('0'))
    else:
        if payload.order_line_id is not None:
            raise HTTPException(422, 'An order discount must not specify a line')
        base = Decimal(_pricing(db, order)['total'])
    amount = (base * rule.value / Decimal('100') if rule.kind == DiscountKind.PERCENTAGE else rule.value).quantize(CENT, rounding=ROUND_HALF_UP)
    if rule.max_amount is not None:
        amount = min(amount, rule.max_amount)
    amount = min(amount, base).quantize(CENT, rounding=ROUND_HALF_UP)
    if amount <= 0:
        raise HTTPException(409, 'No discountable balance remains')
    # Do not accept a caller-supplied approver name as authorization. Approval
    # discounts remain blocked until the authentication/RBAC work is delivered.
    if rule.approval_above_value is not None and rule.value > rule.approval_above_value:
        raise HTTPException(409, 'This discount requires authenticated approval and cannot be applied here')
    db.add(OrderAdjustment(order_id=order.id, order_line_id=payload.order_line_id, rule_id=rule.id,
        kind=rule.kind, source='RULE', value=rule.value, amount=amount, reason=payload.reason.strip() or None))
    return _commit(db, order, 'order.discount.applied')


@router.post('/{order_id}/discounts/{adjustment_id}/reverse')
def reverse_discount(order_id: int, adjustment_id: int, payload: ReverseDiscount, merchant_id: int = 1, db: Session = Depends(get_db)):
    order = _order(db, order_id, merchant_id, editing=True)
    rows = _adjustments(db, order.id)
    original = next((row for row in rows if row.id == adjustment_id and not row.source.startswith('REVERSAL:')), None)
    if original is None:
        raise HTTPException(404, 'Discount not found')
    if any(row.source == f'REVERSAL:{adjustment_id}' for row in rows):
        return _pricing(db, order)  # Retry cannot increase the total twice.
    if not payload.reason.strip():
        raise HTTPException(422, 'Enter a reason for reversing this discount')
    # Reversing an earlier discount can invalidate the base of a later one.
    if any(row.id > original.id for row in _active(rows)):
        raise HTTPException(409, 'Reverse later discounts first')
    db.add(OrderAdjustment(order_id=order.id, order_line_id=original.order_line_id, rule_id=original.rule_id,
        kind=original.kind, source=f'REVERSAL:{adjustment_id}', value=original.value,
        amount=-original.amount, reason=payload.reason.strip()))
    return _commit(db, order, 'order.discount.reversed')
