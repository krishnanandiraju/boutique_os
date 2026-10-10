"""Stateless try-on: customer photographs are never added to public catalog media."""
import base64
import io
import re

import google.auth
import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import Customer, Item
from app.catalog_models import ItemVariant
from app.fashn_tryon import generate_fashn_preview

router = APIRouter(prefix="/api/try-on", tags=["Virtual try-on"])
MAX_BYTES = 10 * 1024 * 1024
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def credentials():
    try:
        return google.auth.default(scopes=SCOPES)[0]
    except GoogleAuthError as exc:
        raise HTTPException(503, "Google Cloud authentication is not configured.") from exc


@router.get("/status")
def status(response: Response):
    response.headers["Cache-Control"] = "no-store"
    reason = "Google Virtual Try-On has not been enabled by the boutique."
    ready = settings.tryon_enabled and bool(settings.google_cloud_project)
    if settings.tryon_enabled and settings.tryon_provider == "huggingface":
        ready = True
        reason = "Free preview service selected; availability depends on its queue and daily allowance."
    elif ready and settings.tryon_provider == "google":
        try:
            credentials()
        except HTTPException:
            ready = False
            reason = "Google Cloud authentication needs to be connected."
    elif settings.tryon_enabled:
        reason = "A Google Cloud project needs to be connected."
    design_ready = settings.fabric_design_enabled and bool(settings.google_cloud_project)
    if design_ready:
        try:
            credentials()
        except HTTPException:
            design_ready = False
    if settings.tryon_provider not in {"google", "huggingface"}:
        ready = False
        reason = "A supported preview provider needs to be selected."
    return {"provider": settings.tryon_provider, "design_configured": design_ready, "configured": ready,
            "message": reason if settings.tryon_provider == "huggingface" else "Ready to generate a preview." if ready else reason}


def read_image(file: UploadFile) -> bytes:
    raw = file.file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "Each photograph must be smaller than 10 MB.")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in {"JPEG", "PNG"}:
                raise HTTPException(422, "Use a JPEG or PNG photograph.")
            if image.width * image.height > 20_000_000 or min(image.size) < 64:
                raise HTTPException(422, "Use a clear image between 64 pixels and 20 megapixels.")
            # Remove EXIF/location metadata before sending to the preview provider.
            image.load()
            image = ImageOps.exif_transpose(image).convert("RGB")
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=95)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(422, "This file is not a valid photograph.") from exc


def generate_preview(person: bytes, garment: bytes) -> dict:
    project = settings.google_cloud_project
    region = settings.google_cloud_location
    model = settings.tryon_model
    if not all(re.fullmatch(r"[a-zA-Z0-9-]+", value) for value in (project, region, model)):
        raise HTTPException(503, "Google Virtual Try-On configuration is invalid.")
    auth = credentials()
    try:
        auth.refresh(Request())
    except GoogleAuthError as exc:
        raise HTTPException(503, "Unable to authenticate with Google Cloud.") from exc
    host = "aiplatform.googleapis.com" if region == "global" else f"{region}-aiplatform.googleapis.com"
    url = f"https://{host}/v1/projects/{project}/locations/{region}/publishers/google/models/{model}:predict"
    body = {
        "instances": [{
            "personImage": {"image": {"bytesBase64Encoded": base64.b64encode(person).decode()}},
            "productImages": [{"image": {"bytesBase64Encoded": base64.b64encode(garment).decode()}}],
        }],
        "parameters": {"sampleCount": 1},
    }
    try:
        result = httpx.post(url, json=body, headers={"Authorization": f"Bearer {auth.token}"}, timeout=120)
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "The preview took too long. Please try again.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(502, "Google Virtual Try-On is temporarily unavailable.") from exc
    if result.status_code != 200:
        messages = {429: "Google is busy or the generation quota has been reached.",
                    403: "Google Cloud model access or billing needs to be checked.",
                    404: "The try-on model is unavailable in the configured region."}
        raise HTTPException(502, messages.get(result.status_code, "Google could not create this preview. Try clearer photographs."))
    try:
        predictions = result.json().get("predictions", [])
        image = next((p for p in predictions if p.get("bytesBase64Encoded")), None)
        if not image:
            raise HTTPException(422, "No preview was returned. Try a clear front-facing photograph and a finished garment.")
        mime = image.get("mimeType", "image/png")
        if mime not in {"image/png", "image/jpeg"}:
            raise ValueError("Unexpected output type")
        base64.b64decode(image["bytesBase64Encoded"], validate=True)
        return {"image": f"data:{mime};base64,{image['bytesBase64Encoded']}", "model": model}
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(502, "Google returned an invalid preview.") from exc


@router.post("/generate")
def generate(response: Response, person: UploadFile = File(...), garment: UploadFile = File(...),
             consent: bool = Form(...), customer_id: int = Form(...), item_id: int = Form(...),
             variant_id: int | None = Form(None), category: str = Form("tops"),
             photo_type: str = Form("flat-lay"), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    if not consent:
        raise HTTPException(422, "Customer permission is required to use their photograph.")
    if not settings.tryon_enabled or settings.tryon_provider not in {"google", "huggingface"} or (settings.tryon_provider == "google" and not settings.google_cloud_project):
        raise HTTPException(503, "Virtual Try-On is not connected yet. You can continue to customization.")
    customer, item = db.get(Customer, customer_id), db.get(Item, item_id)
    if not customer or not item or customer.merchant_id != item.merchant_id:
        raise HTTPException(404, "Customer or garment was not found.")
    if item.inventory_type == "YARDAGE":
        raise HTTPException(422, "Choose a finished garment. Fabric swatches are not supported for try-on.")
    if variant_id is not None:
        variant = db.get(ItemVariant, variant_id)
        if not variant or variant.item_id != item.id:
            raise HTTPException(422, "This variant does not belong to the selected garment.")
    person_bytes, garment_bytes = read_image(person), read_image(garment)
    if settings.tryon_provider == "huggingface":
        return generate_fashn_preview(person_bytes, garment_bytes, category, photo_type)
    return generate_preview(person_bytes, garment_bytes)
