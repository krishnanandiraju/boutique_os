import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.seed import seed_data
from app.stitching.service import seed_garment_definitions


@pytest.fixture(autouse=True)
def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_data(db)
        seed_garment_definitions(db)
    finally:
        db.close()


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_known_garment_types_include_boutique_presets(client: TestClient) -> None:
    response = client.get('/api/stitching/garment-types')
    assert response.status_code == 200
    codes = {row['code'] for row in response.json()}
    assert {'BLOUSE', 'KURTA', 'BOTTOM', 'DRESS', 'LEHENGA_BLOUSE'} <= codes


def test_stitch_feedback_is_separate_from_measurement_history(client: TestClient) -> None:
    profile = client.post(
        '/api/customers/1/measurement-profiles',
        json={
            'name': 'Self',
            'garment_type': 'BLOUSE',
            'unit': 'INCH',
            'measurements': {'bust': 36, 'sleeve_length': 10, 'front_neck_depth': 7},
        },
    )
    assert profile.status_code == 200, profile.text
    profile_body = profile.json()
    version_id = profile_body['latest_version']['id']

    record = client.post(
        '/api/stitching/records',
        json={
            'merchant_id': 1,
            'customer_id': 1,
            'garment_type_code': 'BLOUSE',
            'measurement_profile_id': profile_body['id'],
            'measurement_version_id': version_id,
        },
    )
    assert record.status_code == 200, record.text

    feedback = client.post(
        f"/api/stitching/records/{record.json()['id']}/feedback",
        json={
            'fit_area': 'SLEEVE',
            'direction': 'TOO_LONG',
            'severity': 'MODERATE',
            'adjustment_value': '0.5',
            'adjustment_unit': 'INCH',
            'comment': 'Sleeve was longer than expected at trial.',
        },
    )
    assert feedback.status_code == 200, feedback.text

    unchanged = client.get(f"/api/measurement-profiles/{profile_body['id']}")
    assert unchanged.status_code == 200
    assert unchanged.json()['latest_version']['id'] == version_id
    assert unchanged.json()['latest_version']['measurements']['sleeve_length'] == 10.0


def test_neck_too_deep_feedback_is_supported_for_blouse(client: TestClient) -> None:
    record = client.post('/api/stitching/records', json={'merchant_id': 1, 'customer_id': 1, 'garment_type_code': 'BLOUSE'})
    assert record.status_code == 200
    response = client.post(
        f"/api/stitching/records/{record.json()['id']}/feedback",
        json={'fit_area': 'NECKLINE', 'direction': 'TOO_DEEP', 'severity': 'MAJOR', 'comment': 'Front neck was too deep.'},
    )
    assert response.status_code == 200, response.text
    assert response.json()['fit_area'] == 'NECKLINE'
    assert response.json()['direction'] == 'TOO_DEEP'


def test_feedback_fit_area_must_match_garment_definition(client: TestClient) -> None:
    record = client.post('/api/stitching/records', json={'merchant_id': 1, 'customer_id': 1, 'garment_type_code': 'BOTTOM'})
    response = client.post(
        f"/api/stitching/records/{record.json()['id']}/feedback",
        json={'fit_area': 'NECKLINE', 'direction': 'TOO_DEEP', 'severity': 'MINOR'},
    )
    assert response.status_code == 400
    assert response.json()['error']['code'] == 'INVALID_FIT_AREA'


def test_recurring_fit_feedback_becomes_customer_fit_memory(client: TestClient) -> None:
    for _ in range(2):
        record = client.post('/api/stitching/records', json={'merchant_id': 1, 'customer_id': 1, 'garment_type_code': 'BLOUSE'})
        assert record.status_code == 200
        feedback = client.post(
            f"/api/stitching/records/{record.json()['id']}/feedback",
            json={'fit_area': 'SLEEVE', 'direction': 'TOO_LONG', 'severity': 'MINOR'},
        )
        assert feedback.status_code == 200

    insight = client.get('/api/stitching/customers/1/fit-insights/BLOUSE')
    assert insight.status_code == 200
    assert 'SLEEVE:TOO_LONG' in insight.json()['recurring_feedback']
    assert insight.json()['unresolved_feedback_count'] == 2


def test_measurement_profile_cannot_be_reused_for_another_customer(client: TestClient) -> None:
    profile = client.post(
        '/api/customers/1/measurement-profiles',
        json={'name': 'Self', 'garment_type': 'BLOUSE', 'unit': 'INCH', 'measurements': {'bust': 36}},
    )
    assert profile.status_code == 200
    response = client.post(
        '/api/stitching/records',
        json={
            'merchant_id': 1,
            'customer_id': 2,
            'garment_type_code': 'BLOUSE',
            'measurement_profile_id': profile.json()['id'],
            'measurement_version_id': profile.json()['latest_version']['id'],
        },
    )
    assert response.status_code == 409
    assert response.json()['error']['code'] == 'MEASUREMENT_PROFILE_MISMATCH'
