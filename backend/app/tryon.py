"""Stateless try-on: customer photographs are never added to public catalog media."""

import base64
import io
import hashlib
from pathlib import Path
import re

import google.auth
import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleRequest
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.ai_policy import (
    AuthContext,
    ProductAIConfiguration,
    complete_generation_failure,
    complete_generation_success,
    get_auth_context,
    reserve_generation_credits,
    run_generation_with_retries,
    tenant_generation_slot,
)
from app.catalog_models import ItemVariant
from app.core.config import settings
from app.db import get_db
from app.fashn_tryon import generate_fashn_preview
from app.models import Customer, Item, MediaAsset
from app.services.media_service import LocalMediaStorage, MediaStorageError

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
    ready = settings.tryon_enabled and settings.tryon_provider in {"google", "huggingface"}
    if ready and settings.tryon_provider == "google":
        ready = bool(settings.google_cloud_project)
        if ready:
            try:
                credentials()
            except HTTPException:
                ready = False
    design_ready = settings.fabric_design_enabled and bool(settings.google_cloud_project)
    if design_ready:
        try:
            credentials()
        except HTTPException:
            design_ready = False
    return {
        "design_configured": design_ready,
        "configured": ready,
        "message": "Preparing your preview is available." if ready else "Preview generation is not available right now.",
    }


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
            image.load()
            image = ImageOps.exif_transpose(image).convert("RGB")
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=95)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(422, "This file is not a valid photograph.") from exc


def read_garment(db: Session, item: Item, variant_id: int | None, source: str, upload: UploadFile | None) -> bytes:
    if source == "upload":
        if upload is None:
            raise HTTPException(422, "Upload a photograph for this preview.")
        return read_image(upload)
    if source != "catalog":
        raise HTTPException(422, "Choose a valid photograph source.")
    # Product photographs cannot establish the colour of a specific variant.
    if variant_id is not None:
        raise HTTPException(422, "Upload a photograph of the selected variant.")
    asset = db.query(MediaAsset).filter_by(item_id=item.id, merchant_id=item.merchant_id, is_primary=True).first()
    approved = "fabric-front.png" if item.inventory_type == "YARDAGE" else "kurta-front-clean.png"
    if not asset or asset.original_filename != approved:
        raise HTTPException(422, "Upload a suitable photograph for this preview.")
    try:
        raw = LocalMediaStorage().resolve_path(asset.storage_key).read_bytes()
        reference = (Path(__file__).parent / "data" / "photography" / approved).read_bytes()
    except (OSError, MediaStorageError) as exc:
        raise HTTPException(422, "Product photograph is unavailable. Upload a photograph instead.") from exc
    # Only reviewed, mannequin-free bundled photos may be used automatically.
    # A filename alone does not establish approval of an uploaded image.
    if hashlib.sha256(raw).digest() != hashlib.sha256(reference).digest():
        raise HTTPException(422, "Upload a suitable photograph for this preview.")
    return read_image(UploadFile(file=io.BytesIO(raw), filename=approved))


def generate_preview(person: bytes, garment: bytes) -> dict:
    project = settings.google_cloud_project
    region = settings.google_cloud_location
    model = settings.tryon_model
    if not all(re.fullmatch(r"[a-zA-Z0-9-]+", value) for value in (project, region, model)):
        raise HTTPException(503, "Google Virtual Try-On configuration is invalid.")
    auth = credentials()
    try:
        auth.refresh(GoogleRequest())
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
        raise HTTPException(504, "Preview provider timed out.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(502, "Preview provider is unavailable.") from exc
    if result.status_code != 200:
        raise HTTPException(503, "Preview provider could not create this preview.")
    try:
        predictions = result.json().get("predictions", [])
        image = next((p for p in predictions if p.get("bytesBase64Encoded")), None)
        if not image:
            raise HTTPException(422, "No preview was returned.")
        mime = image.get("mimeType", "image/png")
        if mime not in {"image/png", "image/jpeg"}:
            raise ValueError("Unexpected output type")
        base64.b64decode(image["bytesBase64Encoded"], validate=True)
        return {"image": f"data:{mime};base64,{image['bytesBase64Encoded']}", "model": model}
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(502, "Preview provider returned an invalid preview.") from exc


def _neutral_tryon_error(exc: HTTPException) -> HTTPException:
    if exc.status_code in {402, 403, 404, 409, 422, 429}:
        return exc
    return HTTPException(503, "We couldn’t complete this preview right now. Please retry or continue.")


@router.post("/generate")
def generate(
    response: Response,
    request: Request,
    person: UploadFile = File(...),
    garment: UploadFile | None = File(None),
    consent: bool = Form(...),
    customer_id: int = Form(...),
    item_id: int = Form(...),
    variant_id: int | None = Form(None),
    category: str = Form("tops"),
    photo_type: str = Form("flat-lay"),
    garment_source: str = Form("upload"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
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
    person_bytes, garment_bytes = read_image(person), read_garment(db, item, variant_id, garment_source, garment)
    # Saved catalog inputs use the owner's product settings, not a stale browser default.
    if garment_source == 'catalog':
        configuration = db.query(ProductAIConfiguration).filter_by(
            merchant_id=item.merchant_id, item_id=item.id, variant_id=variant_id).first()
        if configuration:
            category = configuration.garment_category or category
            photo_type = configuration.required_photo_type or photo_type
        # The reviewed bundled kurta is knee length, even before a policy is provisioned.
        if item.name == 'Cotton Kurta - Blue' and variant_id is None:
            category = 'one-pieces'
    job = reserve_generation_credits(
        db=db,
        auth=auth,
        customer_id=customer_id,
        service_id='standard_preview',
        item_id=item_id,
        variant_id=variant_id,
        person_bytes=person_bytes,
        garment_bytes=garment_bytes,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )
    try:
        with tenant_generation_slot(auth.merchant_id):
            if settings.tryon_provider == "huggingface":
                result = run_generation_with_retries(lambda: generate_fashn_preview(person_bytes, garment_bytes, category, photo_type))
            else:
                result = run_generation_with_retries(lambda: generate_preview(person_bytes, garment_bytes))
        complete_generation_success(db, job)
        db.commit()
        return result
    except HTTPException as exc:
        complete_generation_failure(db, job, f'http_{exc.status_code}')
        db.commit()
        raise _neutral_tryon_error(exc)
