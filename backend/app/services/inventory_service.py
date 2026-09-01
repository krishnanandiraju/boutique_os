from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import logging

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.integrations.dto import InventoryAvailabilityExport, OrderExport, OrderExportLine
from app.integrations.service import IntegrationEventService
from app.models import (
    Hold,
    InventoryLot,
    InventoryMovement,
    InventoryMovementType,
    InventoryStatus,
    InventoryType,
    Item,
    MeasurementProfile,
    MeasurementVersion,
    Order,
    OrderLine,
    OrderLineAllocation,
    OrderStatus,
    TailoringStage,
    TailoringTask,
)
from app.schemas import OrderCreate


logger = logging.getLogger(__name__)
integration_events = IntegrationEventService()


@dataclass
class DomainError(Exception):
    status_code: int
    detail: str
    code: str | None = None
    details: dict | None = None

    def __post_init__(self) -> None:
        if self.code is None:
            if self.status_code == 400:
                self.code = "INVALID_INPUT"
            elif self.status_code == 404:
                self.code = "RESOURCE_NOT_FOUND"
            elif self.status_code == 409:
                self.code = "INVENTORY_CONFLICT"
            else:
                self.code = "DOMAIN_ERROR"
        if self.details is None:
            self.details = {}


@dataclass
class InventorySnapshot:
    item_id: int
    item_name: str
    inventory_type: InventoryType
    status: InventoryStatus
    quantity_available: Decimal


@dataclass
class OrderCreationResult:
    order: Order
    inventory_state: list[InventorySnapshot]


def _now() -> datetime:
    return datetime.now(UTC)


def _record_movement(
    db: Session,
    *,
    merchant_id: int,
    item_id: int,
    lot_id: int,
    movement_type: InventoryMovementType,
    quantity: Decimal,
    reference_type: str | None = None,
    reference_id: int | None = None,
    reason: str | None = None,
) -> None:
    db.add(
        InventoryMovement(
            merchant_id=merchant_id,
            item_id=item_id,
            inventory_lot_id=lot_id,
            movement_type=movement_type,
            quantity=quantity,
            reference_type=reference_type,
            reference_id=reference_id,
            reason=reason,
        )
    )


def _active_hold(db: Session, lot_id: int, now: datetime) -> Hold | None:
    return db.scalar(
        select(Hold)
        .where(Hold.inventory_lot_id == lot_id, Hold.released_at.is_(None), Hold.expires_at > now)
        .order_by(Hold.created_at.desc())
    )


def _expired_unreleased_holds(db: Session, lot_id: int, now: datetime) -> list[Hold]:
    return list(
        db.scalars(
            select(Hold).where(Hold.inventory_lot_id == lot_id, Hold.released_at.is_(None), Hold.expires_at <= now)
        )
    )


def _refresh_expired_hold(db: Session, lot: InventoryLot, now: datetime) -> None:
    expired = _expired_unreleased_holds(db, lot.id, now)
    if expired:
        for hold in expired:
            hold.released_at = now
            _record_movement(
                db,
                merchant_id=lot.item.merchant_id,
                item_id=lot.item_id,
                lot_id=lot.id,
                movement_type=InventoryMovementType.HOLD_EXPIRE,
                quantity=Decimal("-1"),
                reference_type="hold",
                reference_id=hold.id,
            )
        if lot.status == InventoryStatus.HELD:
            lot.status = InventoryStatus.AVAILABLE


def _available_quantity(db: Session, item: Item) -> tuple[InventoryStatus, Decimal]:
    if item.inventory_type == InventoryType.UNIQUE:
        lot = db.scalar(select(InventoryLot).where(InventoryLot.item_id == item.id).order_by(InventoryLot.id.asc()))
        if not lot:
            return InventoryStatus.DEPLETED, Decimal("0")
        if lot.status == InventoryStatus.SOLD:
            return InventoryStatus.SOLD, Decimal("0")
        if lot.status == InventoryStatus.HELD:
            return InventoryStatus.HELD, Decimal("0")
        return InventoryStatus.AVAILABLE, Decimal("1")

    qty = db.scalar(select(func.coalesce(func.sum(InventoryLot.quantity), 0)).where(InventoryLot.item_id == item.id))
    quantity = Decimal(qty)
    if quantity <= Decimal("0"):
        return InventoryStatus.DEPLETED, Decimal("0")
    return InventoryStatus.AVAILABLE, quantity


