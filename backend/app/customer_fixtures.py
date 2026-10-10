"""Populate only the exact built-in customer identities; preserve user measurements."""
import json
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Customer, MeasurementProfile, MeasurementUnit, MeasurementVersion

FIXTURES = json.loads((Path(__file__).parent / 'data' / 'customer_fixtures.json').read_text())
ORIGIN = 'seed:customer-fixture:v2'
LEGACY_ORIGIN = 'demo-photo-fixture-unverified'
LEGACY_NAME = 'DEMO ONLY — unverified photo fixture'


def seed_customer_profiles(db: Session, merchant_id: int) -> None:
    for fixture in FIXTURES['customers']:
        customer = db.scalar(select(Customer).where(Customer.merchant_id == merchant_id, Customer.name == fixture['name'], Customer.phone == fixture['phone']))
        if not customer:
            continue
        profiles = list(db.scalars(select(MeasurementProfile).where(MeasurementProfile.customer_id == customer.id)))
        # Update presentation of our prior fixture, retaining version IDs and values.
        legacy = next((p for p in profiles if p.name == LEGACY_NAME and p.versions and all(v.created_by == LEGACY_ORIGIN for v in p.versions)), None)
        if legacy and not any(p.name == 'Blouse' for p in profiles):
            legacy.name = 'Blouse'
            for version in legacy.versions:
                version.notes = None
        for spec in fixture['profiles']:
            if any(p.name == spec['name'] and p.garment_type == spec['garment_type'] for p in profiles):
                continue
            profile = MeasurementProfile(customer_id=customer.id, name=spec['name'], garment_type=spec['garment_type'], unit=MeasurementUnit.INCH, is_active=True)
            db.add(profile)
            db.flush()
            db.add(MeasurementVersion(measurement_profile_id=profile.id, version_number=1, measurements=spec['measurements'], created_by=ORIGIN))
            profiles.append(profile)
