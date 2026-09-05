from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.catalog_models import AudienceSegment, ItemCatalogProfile, ItemVariant, OrderLineVariant, VariantInventoryLot
from app.db import get_db
from app.integrations.service import IntegrationEventService
from app.models import (
    InventoryLot,
    InventoryMovement,
    InventoryMovementType,
    InventoryStatus,
    InventoryType,
    Item,
    MeasurementProfile,
    MeasurementVersion,
    MediaAsset,
    Order,
    OrderLine,
    OrderLineAllocation,
    OrderStatus,
    TailoringStage,
    TailoringTask,
)
from app.services.inventory_service import DomainError
from app.utils import utcnow

router = APIRouter()
logger = logging.getLogger(__name__)
events = IntegrationEventService()


class ApiSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, str_strip_whitespace=True)


class VariantSeed(ApiSchema):
    name: str
    sku: str | None = None
    option_values: dict[str, str] = Field(default_factory=dict)
    selling_price: Decimal | None = None
    cost_price: Decimal | None = None
    quantity: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))


class ProductCreateFull(ApiSchema):
    merchant_id: int = 1
    name: str
    sku: str | None = None
    inventory_type: InventoryType
    category: str
    fabric: str | None = None
    color: str | None = None
    selling_price: Decimal
    cost_price: Decimal | None = None
    published: bool = True
    quantity: Decimal = Field(default=Decimal("1"), ge=Decimal("0"))
    audience: AudienceSegment | None = None
    collection: str | None = None
    season: str | None = None
    description: str | None = None
    variants: list[VariantSeed] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_inventory_shape(self):
        if self.inventory_type == InventoryType.UNIQUE and self.variants:
            raise ValueError("Unique pieces do not use variants; record colour/size as product attributes instead")
        if self.inventory_type == InventoryType.UNIQUE and self.quantity not in {Decimal("0"), Decimal("1")}:
            raise ValueError("Unique pieces may only have quantity 0 or 1")
        seen: set[str] = set()
        for variant in self.variants:
            key = variant.sku.strip().lower() if variant.sku else ""
            if key and key in seen:
                raise ValueError("Variant SKUs must be unique within the product")
            if key:
                seen.add(key)
        return self


class VariantView(ApiSchema):
    id: int
    name: str
    sku: str | None
    option_values: dict[str, str]
    selling_price: Decimal | None
    cost_price: Decimal | None
    quantity_available: Decimal


class ProductView(ApiSchema):
    id: int
    merchant_id: int
    name: str
    sku: str | None
    inventory_type: InventoryType
    category: str
    fabric: str | None
    color: str | None
    selling_price: Decimal
    cost_price: Decimal | None
    published: bool
    availability: str
    quantity_available: Decimal
    audience: AudienceSegment | None = None
    collection: str | None = None
    season: str | None = None
    description: str | None = None
    primary_media_url: str | None = None
    media_count: int = 0
    variants: list[VariantView] = Field(default_factory=list)


class VariantAwareOrderLineCreate(ApiSchema):
    item_id: int
    variant_id: int | None = None
    quantity: Decimal = Field(gt=Decimal("0"))
    requires_tailoring: bool = False
    measurement_profile_id: int | None = None
    measurement_version_id: int | None = None


class VariantAwareOrderCreate(ApiSchema):
    merchant_id: int = 1
    customer_id: int
    status: OrderStatus = OrderStatus.CONFIRMED
    lines: list[VariantAwareOrderLineCreate] = Field(min_length=1)


class VariantAwareOrderLineRead(ApiSchema):
    id: int
    item_id: int
    item_name: str
    variant_id: int | None = None
    variant_name: str | None = None
    variant_sku: str | None = None
    quantity: Decimal
    unit_price: Decimal
    requires_tailoring: bool
    tailoring_stage: TailoringStage | None


class VariantAwareOrderRead(ApiSchema):
    id: int
    merchant_id: int
    customer_id: int
    status: OrderStatus
    total_amount: Decimal
    created_at: datetime
    lines: list[VariantAwareOrderLineRead]


def _variant_quantity(db: Session, variant_id: int) -> Decimal:
    value = db.scalar(
        select(func.coalesce(func.sum(InventoryLot.quantity), 0))
        .join(VariantInventoryLot, VariantInventoryLot.inventory_lot_id == InventoryLot.id)
        .where(VariantInventoryLot.variant_id == variant_id)
    )
    return Decimal(value or 0)


