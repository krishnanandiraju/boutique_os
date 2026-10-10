# Demo photography and preview flows

Products → Demo photo library → Load demo product images adds three original AI-generated studio views to each matching seeded product. It checks current media, preserves products with existing non-demo photography, and can retry a partial import. Existing products support galleries, extra uploads and cover selection through their image button.

The library includes fictional adult portraits for Anjali Rao, Priya Sharma and Neha Reddy. Only exact seeded names and dummy phone numbers receive these portraits in Customers and the try-on shortcut. Real customers must supply their own photographs with permission.

Load labelled demo measurements creates separate BLOUSE/INCH profiles named `DEMO ONLY — unverified photo fixture`. These numbers are invented fixtures, not recovered or known body dimensions. Existing measurement profiles are preserved. They test software flow, not measurement accuracy. Neither model measures bodies or identifies quantitative fit gaps.

Finished merchandise uses Google Virtual Try-On. Yardage uses a separate Gemini fabric-to-garment concept endpoint, with a design brief. Both require customer consent and process sanitized photographs without adding customer images to public catalog storage. Fabric concepts are approximate and may change motif scale, colour or construction; tailors must confirm design and fabric allowance. Fit needs real measured dimensions and a fitting.

Staff enter observed adjustments in the preview step. Those notes carry through Customization and Review, and persist in the tailoring task when the order is confirmed. Unchecking tailoring clears these notes.

## Backend configuration

Existing Virtual Try-On setup remains in TRY_ON_SETUP.md. Fabric concepts additionally require:

```
FABRIC_DESIGN_ENABLED=true
FABRIC_DESIGN_MODEL=gemini-2.5-flash-image
FABRIC_DESIGN_LOCATION=global
```

Uses the same Google Cloud project and application default credentials. Model access, Vertex AI API, billing and quota must be enabled separately. Both generation features default off. Status only checks enablement, project and credential discovery, not live model access.

## Provenance

All 18 PNGs in `frontend/public/demo-images` were generated from original text prompts with the built-in image-generation tool on 2026-10-10. No company photography, stock imagery or designer reference images were supplied. Alternate and detail photographs were generated from each original front view. Prompts requested generic original Indian boutique garments, plain studio backgrounds, and no brands, logos, text, watermarks or identifiable designer patterns. Portraits requested fictional adult Indian women in plain grey t-shirts and navy trousers, without real-person references. These assets depict fictional products and people and must not misrepresent real stock or customers. AI generation is not a legal guarantee of exclusivity or non-infringement.

The generation prompt summaries and asset SHA-256 hashes are recorded in `frontend/public/demo-images/provenance.json`.
