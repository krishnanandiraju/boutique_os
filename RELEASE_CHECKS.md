# Pricing and order operations — 26 September 2026

Orders now support line and order discounts with percentage/flat rules, caps, reasons and stacking validation. Applying a discount updates the persisted order total used by existing reporting. Reversals append an auditable adjustment and support safe retries. Both pricing and fulfilment changes enqueue integration events in the same database transaction.

The Orders workspace includes searchable history, line details, discount application/reversal and fulfilment controls. Fabric quantities accept decimals without losing an in-progress value while typing. Delivery checks reject unfinished tailoring, and pricing is locked after packing, shipping, delivery or cancellation.

## Verification

- Backend: install `backend/requirements.txt`, then from `backend` run `DATABASE_URL=sqlite:///./verification.db python -m pytest -q`: **122 passed** locally.
- Frontend: from `frontend`, run `npm ci`, `npm run lint`, `npm run build` and `npm test`: lint/build passed and **3 interaction tests passed**.
- New API coverage includes rounding/caps, stacking, reasons, merchant and line ownership, reporting totals, event persistence, reversal retries and fulfilment guards.
- DOM tests exercise a fractional fabric order with tailoring, rejected-discount recovery, reversal, delivery and the unfinished-tailoring guard.

## Remaining production work

- Authentication/RBAC is still an existing architecture gap. A caller-provided merchant identifier is not authenticated authorization. This release does not make the existing API suitable for untrusted public access.
- Rules requiring approval are blocked until authenticated approvals exist. The API does not accept an approver name as proof of authorization.
- The existing cancellation path does not implement stock returns/refunds. No cancellation control was added to this UI.
- Courier, payments, offline operation and the other deferred areas in `ENHANCEMENT_STATUS.md` remain separate work.
- Real Azure deployment, payment integrations and live customer data were not changed or verified.
- Browser launch was blocked by unavailable sockets. DOM interaction tests passed but do not verify visual layout. The existing frontend bundle-size warning remains.

No schema migration is needed: this release uses the existing discount-rule and order-adjustment models. Generated databases and Python bytecode are excluded from the change.
