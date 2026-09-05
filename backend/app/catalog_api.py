from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog_models import AudienceSegment, ItemCatalogProfile, ItemVariant, OrderLineVariant, TenantProfile, VariantInventoryLot
from app.db import get_db
from app.models import InventoryLot, InventoryStatus, Item, Merchant, OrderLine

router = APIRouter()


class ApiSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class TenantProfileUpsert(ApiSchema):
    supported_audiences: list[AudienceSegment] = Field(min_length=1)
    default_audience: AudienceSegment
    garment_types: list[str] = Field(default_factory=list)


class TenantProfileRead(TenantProfileUpsert):
    id: int
    merchant_id: int


class CatalogProfileUpsert(ApiSchema):
    audience: AudienceSegment | None = None
    collection: str | None = None
    season: str | None = None
    description: str | None = None


class CatalogProfileRead(CatalogProfileUpsert):
    id: int
    item_id: int


class VariantCreate(ApiSchema):
    name: str
    sku: str | None = None
    option_values: dict[str, str] = Field(default_factory=dict)
    selling_price: Decimal | None = None
    cost_price: Decimal | None = None
    active: bool = True


class VariantPatch(ApiSchema):
    name: str | None = None
    sku: str | None = None
    option_values: dict[str, str] | None = None
    selling_price: Decimal | None = None
    cost_price: Decimal | None = None
    active: bool | None = None


class VariantRead(ApiSchema):
    id: int
    item_id: int
    name: str
    sku: str | None
    option_values: dict
    selling_price: Decimal | None
    cost_price: Decimal | None
    active: bool


class VariantInventoryRead(ApiSchema):
    variant_id: int
    lot_ids: list[int]
    quantity_available: Decimal
    statuses: dict[str, int]


class OrderLineVariantRead(ApiSchema):
    order_line_id: int
    variant_id: int
    variant_name: str
    sku: str | None
    option_values: dict