def _product_view(db: Session, item: Item) -> ProductView:
    lots = list(db.scalars(select(InventoryLot).where(InventoryLot.item_id == item.id)))
    quantity = sum((Decimal(lot.quantity) for lot in lots), Decimal("0"))
    if item.inventory_type == InventoryType.UNIQUE:
        if not lots or quantity <= 0:
            availability = "SOLD" if any(lot.status == InventoryStatus.SOLD for lot in lots) else "OUT_OF_STOCK"
        elif any(lot.status == InventoryStatus.HELD for lot in lots):
            availability = "HELD"
        else:
            availability = "AVAILABLE"
    else:
        availability = "AVAILABLE" if quantity > 0 else "OUT_OF_STOCK"

    profile = db.scalar(select(ItemCatalogProfile).where(ItemCatalogProfile.item_id == item.id))
    media = list(
        db.scalars(
            select(MediaAsset)
            .where(MediaAsset.item_id == item.id)
            .order_by(MediaAsset.is_primary.desc(), MediaAsset.sort_order.asc(), MediaAsset.id.asc())
        )
    )
    primary = next((asset for asset in media if asset.is_primary), media[0] if media else None)
    variants = list(db.scalars(select(ItemVariant).where(ItemVariant.item_id == item.id, ItemVariant.active.is_(True)).order_by(ItemVariant.id.asc())))

    return ProductView(
        id=item.id,
        merchant_id=item.merchant_id,
        name=item.name,
        sku=item.sku,
        inventory_type=item.inventory_type,
        category=item.category,
        fabric=item.fabric,
        color=item.color,
        selling_price=item.selling_price,
        cost_price=item.cost_price,
        published=item.published,
        availability=availability,
        quantity_available=quantity,
        audience=profile.audience if profile else None,
        collection=profile.collection if profile else None,
        season=profile.season if profile else None,
        description=profile.description if profile else None,
        primary_media_url=f"/media/{primary.storage_key}" if primary else None,
        media_count=len(media),
        variants=[
            VariantView(
                id=variant.id,
                name=variant.name,
                sku=variant.sku,
                option_values=variant.option_values,
                selling_price=variant.selling_price,
                cost_price=variant.cost_price,
                quantity_available=_variant_quantity(db, variant.id),
            )
            for variant in variants
        ],
    )


@router.get("/api/catalog/products", response_model=list[ProductView])
def list_catalog_products(merchant_id: int = 1, db: Session = Depends(get_db)) -> list[ProductView]:
    items = list(db.scalars(select(Item).where(Item.merchant_id == merchant_id).order_by(Item.created_at.desc(), Item.id.desc())))
    return [_product_view(db, item) for item in items]


@router.get("/api/catalog/products/{item_id}", response_model=ProductView)
def get_catalog_product(item_id: int, db: Session = Depends(get_db)) -> ProductView:
    item = db.scalar(select(Item).where(Item.id == item_id))
    if not item:
        raise HTTPException(404, "Product not found")
    return _product_view(db, item)


