# Approval Decision Outbox

Approval decisions can be delivered to Temporal through a transactional
Postgres outbox. This prevents the API from reporting a durable decision while
losing its workflow notification in the gap between an external Temporal call
and the database commit.

The outbox is an operational delivery mechanism, not a demo queue. The approval
record, audit evidence and delivery event are committed together. A worker then
claims committed events in bounded batches, sends a structured decision to
Temporal and marks the event delivered. Retries retain the same event ID so the
workflow can deduplicate a signal after an ambiguous timeout or worker crash.

```text
API transaction                Worker dispatch
approval + audit + outbox  ->  claim -> Temporal -> delivered
                                  |         |
                                  +-- retry-+-- stable decision event ID
```

## Configuration

The API enqueue gate and worker dispatch gate are deliberately separate. Both
default to `false`; upgrading does not change approval delivery until an
operator opts in.

| Setting | Default | Purpose |
| --- | ---: | --- |
| `AXIS_APPROVAL_DECISION_OUTBOX_ENABLED` | `false` | Enqueue new approval decisions transactionally instead of using request-time delivery. |
| `AXIS_APPROVAL_DECISION_OUTBOX_DISPATCH_ENABLED` | `false` | Register/run the worker dispatcher. Independent of `AXIS_SCHEDULED_JOBS_ENABLED`. |
| `AXIS_APPROVAL_DECISION_OUTBOX_DISPATCH_INTERVAL_SECONDS` | `5` | Dispatcher cadence (`1`–`3600`). |
| `AXIS_APPROVAL_DECISION_OUTBOX_BATCH_SIZE` | `10` | Maximum events claimed and sent concurrently per tick (`1`–`100`). |
| `AXIS_APPROVAL_DECISION_OUTBOX_CLAIM_TIMEOUT_SECONDS` | `60` | Reclaim a dispatching event after a worker lease expires (`5`–`3600`). |
| `AXIS_APPROVAL_DECISION_OUTBOX_MAX_ATTEMPTS` | `10` | Move an event to the dead-letter state after this many failed sends (`1`–`100`). |
| `AXIS_APPROVAL_DECISION_OUTBOX_RETRY_BASE_SECONDS` | `1` | Initial retry delay (`1`–`3600`). |
| `AXIS_APPROVAL_DECISION_OUTBOX_RETRY_MAX_SECONDS` | `300` | Cap for exponential retry delay (`1`–`86400`). Keep it at least as large as the base delay. |

The claim timeout is validated to exceed the Temporal signal timeout and should
also cover expected database and scheduling latency. Raising batch size increases database and
Temporal load; scale only after measuring dispatch duration and backlog age.

Approval workflow IDs are non-reusable: the worker starts them with Temporal's
`REJECT_DUPLICATE` policy. This prevents a delayed decision from being delivered
to a newer execution under the same workflow ID.

## Safe rollout

1. Apply the database migration while both flags remain off.
2. Deploy the worker version that understands the structured decision signal
   and stable event ID. Wait until no older approval workers are polling.
3. Deploy the compatible API version with enqueue still disabled.
4. Enable `AXIS_APPROVAL_DECISION_OUTBOX_DISPATCH_ENABLED` on the worker. Leave
   API enqueue off and verify the dispatcher starts without errors.
5. Enable `AXIS_APPROVAL_DECISION_OUTBOX_ENABLED` on the API.
6. Verify new events progress from `pending` to `delivered`, backlog age stays
   bounded, and no event reaches `dead_letter`.

Do not enable API enqueue before a compatible dispatcher is running. The
dispatcher gate is independent of the generic scheduled-maintenance switch so
an operator can deliver approvals while maintenance schedules remain paused.

## Rollback and recovery

Disable API enqueue first so no new outbox events are added. Keep dispatch
enabled until `pending` and `dispatching` are empty, then disable it. Disabling
dispatch while enqueue remains enabled preserves decisions but grows an
undelivered backlog.

A worker crash can leave an event `dispatching`; the claim timeout makes it
eligible for another worker. Delivery is therefore at least once. The stable
decision event ID and workflow-side deduplication make a repeated identical
signal a no-op. A conflicting terminal decision must never overwrite the
workflow result.

Dead-letter events require operator investigation. This release does not expose
an automatic re-drive command: do not edit outbox rows manually in production.
Retain the row as audit evidence, correct the underlying Temporal or payload
failure, and follow an approved incident procedure that preserves the original
event ID before any re-drive tooling is introduced.

## Operational checks

Alert on oldest pending-event age, consecutive retry growth, expired claims and
any dead-letter event. During rollout, compare the number of committed approval
decisions with outbox events and delivered workflow results for the same tenant
and event ID. Never include decision notes, identity tokens or credentials in
metrics or logs.
