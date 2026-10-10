# Free virtual try-on

The finished-garment preview supports `TRYON_PROVIDER=huggingface` with
`TRYON_ENABLED=true`. Production deployment selects this provider explicitly.
Google remains available via `TRYON_PROVIDER=google`; it is never called as a
fallback. Fabric design concepts still require the separate Gemini setup.

Provider: FASHN VTON 1.5, hosted by its publisher on the public Hugging Face Space:
https://huggingface.co/spaces/fashn-ai/fashn-vton-1.5
Model weights: https://huggingface.co/fashn-ai/fashn-vton-1.5 (Apache 2.0).
The repository does not redistribute the weights.

This is shared free GPU access, not a dedicated production SLA. Anonymous daily
GPU allowances and queues apply. The provider may change its API or availability.
The backend uploads sanitized JPEGs only after the customer permission checkbox
is selected. Those uploads are processed by a third-party public Space; the app
must not promise immediate deletion at that provider. No account, payment method,
API key, or paid fallback is configured by this integration.

The REST adapter uploads two images, submits `/try_on`, reads the queued result,
and downloads only the same Space's file endpoint. Metadata is removed before
upload. Preview images are returned inline and are not stored by BoutiqueOS.
One simultaneous generation per backend process is allowed. Waiting is bounded;
quota and service errors appear as a retry-later message. API readiness means the
provider has been selected, not that its GPU quota is currently available.

The fitting room provides garment type and photo type controls. Finished outfits
can be previewed; fabric swatches use the separate concept workflow. Try-on output
is visual, not a body-measurement or quantitative-fit estimate. Multi-piece Indian
outfits should be evaluated on the actual imagery; quality is not guaranteed.

Verification covers consent, sanitized inputs, upload/queue/download contract,
quota errors, output-host validation, slot release, and absence of Google fallback.