@router.post("/api/catalog/products", response_model=ProductView, status_code=201)
def create_catalog_product(payload: ProductCreateFull, db: Session = Depends(get_db)) -> ProductView:
    if payload.sku:
        duplicate = db.scalar(select(Item).where(Item.merchant_id == payload.merchant_id, Item.sku == payload.sku))
        if duplicate:
            raise HTTPException(409, "Product SKU already exists")

    try:
        item = Item(
            merchant_id=payload.merchant_id,
            name=payload.name,
            sku=payload.sku or None,
            inventory_type=payload.inventory_type,
            category=payload.category,
            fabric=payload.fabric or None,
            color=payload.color or None,
            selling_price=payload.selling_price,
            cost_price=payload.cost_price,
            published=payload.published,
        )
        db.add(item)
        db.flush()

        if any([payload.audience, payload.collection, payload.season, payload.description]):
            db.add(
                ItemCatalogProfile(
                    item_id=item.id,
                    audience=payload.audience,
                    collection=payload.collection,
                    season=payload.season,
                    description=payload.description,
                )
            )

        if payload.variants:
            for index, seed in enumerate(payload.variants, start=1):
                variant = ItemVariant(
                    item_id=item.id,
                    name=seed.name,
                    sku=seed.sku or None,
                    option_values=seed.option_values,
                    selling_price=seed.selling_price,
                    cost_price=seed.cost_price,
                    active=True,
                )
                db.add(variant)
                db.flush()
                if seed.quantity > 0:
                    lot = InventoryLot(
                        item_id=item.id,
                        lot_code=seed.sku or f"VAR-{item.id}-{index}",
                        quantity=seed.quantity,
                        original_quantity=seed.quantity,
                        status=InventoryStatus.AVAILABLE,
                        received_at=utcnow(),
                        cost_price=seed.cost_price or payload.cost_price,
                        notes=f"Opening stock for variant {seed.name}",
                    )
                    db.add(lot)
                    db.flush()
                    db.add(VariantInventoryLot(variant_id=variant.id, inventory_lot_id=lot.id))
                    db.add(
                        InventoryMovement(
                            merchant_id=item.merchant_id,
                            item_id=item.id,
                            inventory_lot_id=lot.id,
                            movement_type=InventoryMovementType.RECEIPT,
                            quantity=seed.quantity,
                            reference_type="variant",
                            reference_id=variant.id,
                            reason="Opening variant stock",
                        )
                    )
        elif payload.quantity > 0:
            qty = Decimal("1") if payload.inventory_type == InventoryType.UNIQUE else payload.quantity
            lot = InventoryLot(
                item_id=item.id,
                lot_code=payload.sku or f"LOT-{item.id}-1",
                quantity=qty,
                original_quantity=qty,
                status=InventoryStatus.AVAILABLE,
                received_at=utcnow(),
                cost_price=payload.cost_price,
                notes="Opening stock",
            )
            db.add(lot)
            db.flush()
            db.add(
                InventoryMovement(
                    merchant_id=item.merchant_id,
                    item_id=item.id,
                    inventory_lot_id=lot.id,
                    movement_type=InventoryMovementType.RECEIPT,
                    quantity=qty,
                    reference_type="item",
                    reference_id=item.id,
                    reason="Opening stock",
                )
            )

        events.enqueue(
            db,
            merchant_id=item.merchant_id,
            event_type="catalog.product.created",
            aggregate_type="Item",
            aggregate_id=str(item.id),
            payload={"item_id": item.id, "name": item.name, "variant_count": len(payload.variants)},
        )
        db.commit()
        db.refresh(item)
        logger.info("catalog.product.created", extra={"merchant_id": item.merchant_id, "item_id": item.id, "variant_count": len(payload.variants)})
        return _product_view(db, item)
    except Exception:
        db.rollback()
        raise


def _start_write_transaction(db: Session) -> None:
    bind = db.get_bind()
    if bind.dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))


def _allowed_lots(db: Session, item: Item, variant: ItemVariant | None) -> list[InventoryLot]:
    if variant is not None:
        return list(
            db.scalars(
                select(InventoryLot)
                .join(VariantInventoryLot, VariantInventoryLot.inventory_lot_id == InventoryLot.id)
                .where(VariantInventoryLot.variant_id == variant.id, InventoryLot.quantity > 0)
                .order_by(InventoryLot.received_at.asc(), InventoryLot.id.asc())
            )
        )

    active_variant_count = db.scalar(select(func.count(ItemVariant.id)).where(ItemVariant.item_id == item.id, ItemVariant.active.is_(True))) or 0
    if active_variant_count:
        raise DomainError(400, f"Choose a variant for '{item.name}'", code="VARIANT_REQUIRED")

    linked_lot_ids = select(VariantInventoryLot.inventory_lot_id)
    return list(
        db.scalars(
            select(InventoryLot)
            .where(InventoryLot.item_id == item.id, InventoryLot.quantity > 0, ~InventoryLot.id.in_(linked_lot_ids))
            .order_by(InventoryLot.received_at.asc(), InventoryLot.id.asc())
        )
    )


