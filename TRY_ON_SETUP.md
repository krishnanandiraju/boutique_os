# Google Virtual Try-On

Orders now follows Customer → Merchandise → Virtual Try-On → Customization → Review.
Try-on is optional and never blocks order creation. Select a finished garment, upload a
customer photo and obtain permission before generation. A catalog image can be used
for a base product; variants require a photo of that exact variant. Fabric-to-design
generation is outside this feature. Previews are visual guidance, not size predictions.

## Backend configuration

Enable billing and the Vertex AI API (`aiplatform.googleapis.com`) in a Google Cloud
project. Verify model access and region availability for `virtual-try-on-001`.
Grant the backend identity Vertex AI User (`roles/aiplatform.user`).

Set these on the backend (Azure App Service in the current deployment):

```
TRYON_ENABLED=true
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
TRYON_MODEL=virtual-try-on-001
```

Authentication uses Google Application Default Credentials. For local testing, run
`gcloud auth application-default login`. For Azure, use Workload Identity Federation
or mount a service-account credential file securely and set
`GOOGLE_APPLICATION_CREDENTIALS` to its path. Never commit credentials or put them in
frontend environment variables. The feature defaults to disabled. The current app
does not implement end-user authentication: protect the backend with authenticated
access before enabling billable generation on a public deployment.

## Behavior and verification

`GET /api/try-on/status` reports whether configuration and credential discovery are
available; it does not verify billing or model access. `POST /api/try-on/generate`
accepts multipart person/garment files, consent, customer_id, item_id, and optional
variant_id. It checks customer/product merchant consistency and variant membership.
JPEG/PNG uploads are capped at 10 MB and 20 megapixels; photos are re-encoded to
remove EXIF metadata. One prediction is requested with a 120-second provider timeout.
The synchronous request runs in FastAPI's worker pool; this MVP has no durable job
queue. Inputs/results are not added to the DB or public media store. Google processes
the images under your project's service terms. Results stay in browser session state
until navigation away/reset, with an optional download.

Run backend `python -m pytest -q` and frontend `npm run lint && npm run build`.
Provider contract tests are mocked; a real generation still requires configured
Google Cloud credentials, model access, quota and billing.

Official API guide:
https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/generate-virtual-try-on-images
