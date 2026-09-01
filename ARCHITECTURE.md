# BoutiqueOS Architecture

## Domain Boundaries
- BoutiqueOS core owns catalog items, physical inventory lots and movements, customers, measurements, orders, tailoring, and media metadata.
- External channels are projections, not sources of truth, for commerce surfaces such as BoutiqueOS storefront, Labha, Shopify, WhatsApp, Instagram, POS, and future partners.
- Financial ERP systems remain downstream integration targets for invoices, payments, refunds, and accounting exports.

## Dependency Direction
- API routes call application services.
- Application services call domain models and ports.
- Adapters implement ports.
- Core code does not import vendor SDKs or channel-specific adapters.

## Canonical Ownership
- InventoryLot, Hold, InventoryMovement, and OrderLineAllocation remain the inventory truth.
- Customer, MeasurementProfile, and MeasurementVersion remain Boutique customer truth.
- Order and OrderLine remain operational commerce truth.
- TailoringTask remains the boutique workflow truth.
- MediaAsset metadata remains the media truth; physical bytes stay in a storage adapter.

## Ports and Adapters
- CommerceChannelPort publishes catalog and inventory availability.
- AccountingPort exports invoices.
- PaymentGatewayPort captures and refunds payments.
- LogisticsPort creates and updates shipments.
- MessagingPort sends outbound messages.
- MediaStoragePort saves, deletes, and resolves media bytes.
- AIEnrichmentPort provides deterministic suggestion and analysis seams.

## Integration Events and Outbox
- Canonical integration events are written to IntegrationOutbox inside the same DB transaction as the business change.
- Event payloads use typed DTOs before serialization.
- The outbox is processed synchronously in dev/tests and can be retried safely.

## Failure and Retry Model
- External failure never rolls back BoutiqueOS inventory truth after the core transaction commits.
- Failed integration events remain in the outbox with last_error and attempt_count.
- Retries are idempotency-aware and skip already processed events.

## Transaction Boundaries
- Order creation commits order lines, allocations, movements, tailoring tasks, and outbox events as one unit.
- Media uploads commit metadata separately from any later channel mapping or publication step.
- External adapter calls happen after the authoritative DB transaction, never inside it.

## Anti-Corruption Layer
- Integration DTOs convert core entities into canonical external payloads.
- External mapping stays generic through ExternalResourceMapping rather than channel-specific columns on Item.
- ChannelConnection records optional per-channel configuration without storing vendor tokens in domain tables.