def _measurement_version(db: Session, customer_id: int, line: VariantAwareOrderLineCreate) -> tuple[int | None, int | None]:
    if not line.requires_tailoring or not line.measurement_profile_id:
        return None, None
    profile = db.scalar(select(MeasurementProfile).where(MeasurementProfile.id == line.measurement_profile_id))
    if not profile:
        raise DomainError(404, "Measurement profile not found", code="RESOURCE_NOT_FOUND")
    if profile.customer_id != customer_id:
        raise DomainError(409, "Measurement profile belongs to another customer", code="MEASUREMENT_CONFLICT")
    if line.measurement_version_id:
        version = db.scalar(
            select(MeasurementVersion).where(
                MeasurementVersion.id == line.measurement_version_id,
                MeasurementVersion.measurement_profile_id == profile.id,
            )
        )
    else:
        version = db.scalar(
            select(MeasurementVersion)
            .where(MeasurementVersion.measurement_profile_id == profile.id)
            .order_by(MeasurementVersion.version_number.desc())
        )
    if not version:
        raise DomainError(409, "Selected measurement profile has no valid version", code="INVALID_INPUT")
    return profile.id, version.id


def _order_read(db: Session, order_id: int) -> VariantAwareOrderRead:
    order = db.scalar(select(Order).options(selectinload(Order.lines)).where(Order.id == order_id))
    if not order:
        raise DomainError(500, "Created order could not be loaded")
    lines: list[VariantAwareOrderLineRead] = []
    for line in order.lines:
        item = db.scalar(select(Item).where(Item.id == line.item_id))
        link = db.scalar(select(OrderLineVariant).where(OrderLineVariant.order_line_id == line.id))
        variant = db.scalar(select(ItemVariant).where(ItemVariant.id == link.variant_id)) if link else None
        lines.append(
            VariantAwareOrderLineRead(
                id=line.id,
                item_id=line.item_id,
                item_name=item.name if item else f"Item {line.item_id}",
                variant_id=variant.id if variant else None,
                variant_name=variant.name if variant else None,
                variant_sku=variant.sku if variant else None,
                quantity=line.quantity,
                unit_price=line.unit_price,
                requires_tailoring=line.requires_tailoring,
                tailoring_stage=line.tailoring_stage,
            )
        )
    return VariantAwareOrderRead(
        id=order.id,
        merchant_id=order.merchant_id,
        customer_id=order.customer_id,
        status=order.status,
        total_amount=order.total_amount,
        created_at=order.created_at,
        lines=lines,
    )