@router.get("/api/tenants/{merchant_id}/profile", response_model=TenantProfileRead)
def get_tenant_profile(merchant_id: int, db: Session = Depends(get_db)) -> TenantProfileRead:
    merchant = db.scalar(select(Merchant).where(Merchant.id == merchant_id))
    if not merchant:
        raise HTTPException(404, "Merchant not found")
    row = db.scalar(select(TenantProfile).where(TenantProfile.merchant_id == merchant_id))
    if not row:
        row = TenantProfile(
            merchant_id=merchant_id,
            supported_audiences=[AudienceSegment.WOMEN.value],
            default_audience=AudienceSegment.WOMEN,
            garment_types=["BLOUSE", "KURTA", "BOTTOM", "GENERAL"],
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return TenantProfileRead(
        id=row.id,
        merchant_id=row.merchant_id,
        supported_audiences=[AudienceSegment(value) for value in row.supported_audiences],
        default_audience=row.default_audience,
        garment_types=row.garment_types,
    )


@router.put("/api/tenants/{merchant_id}/profile", response_model=TenantProfileRead)
def put_tenant_profile(merchant_id: int, payload: TenantProfileUpsert, db: Session = Depends(get_db)) -> TenantProfileRead:
    merchant = db.scalar(select(Merchant).where(Merchant.id == merchant_id))
    if not merchant:
        raise HTTPException(404, "Merchant not found")
    if payload.default_audience not in payload.supported_audiences:
        raise HTTPException(400, "default_audience must be included in supported_audiences")
    row = db.scalar(select(TenantProfile).where(TenantProfile.merchant_id == merchant_id))
    if not row:
        row = TenantProfile(merchant_id=merchant_id)
        db.add(row)
    row.supported_audiences = [value.value for value in payload.supported_audiences]
    row.default_audience = payload.default_audience
    row.garment_types = sorted({value.strip().upper() for value in payload.garment_types if value.strip()})
    db.commit()
    db.refresh(row)
    return TenantProfileRead(
        id=row.id,
        merchant_id=row.merchant_id,
        supported_audiences=[AudienceSegment(value) for value in row.supported_audiences],
        default_audience=row.default_audience,
        garment_types=row.garment_types,
    )


@router.get("/api/items/{item_id}/catalog-profile", response_model=CatalogProfileRead | None)
def get_item_catalog_profile(item_id: int, db: Session = Depends(get_db)) -> CatalogProfileRead | None:
    item = db.scalar(select(Item).where(Item.id == item_id))
    if not item:
        raise HTTPException(404, "Item not found")
    return db.scalar(select(ItemCatalogProfile).where(ItemCatalogProfile.item_id == item_id))


@router.put("/api/items/{item_id}/catalog-profile", response_model=CatalogProfileRead)
def put_item_catalog_profile(item_id: int, payload: CatalogProfileUpsert, db: Session = Depends(get_db)) -> CatalogProfileRead:
    item = db.scalar(select(Item).where(Item.id == item_id))
    if not item:
        raise HTTPException(404, "Item not found")
    row = db.scalar(select(ItemCatalogProfile).where(ItemCatalogProfile.item_id == item_id))
    if not row:
        row = ItemCatalogProfile(item_id=item_id)
        db.add(row)
    row.audience = payload.audience
    row.collection = payload.collection
    row.season = payload.season
    row.description = payload.description
    db.commit()
    db.refresh(row)
    return CatalogProfileRead.model_validate(row)


@router.get("/api/items/{item_id}/variants", response_model=list[VariantRead])
def list_item_variants(item_id: int, db: Session = Depends(get_db)) -> list[VariantRead]:
    item = db.scalar(select(Item).where(Item.id == item_id))
    if not item:
        raise HTTPException(404, "Item not found")
    return [VariantRead.model_validate(row) for row in db.scalars(select(ItemVariant).where(ItemVariant.item_id == item_id).order_by(ItemVariant.id.asc()))]


@router.post("/api/items/{item_id}/variants", response_model=VariantRead)
def create_item_variant(item_id: int, payload: VariantCreate, db: Session = Depends(get_db)) -> VariantRead:
    item = db.scalar(select(Item).where(Item.id == item_id))
    if not item:
        raise HTTPException(404, "Item not found")
    if payload.sku:
        duplicate = db.scalar(select(ItemVariant).where(ItemVariant.item_id == item_id, ItemVariant.sku == payload.sku))
        if duplicate:
            raise HTTPException(409, "Variant SKU already exists for this item")
    row = ItemVariant(item_id=item_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return VariantRead.model_validate(row)


@router.get("/api/variants/{variant_id}", response_model=VariantRead)
def get_variant(variant_id: int, db: Session = Depends(get_db)) -> VariantRead:
    row = db.scalar(select(ItemVariant).where(ItemVariant.id == variant_id))
    if not row:
        raise HTTPException(404, "Variant not found")
    return VariantRead.model_validate(row)


@router.patch("/api/variants/{variant_id}", response_model=VariantRead)
def patch_variant(variant_id: int, payload: VariantPatch, db: Session = Depends(get_db)) -> VariantRead:
    row = db.scalar(select(ItemVariant).where(ItemVariant.id == variant_id))
    if not row:
        raise HTTPException(404, "Variant not found")
    changes = payload.model_dump(exclude_unset=True)
    if "sku" in changes and changes["sku"]:
        duplicate = db.scalar(select(ItemVariant).where(ItemVariant.item_id == row.item_id, ItemVariant.sku == changes["sku"], ItemVariant.id != row.id))
        if duplicate:
            raise HTTPException(409, "Variant SKU already exists for this item")
    for key, value in changes.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return VariantRead.model_validate(row)


@router.post("/api/variants/{variant_id}/inventory-lots/{lot_id}", response_model=VariantInventoryRead)
def link_variant_lot(variant_id: int, lot_id: int, db: Session = Depends(get_db)) -> VariantInventoryRead:
    variant = db.scalar(select(ItemVariant).where(ItemVariant.id == variant_id))
    lot = db.scalar(select(InventoryLot).where(InventoryLot.id == lot_id))
    if not variant or not lot:
        raise HTTPException(404, "Variant or inventory lot not found")
    if lot.item_id != variant.item_id:
        raise HTTPException(409, "Inventory lot belongs to a different item")
    existing = db.scalar(select(VariantInventoryLot).where(VariantInventoryLot.inventory_lot_id == lot_id))
    if existing and existing.variant_id != variant_id:
        raise HTTPException(409, "Inventory lot is already assigned to another variant")
    if not existing:
        db.add(VariantInventoryLot(variant_id=variant_id, inventory_lot_id=lot_id))
        db.commit()
    return _variant_inventory(db, variant_id)


@router.delete("/api/variants/{variant_id}/inventory-lots/{lot_id}", response_model=VariantInventoryRead)
def unlink_variant_lot(variant_id: int, lot_id: int, db: Session = Depends(get_db)) -> VariantInventoryRead:
    link = db.scalar(select(VariantInventoryLot).where(VariantInventoryLot.variant_id == variant_id, VariantInventoryLot.inventory_lot_id == lot_id))
    if link:
        db.delete(link)
        db.commit()
    return _variant_inventory(db, variant_id)


@router.get("/api/variants/{variant_id}/inventory", response_model=VariantInventoryRead)
def get_variant_inventory(variant_id: int, db: Session = Depends(get_db)) -> VariantInventoryRead:
    return _variant_inventory(db, variant_id)


def _variant_inventory(db: Session, variant_id: int) -> VariantInventoryRead:
    variant = db.scalar(select(ItemVariant).where(ItemVariant.id == variant_id))
    if not variant:
        raise HTTPException(404, "Variant not found")
    lot_ids = list(db.scalars(select(VariantInventoryLot.inventory_lot_id).where(VariantInventoryLot.variant_id == variant_id)))
    if not lot_ids:
        return VariantInventoryRead(variant_id=variant_id, lot_ids=[], quantity_available=Decimal("0"), statuses={})
    lots = list(db.scalars(select(InventoryLot).where(InventoryLot.id.in_(lot_ids))))
    quantity = sum((Decimal(lot.quantity) for lot in lots), Decimal("0"))
    statuses: dict[str, int] = {}
    for lot in lots:
        statuses[lot.status.value] = statuses.get(lot.status.value, 0) + 1
    return VariantInventoryRead(variant_id=variant_id, lot_ids=lot_ids, quantity_available=quantity, statuses=statuses)


@router.put("/api/order-lines/{line_id}/variant/{variant_id}", response_model=OrderLineVariantRead)
def set_order_line_variant(line_id: int, variant_id: int, db: Session = Depends(get_db)) -> OrderLineVariantRead:
    line = db.scalar(select(OrderLine).where(OrderLine.id == line_id))
    variant = db.scalar(select(ItemVariant).where(ItemVariant.id == variant_id))
    if not line or not variant:
        raise HTTPException(404, "Order line or variant not found")
    if line.item_id != variant.item_id:
        raise HTTPException(409, "Variant does not belong to the order line item")
    row = db.scalar(select(OrderLineVariant).where(OrderLineVariant.order_line_id == line_id))
    if not row:
        row = OrderLineVariant(order_line_id=line_id, variant_id=variant_id)
        db.add(row)
    else:
        row.variant_id = variant_id
    db.commit()
    return OrderLineVariantRead(order_line_id=line_id, variant_id=variant.id, variant_name=variant.name, sku=variant.sku, option_values=variant.option_values)


@router.get("/api/order-lines/{line_id}/variant", response_model=OrderLineVariantRead | None)
def get_order_line_variant(line_id: int, db: Session = Depends(get_db)) -> OrderLineVariantRead | None:
    row = db.scalar(select(OrderLineVariant).where(OrderLineVariant.order_line_id == line_id))
    if not row:
        return None
    variant = db.scalar(select(ItemVariant).where(ItemVariant.id == row.variant_id))
    if not variant:
        return None
    return OrderLineVariantRead(order_line_id=line_id, variant_id=variant.id, variant_name=variant.name, sku=variant.sku, option_values=variant.option_values)
