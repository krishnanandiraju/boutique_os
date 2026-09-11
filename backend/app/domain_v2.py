from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base, get_db
from app.models import TailoringStage
from app.utils import utcnow

router = APIRouter(prefix="/api/v2", tags=["domain-v2"])


class AppSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, str_strip_whitespace=True)


class InventoryPurpose(str, enum.Enum):
    SELLABLE = "SELLABLE"
    RAW_MATERIAL = "RAW_MATERIAL"
    TRIM = "TRIM"
    PACKAGING = "PACKAGING"
    CONSUMABLE = "CONSUMABLE"


class Audience(str, enum.Enum):
    WOMEN = "WOMEN"
    MEN = "MEN"
    GIRLS = "GIRLS"
    BOYS = "BOYS"
    UNISEX = "UNISEX"


class MeasurementEditMode(str, enum.Enum):
    UNTIL_STAGE = "UNTIL_STAGE"
    TIME_WINDOW = "TIME_WINDOW"
    STAGE_AND_TIME = "STAGE_AND_TIME"
    APPROVAL_AFTER_STAGE = "APPROVAL_AFTER_STAGE"


class MaterialSource(str, enum.Enum):
    SHOP_STOCK = "SHOP_STOCK"
    TO_PURCHASE = "TO_PURCHASE"
    CUSTOMER_PROVIDED = "CUSTOMER_PROVIDED"
    TAILOR_PROVIDED = "TAILOR_PROVIDED"


class MaterialStatus(str, enum.Enum):
    NEEDED = "NEEDED"
    SOURCED = "SOURCED"
    NOT_REQUIRED = "NOT_REQUIRED"


class DiscountKind(str, enum.Enum):
    PERCENTAGE = "PERCENTAGE"
    FLAT = "FLAT"


class DiscountScope(str, enum.Enum):
    LINE = "LINE"
    ORDER = "ORDER"


class ItemProfile(Base):
    __tablename__ = "item_profiles_v2"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False, unique=True)
    system_code: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    boutique_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    audience: Mapped[Audience | None] = mapped_column(Enum(Audience), nullable=True)
    purpose: Mapped[InventoryPurpose] = mapped_column(Enum(InventoryPurpose), default=InventoryPurpose.SELLABLE, nullable=False)
    material_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    material_details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    system_tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    merchant_tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class MerchantPolicy(Base):
    __tablename__ = "merchant_policies_v2"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, unique=True)
    measurement_edit_mode: Mapped[MeasurementEditMode] = mapped_column(Enum(MeasurementEditMode), default=MeasurementEditMode.UNTIL_STAGE, nullable=False)
    measurement_grace_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    measurement_lock_stage: Mapped[str] = mapped_column(String(64), default=TailoringStage.CUTTING.value, nullable=False)
    post_lock_requires_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    dashboard_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Supplier(Base):
    __tablename__ = "suppliers_v2"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("merchant_id", "name", name="uq_supplier_v2_merchant_name"),)


class ItemSupplier(Base):
    __tablename__ = "item_suppliers_v2"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers_v2.id"), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supplier_sku: Mapped[str | None] = mapped_column(String(120), nullable=True)

    __table_args__ = (UniqueConstraint("item_id", "supplier_id", name="uq_item_supplier_v2"),)