def _lock_unique_lot(db: Session, item_id: int) -> InventoryLot:
    lot = db.scalar(
        select(InventoryLot)
        .join(Item)
        .where(Item.id == item_id, Item.inventory_type == InventoryType.UNIQUE)
        .order_by(InventoryLot.received_at.asc(), InventoryLot.id.asc())
    )
    if not lot:
        raise DomainError(404, "Unique inventory lot not found for item", code="RESOURCE_NOT_FOUND")
    return lot


def _stocked_lots_ordered(db: Session, item_id: int) -> list[InventoryLot]:
    return list(
        db.scalars(
            select(InventoryLot)
            .where(InventoryLot.item_id == item_id, InventoryLot.quantity > 0)
            .order_by(InventoryLot.received_at.asc(), InventoryLot.id.asc())
        )
    )


def _yardage_roll_smallest_sufficient(db: Session, item_id: int, qty: Decimal) -> InventoryLot | None:
    return db.scalar(
        select(InventoryLot)
        .where(InventoryLot.item_id == item_id, InventoryLot.quantity >= qty)
        .order_by(InventoryLot.quantity.asc(), InventoryLot.received_at.asc(), InventoryLot.id.asc())
    )


def _apply_yardage_status(lot: InventoryLot) -> None:
    threshold = Decimal(settings.remnant_threshold_m)
    if lot.quantity <= Decimal("0"):
        lot.quantity = Decimal("0")
        lot.status = InventoryStatus.DEPLETED
    elif lot.quantity <= threshold:
        lot.status = InventoryStatus.REMNANT
    else:
        lot.status = InventoryStatus.AVAILABLE


def place_hold(db: Session, item_id: int, customer_id: int, ttl_hours: int | None = None) -> Hold:
    now = _now()
    ttl = settings.hold_default_ttl_hours if ttl_hours is None else ttl_hours

    item = db.scalar(select(Item).where(Item.id == item_id))
    if not item:
        raise DomainError(404, "Item not found")
    if item.inventory_type != InventoryType.UNIQUE:
        raise DomainError(409, "Holds are only supported for UNIQUE items")

    db.execute(text("BEGIN IMMEDIATE"))
    lot = _lock_unique_lot(db, item_id)
    _refresh_expired_hold(db, lot, now)

    if lot.status == InventoryStatus.SOLD:
        db.rollback()
        raise DomainError(409, "Item already sold", code="UNIQUE_ITEM_UNAVAILABLE")

    active = _active_hold(db, lot.id, now)
    if active:
        db.rollback()
        raise DomainError(409, "Item already has an active hold", code="INVENTORY_CONFLICT")

    lot.status = InventoryStatus.HELD
    hold = Hold(
        inventory_lot_id=lot.id,
        customer_id=customer_id,
        created_at=now,
        expires_at=now + timedelta(hours=ttl),
    )
    db.add(hold)
    db.flush()
    _record_movement(
        db,
        merchant_id=item.merchant_id,
        item_id=item.id,
        lot_id=lot.id,
        movement_type=InventoryMovementType.HOLD,
        quantity=Decimal("1"),
        reference_type="hold",
        reference_id=hold.id,
    )
    db.commit()
    db.refresh(hold)
    return hold


def release_hold(db: Session, item_id: int) -> Hold:
    now = _now()

    item = db.scalar(select(Item).where(Item.id == item_id))
    if not item:
        raise DomainError(404, "Item not found")
    if item.inventory_type != InventoryType.UNIQUE:
        raise DomainError(409, "Release hold is only supported for UNIQUE items")

    db.execute(text("BEGIN IMMEDIATE"))
    lot = _lock_unique_lot(db, item_id)
    _refresh_expired_hold(db, lot, now)
    active = _active_hold(db, lot.id, now)
    if not active:
        db.rollback()
        raise DomainError(404, "No active hold found", code="RESOURCE_NOT_FOUND")

    active.released_at = now
    if lot.status == InventoryStatus.HELD:
        lot.status = InventoryStatus.AVAILABLE

    _record_movement(
        db,
        merchant_id=item.merchant_id,
        item_id=item.id,
        lot_id=lot.id,
        movement_type=InventoryMovementType.HOLD_RELEASE,
        quantity=Decimal("-1"),
        reference_type="hold",
        reference_id=active.id,
    )
    db.commit()
    db.refresh(active)
    return active


