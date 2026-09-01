from decimal import Decimal
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ChannelConnection,
    ChannelConnectionStatus,
    CommerceChannelType,
    Customer,
    InventoryLot,
    InventoryStatus,
    InventoryType,
    Item,
    MeasurementProfile,
    MeasurementUnit,
    MeasurementVersion,
    Merchant,
    Order,
    OrderLine,
    OrderStatus,
    TailoringPriority,
    TailoringStage,
    TailoringTask,
)


def seed_data(db: Session) -> None:
    merchant = db.scalar(select(Merchant).where(Merchant.name == "Meera Boutique"))
    if not merchant:
        merchant = Merchant(name="Meera Boutique")
        db.add(merchant)
        db.flush()

    boutique_channel = db.scalar(
        select(ChannelConnection).where(
            ChannelConnection.merchant_id == merchant.id,
            ChannelConnection.channel_type == CommerceChannelType.BOUTIQUEOS,
        )
    )
    if not boutique_channel:
        db.add(
            ChannelConnection(
                merchant_id=merchant.id,
                channel_type=CommerceChannelType.BOUTIQUEOS,
                status=ChannelConnectionStatus.CONNECTED,
                configuration_reference="core-local",
            )
        )

    customer_seed = [
        ("Anjali Rao", "+91-9000000001"),
        ("Priya Sharma", "+91-9000000002"),
        ("Neha Reddy", "+91-9000000003"),
    ]
    customer_map: dict[str, Customer] = {}
    for name, phone in customer_seed:
        existing = db.scalar(
            select(Customer).where(Customer.merchant_id == merchant.id, Customer.name == name)
        )
        if not existing:
            existing = Customer(merchant_id=merchant.id, name=name, phone=phone)
            db.add(existing)
            db.flush()
        customer_map[name] = existing

    item_seed = [
        ("Hand Embroidered Bridal Lehenga", InventoryType.UNIQUE, "Lehenga", Decimal("48000.00"), Decimal("1")),
        ("Chanderi Fabric Roll", InventoryType.YARDAGE, "Fabric", Decimal("1850.00"), Decimal("22.500")),
        ("Cotton Kurta - Blue", InventoryType.STOCKED, "Kurta", Decimal("2499.00"), Decimal("8.000")),
        ("Kanjeevaram Saree", InventoryType.UNIQUE, "Saree", Decimal("18500.00"), Decimal("1")),
        ("Designer Blouse", InventoryType.STOCKED, "Blouse", Decimal("4500.00"), Decimal("5.000")),
    ]

    item_map: dict[str, Item] = {}
    for name, inv_type, category, price, qty in item_seed:
        item = db.scalar(select(Item).where(Item.merchant_id == merchant.id, Item.name == name))
        if not item:
            item = Item(
                merchant_id=merchant.id,
                name=name,
                inventory_type=inv_type,
                category=category,
                selling_price=price,
                published=True,
            )
            db.add(item)
            db.flush()

        lot = db.scalar(select(InventoryLot).where(InventoryLot.item_id == item.id))
        if not lot:
            db.add(
                InventoryLot(
                    item_id=item.id,
                    lot_code=f"LOT-{item.id}-1",
                    quantity=qty,
                    original_quantity=qty,
                    received_at=datetime.now(UTC),
                    cost_price=item.cost_price,
                    status=InventoryStatus.AVAILABLE,
                )
            )
        item_map[name] = item

    anjali = customer_map["Anjali Rao"]
    profile = db.scalar(
        select(MeasurementProfile).where(
            MeasurementProfile.customer_id == anjali.id,
            MeasurementProfile.name == "Self",
            MeasurementProfile.garment_type == "BLOUSE",
        )
    )
    if not profile:
        profile = MeasurementProfile(
            customer_id=anjali.id,
            name="Self",
            garment_type="BLOUSE",
            unit=MeasurementUnit.INCH,
            is_active=True,
        )
        db.add(profile)
        db.flush()

    version1 = db.scalar(
        select(MeasurementVersion).where(
            MeasurementVersion.measurement_profile_id == profile.id,
            MeasurementVersion.version_number == 1,
        )
    )
    if not version1:
        version1 = MeasurementVersion(
            measurement_profile_id=profile.id,
            version_number=1,
            measurements={
                "bust": 36,
                "waist": 30,
                "shoulder": 14,
                "blouse_length": 14.5,
                "sleeve_length": 10,
                "armhole": 16,
                "front_neck_depth": 7,
                "back_neck_depth": 9,
            },
            created_by="seed",
        )
        db.add(version1)
        db.flush()

    now = datetime.now(UTC)
    seeded_order = db.scalar(select(Order).where(Order.merchant_id == merchant.id, Order.status == OrderStatus.CONFIRMED))
    if not seeded_order:
        seeded_order = Order(merchant_id=merchant.id, customer_id=anjali.id, status=OrderStatus.CONFIRMED, total_amount=Decimal("9000.00"))
        db.add(seeded_order)
        db.flush()

    blouse_line = db.scalar(
        select(OrderLine).where(OrderLine.order_id == seeded_order.id, OrderLine.item_id == item_map["Designer Blouse"].id)
    )
    if not blouse_line:
        blouse_line = OrderLine(
            order_id=seeded_order.id,
            item_id=item_map["Designer Blouse"].id,
            inventory_lot_id=db.scalar(select(InventoryLot.id).where(InventoryLot.item_id == item_map["Designer Blouse"].id)),
            measurement_profile_id=profile.id,
            measurement_version_id=version1.id,
            quantity=Decimal("1"),
            unit_price=Decimal("4500.00"),
            requires_tailoring=True,
            tailoring_stage=TailoringStage.CUTTING,
        )
        db.add(blouse_line)
        db.flush()

    kurta_line = db.scalar(
        select(OrderLine).where(OrderLine.order_id == seeded_order.id, OrderLine.item_id == item_map["Cotton Kurta - Blue"].id)
    )
    if not kurta_line:
        kurta_line = OrderLine(
            order_id=seeded_order.id,
            item_id=item_map["Cotton Kurta - Blue"].id,
            inventory_lot_id=db.scalar(select(InventoryLot.id).where(InventoryLot.item_id == item_map["Cotton Kurta - Blue"].id)),
            quantity=Decimal("1"),
            unit_price=Decimal("2499.00"),
            requires_tailoring=True,
            tailoring_stage=TailoringStage.STITCHING,
        )
        db.add(kurta_line)
        db.flush()

    overdue_task = db.scalar(select(TailoringTask).where(TailoringTask.order_line_id == blouse_line.id))
    if not overdue_task:
        db.add(
            TailoringTask(
                order_line_id=blouse_line.id,
                stage=TailoringStage.CUTTING,
                assignee="Ritu",
                due_at=now - timedelta(days=1),
                priority=TailoringPriority.URGENT,
                notes="Urgent trial prep",
            )
        )

    today_task = db.scalar(select(TailoringTask).where(TailoringTask.order_line_id == kurta_line.id))
    if not today_task:
        db.add(
            TailoringTask(
                order_line_id=kurta_line.id,
                stage=TailoringStage.STITCHING,
                assignee="Mina",
                due_at=now,
                priority=TailoringPriority.NORMAL,
            )
        )

    db.commit()
