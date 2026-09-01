# BoutiqueOS Workflow Boundary

BoutiqueOS has two different asynchronous concerns and they must stay separate.

## 1. Transactional integration outbox

`IntegrationOutbox` is a reliability boundary between an already-committed BoutiqueOS transaction and external systems. It guarantees that events such as `order.created` and `inventory.changed` are durably recorded with the business transaction.

The outbox is **not** the business workflow engine. Its responsibilities are delivery state, retry metadata, idempotency, and adapter hand-off.

## 2. Long-running business workflows

Processes such as tailoring, fulfillment, trial scheduling, customer follow-up, and multi-step channel synchronization can last minutes to weeks and may include timers, human actions, retries, compensations, and external callbacks. Those should be orchestrated through `WorkflowPort` rather than by adding more queue-state logic to BoutiqueOS tables.

A future production adapter can use Temporal (preferred code-first option for the current Python stack) or another workflow engine. Core domain code must depend only on `WorkflowPort`, never on a vendor SDK.

## Transaction rule

Business state + integration outbox rows commit atomically first. A workflow may then be started or signalled after commit, typically from a durable outbox event. External/workflow-engine availability must never corrupt BoutiqueOS inventory truth.

## Tailoring example

A future `TailoringWorkflow` can coordinate:

`MEASUREMENT_PENDING -> CUTTING -> STITCHING -> TRIAL -> ALTERATION? -> READY -> DELIVERED`

Human feedback such as `SLEEVE:TOO_LONG` or `NECKLINE:TOO_DEEP` is domain data, not workflow-engine state. It is stored in stitch records and can later influence a proposed measurement/fit-preference revision without silently rewriting historical body measurements.
