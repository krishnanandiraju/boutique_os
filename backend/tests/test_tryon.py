import base64
from io import BytesIO
from unittest.mock import Mock

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from app import tryon
from app.main import app


def photo():
    image = BytesIO()
    Image.new("RGB", (128, 192), "purple").save(image, "PNG")
    return image.getvalue()


@pytest.fixture()
def client():
    with TestClient(app) as value:
        yield value


def fields(client):
    return {"customer_id": client.get("/api/customers").json()[0]["id"],
            "item_id": next(i["id"] for i in client.get("/api/items").json() if i["inventory_type"] != "YARDAGE"),
            "consent": "true"}


def files():
    return {"person": ("person.png", photo(), "image/png"), "garment": ("garment.png", photo(), "image/png")}


def test_disabled_never_calls_google(client, monkeypatch):
    monkeypatch.setattr(tryon.settings, "tryon_enabled", False)
    google = Mock()
    monkeypatch.setattr(tryon, "generate_preview", google)
    assert client.get("/api/try-on/status").json()["configured"] is False
    assert client.post("/api/try-on/generate", data=fields(client), files=files()).status_code == 503
    google.assert_not_called()


def test_consent_and_valid_photos_required(client, monkeypatch):
    monkeypatch.setattr(tryon.settings, "tryon_enabled", True)
    monkeypatch.setattr(tryon.settings, "google_cloud_project", "test-project")
    google = Mock(return_value={"image": "data:image/png;base64," + base64.b64encode(photo()).decode(), "model": "test"})
    monkeypatch.setattr(tryon, "generate_preview", google)
    data = fields(client)
    data["consent"] = "false"
    assert client.post("/api/try-on/generate", data=data, files=files()).status_code == 422
    data["consent"] = "true"
    bad_files = files(); bad_files["person"] = ("fake.png", b"not an image", "image/png")
    assert client.post("/api/try-on/generate", data=data, files=bad_files).status_code == 422
    google.assert_not_called()
    response = client.post("/api/try-on/generate", data=data, files=files())
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["image"].startswith("data:image/png;")
    assert google.call_args.args[0].startswith(b"\xff\xd8")  # sanitized JPEG
    yardage = next(i for i in client.get("/api/items").json() if i["inventory_type"] == "YARDAGE")
    data["item_id"] = yardage["id"]
    assert client.post("/api/try-on/generate", data=data, files=files()).status_code == 422
    data = fields(client); data["variant_id"] = 999999
    assert client.post("/api/try-on/generate", data=data, files=files()).status_code == 422


def test_google_contract_and_errors(monkeypatch):
    monkeypatch.setattr(tryon.settings, "google_cloud_project", "test-project")
    monkeypatch.setattr(tryon.settings, "google_cloud_location", "us-central1")
    auth = Mock(token="test-token")
    monkeypatch.setattr(tryon, "credentials", lambda: auth)
    request = Mock(return_value=httpx.Response(200, json={"predictions": [{"mimeType": "image/png", "bytesBase64Encoded": base64.b64encode(photo()).decode()}]}))
    monkeypatch.setattr(tryon.httpx, "post", request)
    result = tryon.generate_preview(photo(), photo())
    assert result["image"].startswith("data:image/png;")
    assert request.call_args.args[0].endswith("/publishers/google/models/virtual-try-on-001:predict")
    assert request.call_args.kwargs["json"]["parameters"] == {"sampleCount": 1}
    assert request.call_args.kwargs["json"]["instances"][0]["productImages"]
    request.return_value = httpx.Response(403, json={"error": "private provider details"})
    with pytest.raises(HTTPException) as failure:
        tryon.generate_preview(photo(), photo())
    assert failure.value.status_code == 502
    assert "private provider" not in failure.value.detail
    request.return_value = httpx.Response(200, json={"predictions": []})
    with pytest.raises(HTTPException) as failure:
        tryon.generate_preview(photo(), photo())
    assert failure.value.status_code == 422
