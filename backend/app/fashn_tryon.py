"""Free FASHN Space adapter. No paid provider fallback or persisted results."""
import base64
import io
import json
import re
import threading
import time
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException
from PIL import Image

SPACE = "https://fashn-ai-fashn-vton-1-5.hf.space"
_slot = threading.BoundedSemaphore(1)


def generate_fashn_preview(person: bytes, garment: bytes, category: str = "tops",
                           photo_type: str = "flat-lay") -> dict:
    if category not in {"tops", "bottoms", "one-pieces"} or photo_type not in {"model", "flat-lay"}:
        raise HTTPException(422, "Choose a supported garment and photograph type.")
    if not _slot.acquire(blocking=False):
        raise HTTPException(429, "Another preview is being created. Please try again shortly.")
    deadline = time.monotonic() + 115
    try:
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            upload = client.post(SPACE + "/gradio_api/upload", files=[
                ("files", ("person.jpg", person, "image/jpeg")),
                ("files", ("garment.jpg", garment, "image/jpeg")),
            ])
            upload.raise_for_status()
            paths = upload.json()
            if not isinstance(paths, list) or len(paths) != 2 or not all(isinstance(p, str) for p in paths):
                raise ValueError("Invalid upload response")
            data = [{"path": p, "meta": {"_type": "gradio.FileData"}} for p in paths]
            submitted = client.post(SPACE + "/gradio_api/call/try_on", json={
                "data": [*data, category, photo_type, 30, 1.5, 42, True],
            })
            submitted.raise_for_status()
            event_id = submitted.json().get("event_id", "")
            if not isinstance(event_id, str) or not re.fullmatch(r"[a-zA-Z0-9-]{1,100}", event_id):
                raise ValueError("Invalid job identifier")
            output = None
            event = ""
            with client.stream("GET", SPACE + "/gradio_api/call/try_on/" + event_id) as stream:
                stream.raise_for_status()
                for line in stream.iter_lines():
                    if time.monotonic() > deadline:
                        raise httpx.TimeoutException("Preview deadline exceeded")
                    if line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:"):
                        if event == "error":
                            raise HTTPException(503, "The free preview service is busy or its daily allowance has been used. Please try later.")
                        if event == "complete":
                            output = json.loads(line[5:])[0]
                            break
            if not isinstance(output, dict):
                raise ValueError("No preview returned")
            url = output.get("url", "")
            parsed = urlsplit(url)
            if parsed.scheme != "https" or parsed.netloc != urlsplit(SPACE).netloc or not parsed.path.startswith("/gradio_api/file="):
                raise ValueError("Unexpected preview location")
            # Fetch only this Space's file endpoint, never arbitrary provider URLs.
            image_bytes = bytearray()
            with client.stream("GET", url) as image_response:
                image_response.raise_for_status()
                for chunk in image_response.iter_bytes():
                    image_bytes.extend(chunk)
                    if len(image_bytes) > 10 * 1024 * 1024:
                        raise ValueError("Preview too large")
                    if time.monotonic() > deadline:
                        raise httpx.TimeoutException("Preview deadline exceeded")
            with Image.open(io.BytesIO(image_bytes)) as image:
                if image.width * image.height > 20_000_000:
                    raise ValueError("Preview dimensions too large")
                image.load()
                result = io.BytesIO()
                image.convert("RGB").save(result, format="PNG")
            encoded = base64.b64encode(result.getvalue()).decode()
            return {"image": "data:image/png;base64," + encoded, "model": "fashn-vton-1.5"}
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "The free preview queue took too long. Please try later.") from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403, 429}:
            raise HTTPException(503, "The free preview allowance is unavailable right now. Please try later.") from exc
        raise HTTPException(502, "The preview service is temporarily unavailable.") from exc
    except (httpx.RequestError, ValueError, TypeError, IndexError, KeyError, OSError) as exc:
        raise HTTPException(502, "Unable to create this preview. Please try later.") from exc
    finally:
        _slot.release()
