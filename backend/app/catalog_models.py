from __future__ import annotations

import enum
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.utils import utcnow


class AudienceSegment(str, enum.Enum):
    WOMEN = "WOMEN"
    MEN = "MEN"
    UNISEX = "UNISEX"
    CHILDREN = "CHILDREN"


class TenantProfile(Base):
    """Tenant-level merchandising/measurement scope without hard-coding a gender into BoutiqueOS."""

    __tablename__ = "tenant_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, unique=True)
    supported_audiences: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=lambda: [AudienceSegment.WOMEN.value])
    default_audience: Mapped[AudienceSegment] = mapped_column(Enum(AudienceSegment), nullable=False, default=AudienceSegment.WOMEN)
    garment_types: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class ItemCatalogProfile(Base):
    """Optional merchandising metadata for a sellable Item."""

    __tablename__ = "item_catalog_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False, unique=True)
    audience: Mapped[AudienceSegment | None] = mapped_column(Enum(AudienceSegment), nullable=True)
    collection: Mapped[str | None] = mapped_column(String(120), nullable=True)
    season: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class ItemVariant(Base):
    """Optional variant identity under an Item. SKU is deliberately nullable."""

    __tablename__ = "item_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(120), nullable=True)
    option_values: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    selling_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    cost_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("item_id", "sku", name="uq_item_variant_sku"),
    )


class VariantInventoryLot(Base):
    """Optional link: unlinked lots remain valid for non-variant items."""

    __tablename__ = "variant_inventory_lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("item_variants.id"), nullable=False)
    inventory_lot_id: Mapped[int] = mapped_column(ForeignKey("inventory_lots.id"), nullable=False, unique=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class OrderLineVariant(Base):
    """Preserves the exact optional variant selected on an order line."""

    __tablename__ = "order_line_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_line_id: Mapped[int] = mapped_column(ForeignKey("order_lines.id"), nullable=False, unique=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("item_variants.id"), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
