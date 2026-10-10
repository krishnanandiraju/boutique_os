"""Stateless fabric concept previews, separate from finished-garment try-on."""
import base64
import re
import httpx
from fastapi import Depends, File, Form, HTTPException, Response, UploadFile
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from sqlalchemy.orm import Session
from app import tryon
from app.db import get_db
from app.models import Customer, Item
from app.catalog_models import ItemVariant


def generate_concept(person: bytes, fabric: bytes, brief: str) -> dict:
    settings = tryon.settings
    project, region, model = settings.google_cloud_project, settings.fabric_design_location, settings.fabric_design_model
    if not all(re.fullmatch(r'[a-zA-Z0-9-]+', value) for value in (project, region)) or not re.fullmatch(r'[a-zA-Z0-9.-]+', model):
        raise HTTPException(503, 'Fabric preview configuration is invalid.')
    auth = tryon.credentials()
    try:
        auth.refresh(Request())
    except GoogleAuthError as exc:
        raise HTTPException(503, 'Unable to authenticate with the design service.') from exc
    host = 'aiplatform.googleapis.com' if region == 'global' else f'{region}-aiplatform.googleapis.com'
    url = f'https://{host}/v1/projects/{project}/locations/{region}/publishers/google/models/{model}:generateContent'
    prompt = ('Create one realistic approximate garment design concept on the person in the first image, using the fabric in the second image. '
              'Keep the person identity, pose, body shape and background. Preserve fabric colour and motifs as closely as possible. '
              'This is an illustrative proposed design, not a prediction of fit or measurements. Do not add text, labels, logos or measurements. '
              'Boutique design brief: ' + brief)
    body = {'contents': [{'role': 'user', 'parts': [{'text': prompt},
            {'inlineData': {'mimeType': 'image/jpeg', 'data': base64.b64encode(person).decode()}},
            {'inlineData': {'mimeType': 'image/jpeg', 'data': base64.b64encode(fabric).decode()}}]}],
            'generationConfig': {'responseModalities': ['TEXT', 'IMAGE'], 'candidateCount': 1}}
    try:
        response = httpx.post(url, json=body, headers={'Authorization': f'Bearer {auth.token}'}, timeout=120)
    except httpx.TimeoutException as exc:
        raise HTTPException(504, 'The design preview took too long.') from exc
    except httpx.RequestError as exc:
        raise HTTPException(502, 'The design preview is temporarily unavailable.') from exc
    if response.status_code != 200:
        raise HTTPException(502, 'The design service could not create a concept. Check model access, billing and quota in Admin.')
    try:
        parts = [part for candidate in response.json().get('candidates', []) for part in candidate.get('content', {}).get('parts', [])]
        output = next((part['inlineData'] for part in parts if part.get('inlineData', {}).get('mimeType') in {'image/png', 'image/jpeg'}), None)
        if not output:
            raise HTTPException(422, 'No design image was returned. Try clearer photos or a different design brief.')
        raw = base64.b64decode(output['data'], validate=True)
        if not raw or len(raw) > tryon.MAX_BYTES:
            raise ValueError('Invalid image size')
        return {'image': f"data:{output['mimeType']};base64,{output['data']}", 'model': model, 'preview_type': 'DESIGN_CONCEPT'}
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise HTTPException(502, 'The design service returned an invalid image.') from exc


@tryon.router.post('/design')
def design(response: Response, person: UploadFile = File(...), garment: UploadFile = File(...),
           consent: bool = Form(...), customer_id: int = Form(...), item_id: int = Form(...),
           brief: str = Form(..., min_length=3, max_length=1000), variant_id: int | None = Form(None), db: Session = Depends(get_db)):
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
    return generate_concept(tryon.read_image(person), tryon.read_image(garment), brief.strip())
