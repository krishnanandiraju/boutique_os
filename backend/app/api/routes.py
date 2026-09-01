from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import (
    ChannelConnection,
    CommerceChannelType,
    Customer,
    Hold,
    ExternalResourceMapping,
    IntegrationOutbox,
    IntegrationOutboxStatus,
    InventoryLot,
    InventoryMovement,
    InventoryMovementType,
    InventoryStatus,
    InventoryType,
    Item,
    MeasurementProfile,
    MeasurementVersion,
    MeasurementUnit,
    Order,
    OrderLine,
    OrderStatus,
    TailoringPriority,
    TailoringStage,
    TailoringTask,
)
from app.integrations.schemas import ChannelConnectionRead, ExternalResourceMappingRead, IntegrationOutboxRead
from app.integrations.service import IntegrationEventService
from app.schemas import (
    CustomerCreate,
    CustomerRead,
    DashboardRead,
    HoldRead,
    HoldRequest,
    InventoryLotAdjustRequest,
    InventoryLotCreate,
    InventoryLotRead,
    InventoryMovementRead,
    InventoryStateRead,
    ItemCreate,
    ItemRead,
    MeasurementProfileCreate,
    MeasurementProfileDetailRead,
    MeasurementProfileRead,
    MeasurementVersionCreate,
    MeasurementVersionRead,
    OrderCreate,
    OrderDetailRead,
    OrderRead,
    OrderStatusPatch,
    OrderLineAllocationRead,
    OrderLineRead,
    TailoringTaskPatch,
    TailoringTaskRead,
    TailoringStagePatch,
)
from app.models import MediaAsset, MediaType
from app.schemas import MediaAssetPatch, MediaAssetRead, MediaUploadResponse
from app.services.inventory_service import DomainError, create_order, order_get, order_list, place_hold, release_hold, sales_today
from app.services.media_service import LocalMediaStorage, MediaStorageError

router = APIRouter()
media_storage = LocalMediaStorage()
integration_events = IntegrationEventService()
logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _item_view(db: Session, item: Item) -> ItemRead:
    lots = list(db.scalars(select(InventoryLot).where(InventoryLot.item_id == item.id)))
    hold_expiry = None

    if item.inventory_type == InventoryType.UNIQUE:
        lot = lots[0] if lots else None
        if not lot:
            availability = "UNAVAILABLE"
            qty = Decimal("0")
        elif lot.status == InventoryStatus.SOLD:
            availability = "SOLD"
            qty = Decimal("0")
        else:
            hold = db.scalar(
                select(Hold)
                .where(Hold.inventory_lot_id == lot.id, Hold.released_at.is_(None))
                .order_by(Hold.created_at.desc())
            )
            now = _now()
            if hold and hold.expires_at > now:
                availability = "HELD"
                hold_expiry = hold.expires_at
                qty = Decimal("0")
            else:
                availability = "AVAILABLE"
                qty = Decimal("1")
        quantity_available = qty
    else:
        quantity_available = sum((Decimal(l.quantity) for l in lots), Decimal("0"))
        availability = "AVAILABLE" if quantity_available > Decimal("0") else "OUT_OF_STOCK"

    return ItemRead(
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
        created_at=item.created_at,
        availability=availability,
        hold_expires_at=hold_expiry,
        quantity_available=quantity_available,
    )


def _order_view(db: Session, order: Order, inventory_state: list[InventoryStateRead] | None = None) -> OrderDetailRead:
    item_ids = {line.item_id for line in order.lines}
    item_rows = list(db.scalars(select(Item).where(Item.id.in_(item_ids)))) if item_ids else []
    item_map = {item.id: item for item in item_rows}

    profile_ids = {line.measurement_profile_id for line in order.lines if line.measurement_profile_id is not None}
    version_ids = {line.measurement_version_id for line in order.lines if line.measurement_version_id is not None}

    profile_rows = list(db.scalars(select(MeasurementProfile).where(MeasurementProfile.id.in_(profile_ids)))) if profile_ids else []
    version_rows = list(db.scalars(select(MeasurementVersion).where(MeasurementVersion.id.in_(version_ids)))) if version_ids else []
    profile_map = {profile.id: profile for profile in profile_rows}
    version_map = {version.id: version for version in version_rows}

    lines: list[OrderLineRead] = []
    all_lot_ids = {a.inventory_lot_id for line in order.lines for a in line.allocations}
    lots = list(db.scalars(select(InventoryLot).where(InventoryLot.id.in_(all_lot_ids)))) if all_lot_ids else []
    lot_code_map = {lot.id: lot.lot_code for lot in lots}

    for line in order.lines:
        item_name = item_map.get(line.item_id).name if line.item_id in item_map else None
        profile = profile_map.get(line.measurement_profile_id) if line.measurement_profile_id else None
        version = version_map.get(line.measurement_version_id) if line.measurement_version_id else None
        allocations = [
            OrderLineAllocationRead(
                id=alloc.id,
                order_line_id=alloc.order_line_id,
                inventory_lot_id=alloc.inventory_lot_id,
                lot_code=lot_code_map.get(alloc.inventory_lot_id),
                quantity=alloc.quantity,
                created_at=alloc.created_at,
            )
            for alloc in line.allocations
        ]
        lines.append(
            OrderLineRead(
                id=line.id,
                item_id=line.item_id,
                item_name=item_name,
                inventory_lot_id=line.inventory_lot_id,
                measurement_profile_id=line.measurement_profile_id,
                measurement_version_id=line.measurement_version_id,
                measurement_profile_name=profile.name if profile else None,
                measurement_garment_type=profile.garment_type if profile else None,
                measurement_unit=profile.unit if profile else None,
                measurement_values=version.measurements if version else None,
                measurement_version_number=version.version_number if version else None,
                allocations=allocations,
                quantity=line.quantity,
                unit_price=line.unit_price,
                line_total=Decimal(line.quantity) * Decimal(line.unit_price),
                requires_tailoring=line.requires_tailoring,
                tailoring_stage=line.tailoring_stage,
            )
        )

    return OrderDetailRead(
        id=order.id,
        merchant_id=order.merchant_id,
        customer_id=order.customer_id,
        status=order.status,
        total_amount=order.total_amount,
        created_at=order.created_at,
        lines=lines,
        inventory_state=inventory_state or [],
    )