def create_order(db: Session, payload: OrderCreate) -> OrderCreationResult:
    now = _now()
    if not payload.lines:
        raise DomainError(400, "Order must contain at least one line", code="INVALID_INPUT")

    db.execute(text("BEGIN IMMEDIATE"))

    try:
        unique_seen: set[int] = set()

        order = Order(
            merchant_id=payload.merchant_id,
            customer_id=payload.customer_id,
            status=payload.status,
            created_at=now,
            total_amount=Decimal("0.00"),
        )
        db.add(order)
        db.flush()

        total = Decimal("0.00")
        touched_items: dict[int, Item] = {}

        for line in payload.lines:
            item = db.scalar(select(Item).where(Item.id == line.item_id))
            if not item:
                raise DomainError(404, f"Item {line.item_id} not found", code="RESOURCE_NOT_FOUND")

            qty = Decimal(line.quantity)
            if qty <= Decimal("0"):
                raise DomainError(400, f"Quantity must be greater than zero for '{item.name}'", code="INVALID_INPUT")

            unit_price = Decimal(item.selling_price)
            first_lot_id: int | None = None
            allocations: list[tuple[int, Decimal]] = []

            if item.inventory_type == InventoryType.UNIQUE:
                if line.item_id in unique_seen:
                    raise DomainError(400, f"Duplicate UNIQUE item '{item.name}' in cart", code="INVALID_INPUT")
                unique_seen.add(line.item_id)

                if qty != Decimal("1"):
                    raise DomainError(400, f"UNIQUE item '{item.name}' must have quantity 1", code="INVALID_INPUT")

                lot = db.scalar(
                    select(InventoryLot)
                    .where(InventoryLot.item_id == item.id)
                    .order_by(InventoryLot.received_at.asc(), InventoryLot.id.asc())
                )
                if not lot:
                    raise DomainError(404, f"Inventory lot not found for '{item.name}'", code="RESOURCE_NOT_FOUND")

                _refresh_expired_hold(db, lot, now)
                active = _active_hold(db, lot.id, now)

                if lot.status == InventoryStatus.SOLD:
                    raise DomainError(409, f"{item.name} is already sold", code="UNIQUE_ITEM_UNAVAILABLE")

                if active and active.customer_id != payload.customer_id:
                    raise DomainError(409, f"{item.name} is currently held for another customer", code="INVENTORY_CONFLICT")

                if active and active.customer_id == payload.customer_id:
                    active.released_at = now
                    _record_movement(
                        db,
                        merchant_id=item.merchant_id,
                        item_id=item.id,
                        lot_id=lot.id,
                        movement_type=InventoryMovementType.HOLD_RELEASE,
                        quantity=Decimal("-1"),
                        reference_type="hold",
                        reference_id=active.id,
                    )

                lot.quantity = Decimal("0")
                lot.status = InventoryStatus.SOLD
                first_lot_id = lot.id
                allocations.append((lot.id, Decimal("1")))
                logger.info(
                    "inventory.allocation.created",
                    extra={
                        "merchant_id": payload.merchant_id,
                        "customer_id": payload.customer_id,
                        "order_id": order.id,
                        "order_line_item_id": item.id,
                        "lot_id": lot.id,
                        "quantity": str(Decimal("1")),
                    },
                )

                _record_movement(
                    db,
                    merchant_id=item.merchant_id,
                    item_id=item.id,
                    lot_id=lot.id,
                    movement_type=InventoryMovementType.SALE,
                    quantity=Decimal("-1"),
                    reference_type="order",
                    reference_id=order.id,
                )

            elif item.inventory_type == InventoryType.STOCKED:
                if qty != qty.to_integral_value():
                    raise DomainError(400, f"STOCKED item '{item.name}' requires whole number quantity")

                lots = _stocked_lots_ordered(db, item.id)
                available_total = sum((Decimal(l.quantity) for l in lots), Decimal("0"))
                if available_total < qty:
                    raise DomainError(409, f"Insufficient stock for '{item.name}'")

                remaining = qty
                for lot in lots:
                    if remaining <= Decimal("0"):
                        break
                    take = min(Decimal(lot.quantity), remaining)
                    if take <= Decimal("0"):
                        continue

                    lot.quantity = Decimal(lot.quantity) - take
                    lot.status = InventoryStatus.DEPLETED if lot.quantity <= Decimal("0") else InventoryStatus.AVAILABLE
                    if first_lot_id is None:
                        first_lot_id = lot.id
                    allocations.append((lot.id, take))
                    remaining -= take
                    logger.info(
                        "inventory.allocation.created",
                        extra={
                            "merchant_id": payload.merchant_id,
                            "customer_id": payload.customer_id,
                            "order_id": order.id,
                            "order_line_item_id": item.id,
                            "lot_id": lot.id,
                            "quantity": str(take),
                        },
                    )

                    _record_movement(
                        db,
                        merchant_id=item.merchant_id,
                        item_id=item.id,
                        lot_id=lot.id,
                        movement_type=InventoryMovementType.SALE,
                        quantity=-take,
                        reference_type="order",
                        reference_id=order.id,
                    )

            else:
                lot = _yardage_roll_smallest_sufficient(db, item.id, qty)
                if not lot:
                    raise DomainError(409, f"No single roll has enough yardage for '{item.name}'")

                lot.quantity = Decimal(lot.quantity) - qty
                _apply_yardage_status(lot)
                first_lot_id = lot.id
                allocations.append((lot.id, qty))
                logger.info(
                    "inventory.allocation.created",
                    extra={
                        "merchant_id": payload.merchant_id,
                        "customer_id": payload.customer_id,
                        "order_id": order.id,
                        "order_line_item_id": item.id,
                        "lot_id": lot.id,
                        "quantity": str(qty),
                    },
                )

                _record_movement(
                    db,
                    merchant_id=item.merchant_id,
                    item_id=item.id,
                    lot_id=lot.id,
                    movement_type=InventoryMovementType.YARDAGE_CUT,
                    quantity=-qty,
                    reference_type="order",
                    reference_id=order.id,
                )

            line_total = qty * unit_price
            total += line_total
            touched_items[item.id] = item

            measurement_profile_id: int | None = None
            measurement_version_id: int | None = None
            if line.requires_tailoring and line.measurement_profile_id:
                profile = db.scalar(select(MeasurementProfile).where(MeasurementProfile.id == line.measurement_profile_id))
                if not profile:
                    raise DomainError(404, "Measurement profile not found", code="RESOURCE_NOT_FOUND")
                if profile.customer_id != payload.customer_id:
                    raise DomainError(409, "Measurement profile belongs to another customer", code="INVENTORY_CONFLICT")

                if line.measurement_version_id:
                    version = db.scalar(
                        select(MeasurementVersion).where(
                            MeasurementVersion.id == line.measurement_version_id,
                            MeasurementVersion.measurement_profile_id == profile.id,
                        )
                    )
                    if not version:
                        raise DomainError(404, "Measurement version not found for selected profile", code="RESOURCE_NOT_FOUND")
                else:
                    version = db.scalar(
                        select(MeasurementVersion)
                        .where(MeasurementVersion.measurement_profile_id == profile.id)
                        .order_by(MeasurementVersion.version_number.desc())
                    )
                    if not version:
                        raise DomainError(409, "Selected measurement profile has no versions", code="INVALID_INPUT")

                measurement_profile_id = profile.id
                measurement_version_id = version.id

            order_line = OrderLine(
                order_id=order.id,
                item_id=item.id,
                inventory_lot_id=first_lot_id,
                measurement_profile_id=measurement_profile_id,
                measurement_version_id=measurement_version_id,
                quantity=qty,
                unit_price=unit_price,
                requires_tailoring=line.requires_tailoring,
                tailoring_stage=TailoringStage.MEASUREMENT_PENDING if line.requires_tailoring else None,
            )
            db.add(order_line)
            db.flush()

            for lot_id, alloc_qty in allocations:
                db.add(
                    OrderLineAllocation(
                        order_line_id=order_line.id,
                        inventory_lot_id=lot_id,
                        quantity=alloc_qty,
                    )
                )

            if line.requires_tailoring:
                db.add(
                    TailoringTask(
                        order_line_id=order_line.id,
                        stage=TailoringStage.MEASUREMENT_PENDING,
                    )
                )

        order.total_amount = total
        db.flush()

        order_for_event = db.scalar(
            select(Order)
            .options(selectinload(Order.lines).selectinload(OrderLine.allocations))
            .where(Order.id == order.id)
        )
        if not order_for_event:
            raise DomainError(500, "Failed to load created order")

        integration_events.enqueue(
            db,
            merchant_id=payload.merchant_id,
            event_type="order.created",
            aggregate_type="Order",
            aggregate_id=str(order.id),
            payload=OrderExport(
                order_id=order_for_event.id,
                merchant_id=order_for_event.merchant_id,
                customer_id=order_for_event.customer_id,
                status=order_for_event.status,
                total_amount=order_for_event.total_amount,
                lines=[
                    OrderExportLine(
                        item_id=line.item_id,
                        quantity=line.quantity,
                        unit_price=line.unit_price,
                        line_total=Decimal(line.quantity) * Decimal(line.unit_price),
                    )
                    for line in order_for_event.lines
                ],
            ).model_dump(mode="json"),
        )

        for item in touched_items.values():
            status, quantity_available = _available_quantity(db, item)
            integration_events.enqueue(
                db,
                merchant_id=payload.merchant_id,
                event_type="inventory.changed",
                aggregate_type="Item",
                aggregate_id=str(item.id),
                payload=InventoryAvailabilityExport(
                    item_id=item.id,
                    inventory_type=item.inventory_type,
                    available_quantity=quantity_available,
                    sellable=status in {InventoryStatus.AVAILABLE, InventoryStatus.HELD},
                    updated_at=now,
                ).model_dump(mode="json"),
            )

        db.commit()

        loaded_order = db.scalar(
            select(Order)
            .options(selectinload(Order.lines).selectinload(OrderLine.allocations))
            .where(Order.id == order.id)
        )
        inventory_state: list[InventorySnapshot] = []
        for item in touched_items.values():
            status, quantity_available = _available_quantity(db, item)
            inventory_state.append(
                InventorySnapshot(
                    item_id=item.id,
                    item_name=item.name,
                    inventory_type=item.inventory_type,
                    status=status,
                    quantity_available=quantity_available,
                )
            )

        if not loaded_order:
            raise DomainError(500, "Failed to load created order")

        logger.info(
            "inventory.order.created",
            extra={
                "merchant_id": payload.merchant_id,
                "customer_id": payload.customer_id,
                "order_id": loaded_order.id,
                "line_count": len(loaded_order.lines),
            },
        )

        return OrderCreationResult(order=loaded_order, inventory_state=inventory_state)
    except DomainError:
        logger.warning(
            "inventory.order.rollback",
            extra={
                "merchant_id": payload.merchant_id,
                "customer_id": payload.customer_id,
                "item_ids": [line.item_id for line in payload.lines],
            },
        )
        db.rollback()
        raise
    except Exception:
        logger.exception(
            "inventory.order.rollback",
            extra={
                "merchant_id": payload.merchant_id,
                "customer_id": payload.customer_id,
                "item_ids": [line.item_id for line in payload.lines],
            },
        )
        db.rollback()
        raise


def order_list(db: Session) -> list[Order]:
    return list(
        db.scalars(
            select(Order)
            .options(selectinload(Order.lines).selectinload(OrderLine.allocations))
            .order_by(Order.created_at.desc())
        )
    )


def order_get(db: Session, order_id: int) -> Order | None:
    return db.scalar(
        select(Order)
        .options(selectinload(Order.lines).selectinload(OrderLine.allocations))
        .where(Order.id == order_id)
    )


def sales_today(db: Session) -> Decimal:
    now = _now()
    start = datetime(now.year, now.month, now.day, tzinfo=UTC)
    value = db.scalar(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.created_at >= start,
            Order.status != OrderStatus.CANCELLED,
        )
    )
    return Decimal(value)
