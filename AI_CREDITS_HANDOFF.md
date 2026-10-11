# BoutiqueOS AI tenant controls and credits — implementation handoff

## What is now enforced

### Tenant-owned AI credits (B2B)

- Tenant credits are stored in `tenant_ai_credit_accounts` and only tracked at business level.
- Ledger entries are auditable in `tenant_ai_credit_ledger` with `fund`, `reserve`, `charge`, and `release`.
- Customers do not have wallet balances, purchases, or top-ups.
- Successful generations are charged once; failed generations release reservations.

### Authorization model in this implementation

- Generation and policy logic resolve tenant/staff from authenticated context dependency (`get_auth_context`), not caller-supplied form/body tenant IDs.
- Policy admin endpoints remain guarded behind:
  - `AI_POLICY_ADMIN_ENABLED=true`
  - `ENVIRONMENT=development`
  - owner/admin/platform role checks
- Funding endpoint (`POST /api/ai-policy/tenant/fund`) is restricted to `platform_ops`.

### Eligibility and controls

- Segment eligibility uses existing CRM segments: `New`, `Repeat`, `VIP`.
- Customer control is now:
  - `follow_segment_policy`
  - `allow`
  - `disable`
- `allow` can bypass segment policy, but cannot bypass:
  - tenant disablement
  - disabled service
  - insufficient tenant credits
  - product/service restrictions
- Per-customer monthly limits are anti-abuse request caps, not customer credit allocations.

### Service and product controls

- Business service labels:
  - `Standard Preview`
  - `Premium Preview 1`
  - `Design Studio 1`
- Per-service tenant config stores:
  - enabled state
  - credits per successful request
  - optional per-service spending cap
  - internal provider reference field (`provider_ref`) for platform-only metadata
- Product AI config (`product_ai_configurations`) supports:
  - AI enabled flag
  - suitable photo required
  - garment category
  - required photo type
  - approved services

### Endpoint enforcement

- `/api/try-on/generate` and `/api/try-on/design` now:
  - reserve tenant credits before generation
  - prevent duplicate requests via idempotency key (or deterministic implicit key)
  - run generation with bounded retries
  - apply tenant fairness via per-tenant concurrency slot limits
  - charge on success, release on failure
- Customer-facing errors in fitting flow are neutralized (no provider internals or quota diagnostics).
- Provider authorization headers were corrected to use real bearer tokens server-side.

## Frontend/admin behavior updates

- Tenant admin panel shows:
  - tenant credit balance (available/reserved/spent)
  - service enablement + credits per success + spending caps
  - recent ledger usage history
- Customer CRM AI control text now uses “Allow AI previews” and segment-following terminology.
- Virtual try-on uses reviewed saved photographs or suitable uploaded merchandise/fabric photographs (no unreviewed catalog/mannequin fallback input for generation requests).
- Fitting flow status messaging avoids provider names and raw provider errors.

## Validation completed

- Backend: `pytest` updated for policy/ledger reservation behaviors, idempotency conflict, and cross-tenant isolation checks.
- Existing try-on related tests updated to seed tenant policy + funded account prerequisites.
- Frontend code updated to match revised API contract and B2B wording.

## Remaining production-hardening blockers

1. The authenticated context currently supports development defaults and optional trusted dev headers; full production identity integration (real auth/session/JWT-backed tenant+role assertions) still needs to be wired before removing the production admin guard.
2. Queue/fairness is implemented in-process; if multi-replica horizontal scale is required, move slot fairness and queueing to shared infrastructure.
3. Visual validation matrix (4 finished products × 3 customers) still requires manual execution against live provider readiness and should be logged separately from quota/credit failures.


## Saved product photographs

The fitting room displays the selected product photograph automatically. Reviewed mannequin-free bundled kurta and fabric photographs can be used without an upload; the backend resolves primary media scoped to the selected tenant/product and verifies its bytes against the reviewed asset. Variant selections and other photographs require an exact suitable upload. Catalog inputs go through the same tenant policy, eligibility and credit reservation/charge/release lifecycle as uploads. No arbitrary image URL is accepted.


## Meera Boutique demo provisioning

The demo Azure workflow explicitly enables AI_DEMO_BOOTSTRAP_ENABLED. Startup provisions only merchant 1 named Meera Boutique, only with the free Hugging Face provider enabled: Standard Preview at one tenant credit per success, a one-time ledger grant of 100 credits, and access for Anjali Rao, Priya Sharma and Neha Reddy. The reviewed Cotton Kurta product is enabled. Other tenants, premium services and production admin write guards are unchanged. A ledger marker prevents restart top-ups or repeated policy overwrites. Set the flag false on deployments outside this demo. Each preview click now supplies a fresh idempotency key so repeat demonstrations work; provider retries retain the same reservation. No paid provider is enabled.