class GarmentSpec(Base):
    __tablename__ = "garment_specs_v2"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_line_id: Mapped[int] = mapped_column(ForeignKey("order_lines.id"), nullable=False, unique=True)
    garment_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    finished_values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    style_attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class TailoringMaterial(Base):
    __tablename__ = "tailoring_materials_v2"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_line_id: Mapped[int] = mapped_column(ForeignKey("order_lines.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("1"), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), default="pcs", nullable=False)
    source: Mapped[MaterialSource] = mapped_column(Enum(MaterialSource), default=MaterialSource.SHOP_STOCK, nullable=False)
    status: Mapped[MaterialStatus] = mapped_column(Enum(MaterialStatus), default=MaterialStatus.NEEDED, nullable=False)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DiscountRule(Base):
    __tablename__ = "discount_rules_v2"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    kind: Mapped[DiscountKind] = mapped_column(Enum(DiscountKind), nullable=False)
    scope: Mapped[DiscountScope] = mapped_column(Enum(DiscountScope), default=DiscountScope.ORDER, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    requires_reason: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    approval_above_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    stackable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class OrderAdjustment(Base):
    __tablename__ = "order_adjustments_v2"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    order_line_id: Mapped[int | None] = mapped_column(ForeignKey("order_lines.id"), nullable=True)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("discount_rules_v2.id"), nullable=True)
    kind: Mapped[DiscountKind] = mapped_column(Enum(DiscountKind), nullable=False)
    source: Mapped[str] = mapped_column(String(64), default="MANUAL", nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ItemProfileWrite(AppSchema):
    system_code: str | None = None
    boutique_code: str | None = None
    audience: Audience | None = None
    purpose: InventoryPurpose = InventoryPurpose.SELLABLE
    material_name: str | None = None
    material_details: dict[str, Any] = Field(default_factory=dict)
    system_tags: list[str] = Field(default_factory=list)
    merchant_tags: list[str] = Field(default_factory=list)


class ItemProfileRead(ItemProfileWrite):
    id: int
    item_id: int
    updated_at: datetime


class MerchantPolicyWrite(AppSchema):
    measurement_edit_mode: MeasurementEditMode = MeasurementEditMode.UNTIL_STAGE
    measurement_grace_hours: int | None = Field(default=None, ge=0, le=720)
    measurement_lock_stage: str = TailoringStage.CUTTING.value
    post_lock_requires_approval: bool = True
    dashboard_config: dict[str, Any] = Field(default_factory=dict)


class MerchantPolicyRead(MerchantPolicyWrite):
    id: int
    merchant_id: int
    updated_at: datetime


class SupplierCreate(AppSchema):
    merchant_id: int = 1
    name: str
    phone: str | None = None
    email: str | None = None
    notes: str | None = None


class SupplierRead(SupplierCreate):
    id: int
    active: bool
    created_at: datetime


class ItemSupplierWrite(AppSchema):
    supplier_id: int
    is_default: bool = False
    supplier_sku: str | None = None


class GarmentSpecWrite(AppSchema):
    garment_type: str | None = None
    finished_values: dict[str, Any] = Field(default_factory=dict)
    style_attributes: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None


class GarmentSpecRead(GarmentSpecWrite):
    id: int
    order_line_id: int
    updated_at: datetime


class TailoringMaterialCreate(AppSchema):
    name: str
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit: str = "pcs"
    source: MaterialSource = MaterialSource.SHOP_STOCK
    status: MaterialStatus = MaterialStatus.NEEDED
    cost: Decimal | None = None
    required: bool = True
    notes: str | None = None


class TailoringMaterialPatch(AppSchema):
    quantity: Decimal | None = Field(default=None, gt=0)
    unit: str | None = None
    source: MaterialSource | None = None
    status: MaterialStatus | None = None
    cost: Decimal | None = None
    required: bool | None = None
    notes: str | None = None


class TailoringMaterialRead(TailoringMaterialCreate):
    id: int
    order_line_id: int


class DiscountRuleCreate(AppSchema):
    merchant_id: int = 1
    name: str
    kind: DiscountKind
    scope: DiscountScope = DiscountScope.ORDER
    value: Decimal = Field(gt=0)
    max_amount: Decimal | None = Field(default=None, gt=0)
    requires_reason: bool = True
    approval_above_value: Decimal | None = Field(default=None, gt=0)
    stackable: bool = False
    active: bool = True


class DiscountRuleRead(DiscountRuleCreate):
    id: int
    created_at: datetime


def _merchant_policy(db: Session, merchant_id: int = 1) -> MerchantPolicy:
    policy = db.scalar(select(MerchantPolicy).where(MerchantPolicy.merchant_id == merchant_id))
    if policy:
        return policy
    policy = MerchantPolicy(merchant_id=merchant_id)
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@router.get("/merchant-policy", response_model=MerchantPolicyRead)
def get_merchant_policy(merchant_id: int = 1, db: Session = Depends(get_db)) -> MerchantPolicy:
    return _merchant_policy(db, merchant_id)


@router.put("/merchant-policy", response_model=MerchantPolicyRead)
def put_merchant_policy(payload: MerchantPolicyWrite, merchant_id: int = 1, db: Session = Depends(get_db)) -> MerchantPolicy:
    policy = _merchant_policy(db, merchant_id)
    for key, value in payload.model_dump().items():
        setattr(policy, key, value)
    db.commit(); db.refresh(policy)
    return policy


@router.get("/items/{item_id}/profile", response_model=ItemProfileRead | None)
def get_item_profile(item_id: int, db: Session = Depends(get_db)) -> ItemProfile | None:
    return db.scalar(select(ItemProfile).where(ItemProfile.item_id == item_id))


@router.put("/items/{item_id}/profile", response_model=ItemProfileRead)
def put_item_profile(item_id: int, payload: ItemProfileWrite, db: Session = Depends(get_db)) -> ItemProfile:
    profile = db.scalar(select(ItemProfile).where(ItemProfile.item_id == item_id))
    if profile is None:
        profile = ItemProfile(item_id=item_id)
        db.add(profile)
    for key, value in payload.model_dump().items():
        setattr(profile, key, value)
    db.commit(); db.refresh(profile)
    return profile


@router.get("/suppliers", response_model=list[SupplierRead])
def list_suppliers(merchant_id: int = 1, db: Session = Depends(get_db)) -> list[Supplier]:
    return list(db.scalars(select(Supplier).where(Supplier.merchant_id == merchant_id, Supplier.active.is_(True)).order_by(Supplier.name)))


@router.post("/suppliers", response_model=SupplierRead)
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db)) -> Supplier:
    supplier = Supplier(**payload.model_dump())
    db.add(supplier); db.commit(); db.refresh(supplier)
    return supplier


@router.get("/items/{item_id}/suppliers")
def list_item_suppliers(item_id: int, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.execute(select(ItemSupplier, Supplier).join(Supplier, Supplier.id == ItemSupplier.supplier_id).where(ItemSupplier.item_id == item_id)).all()
    return [{"id": link.id, "supplier_id": supplier.id, "supplier_name": supplier.name, "is_default": link.is_default, "supplier_sku": link.supplier_sku} for link, supplier in rows]


@router.post("/items/{item_id}/suppliers")
def link_item_supplier(item_id: int, payload: ItemSupplierWrite, db: Session = Depends(get_db)) -> dict[str, Any]:
    if payload.is_default:
        for existing in db.scalars(select(ItemSupplier).where(ItemSupplier.item_id == item_id)):
            existing.is_default = False
    link = ItemSupplier(item_id=item_id, **payload.model_dump())
    db.add(link); db.commit(); db.refresh(link)
    return {"id": link.id, "item_id": item_id, **payload.model_dump()}


@router.get("/order-lines/{order_line_id}/garment-spec", response_model=GarmentSpecRead | None)
def get_garment_spec(order_line_id: int, db: Session = Depends(get_db)) -> GarmentSpec | None:
    return db.scalar(select(GarmentSpec).where(GarmentSpec.order_line_id == order_line_id))


@router.put("/order-lines/{order_line_id}/garment-spec", response_model=GarmentSpecRead)
def put_garment_spec(order_line_id: int, payload: GarmentSpecWrite, db: Session = Depends(get_db)) -> GarmentSpec:
    spec = db.scalar(select(GarmentSpec).where(GarmentSpec.order_line_id == order_line_id))
    if spec is None:
        spec = GarmentSpec(order_line_id=order_line_id)
        db.add(spec)
    for key, value in payload.model_dump().items(): setattr(spec, key, value)
    db.commit(); db.refresh(spec)
    return spec


@router.get("/order-lines/{order_line_id}/materials", response_model=list[TailoringMaterialRead])
def list_tailoring_materials(order_line_id: int, db: Session = Depends(get_db)) -> list[TailoringMaterial]:
    return list(db.scalars(select(TailoringMaterial).where(TailoringMaterial.order_line_id == order_line_id).order_by(TailoringMaterial.id)))


@router.post("/order-lines/{order_line_id}/materials", response_model=TailoringMaterialRead)
def create_tailoring_material(order_line_id: int, payload: TailoringMaterialCreate, db: Session = Depends(get_db)) -> TailoringMaterial:
    material = TailoringMaterial(order_line_id=order_line_id, **payload.model_dump())
    db.add(material); db.commit(); db.refresh(material)
    return material


@router.patch("/materials/{material_id}", response_model=TailoringMaterialRead)
def patch_tailoring_material(material_id: int, payload: TailoringMaterialPatch, db: Session = Depends(get_db)) -> TailoringMaterial:
    material = db.get(TailoringMaterial, material_id)
    if not material: raise HTTPException(404, "Tailoring material not found")
    for key, value in payload.model_dump(exclude_none=True).items(): setattr(material, key, value)
    db.commit(); db.refresh(material)
    return material


@router.get("/discount-rules", response_model=list[DiscountRuleRead])
def list_discount_rules(merchant_id: int = 1, db: Session = Depends(get_db)) -> list[DiscountRule]:
    return list(db.scalars(select(DiscountRule).where(DiscountRule.merchant_id == merchant_id).order_by(DiscountRule.name)))


@router.post("/discount-rules", response_model=DiscountRuleRead)
def create_discount_rule(payload: DiscountRuleCreate, db: Session = Depends(get_db)) -> DiscountRule:
    if payload.kind == DiscountKind.PERCENTAGE and payload.value > Decimal("100"):
        raise HTTPException(422, "Percentage discount cannot exceed 100")
    rule = DiscountRule(**payload.model_dump())
    db.add(rule); db.commit(); db.refresh(rule)
    return rule
