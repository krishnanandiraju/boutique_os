# BoutiqueOS Technical Debt

## P0 — Correctness / Security
- Local filesystem media storage: uploaded assets are written under `./data/media`, which is safe for the MVP but not durable or shareable across machines. Future fix: move to object storage with signed URLs.
- No authentication or RBAC enforcement is present in the app routes. Future fix: add login/session or token-based access control before exposing the system beyond trusted local use.

## P1 — Architecture
- The frontend is still centered in a single large `frontend/src/App.tsx` component. Future fix: extract media, inventory, orders, and tailoring panels into smaller components.
- Database schema changes are applied through `Base.metadata.create_all` rather than a migration tool. Future fix: introduce Alembic for controlled schema evolution.

## P2 — Scale / Maintainability
- SQLite is the active persistence layer, which is fine for local MVP use but limited for concurrent production workloads. Future fix: migrate to a server database when multi-user concurrency matters.
