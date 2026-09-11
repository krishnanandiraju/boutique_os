# BoutiqueOS enhancement status

Updated: 2026-09-11

| Area | Decision / capability | Status | Notes / next |
|---|---|---|---|
| UX v2 | Guided order flow | Built | Customer → Items → Tailoring → Review |
| Measurements | Visual garment guide | Built | Blouse/Kurta/Bottom deterministic SVG guide |
| Measurements | Body measurement vs finished garment separation | Built foundation | Body values stay in MeasurementVersion; finished values now have GarmentSpec on OrderLine |
| Measurements | Merchant-configurable correction policy | Built foundation | Configurable mode, grace hours, lock stage, approval-after-lock |
| Products | Material/fabric is part of SKU/product identity | Built foundation | ItemProfile supports material name/details without changing inventory behavior |
| Products | System code + boutique code | Built foundation | System code unique; boutique code searchable metadata foundation |
| Products | Audience | Built foundation | Women/Men/Girls/Boys/Unisex |
| Products | System + merchant tags | Built foundation | Separate arrays; UI integration into catalog is next |
| Inventory | Purpose separated from inventory behavior | Built foundation | SELLABLE/RAW_MATERIAL/TRIM/PACKAGING/CONSUMABLE independent of UNIQUE/STOCKED/YARDAGE |
| Suppliers | Supplier master | Built | CRUD foundation and item-supplier mapping API |
| Tailoring | Materials checklist | Built foundation | Required materials can be sourced manually; unsourced required material blocks CUTTING |
| Tailoring | Material inventory consumption | Next | Link checklist items to stocked/yardage inventory after procurement design |
| Tailoring | Trial records / outcomes | Next | Build repeatable trials and alteration feedback linkage |
| Discounts | Rule model | Built foundation | Percentage/flat, line/order scope, reason, approval threshold, stackable |
| Discounts | Apply adjustments to order totals | Next | Needs pricing service integration and audit-safe recalculation |
| Discounts | Promo/campaign engine | Next | Build on same rule/adjustment primitives |
| Dashboard | Config payload foundation | Built foundation | Keep role-ready configuration; RBAC will govern visibility later |
| Responsive UX | Shared responsive patterns | In progress | Collection, work-queue, analytics patterns; avoid one universal component |
| Customer CRM | Custom tags | Planned | Merchant + OS tags yes |
| Customer CRM | Relationships / households | Deferred | Explicitly outside BoutiqueOS core for now |
| Fulfilment/logistics | Courier/delivery model | Deferred | Crosses current product boundary |
| RBAC | Role + permission + scope enforcement | Architecture hold | Must be server-side; Admin/Sales/Attendant/Accountant |
| Multi-location | Location-aware stock/orders/reporting | Architecture hold | Requires scope and inventory transfer decisions |
| Procurement | PO/receipts/returns | Architecture next | Supplier master is ready; PO model not yet built |
| Offline billing | Offline create/pay/print/sync | Architecture hold | Requires local persistence, conflict resolution and idempotent sync |
| Messaging workflows | WhatsApp/SMS orchestration | Architecture hold | WorkflowPort retained; durable workflow engine later |
| Payments | Gateway/reconciliation/day close | Architecture hold | Need boundary decision before implementation |
| Android hybrid | Native shell | Architecture hold | Responsive web remains primary until shell work begins |
| AI | Optional metered assistive features | Deferred | No core workflow depends on AI; measurements never inferred |
