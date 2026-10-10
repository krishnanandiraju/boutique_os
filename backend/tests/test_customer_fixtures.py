from sqlalchemy import select
from app.customer_fixtures import FIXTURES, LEGACY_NAME, LEGACY_ORIGIN, ORIGIN, seed_customer_profiles
from app.db import Base, SessionLocal, engine
from app.models import Customer, MeasurementProfile, MeasurementUnit, MeasurementVersion
from app.seed import seed_data


def reset():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_data(db)
    return db


def test_all_three_customers_have_both_profiles_and_second_seed_is_idempotent():
    with reset() as db:
        for fixture in FIXTURES['customers']:
            customer = db.scalar(select(Customer).where(Customer.name == fixture['name']))
            profiles = list(db.scalars(select(MeasurementProfile).where(MeasurementProfile.customer_id == customer.id)))
            for spec in fixture['profiles']:
                profile = next(p for p in profiles if p.name == spec['name'])
                assert profile.unit == MeasurementUnit.INCH
                assert profile.versions[0].measurements == spec['measurements']
                assert profile.versions[0].created_by == ORIGIN
            kurta = fixture['profiles'][1]['measurements']
            assert kurta['hip'] > kurta['waist'] and kurta['bust'] > kurta['waist']
        before = list(db.scalars(select(MeasurementVersion.id)))
        seed_data(db)
        assert list(db.scalars(select(MeasurementVersion.id))) == before


def test_legacy_fixture_is_renamed_without_replacing_values_or_version_ids():
    with reset() as db:
        profile = db.scalar(select(MeasurementProfile).where(MeasurementProfile.name == 'Blouse'))
        profile.name = LEGACY_NAME
        version = profile.versions[0]
        version.created_by = LEGACY_ORIGIN
        version.notes = 'Old fixture disclaimer'
        version.measurements = {'bust': 37, 'waist': 31}
        version_id = version.id
        db.commit()
        seed_customer_profiles(db, profile.customer.merchant_id)
        db.commit()
        assert profile.name == 'Blouse'
        assert version.id == version_id and version.measurements['bust'] == 37
        assert version.notes is None and version.created_by == LEGACY_ORIGIN


def test_does_not_rename_user_profile_or_seed_customer_with_real_phone():
    with reset() as db:
        profile = db.scalar(select(MeasurementProfile).where(MeasurementProfile.name == 'Blouse'))
        profile.name = LEGACY_NAME
        profile.versions[0].created_by = 'tailor'
        profile.versions[0].notes = 'Real tailoring note'
        db.add(Customer(merchant_id=profile.customer.merchant_id, name='Anjali Rao', phone='actual-phone'))
        db.commit()
        seed_customer_profiles(db, profile.customer.merchant_id)
        db.commit()
        assert profile.name == LEGACY_NAME
        assert profile.versions[0].notes == 'Real tailoring note'
        real = db.scalar(select(Customer).where(Customer.phone == 'actual-phone'))
        assert not list(db.scalars(select(MeasurementProfile).where(MeasurementProfile.customer_id == real.id)))


def test_customer_photos_are_saved_in_crm_and_product_galleries_exist():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.models import CustomerPhoto, MediaAsset
    from app.seed_photography import PRODUCTS
    with reset() as db:
        assert len(list(db.scalars(select(CustomerPhoto)))) == 3
        before = list(db.scalars(select(MediaAsset.id)))
        seed_data(db)
        assert list(db.scalars(select(MediaAsset.id))) == before
    with TestClient(app) as client:
        customers = client.get('/api/customers').json()
        for customer in customers:
            assert '/customers/' in customer['photo_url']
            assert client.get(customer['photo_url']).status_code == 200
            profiles = client.get(f"/api/customers/{customer['id']}/measurement-profiles").json()
            assert {'Blouse', 'Kurta'} <= {p['name'] for p in profiles}
        products = client.get('/api/catalog/products').json()
        for product in products:
            if product['name'] in PRODUCTS:
                assert product['media_count'] == 3 and product['primary_media_url']
                assert client.get(product['primary_media_url']).status_code == 200


def test_existing_product_photos_are_preserved():
    from app.models import Item, MediaAsset, MediaType
    from app.seed_photography import seed_photography
    with reset() as db:
        item = db.scalar(select(Item).where(Item.name == 'Cotton Kurta - Blue'))
        for media in list(db.scalars(select(MediaAsset).where(MediaAsset.item_id == item.id))):
            db.delete(media)
        db.add(MediaAsset(merchant_id=item.merchant_id, item_id=item.id, media_type=MediaType.IMAGE, storage_key='existing/photo.png', original_filename='shop-owner-photo.png', mime_type='image/png', is_primary=True))
        db.commit()
        seed_photography(db, item.merchant_id)
        db.commit()
        rows = list(db.scalars(select(MediaAsset).where(MediaAsset.item_id == item.id)))
        assert len(rows) == 1 and rows[0].original_filename == 'shop-owner-photo.png'