def _validate_measurements(measurements: dict[str, Any]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    if not measurements:
        raise HTTPException(400, "At least one measurement is required")

    for key, value in measurements.items():
        label = str(key).strip()
        if not label:
            raise HTTPException(400, "Measurement label cannot be empty")
        try:
            numeric = Decimal(str(value))
        except Exception as exc:
            raise HTTPException(400, f"Invalid value for measurement '{label}'") from exc
        if numeric <= Decimal("0"):
            raise HTTPException(400, f"Measurement '{label}' must be greater than zero")
        normalized[label] = float(numeric)
    return normalized


def _latest_version(db: Session, profile_id: int) -> MeasurementVersion | None:
    return db.scalar(
        select(MeasurementVersion)
        .where(MeasurementVersion.measurement_profile_id == profile_id)
        .order_by(MeasurementVersion.version_number.desc())
    )


def _profile_read(db: Session, profile: MeasurementProfile) -> MeasurementProfileRead:
    latest = _latest_version(db, profile.id)
    latest_read = MeasurementVersionRead.model_validate(latest) if latest else None
    return MeasurementProfileRead(
        id=profile.id,
        customer_id=profile.customer_id,
        name=profile.name,
        garment_type=profile.garment_type,
        unit=profile.unit,
        is_active=profile.is_active,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
        latest_version=latest_read,
    )


def _task_read(db: Session, task: TailoringTask) -> TailoringTaskRead:
    line = db.scalar(select(OrderLine).where(OrderLine.id == task.order_line_id))
    order = db.scalar(select(Order).where(Order.id == line.order_id))
    customer = db.scalar(select(Customer).where(Customer.id == order.customer_id))
    item = db.scalar(select(Item).where(Item.id == line.item_id))
    profile = db.scalar(select(MeasurementProfile).where(MeasurementProfile.id == line.measurement_profile_id)) if line.measurement_profile_id else None
    version = db.scalar(select(MeasurementVersion).where(MeasurementVersion.id == line.measurement_version_id)) if line.measurement_version_id else None

    return TailoringTaskRead(
        id=task.id,
        order_line_id=task.order_line_id,
        stage=task.stage,
        assignee=task.assignee,
        due_at=task.due_at,
        priority=task.priority,
        notes=task.notes,
        created_at=task.created_at,
        updated_at=task.updated_at,
        customer_id=customer.id,
        customer_name=customer.name,
        order_id=order.id,
        order_status=order.status,
        item_id=item.id,
        item_name=item.name,
        measurement_profile_id=profile.id if profile else None,
        measurement_profile_name=profile.name if profile else None,
        measurement_version_id=version.id if version else None,
        measurement_version_number=version.version_number if version else None,
        measurement_unit=profile.unit if profile else None,
        measurement_values=version.measurements if version else None,
    )


def _lot_read(lot: InventoryLot) -> InventoryLotRead:
    return InventoryLotRead.model_validate(lot)


def _apply_lot_status(item: Item, lot: InventoryLot) -> None:
    quantity = Decimal(lot.quantity)
    if item.inventory_type == InventoryType.UNIQUE:
        if quantity <= Decimal("0"):
            lot.status = InventoryStatus.SOLD
        elif lot.status != InventoryStatus.HELD:
            lot.status = InventoryStatus.AVAILABLE
        return

    if quantity <= Decimal("0"):
        lot.quantity = Decimal("0")
        lot.status = InventoryStatus.DEPLETED
        return

    if item.inventory_type == InventoryType.YARDAGE and quantity <= Decimal(str(settings.remnant_threshold_m)):
        lot.status = InventoryStatus.REMNANT
    else:
        lot.status = InventoryStatus.AVAILABLE


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/dashboard", response_model=DashboardRead)
def dashboard(db: Session = Depends(get_db)) -> DashboardRead:
    sales = sales_today(db)

    unique_lots = list(
        db.scalars(
            select(InventoryLot)
            .join(Item)
            .where(Item.inventory_type == InventoryType.UNIQUE)
        )
    )
    held = 0
    available = 0
    now = _now()

    for lot in unique_lots:
        if lot.status == InventoryStatus.SOLD:
            continue
        hold = db.scalar(
            select(Hold)
            .where(Hold.inventory_lot_id == lot.id, Hold.released_at.is_(None))
            .order_by(Hold.created_at.desc())
        )
        if hold and hold.expires_at > now:
            held += 1
        else:
            available += 1

    stocked_available = db.scalar(
        select(func.count(Item.id))
        .join(InventoryLot)
        .where(
            Item.inventory_type.in_([InventoryType.STOCKED, InventoryType.YARDAGE]),
            InventoryLot.quantity > 0,
        )
    )
    available += int(stocked_available or 0)

    orders_pending = db.scalar(
        select(func.count(Order.id)).where(
            Order.status.in_(
                [OrderStatus.DRAFT, OrderStatus.CONFIRMED, OrderStatus.TAILORING, OrderStatus.READY, OrderStatus.PACKED, OrderStatus.SHIPPED]
            )
        )
    )
    tailoring_pending = db.scalar(
        select(func.count(OrderLine.id)).where(OrderLine.requires_tailoring.is_(True), OrderLine.tailoring_stage.is_(None))
    )
    low_stock_items = db.scalar(
        select(func.count(Item.id))
        .join(InventoryLot)
        .where(
            Item.inventory_type == InventoryType.STOCKED,
            InventoryLot.quantity > 0,
            InventoryLot.quantity <= Decimal("2"),
        )
    )
    remnant_rolls = db.scalar(
        select(func.count(InventoryLot.id)).where(
            InventoryLot.status == InventoryStatus.REMNANT,
        )
    )

    return DashboardRead(
        sales_today=sales,
        available_items=available,
        held_items=held,
        orders_pending=int(orders_pending or 0),
        tailoring_pending=int(tailoring_pending or 0),
        low_stock_items=int(low_stock_items or 0),
        remnant_rolls=int(remnant_rolls or 0),
    )


@router.get("/api/items", response_model=list[ItemRead])
def get_items(db: Session = Depends(get_db)) -> list[ItemRead]:
    items = list(db.scalars(select(Item).order_by(Item.created_at.desc())))
    return [_item_view(db, item) for item in items]


@router.post("/api/items", response_model=ItemRead)
def post_item(payload: ItemCreate, db: Session = Depends(get_db)) -> ItemRead:
    item = Item(
        merchant_id=payload.merchant_id,
        name=payload.name,
        sku=payload.sku,
        inventory_type=payload.inventory_type,
        category=payload.category,
        fabric=payload.fabric,
        color=payload.color,
        selling_price=payload.selling_price,
        cost_price=payload.cost_price,
        published=payload.published,
    )
    db.add(item)
    db.flush()

    qty = Decimal("1") if payload.inventory_type == InventoryType.UNIQUE else payload.quantity
    lot = InventoryLot(
        item_id=item.id,
        lot_code=f"LOT-{item.id}-1",
        quantity=qty,
        original_quantity=qty,
        status=InventoryStatus.AVAILABLE,
        cost_price=payload.cost_price,
    )
    db.add(lot)
    db.commit()
    db.refresh(item)
    return _item_view(db, item)


@router.get("/api/items/{item_id}", response_model=ItemRead)
def get_item(item_id: int, db: Session = Depends(get_db)) -> ItemRead:
    item = db.scalar(select(Item).where(Item.id == item_id))
    if not item:
        raise HTTPException(404, "Item not found")
    return _item_view(db, item)


@router.get("/api/items/{item_id}/lots", response_model=list[InventoryLotRead])
def get_item_lots(item_id: int, db: Session = Depends(get_db)) -> list[InventoryLotRead]:
    item = db.scalar(select(Item).where(Item.id == item_id))
    if not item:
        raise HTTPException(404, "Item not found")

    lots = list(
        db.scalars(
            select(InventoryLot)
            .where(InventoryLot.item_id == item_id)
            .order_by(InventoryLot.received_at.asc(), InventoryLot.id.asc())
        )
    )
    return [_lot_read(lot) for lot in lots]


@router.post("/api/media/upload", response_model=MediaUploadResponse)
async def upload_media(file: UploadFile = File(...), item_id: int | None = None, db: Session = Depends(get_db)) -> MediaUploadResponse:
    if not file.filename:
        raise HTTPException(400, "A file is required")

    content_type = file.content_type or "application/octet-stream"
    allowed_images = {"image/jpeg", "image/png", "image/webp"}
    allowed_videos = {"video/mp4", "video/webm"}

    if content_type in allowed_images:
        media_type = MediaType.IMAGE
        max_bytes = settings.media_max_image_mb * 1024 * 1024
    elif content_type in allowed_videos:
        media_type = MediaType.VIDEO
        max_bytes = settings.media_max_video_mb * 1024 * 1024
    else:
        raise HTTPException(415, "Unsupported media type")

    if hasattr(file, "file"):
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)
    else:
        size = 0

    if size == 0:
        raise HTTPException(400, "Uploaded file is empty")
    if size > max_bytes:
        raise HTTPException(413, f"File exceeds the configured limit for {media_type.value.lower()} media")

    try:
        storage_key, _ = media_storage.save(file, merchant_id=1)
    except MediaStorageError as exc:
        raise HTTPException(400, str(exc)) from exc

    asset = MediaAsset(
        merchant_id=1,
        item_id=item_id,
        media_type=media_type,
        storage_key=storage_key,
        original_filename=file.filename,
        mime_type=content_type,
        file_size_bytes=size,
        sort_order=0,
        is_primary=False,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    logger.info(
        "media.uploaded",
        extra={
            "merchant_id": asset.merchant_id,
            "item_id": asset.item_id,
            "media_id": asset.id,
            "media_type": asset.media_type.value,
            "file_size_bytes": asset.file_size_bytes,
        },
    )
    return MediaUploadResponse(
        id=asset.id,
        merchant_id=asset.merchant_id,
        item_id=asset.item_id,
        media_type=asset.media_type,
        storage_key=asset.storage_key,
        original_filename=asset.original_filename,
        mime_type=asset.mime_type,
        file_size_bytes=asset.file_size_bytes,
        width=asset.width,
        height=asset.height,
        duration_seconds=asset.duration_seconds,
        sort_order=asset.sort_order,
        is_primary=asset.is_primary,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
        url=f"/media/{asset.storage_key}",
    )


@router.get("/media/{storage_key:path}")
def serve_media(storage_key: str) -> FileResponse:
    if ".." in storage_key.split("/"):
        raise HTTPException(400, "Invalid storage key")
    try:
        path = media_storage.resolve_path(storage_key)
    except MediaStorageError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not path.exists():
        raise HTTPException(404, "Media not found")
    return FileResponse(path)


@router.get("/api/items/{item_id}/media", response_model=list[MediaAssetRead])
def get_item_media(item_id: int, db: Session = Depends(get_db)) -> list[MediaAssetRead]:
    item = db.scalar(select(Item).where(Item.id == item_id))
    if not item:
        raise HTTPException(404, "Item not found")
    media = list(
        db.scalars(
            select(MediaAsset)
            .where(MediaAsset.item_id == item_id)
            .order_by(MediaAsset.sort_order.asc(), MediaAsset.created_at.asc(), MediaAsset.id.asc())
        )
    )
    return [MediaAssetRead.model_validate(asset) for asset in media]


@router.get("/api/integrations/channels", response_model=list[ChannelConnectionRead])
def get_integrations_channels(db: Session = Depends(get_db)) -> list[ChannelConnectionRead]:
    rows = list(db.scalars(select(ChannelConnection).order_by(ChannelConnection.created_at.asc(), ChannelConnection.id.asc())))
    return [ChannelConnectionRead.model_validate(row) for row in rows]


@router.get("/api/integrations/mappings", response_model=list[ExternalResourceMappingRead])
def get_integrations_mappings(db: Session = Depends(get_db)) -> list[ExternalResourceMappingRead]:
    rows = list(db.scalars(select(ExternalResourceMapping).order_by(ExternalResourceMapping.created_at.asc(), ExternalResourceMapping.id.asc())))
    return [ExternalResourceMappingRead.model_validate(row) for row in rows]


@router.get("/api/integrations/outbox", response_model=list[IntegrationOutboxRead])
def get_integrations_outbox(
    status: IntegrationOutboxStatus | None = None,
    event_type: str | None = None,
    db: Session = Depends(get_db),
) -> list[IntegrationOutboxRead]:
    query = select(IntegrationOutbox).order_by(IntegrationOutbox.created_at.desc(), IntegrationOutbox.id.desc())
    if status is not None:
        query = query.where(IntegrationOutbox.status == status)
    if event_type is not None:
        query = query.where(IntegrationOutbox.event_type == event_type)
    rows = list(db.scalars(query))
    return [IntegrationOutboxRead.model_validate(row) for row in rows]


@router.get("/api/integrations/outbox/{outbox_id}", response_model=IntegrationOutboxRead)
def get_integrations_outbox_item(outbox_id: int, db: Session = Depends(get_db)) -> IntegrationOutboxRead:
    row = db.scalar(select(IntegrationOutbox).where(IntegrationOutbox.id == outbox_id))
    if not row:
        raise HTTPException(404, "Integration outbox item not found")
    return IntegrationOutboxRead.model_validate(row)


@router.post("/api/integrations/outbox/{outbox_id}/retry", response_model=IntegrationOutboxRead)
def retry_integrations_outbox_item(outbox_id: int, db: Session = Depends(get_db)) -> IntegrationOutboxRead:
    row = db.scalar(select(IntegrationOutbox).where(IntegrationOutbox.id == outbox_id))
    if not row:
        raise HTTPException(404, "Integration outbox item not found")
    integration_events.retry(db, row.event_id)
    db.commit()
    db.refresh(row)
    return IntegrationOutboxRead.model_validate(row)


@router.post("/api/items/{item_id}/media/{media_id}/attach", response_model=MediaAssetRead)
def attach_media_to_item(item_id: int, media_id: int, db: Session = Depends(get_db)) -> MediaAssetRead:
    item = db.scalar(select(Item).where(Item.id == item_id))
    if not item:
        raise HTTPException(404, "Item not found")
    media = db.scalar(select(MediaAsset).where(MediaAsset.id == media_id))
    if not media:
        raise HTTPException(404, "Media asset not found")
    media.item_id = item_id
    media.sort_order = media.sort_order or 0
    db.commit()
    db.refresh(media)
    logger.info(
        "media.attached",
        extra={
            "item_id": item_id,
            "media_id": media.id,
        },
    )
    return MediaAssetRead.model_validate(media)


@router.delete("/api/items/{item_id}/media/{media_id}", response_model=MediaAssetRead)
def detach_media_from_item(item_id: int, media_id: int, db: Session = Depends(get_db)) -> MediaAssetRead:
    item = db.scalar(select(Item).where(Item.id == item_id))
    if not item:
        raise HTTPException(404, "Item not found")
    media = db.scalar(select(MediaAsset).where(MediaAsset.id == media_id, MediaAsset.item_id == item_id))
    if not media:
        raise HTTPException(404, "Media asset not found for item")
    media.item_id = None
    if media.is_primary:
        media.is_primary = False
    db.commit()
    db.refresh(media)
    logger.info(
        "media.detached",
        extra={
            "item_id": item_id,
            "media_id": media.id,
        },
    )
    return MediaAssetRead.model_validate(media)


@router.patch("/api/items/{item_id}/media/{media_id}", response_model=MediaAssetRead)
def update_item_media(item_id: int, media_id: int, payload: MediaAssetPatch, db: Session = Depends(get_db)) -> MediaAssetRead:
    item = db.scalar(select(Item).where(Item.id == item_id))
    if not item:
        raise HTTPException(404, "Item not found")
    media = db.scalar(select(MediaAsset).where(MediaAsset.id == media_id, MediaAsset.item_id == item_id))
    if not media:
        raise HTTPException(404, "Media asset not found for item")
    if payload.is_primary is not None:
        if payload.is_primary:
            for asset in db.scalars(select(MediaAsset).where(MediaAsset.item_id == item_id)):
                asset.is_primary = asset.id == media.id
        media.is_primary = payload.is_primary
    if payload.sort_order is not None:
        media.sort_order = payload.sort_order
    db.commit()
    db.refresh(media)
    logger.info(
        "media.updated",
        extra={
            "item_id": item_id,
            "media_id": media.id,
            "is_primary": media.is_primary,
            "sort_order": media.sort_order,
        },
    )
    return MediaAssetRead.model_validate(media)


@router.post("/api/items/{item_id}/lots", response_model=InventoryLotRead)
def post_item_lot(item_id: int, payload: InventoryLotCreate, db: Session = Depends(get_db)) -> InventoryLotRead:
    item = db.scalar(select(Item).where(Item.id == item_id))
    if not item:
        raise HTTPException(404, "Item not found")

    quantity = Decimal("1") if item.inventory_type == InventoryType.UNIQUE else Decimal(payload.quantity)
    if item.inventory_type == InventoryType.UNIQUE and payload.quantity != Decimal("1"):
        raise HTTPException(409, "UNIQUE item lots must have quantity 1")

    existing_count = db.scalar(select(func.count(InventoryLot.id)).where(InventoryLot.item_id == item_id)) or 0
    lot = InventoryLot(
        item_id=item_id,
        lot_code=payload.lot_code or f"LOT-{item_id}-{int(existing_count) + 1}",
        quantity=quantity,
        original_quantity=quantity,
        received_at=payload.received_at or _now(),
        cost_price=payload.cost_price,
        notes=payload.notes,
        status=InventoryStatus.AVAILABLE,
    )
    _apply_lot_status(item, lot)
    db.add(lot)
    db.flush()

    db.add(
        InventoryMovement(
            merchant_id=item.merchant_id,
            item_id=item.id,
            inventory_lot_id=lot.id,
            movement_type=InventoryMovementType.RECEIPT,
            quantity=quantity,
            reference_type="lot",
            reference_id=lot.id,
            reason="Stock receipt",
        )
    )
    db.commit()
    db.refresh(lot)
    logger.info(
        "inventory.lot.received",
        extra={
            "merchant_id": item.merchant_id,
            "item_id": item.id,
            "lot_id": lot.id,
            "quantity": str(quantity),
        },
    )
    return _lot_read(lot)


@router.get("/api/inventory/lots/{lot_id}", response_model=InventoryLotRead)
def get_inventory_lot(lot_id: int, db: Session = Depends(get_db)) -> InventoryLotRead:
    lot = db.scalar(select(InventoryLot).where(InventoryLot.id == lot_id))
    if not lot:
        raise HTTPException(404, "Inventory lot not found")
    return _lot_read(lot)


@router.post("/api/inventory/lots/{lot_id}/adjust", response_model=InventoryLotRead)
def post_inventory_lot_adjust(
    lot_id: int,
    payload: InventoryLotAdjustRequest,
    db: Session = Depends(get_db),
) -> InventoryLotRead:
    lot = db.scalar(select(InventoryLot).where(InventoryLot.id == lot_id))
    if not lot:
        raise HTTPException(404, "Inventory lot not found")

    item = db.scalar(select(Item).where(Item.id == lot.item_id))
    if not item:
        raise HTTPException(404, "Item not found")

    quantity = Decimal(payload.quantity)
    positive_types = {InventoryMovementType.ADJUSTMENT_IN, InventoryMovementType.RETURN, InventoryMovementType.RECEIPT}
    negative_types = {InventoryMovementType.ADJUSTMENT_OUT, InventoryMovementType.DAMAGE, InventoryMovementType.GIFT}

    if payload.adjustment_type in positive_types:
        lot.quantity = Decimal(lot.quantity) + quantity
        movement_qty = quantity
    elif payload.adjustment_type in negative_types:
        if Decimal(lot.quantity) < quantity:
            raise HTTPException(409, "Adjustment exceeds available quantity in lot")
        lot.quantity = Decimal(lot.quantity) - quantity
        movement_qty = -quantity
    else:
        raise HTTPException(409, "Unsupported adjustment movement type")

    _apply_lot_status(item, lot)

    db.add(
        InventoryMovement(
            merchant_id=item.merchant_id,
            item_id=item.id,
            inventory_lot_id=lot.id,
            movement_type=payload.adjustment_type,
            quantity=movement_qty,
            reference_type="lot_adjustment",
            reference_id=lot.id,
            reason=payload.reason,
        )
    )
    db.commit()
    db.refresh(lot)
    logger.info(
        "inventory.adjustment.created",
        extra={
            "merchant_id": item.merchant_id,
            "item_id": item.id,
            "lot_id": lot.id,
            "movement_type": payload.adjustment_type.value,
            "quantity": str(movement_qty),
        },
    )
    return _lot_read(lot)


@router.get("/api/inventory/movements", response_model=list[InventoryMovementRead])
def get_inventory_movements(
    item_id: int | None = None,
    lot_id: int | None = None,
    movement_type: InventoryMovementType | None = None,
    reference_type: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> list[InventoryMovementRead]:
    query = select(InventoryMovement).order_by(InventoryMovement.created_at.desc(), InventoryMovement.id.desc())
    if item_id is not None:
        query = query.where(InventoryMovement.item_id == item_id)
    if lot_id is not None:
        query = query.where(InventoryMovement.inventory_lot_id == lot_id)
    if movement_type is not None:
        query = query.where(InventoryMovement.movement_type == movement_type)
    if reference_type is not None:
        query = query.where(InventoryMovement.reference_type == reference_type)
    if since is not None:
        query = query.where(InventoryMovement.created_at >= since)
    if until is not None:
        query = query.where(InventoryMovement.created_at <= until)

    capped = min(max(limit, 1), 1000)
    rows = list(db.scalars(query.limit(capped)))
    return [InventoryMovementRead.model_validate(row) for row in rows]


@router.post("/api/items/{item_id}/hold", response_model=HoldRead)
def post_hold(item_id: int, payload: HoldRequest, db: Session = Depends(get_db)) -> HoldRead:
    try:
        hold = place_hold(db, item_id=item_id, customer_id=payload.customer_id, ttl_hours=payload.ttl_hours)
    except DomainError as exc:
        raise HTTPException(exc.status_code, {"code": exc.code, "message": exc.detail}) from exc
    return HoldRead.model_validate(hold)


@router.delete("/api/items/{item_id}/hold", response_model=HoldRead)
def delete_hold(item_id: int, db: Session = Depends(get_db)) -> HoldRead:
    try:
        hold = release_hold(db, item_id=item_id)
    except DomainError as exc:
        raise HTTPException(exc.status_code, {"code": exc.code, "message": exc.detail}) from exc
    return HoldRead.model_validate(hold)


@router.get("/api/customers", response_model=list[CustomerRead])
def get_customers(db: Session = Depends(get_db)) -> list[CustomerRead]:
    return list(db.scalars(select(Customer).order_by(Customer.created_at.desc() if hasattr(Customer, "created_at") else Customer.id.desc())))


@router.post("/api/customers", response_model=CustomerRead)
def post_customers(payload: CustomerCreate, db: Session = Depends(get_db)) -> CustomerRead:
    customer = Customer(**payload.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return CustomerRead.model_validate(customer)


@router.get("/api/customers/{customer_id}/measurement-profiles", response_model=list[MeasurementProfileRead])
def get_customer_measurement_profiles(customer_id: int, db: Session = Depends(get_db)) -> list[MeasurementProfileRead]:
    customer = db.scalar(select(Customer).where(Customer.id == customer_id))
    if not customer:
        raise HTTPException(404, "Customer not found")
    profiles = list(
        db.scalars(
            select(MeasurementProfile)
            .where(MeasurementProfile.customer_id == customer_id)
            .order_by(MeasurementProfile.updated_at.desc())
        )
    )
    return [_profile_read(db, profile) for profile in profiles]


@router.post("/api/customers/{customer_id}/measurement-profiles", response_model=MeasurementProfileDetailRead)
def post_customer_measurement_profiles(
    customer_id: int,
    payload: MeasurementProfileCreate,
    db: Session = Depends(get_db),
) -> MeasurementProfileDetailRead:
    customer = db.scalar(select(Customer).where(Customer.id == customer_id))
    if not customer:
        raise HTTPException(404, "Customer not found")

    measurements = _validate_measurements(payload.measurements)
    profile = MeasurementProfile(
        customer_id=customer_id,
        name=payload.name,
        garment_type=payload.garment_type,
        unit=payload.unit,
        is_active=payload.is_active,
    )
    db.add(profile)
    db.flush()

    version = MeasurementVersion(
        measurement_profile_id=profile.id,
        version_number=1,
        measurements=measurements,
        notes=payload.notes,
        created_by=payload.created_by,
    )
    db.add(version)
    db.commit()
    db.refresh(profile)
    logger.info(
        "measurement.version.created",
        extra={
            "merchant_id": customer.merchant_id,
            "customer_id": customer.id,
            "measurement_profile_id": profile.id,
            "version_number": 1,
        },
    )

    return MeasurementProfileDetailRead(
        **_profile_read(db, profile).model_dump(),
        versions=[MeasurementVersionRead.model_validate(v) for v in db.scalars(select(MeasurementVersion).where(MeasurementVersion.measurement_profile_id == profile.id).order_by(MeasurementVersion.version_number.desc())).all()],
    )


@router.get("/api/measurement-profiles/{profile_id}", response_model=MeasurementProfileDetailRead)
def get_measurement_profile(profile_id: int, db: Session = Depends(get_db)) -> MeasurementProfileDetailRead:
    profile = db.scalar(select(MeasurementProfile).where(MeasurementProfile.id == profile_id))
    if not profile:
        raise HTTPException(404, "Measurement profile not found")
    versions = list(
        db.scalars(
            select(MeasurementVersion)
            .where(MeasurementVersion.measurement_profile_id == profile_id)
            .order_by(MeasurementVersion.version_number.desc())
        )
    )
    return MeasurementProfileDetailRead(
        **_profile_read(db, profile).model_dump(),
        versions=[MeasurementVersionRead.model_validate(v) for v in versions],
    )


@router.post("/api/measurement-profiles/{profile_id}/versions", response_model=MeasurementVersionRead)
def post_measurement_profile_version(
    profile_id: int,
    payload: MeasurementVersionCreate,
    db: Session = Depends(get_db),
) -> MeasurementVersionRead:
    profile = db.scalar(select(MeasurementProfile).where(MeasurementProfile.id == profile_id))
    if not profile:
        raise HTTPException(404, "Measurement profile not found")

    measurements = _validate_measurements(payload.measurements)
    latest = _latest_version(db, profile_id)
    next_version = 1 if not latest else latest.version_number + 1

    version = MeasurementVersion(
        measurement_profile_id=profile_id,
        version_number=next_version,
        measurements=measurements,
        notes=payload.notes,
        created_by=payload.created_by,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    logger.info(
        "measurement.version.created",
        extra={
            "merchant_id": profile.customer_id,
            "customer_id": profile.customer_id,
            "measurement_profile_id": profile.id,
            "measurement_version_id": version.id,
            "version_number": version.version_number,
        },
    )
    return MeasurementVersionRead.model_validate(version)


@router.get("/api/measurement-profiles/{profile_id}/versions", response_model=list[MeasurementVersionRead])
def get_measurement_profile_versions(profile_id: int, db: Session = Depends(get_db)) -> list[MeasurementVersionRead]:
    profile = db.scalar(select(MeasurementProfile).where(MeasurementProfile.id == profile_id))
    if not profile:
        raise HTTPException(404, "Measurement profile not found")
    versions = list(
        db.scalars(
            select(MeasurementVersion)
            .where(MeasurementVersion.measurement_profile_id == profile_id)
            .order_by(MeasurementVersion.version_number.desc())
        )
    )
    return [MeasurementVersionRead.model_validate(v) for v in versions]


@router.get("/api/measurement-profiles/{profile_id}/versions/{version_id}", response_model=MeasurementVersionRead)
def get_measurement_profile_version(profile_id: int, version_id: int, db: Session = Depends(get_db)) -> MeasurementVersionRead:
    version = db.scalar(
        select(MeasurementVersion).where(
            MeasurementVersion.id == version_id,
            MeasurementVersion.measurement_profile_id == profile_id,
        )
    )
    if not version:
        raise HTTPException(404, "Measurement version not found")
    return MeasurementVersionRead.model_validate(version)


@router.get("/api/orders", response_model=list[OrderRead])
def get_orders(db: Session = Depends(get_db)) -> list[OrderRead]:
    return [_order_view(db, o) for o in order_list(db)]


@router.post("/api/orders", response_model=OrderDetailRead)
def post_orders(payload: OrderCreate, db: Session = Depends(get_db)) -> OrderDetailRead:
    try:
        result = create_order(db, payload)
    except DomainError as exc:
        raise HTTPException(exc.status_code, {"code": exc.code, "message": exc.detail}) from exc
    inventory_state = [
        InventoryStateRead(
            item_id=snapshot.item_id,
            item_name=snapshot.item_name,
            inventory_type=snapshot.inventory_type,
            status=snapshot.status,
            quantity_available=snapshot.quantity_available,
        )
        for snapshot in result.inventory_state
    ]
    return _order_view(db, result.order, inventory_state)


@router.get("/api/orders/{order_id}", response_model=OrderDetailRead)
def get_order(order_id: int, db: Session = Depends(get_db)) -> OrderDetailRead:
    order = order_get(db, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    return _order_view(db, order)


@router.patch("/api/orders/{order_id}/status", response_model=OrderRead)
def patch_order_status(order_id: int, payload: OrderStatusPatch, db: Session = Depends(get_db)) -> OrderRead:
    order = db.scalar(select(Order).where(Order.id == order_id))
    if not order:
        raise HTTPException(404, "Order not found")
    order.status = payload.status
    db.commit()
    db.refresh(order)
    return _order_view(db, order_get(db, order.id))


@router.patch("/api/order-lines/{line_id}/tailoring-stage")
def patch_tailoring_stage(line_id: int, payload: TailoringStagePatch, db: Session = Depends(get_db)) -> dict[str, str]:
    line = db.scalar(select(OrderLine).where(OrderLine.id == line_id))
    if not line:
        raise HTTPException(404, "Order line not found")
    if not line.requires_tailoring:
        raise HTTPException(409, "Tailoring stage can only be set for tailoring lines")
    line.tailoring_stage = payload.tailoring_stage
    task = db.scalar(select(TailoringTask).where(TailoringTask.order_line_id == line.id))
    if task:
        task.stage = payload.tailoring_stage
    db.commit()
    return {"status": "updated"}


@router.get("/api/tailoring/tasks", response_model=list[TailoringTaskRead])
def get_tailoring_tasks(
    stage: TailoringStage | None = None,
    assignee: str | None = None,
    due: str | None = None,
    db: Session = Depends(get_db),
) -> list[TailoringTaskRead]:
    query = select(TailoringTask).order_by(TailoringTask.updated_at.desc())
    if stage is not None:
        query = query.where(TailoringTask.stage == stage)
    if assignee is not None:
        query = query.where(TailoringTask.assignee == assignee)

    now = _now()
    start_today = datetime(now.year, now.month, now.day, tzinfo=UTC)
    end_today = start_today + timedelta(days=1)

    if due == "overdue":
        query = query.where(TailoringTask.due_at.is_not(None), TailoringTask.due_at < now, TailoringTask.stage != TailoringStage.READY)
    elif due == "today":
        query = query.where(TailoringTask.due_at.is_not(None), TailoringTask.due_at >= start_today, TailoringTask.due_at < end_today)
    elif due == "upcoming":
        query = query.where(TailoringTask.due_at.is_not(None), TailoringTask.due_at >= end_today)

    tasks = list(db.scalars(query))
    return [_task_read(db, task) for task in tasks]


@router.get("/api/tailoring/tasks/{task_id}", response_model=TailoringTaskRead)
def get_tailoring_task(task_id: int, db: Session = Depends(get_db)) -> TailoringTaskRead:
    task = db.scalar(select(TailoringTask).where(TailoringTask.id == task_id))
    if not task:
        raise HTTPException(404, "Tailoring task not found")
    return _task_read(db, task)


@router.patch("/api/tailoring/tasks/{task_id}", response_model=TailoringTaskRead)
def patch_tailoring_task(task_id: int, payload: TailoringTaskPatch, db: Session = Depends(get_db)) -> TailoringTaskRead:
    task = db.scalar(select(TailoringTask).where(TailoringTask.id == task_id))
    if not task:
        raise HTTPException(404, "Tailoring task not found")

    if payload.stage is not None:
        task.stage = payload.stage
        line = db.scalar(select(OrderLine).where(OrderLine.id == task.order_line_id))
        if line:
            line.tailoring_stage = payload.stage
    if payload.assignee is not None:
        task.assignee = payload.assignee
    if payload.priority is not None:
        task.priority = payload.priority
    if payload.notes is not None:
        task.notes = payload.notes
    if "due_at" in payload.model_fields_set:
        task.due_at = payload.due_at

    db.commit()
    db.refresh(task)
    logger.info(
        "tailoring.task.updated",
        extra={
            "task_id": task.id,
            "order_line_id": task.order_line_id,
            "stage": task.stage.value,
            "assignee": task.assignee or "",
        },
    )
    return _task_read(db, task)


@router.get("/api/tailoring-lines")
def get_tailoring_lines(db: Session = Depends(get_db)) -> list[dict]:
    tasks = list(db.scalars(select(TailoringTask).order_by(TailoringTask.updated_at.desc())))
    result: list[dict] = []
    for task in tasks:
        task_data = _task_read(db, task)
        result.append(
            {
                "id": task_data.order_line_id,
                "order_id": task_data.order_id,
                "item_name": task_data.item_name,
                "customer_name": task_data.customer_name,
                "tailoring_stage": task_data.stage,
            }
        )
    return result
