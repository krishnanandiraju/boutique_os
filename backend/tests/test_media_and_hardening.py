from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.core.config import get_settings
from app.db import Base, SessionLocal, engine
from app.main import app
from app.seed import seed_data
from app.services.media_service import LocalMediaStorage


def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()


def _create_item(client: TestClient, name: str, inventory_type: str, price: str, quantity: str) -> int:
    response = client.post(
        "/api/items",
        json={
            "name": name,
            "inventory_type": inventory_type,
            "category": "Test",
            "fabric": "Silk",
            "color": "Red",
            "selling_price": price,
            "quantity": quantity,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def media_storage(tmp_path, monkeypatch) -> LocalMediaStorage:
    storage = LocalMediaStorage(tmp_path)
    monkeypatch.setattr(routes, "media_storage", storage)
    return storage


def test_settings_load_decimal_and_media_paths() -> None:
    settings = get_settings()
    assert str(settings.remnant_threshold_m) == "0.5"
    assert settings.media_storage_path.endswith("data/media") or "media" in settings.media_storage_path
    assert settings.media_max_image_mb == 10
    assert settings.media_max_video_mb == 100


def test_request_id_is_returned_and_preserved() -> None:
    _reset_db()
    client = TestClient(app)
    response = client.get("/health", headers={"X-Request-ID": "req-123"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-123"

    generated = client.get("/health")
    assert generated.status_code == 200
    assert generated.headers["X-Request-ID"]


def test_standardized_error_contract_includes_request_id() -> None:
    _reset_db()
    client = TestClient(app)
    response = client.get("/api/items/999999")
    assert response.status_code == 404
    payload = response.json()
    assert "error" in payload
    assert payload["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert payload["request_id"]


@pytest.mark.parametrize(
    ("filename", "content_type", "expected_type"),
    [
        ("sample.jpg", "image/jpeg", "IMAGE"),
        ("sample.png", "image/png", "IMAGE"),
        ("sample.webp", "image/webp", "IMAGE"),
        ("sample.mp4", "video/mp4", "VIDEO"),
    ],
)
def test_supported_media_uploads_succeed(
    client: TestClient,
    media_storage: LocalMediaStorage,
    filename: str,
    content_type: str,
    expected_type: str,
) -> None:
    response = client.post(
        "/api/media/upload",
        files={"file": (filename, BytesIO(b"binary-media"), content_type)},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["media_type"] == expected_type
    assert payload["storage_key"].startswith("merchant_1/")
    assert media_storage.resolve_path(payload["storage_key"]).exists()


def test_unsupported_mime_returns_controlled_error_and_request_id(client: TestClient) -> None:
    response = client.post(
        "/api/media/upload",
        headers={"X-Request-ID": "media-err"},
        files={"file": ("sample.txt", BytesIO(b"nope"), "text/plain")},
    )
    assert response.status_code == 415
    assert response.headers["X-Request-ID"] == "media-err"
    payload = response.json()
    assert payload["request_id"] == "media-err"
    assert payload["error"]["code"] == "HTTP_ERROR"


def test_oversized_image_rejected(client: TestClient, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "media_max_image_mb", 0)
    response = client.post(
        "/api/media/upload",
        headers={"X-Request-ID": "oversized-image"},
        files={"file": ("too-big.jpg", BytesIO(b"x"), "image/jpeg")},
    )
    assert response.status_code == 413
    assert response.headers["X-Request-ID"] == "oversized-image"
    payload = response.json()
    assert payload["request_id"] == "oversized-image"
    assert payload["error"]["code"] == "HTTP_ERROR"


def test_oversized_video_rejected(client: TestClient, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "media_max_video_mb", 0)
    response = client.post(
        "/api/media/upload",
        headers={"X-Request-ID": "oversized-video"},
        files={"file": ("too-big.mp4", BytesIO(b"x"), "video/mp4")},
    )
    assert response.status_code == 413
    assert response.headers["X-Request-ID"] == "oversized-video"
    payload = response.json()
    assert payload["request_id"] == "oversized-video"


def test_media_upload_attach_list_sort_and_primary_flow(client: TestClient, media_storage: LocalMediaStorage) -> None:
    item_id = _create_item(client, "Media Flow Item", "STOCKED", "500.00", "3")
    first = client.post(
        "/api/media/upload",
        files={"file": ("first.jpg", BytesIO(b"a"), "image/jpeg")},
    ).json()
    second = client.post(
        "/api/media/upload",
        files={"file": ("second.png", BytesIO(b"b"), "image/png")},
    ).json()

    client.post(f"/api/items/{item_id}/media/{first['id']}/attach")
    client.post(f"/api/items/{item_id}/media/{second['id']}/attach")

    patch = client.patch(f"/api/items/{item_id}/media/{first['id']}", json={"sort_order": 20})
    assert patch.status_code == 200, patch.text
    patch = client.patch(f"/api/items/{item_id}/media/{second['id']}", json={"sort_order": 10, "is_primary": True})
    assert patch.status_code == 200, patch.text

    listing = client.get(f"/api/items/{item_id}/media")
    assert listing.status_code == 200
    payload = listing.json()
    assert [entry["id"] for entry in payload] == [second["id"], first["id"]]
    assert payload[0]["is_primary"] is True
    assert payload[1]["is_primary"] is False
    assert media_storage.resolve_path(first["storage_key"]).exists()


def test_primary_media_assignment_clears_previous_primary(client: TestClient) -> None:
    item_id = _create_item(client, "Primary Switch Item", "STOCKED", "600.00", "2")
    first = client.post(
        "/api/media/upload",
        files={"file": ("first.jpg", BytesIO(b"a"), "image/jpeg")},
    ).json()
    second = client.post(
        "/api/media/upload",
        files={"file": ("second.jpg", BytesIO(b"b"), "image/jpeg")},
    ).json()
    client.post(f"/api/items/{item_id}/media/{first['id']}/attach")
    client.post(f"/api/items/{item_id}/media/{second['id']}/attach")

    response = client.patch(f"/api/items/{item_id}/media/{second['id']}", json={"is_primary": True})
    assert response.status_code == 200, response.text

    listing = client.get(f"/api/items/{item_id}/media")
    payload = listing.json()
    primary_flags = {entry["id"]: entry["is_primary"] for entry in payload}
    assert primary_flags[first["id"]] is False
    assert primary_flags[second["id"]] is True


def test_media_can_be_detached_without_destroying_file(client: TestClient, media_storage: LocalMediaStorage) -> None:
    item_id = _create_item(client, "Detach Item", "STOCKED", "700.00", "2")
    media = client.post(
        "/api/media/upload",
        files={"file": ("detach.jpg", BytesIO(b"keep-me"), "image/jpeg")},
    ).json()
    client.post(f"/api/items/{item_id}/media/{media['id']}/attach")

    detached = client.delete(f"/api/items/{item_id}/media/{media['id']}")
    assert detached.status_code == 200, detached.text
    assert detached.json()["item_id"] is None
    assert media_storage.resolve_path(media["storage_key"]).exists()


def test_item_a_media_does_not_mutate_item_b(client: TestClient) -> None:
    item_a = _create_item(client, "Item A", "STOCKED", "800.00", "2")
    item_b = _create_item(client, "Item B", "STOCKED", "900.00", "2")
    media = client.post(
        "/api/media/upload",
        files={"file": ("a.jpg", BytesIO(b"a"), "image/jpeg")},
    ).json()
    client.post(f"/api/items/{item_a}/media/{media['id']}/attach")

    item_b_media = client.get(f"/api/items/{item_b}/media")
    assert item_b_media.status_code == 200
    assert item_b_media.json() == []


def test_missing_media_returns_standardized_404(client: TestClient) -> None:
    response = client.get("/media/merchant_1/2099/01/01/missing.jpg", headers={"X-Request-ID": "missing-media"})
    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "missing-media"
    payload = response.json()
    assert payload["request_id"] == "missing-media"
    assert payload["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_media_serving_path_traversal_is_rejected(client: TestClient) -> None:
    response = client.get("/media/%2e%2e/%2e%2e/windows/system.ini")
    assert response.status_code == 400


@pytest.mark.parametrize(
    ("path", "expected_status"),
    [
        ("/api/orders", 400),
        ("/api/items/999999", 404),
        ("/api/items/1/hold", 409),
    ],
)
def test_standardized_error_contract_for_common_codes(client: TestClient, path: str, expected_status: int) -> None:
    if path == "/api/orders":
        response = client.post(path, json={"customer_id": 1, "lines": []})
    elif path == "/api/items/999999":
        response = client.get(path)
    else:
        item_id = _create_item(client, "Hold Conflict Item", "UNIQUE", "1000.00", "1")
        assert client.post(f"/api/items/{item_id}/hold", json={"customer_id": 1, "ttl_hours": 24}).status_code == 200
        response = client.post(f"/api/items/{item_id}/hold", json={"customer_id": 2, "ttl_hours": 24})

    assert response.status_code == expected_status
    payload = response.json()
    assert payload["error"]["message"]
    assert payload["request_id"]


def test_jpeg_upload_and_attach_to_item() -> None:
    _reset_db()
    client = TestClient(app)
    item_id = _create_item(client, "Media Test Item", "UNIQUE", "1200.00", "1")

    image = BytesIO(b"fakejpegcontent")
    image.name = "sample.jpg"
    response = client.post(
        "/api/media/upload",
        files={"file": (image.name, image, "image/jpeg")},
    )
    assert response.status_code == 200, response.text
    media = response.json()
    assert media["media_type"] == "IMAGE"
    media_id = media["id"]

    attach = client.post(f"/api/items/{item_id}/media/{media_id}/attach")
    assert attach.status_code == 200, attach.text
    item_media = client.get(f"/api/items/{item_id}/media")
    assert item_media.status_code == 200
    payload = item_media.json()
    assert len(payload) == 1
    assert payload[0]["id"] == media_id


def test_primary_media_assignment_and_ordering() -> None:
    _reset_db()
    client = TestClient(app)
    item_id = _create_item(client, "Media Ordering Item", "STOCKED", "500.00", "3")

    first = client.post(
        "/api/media/upload",
        files={"file": ("first.jpg", BytesIO(b"a"), "image/jpeg")},
    ).json()
    second = client.post(
        "/api/media/upload",
        files={"file": ("second.png", BytesIO(b"b"), "image/png")},
    ).json()

    client.post(f"/api/items/{item_id}/media/{first['id']}/attach")
    client.post(f"/api/items/{item_id}/media/{second['id']}/attach")
    patch = client.patch(f"/api/items/{item_id}/media/{second['id']}", json={"is_primary": True, "sort_order": 10})
    assert patch.status_code == 200, patch.text
    assert patch.json()["is_primary"] is True

    list_response = client.get(f"/api/items/{item_id}/media")
    data = list_response.json()
    assert [entry["id"] for entry in data] == [first["id"], second["id"]] or [entry["id"] for entry in data] == [second["id"], first["id"]]
    assert any(entry["is_primary"] for entry in data)


def test_malicious_filename_cannot_escape_media_directory() -> None:
    _reset_db()
    client = TestClient(app)
    response = client.post(
        "/api/media/upload",
        files={"file": ("../../escape.jpg", BytesIO(b"malicious"), "image/jpeg")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "../" not in payload["storage_key"]
    assert payload["storage_key"].startswith("merchant_1/")
