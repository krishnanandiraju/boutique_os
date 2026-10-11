"""Attach bundled photography to the existing built-in inventory and CRM records."""
from pathlib import Path
import shutil
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.customer_fixtures import FIXTURES
from app.models import Customer, CustomerPhoto, Item, MediaAsset, MediaType

ASSET_ROOT = Path(__file__).parent / 'data' / 'photography'
PRODUCTS = {'Cotton Kurta - Blue': 'kurta', 'Designer Blouse': 'blouse', 'Hand Embroidered Bridal Lehenga': 'lehenga', 'Kanjeevaram Saree': 'saree', 'Chanderi Fabric Roll': 'fabric'}


def ensure_file(filename: str, key: str) -> Path:
    destination = Path(settings.media_storage_path) / key
    if not destination.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ASSET_ROOT / filename, destination)
    return destination


def seed_photography(db: Session, merchant_id: int) -> None:
    for name, product_key in PRODUCTS.items():
        item = db.scalar(select(Item).where(Item.merchant_id == merchant_id, Item.name == name))
        if not item:
            continue
        media = list(db.scalars(select(MediaAsset).where(MediaAsset.item_id == item.id)))
        expected = [f'{product_key}-{view}.png' for view in ('front', 'alternate', 'detail')]
        if product_key == 'kurta':
            expected[0] = 'kurta-front-clean.png'
        allowed = set(expected) | ({'kurta-front.png'} if product_key == 'kurta' else set())
        if any(asset.original_filename not in allowed for asset in media):
            continue
        # Upgrade only the bundled front photograph; preserve uploaded owner photos.
        legacy = next((asset for asset in media if asset.original_filename == 'kurta-front.png'
                       and asset.storage_key == f'{merchant_id}/products/{item.id}/kurta-front.png'), None)
        if product_key == 'kurta' and legacy:
            filename = 'kurta-front-clean.png'
            key = f'{merchant_id}/products/{item.id}/{filename}'
            path = ensure_file(filename, key)
            with Image.open(path) as image:
                legacy.width, legacy.height = image.size
            legacy.storage_key = key
            legacy.original_filename = filename
            legacy.file_size_bytes = path.stat().st_size
        has_primary = any(asset.is_primary for asset in media)
        for index, filename in enumerate(expected):
            existing = next((asset for asset in media if asset.original_filename == filename), None)
            key = existing.storage_key if existing else f'{merchant_id}/products/{item.id}/{filename}'
            path = ensure_file(filename, key)
            if existing:
                continue
            with Image.open(path) as image:
                width, height = image.size
            db.add(MediaAsset(merchant_id=merchant_id, item_id=item.id, media_type=MediaType.IMAGE, storage_key=key, original_filename=filename, mime_type='image/png', file_size_bytes=path.stat().st_size, width=width, height=height, sort_order=index, is_primary=not has_primary))
            has_primary = True
    for index, fixture in enumerate(FIXTURES['customers'], 1):
        customer = db.scalar(select(Customer).where(Customer.merchant_id == merchant_id, Customer.name == fixture['name'], Customer.phone == fixture['phone']))
        if not customer:
            continue
        existing = db.scalar(select(CustomerPhoto).where(CustomerPhoto.customer_id == customer.id))
        filename = f'person-{index:02d}-v2.png'
        if existing and existing.created_by != 'seed:customer-fixture:v2':
            continue
        key = f'{merchant_id}/customers/{customer.id}/{filename}'
        ensure_file(filename, key)
        if not existing:
            db.add(CustomerPhoto(customer_id=customer.id, storage_key=key, mime_type='image/png', created_by='seed:customer-fixture:v2'))
        else:
            existing.storage_key = key
