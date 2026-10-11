# AI credits and customer eligibility — coding handoff

## Implemented foundation

- TenantAIPolicy and CustomerAIPolicy use separate tables; existing customer schema is unchanged.
- Admin controls tenant enablement, New/Repeat/VIP segment eligibility, service selection and default monthly customer allowance.
- CRM has Off / Follow boutique policy / Individual allowance controls.
- Explicit Off wins; individual allowance bypasses segment filtering but never tenant disablement. Zero allowance denies policy eligibility.
- Business service names: Standard Preview, Premium Preview 1, Design Studio 1. Standard's 1-credit charge is provisional; other charges are unset. No provider secrets or names appear in these owner panels.
- Existing customer_segment is reused, case-insensitively. Other CRM segments are preserved but not automatically eligible.
- Settings persist using /api/ai-policy. The API is disabled by default (AI_POLICY_ADMIN_ENABLED=false), and deliberately refuses production even if the flag is enabled.
- For local review, set ENVIRONMENT=development and AI_POLICY_ADMIN_ENABLED=true; restart backend. Developer workspace resolves merchant 1 only. This is NOT tenant authentication.

## Recommended starting policy

New: no complimentary AI access. Repeat: 3 credits/month. VIP: manually selected, individual allowance 10 credits/month. Explicitly enable a few chosen customers through Individual allowance. These are proposed commercial limits, not provider prices. Repeat should eventually derive from two completed, paid orders; VIP remains owner-selected. Do not overwrite existing segment labels automatically.

## Required before rollout

1. Replace workspace_merchant with authenticated tenant context, and authorize owner/admin versus staff. Customers must not modify entitlements. No caller-supplied merchant ID may grant access. Test same-tenant and cross-tenant reads/writes. Rework the production guard only after this is implemented.
2. Add platform service catalog with verified product capabilities, internal provider costs, public credit charges, secret references and connection readiness. Tenant entitlements must not manufacture service availability. Optional tenant-owned connections need an explicit billing policy. Secrets never go to browser/VITE variables.
3. Add tenant credit account and auditable ledger, funded by platform-authorized grants/purchases. Do not expose a balance until computed from the ledger. Current credit_balance=null and generation_enabled=false accurately mark these as unfinished. Customer allowances are caps on tenant spending, not separate money balances.
4. Enforce BOTH tenant balance and customer monthly cap on the server, before provider submission. Use atomic reservation, request idempotency and safe concurrent debits. Reserve service-specific credits; charge only on successful delivery; release on failure/cancellation. Define monthly boundary using tenant timezone. Tenant disablement and customer Off must be checked for every new request. Policy settings currently DO NOT control existing /api/try-on/generate or /design endpoints: wire enforcement into both; UI-only limits are insufficient.
5. Add tenant global spending limit, staff limits and optional customer paid/top-up policy. No staff or customer may mint credits through policy updates. Service price changes must not alter existing reservations.
6. Add ProductAIConfiguration: designated suitable image, category, photograph type, approved services and fabric-design requirement. Clean remaining product mannequin images. Saree/lehenga coverage needs visual validation; absence of Gemini is not itself a saree prohibition.
7. Queue requests with bounded retries and tenant fairness. Free-provider quota is distinct from credits. Customer says Preparing your preview, never provider/model busy. On expiry show a neutral retry/continue message; release credits. No infinite spinner or unapproved paid fallback.
8. Wire tenant-and-customer eligibility into the fitting room availability response. Hide/disable unavailable actions with meaningful neutral guidance; no owner balances, service secrets or raw provider errors in customer responses.

## Acceptance and tests

- Cover tenant defaults, persistence, segment inheritance, manual grant, explicit Off, zero cap, tenant disablement, invalid limits and unknown service IDs.
- Cover owner/staff/customer authorization, cross-tenant records and secret isolation.
- Cover concurrent requests at final available credit, duplicate jobs, retry double-charge prevention, reservation expiry, refunds, month rollover and separately priced fabric + preview stages.
- Cover product/service compatibility, provider readiness versus quota, unavailable services and funded/approved fallback only.
- Test four finished products with all three customers (12 visual cases); record quota-blocked cases separately. Measurement accuracy is not established by these tests.
- Run backend pytest and frontend lint/tests/build. Review draft PR; complete outstanding work before merging/deploying.

## Files

Backend: app/ai_policy.py, app/core/config.py, app/main.py, tests/test_ai_policy.py, .env.example.
Frontend: features/workspace/AIPolicy.tsx, BoutiqueWorkspace.tsx, CustomerCrmModal.tsx.

Frontend build is verified separately from live provider generation; this foundation makes no live generation API calls.
