"""Stateless fabric concept previews, separate from finished-garment try-on."""

import base64
import re

import httpx
from fastapi import Depends, File, Form, HTTPException, Request, Response, UploadFile
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleRequest
from sqlalchemy.orm import Session

from app import tryon
from app.ai_policy import (
    AuthContext,
    complete_generation_failure,
    complete_generation_success,
    get_auth_context,
    reserve_generation_credits,
    run_generation_with_retries,
    tenant_generation_slot,
)
from app.catalog_models import ItemVariant
from app.db import get_db
from app.models import Customer, Item


def generate_concept(person: bytes, fabric: bytes, brief: str) -> dict:
    settings = tryon.settings
    project, region, model = settings.google_cloud_project, settings.fabric_design_location, settings.fabric_design_model
    if not all(re.fullmatch(r'[a-zA-Z0-9-]+', value) for value in (project, region)) or not re.fullmatch(r'[a-zA-Z0-9.-]+', model):
        raise HTTPException(503, 'Fabric preview configuration is invalid.')
    auth = tryon.credentials()
    try:
        auth.refresh(GoogleRequest())
    except GoogleAuthError as exc:
        raise HTTPException(503, 'Unable to authenticate with the design service.') from exc
    host = 'aiplatform.googleapis.com' if region == 'global' else f'{region}-aiplatform.googleapis.com'
    url = f'https://{host}/v1/projects/{project}/locations/{region}/publishers/google/models/{model}:generateContent'
    prompt = (
        'Create one realistic approximate garment design concept on the person in the first image, using the fabric in the second image. '
        'Keep the person identity, pose, body shape and background. Preserve fabric colour and motifs as closely as possible. '
        'This is an illustrative proposed design, not a prediction of fit or measurements. Do not add text, labels, logos or measurements. '
        'Boutique design brief: ' + brief
    )
    body = {
        'contents': [{
            'role': 'user',
            'parts': [
                {'text': prompt},
                {'inlineData': {'mimeType': 'image/jpeg', 'data': base64.b64encode(person).decode()}},
                {'inlineData': {'mimeType': 'image/jpeg', 'data': base64.b64encode(fabric).decode()}},
            ],
        }],
        'generationConfig': {'responseModalities': ['TEXT', 'IMAGE'], 'candidateCount': 1},
    }
    try:
        response = httpx.post(url, json=body, headers={'Authorization': f'Bearer {auth.token}'}, timeout=120)
    except httpx.TimeoutException as exc:
        raise HTTPException(504, 'Preview provider timed out.') from exc
    except httpx.RequestError as exc:
        raise HTTPException(502, 'Preview provider is temporarily unavailable.') from exc
    if response.status_code != 200:
        raise HTTPException(503, 'Preview provider could not create a concept image.')
    try:
        parts = [part for candidate in response.json().get('candidates', []) for part in candidate.get('content', {}).get('parts', [])]
        output = next((part['inlineData'] for part in parts if part.get('inlineData', {}).get('mimeType') in {'image/png', 'image/jpeg'}), None)
        if not output:
            raise HTTPException(422, 'No design image was returned.')
        raw = base64.b64decode(output['data'], validate=True)
        if not raw or len(raw) > tryon.MAX_BYTES:
            raise ValueError('Invalid image size')
        return {'image': f"data:{output['mimeType']};base64,{output['data']}", 'model': model, 'preview_type': 'DESIGN_CONCEPT'}
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise HTTPException(502, 'The design service returned an invalid image.') from exc


def _neutral_design_error(exc: HTTPException) -> HTTPException:
    if exc.status_code in {402, 403, 404, 409, 422, 429}:
        return exc
    return HTTPException(503, 'We couldn’t complete this preview right now. Please retry or continue.')


@tryon.router.post('/design')
def design(
    response: Response,
    request: Request,
    person: UploadFile = File(...),
    garment: UploadFile | None = File(None),
    consent: bool = Form(...),
    customer_id: int = Form(...),
    item_id: int = Form(...),
    brief: str = Form(..., min_length=3, max_length=1000),
    variant_id: int | None = Form(None),
    garment_source: str = Form('upload'),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    response.headers['Cache-Control'] = 'no-store'
    if not consent:
        raise HTTPException(422, 'Customer permission is required to use their photograph.')
    if not tryon.settings.fabric_design_enabled or not tryon.settings.google_cloud_project:
        raise HTTPException(503, 'Fabric design previews are not connected yet.')
    customer, item = db.get(Customer, customer_id), db.get(Item, item_id)
    if not customer or not item or customer.merchant_id != item.merchant_id:
        raise HTTPException(404, 'Customer or fabric was not found.')
    if item.inventory_type != 'YARDAGE':
        raise HTTPException(422, 'Design concepts require a fabric item. Use try-on for finished garments.')
    if variant_id is not None:
        variant = db.get(ItemVariant, variant_id)
        if not variant or variant.item_id != item.id:
            raise HTTPException(422, 'This variant does not belong to the selected fabric.')
    person_bytes, garment_bytes = tryon.read_image(person), tryon.read_garment(db, item, variant_id, garment_source, garment)
    job = reserve_generation_credits(
        db=db,
        auth=auth,
        customer_id=customer_id,
        service_id='design_studio_1',
        item_id=item_id,
        variant_id=variant_id,
        person_bytes=person_bytes,
        garment_bytes=garment_bytes,
        idempotency_key=request.headers.get('Idempotency-Key'),
    )
    try:
        with tenant_generation_slot(auth.merchant_id):
            result = run_generation_with_retries(lambda: generate_concept(person_bytes, garment_bytes, brief.strip()))
        complete_generation_success(db, job)
        db.commit()
        return result
    except HTTPException as exc:
        complete_generation_failure(db, job, f'http_{exc.status_code}')
        db.commit()
        raise _neutral_design_error(exc)
