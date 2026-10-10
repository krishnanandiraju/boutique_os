import base64
import io
import json
from unittest.mock import Mock

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from app import fashn_tryon, tryon
from app.main import app


def image():
    out = io.BytesIO()
    Image.new("RGB", (128, 192), "blue").save(out, "WEBP")
    return out.getvalue()


def provider(monkeypatch, event="complete", output_url=None, upload_status=200):
    calls = []
    url = output_url or fashn_tryon.SPACE + "/gradio_api/file=/tmp/result.webp"
    def handler(request):
        calls.append(request)
        path = request.url.path
        if path.endswith("/upload"):
            return httpx.Response(upload_status, json=["/tmp/person.jpg", "/tmp/garment.jpg"])
        if path.endswith("/try_on"):
            return httpx.Response(200, json={"event_id": "abc123"})
        if path.endswith("/abc123"):
            value = [{"url": url}] if event == "complete" else "Private upstream diagnostics"
            return httpx.Response(200, text="event: heartbeat\ndata: null\n\nevent: " + event + "\ndata: " + json.dumps(value) + "\n\n")
        return httpx.Response(200, content=image())
    original = httpx.Client
    monkeypatch.setattr(fashn_tryon.httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    return calls


def test_free_api_upload_queue_download_contract(monkeypatch):
    calls = provider(monkeypatch)
    result = fashn_tryon.generate_fashn_preview(b"person", b"garment", "one-pieces", "flat-lay")
    assert result["model"] == "fashn-vton-1.5"
    assert base64.b64decode(result["image"].split(",")[1]).startswith(b"\x89PNG")
    assert b'filename="person.jpg"' in calls[0].content
    assert json.loads(calls[1].content)["data"][2:] == ["one-pieces", "flat-lay", 30, 1.5, 42, True]
    assert len(calls) == 4
    assert all(request.url.host == "fashn-ai-fashn-vton-1-5.hf.space" for request in calls)


@pytest.mark.parametrize("kwargs", [{"event": "error"}, {"upload_status": 429},
                                    {"output_url": "https://example.com/private"}])
def test_free_service_errors_and_untrusted_output_do_not_fall_back(monkeypatch, kwargs):
    calls = provider(monkeypatch, **kwargs)
    with pytest.raises(HTTPException) as error:
        fashn_tryon.generate_fashn_preview(b"person", b"garment")
    assert "Private upstream" not in error.value.detail
    assert all(request.url.host == "fashn-ai-fashn-vton-1-5.hf.space" for request in calls)
    assert fashn_tryon._slot.acquire(blocking=False)  # Failure releases the slot.
    fashn_tryon._slot.release()


def test_free_provider_route_still_requires_permission(monkeypatch):
    monkeypatch.setattr(tryon.settings, "tryon_provider", "huggingface")
    monkeypatch.setattr(tryon.settings, "tryon_enabled", True)
    monkeypatch.setattr(tryon.settings, "google_cloud_project", "")
    preview = Mock(return_value={"image": "data:image/png;base64,abc", "model": "fashn-vton-1.5"})
    google = Mock()
    monkeypatch.setattr(tryon, "generate_fashn_preview", preview)
    monkeypatch.setattr(tryon, "generate_preview", google)
    png = io.BytesIO()
    Image.new("RGB", (128, 192), "blue").save(png, "PNG")
    with TestClient(app) as client:
        assert client.get("/api/try-on/status").json()["configured"] is True
        customer = client.get("/api/customers").json()[0]
        item = next(i for i in client.get("/api/items").json() if i["inventory_type"] != "YARDAGE")
        data = {"customer_id": customer["id"], "item_id": item["id"], "consent": "false", "category": "tops", "photo_type": "model"}
        files = {name: (name + ".png", png.getvalue(), "image/png") for name in ["person", "garment"]}
        assert client.post("/api/try-on/generate", data=data, files=files).status_code == 422
        preview.assert_not_called()
        data["consent"] = "true"
        assert client.post("/api/try-on/generate", data=data, files=files).status_code == 200
        assert preview.call_args.args[2:] == ("tops", "model")
        assert preview.call_args.args[0].startswith(b"\xff\xd8")
        google.assert_not_called()
