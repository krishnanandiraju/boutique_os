# Bundled customer profiles and product photography

Startup attaches the bundled photographs directly to the five existing Meera Boutique products. Each product has front, alternate and detail views. Galleries support browsing, adding images and changing the cover. There is no manual demo-loading button. Products with non-bundled photography are preserved; partial imports and missing files can be repaired on restart without duplicate records.

Portraits are persisted in `customer_photos`, keyed to the exact existing Anjali Rao, Priya Sharma and Neha Reddy records and dummy phone numbers. `/api/customers` supplies their `photo_url`. Customers, CRM profile and Virtual Try-On use that stored association. Customer photos are not product media. The three portraits have different clothes, hairstyles and approximate body proportions.

Each customer receives Blouse and Kurta measurement profiles in inches on startup. Existing user profiles and measured values are preserved. A legacy profile is renamed only when all its versions were created by our earlier fixture loader; IDs, dimensions and links are preserved. Normal customer screens use ordinary profile and photo labels.

## Internal provenance

Specifications are in `backend/app/data/customer_fixtures.json`. These are invented, internally consistent workflow-test measurements, not dimensions measured from generated images. Portrait prompts use them only as approximate proportion guidance. Version `created_by` markers retain the test origin. This data cannot validate measurement-estimation accuracy or quantitative fit gaps.

The 15 original product images and three replacement adult portraits are packaged in `backend/app/data/photography`. All were generated with the built-in image-generation tool from original prompts on 2026-10-10; no company or stock photography, designer imagery or real-person reference was supplied. Prompt summaries, complete replacement portrait prompts and SHA-256 hashes are in provenance.json. The original grey-top portrait entries remain in that file as historical provenance; those images are no longer shipped. Generated images are not a legal guarantee of exclusivity or non-infringement.

## Preview generation

Finished garments use Google Virtual Try-On. Fabric uses a separate Gemini design-concept endpoint with a design brief. These are visual previews, not verified fit or measurements. Tailors confirm construction, cloth allowance and actual alterations. Staff notes carry through customization and review to tailoring tasks.

Existing configuration is in TRY_ON_SETUP.md. Fabric concepts additionally require:

```
FABRIC_DESIGN_ENABLED=true
FABRIC_DESIGN_MODEL=gemini-2.5-flash-image
FABRIC_DESIGN_LOCATION=global
```

Both features default off and require Google Cloud credentials, project, billing, quota and model access. Customer photo processing requires permission. Generation remains stateless; uploaded preview photos are not added to public product media. Bundled fictional portraits are served through the existing media endpoint.