@router.post("/api/orders/variant-aware", response_model=VariantAwareOrderRead, status_code=201)
def create_variant_aware_order(payload: VariantAwareOrderCreate, db: Session = Depends(get_db)) -> VariantAwareOrderRead:
    _start_write_transaction(db)
    now = datetime.now(UTC)
    try:
        order = Order(
            merchant_id=payload.merchant_id,
            customer_id=payload.customer_id,
            status=payload.status,
            total_amount=Decimal("0"),
            created_at=now,
        )
        db.add(order)
        db.flush()
        total = Decimal("0")
        touched_items: set[int] = set()

        for request_line in payload.lines:
            item = db.scalar(select(Item).where(Item.id == request_line.item_id, Item.merchant_id == payload.merchant_id))
            if not item:
                raise DomainError(404, f"Item {request_line.item_id} not found", code="RESOURCE_NOT_FOUND")

            variant: ItemVariant | None = None
            if request_line.variant_id is not None:
                variant = db.scalar(
                    select(ItemVariant).where(
                        ItemVariant.id == request_line.variant_id,
                        ItemVariant.item_id == item.id,
                        ItemVariant.active.is_(True),
                    )
                )
                if not variant:
                    raise DomainError(409, f"Variant does not belong to '{item.name}'", code="VARIANT_CONFLICT")

            qty = Decimal(request_line.quantity)
            unit_price = Decimal(variant.selling_price if variant and variant.selling_price is not None else item.selling_price)
            lots = _allowed_lots(db, item, variant)
            allocations: list[tuple[InventoryLot, Decimal]] = []

            if item.inventory_type == InventoryType.UNIQUE:
                if qty != Decimal("1"):
                    raise DomainError(400, f"Unique item '{item.name}' requires quantity 1", code="INVALID_INPUT")
                lot = lots[0] if lots else None
                if not lot or lot.status not in {InventoryStatus.AVAILABLE, InventoryStatus.HELD}:
                    raise DomainError(409, f"'{item.name}' is not available", code="UNIQUE_ITEM_UNAVAILABLE")
                lot.quantity = Decimal("0")
                lot.status = InventoryStatus.SOLD
                allocations.append((lot, Decimal("1")))
            elif item.inventory_type == InventoryType.STOCKED:
                if qty != qty.to_integral_value():
                    raise DomainError(400, f"Stocked item '{item.name}' requires a whole-number quantity", code="INVALID_INPUT")
                available = sum((Decimal(lot.quantity) for lot in lots), Decimal("0"))
                if available < qty:
                    raise DomainError(409, f"Insufficient stock for '{item.name}'", code="INVENTORY_CONFLICT")
                remaining = qty
                for lot in lots:
                    if remaining <= 0:
                        break
                    take = min(Decimal(lot.quantity), remaining)
                    if take <= 0:
                        continue
                    lot.quantity = Decimal(lot.quantity) - take
                    lot.status = InventoryStatus.DEPLETED if lot.quantity <= 0 else InventoryStatus.AVAILABLE
                    allocations.append((lot, take))
                    remaining -= take
            else:
                candidate = next((lot for lot in sorted(lots, key=lambda row: (Decimal(row.quantity), row.id)) if Decimal(lot.quantity) >= qty), None)
                if not candidate:
                    raise DomainError(409, f"No single roll has enough yardage for '{item.name}'", code="INVENTORY_CONFLICT")
                candidate.quantity = Decimal(candidate.quantity) - qty
                candidate.status = InventoryStatus.DEPLETED if candidate.quantity <= 0 else InventoryStatus.AVAILABLE
                allocations.append((candidate, qty))

            profile_id, version_id = _measurement_version(db, payload.customer_id, request_line)
            first_lot = allocations[0][0] if allocations else None
            order_line = OrderLine(
                order_id=order.id,
                item_id=item.id,
                inventory_lot_id=first_lot.id if first_lot else None,
                measurement_profile_id=profile_id,
                measurement_version_id=version_id,
                quantity=qty,
                unit_price=unit_price,
                requires_tailoring=request_line.requires_tailoring,
                tailoring_stage=TailoringStage.MEASUREMENT_PENDING if request_line.requires_tailoring else None,
            )
            db.add(order_line)
            db.flush()
            if variant:
                db.add(OrderLineVariant(order_line_id=order_line.id, variant_id=variant.id))

            for lot, allocated in allocations:
                db.add(OrderLineAllocation(order_line_id=order_line.id, inventory_lot_id=lot.id, quantity=allocated))
                movement_type = InventoryMovementType.YARDAGE_CUT if item.inventory_type == InventoryType.YARDAGE else InventoryMovementType.SALE
                db.add(
                    InventoryMovement(
                        merchant_id=item.merchant_id,
                        item_id=item.id,
                        inventory_lot_id=lot.id,
                        movement_type=movement_type,
                        quantity=-allocated,
                        reference_type="order",
                        reference_id=order.id,
                        reason=f"Order #{order.id}" + (f" · variant {variant.id}" if variant else ""),
                    )
                )

            if request_line.requires_tailoring:
                db.add(TailoringTask(order_line_id=order_line.id, stage=TailoringStage.MEASUREMENT_PENDING))

            total += qty * unit_price
            touched_items.add(item.id)

        order.total_amount = total
        db.flush()
        events.enqueue(
            db,
            merchant_id=order.merchant_id,
            event_type="order.created",
            aggregate_type="Order",
            aggregate_id=str(order.id),
            payload={
                "order_id": order.id,
                "customer_id": order.customer_id,
                "status": order.status.value,
                "total_amount": str(order.total_amount),
                "variant_aware": True,
            },
        )
        for item_id in touched_items:
            events.enqueue(
                db,
                merchant_id=order.merchant_id,
                event_type="inventory.changed",
                aggregate_type="Item",
                aggregate_id=str(item_id),
                payload={"item_id": item_id, "reason": "order.created"},
            )
        db.commit()
        logger.info("order.variant_aware.created", extra={"merchant_id": order.merchant_id, "order_id": order.id, "line_count": len(payload.lines)})
        return _order_read(db, order.id)
    except DomainError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("order.variant_aware.rollback", extra={"merchant_id": payload.merchant_id, "customer_id": payload.customer_id})
        raise
