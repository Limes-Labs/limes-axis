# Ingestion strategy evidence, version 1

**PASS:** both experiment matrices completed with identical expected payloads and
checkpoint outcomes across all strategies and repeats. This is a synthetic
strategy evaluation for [#365](https://github.com/Limes-Labs/limes-axis/issues/365),
not a production throughput or tenant-fairness certification. The
[experiment contract](../../ingestion-performance.md) defines fixtures, limits,
metrics, comparison policy and reproduction commands.

## Capture

- Runtime/harness commit: `56d988cf1356a0b717294eabb0c00aead3a58063`, clean at both
  capture starts, 2026-09-07 at 18:39 and 18:42 UTC.
- Host: macOS 26.5.2, ARM64; Python 3.12.6; SQLite 3.45.3. Each trial ran in a
  fresh process. Relevant source/lockfile hashes and dependency versions are
  retained in the reports.
- Four source shapes × four strategies × three repeats for each profile. Local
  component test suites and builds were not run concurrently with capture.
- Representative profile: **864 offered, 864 completed, zero rejected/failed**.
  Saturation profile: **1,536 offered, 768 completed, 768 rejected, zero failed**.
  Every rejection is retained as admission evidence.

## Representative results

Each cell is median elapsed seconds / median traced Python peak KiB across three
trials. One case processes 18 jobs, each with 128 records containing 2,048 UTF-8
text bytes. The sink is a digest/acknowledgement fixture. Read and sink delays are
two milliseconds per batch; they are configured fixture delays, not observed
provider latency.

| Source fixture | Materialized serial | Streamed serial | Streamed parallel | Streamed tenant turns |
| --- | --- | --- | --- | --- |
| REST / in-process HTTP | 1.263 / 1,435.3 | 1.156 / 1,485.0 | 0.372 / 1,728.6 | 0.754 / 1,634.0 |
| Database / SQLite | 1.222 / 307.8 | 1.226 / 162.1 | 0.253 / 273.2 | 0.736 / 229.6 |
| Object / S3 reader with file provider | 1.702 / 772.8 | 1.703 / 388.3 | 1.037 / 1,048.8 | 1.393 / 897.5 |
| Document / UTF-8 files | 1.249 / 310.5 | 1.124 / 156.8 | 0.299 / 309.6 | 0.711 / 224.2 |

Streaming serially reduces traced peak memory by **47.3%, 49.8% and 49.5%** for
the database, object and document fixtures. Those differences exceed the local
noise allowance. REST's **+3.5%** difference remains within noise, despite retained
batch rows falling from 128 to 16. This shows why a smaller retained payload
cannot be treated as a guaranteed reduction in total Python allocations.

Moving from serial streaming to four-worker FIFO reduces elapsed time by
**67.8%, 79.3%, 39.1% and 73.4%**, respectively, with traced peak increases of
**16.4%, 68.6%, 170.1% and 97.5%**. These are workload/fixture observations, not
predictions for real REST, PostgreSQL, MinIO or document services. In particular,
the object reader still retains a bounded full listing and checkpoint inventory;
batch streaming does not remove those structures.

Process RSS high-water marks include imports and fixture preparation and remain
86.3–92.3 MiB in these captures. The traced-heap differences above do not
establish an equivalent RSS reduction.

## Queue delay and the cost of tenant turns

The fair candidate permits one active job per tenant, with up to four globally.
It lets admitted light-tenant jobs complete while heavy-tenant work remains.
After the two light tenants drain, only one worker processes the heavy tenant.

The table uses light tenant B's descriptive queue p95, pooled across nine jobs
from three trials. This small sample is not an SLO acceptance result.

| Source fixture | FIFO parallel queue p95 | Tenant-turn queue p95 | Total elapsed change, turns vs FIFO |
| --- | --- | --- | --- |
| REST | 312.2 ms | 131.9 ms | +102.8% |
| Database | 203.4 ms | 102.0 ms | +190.5% |
| Object | 903.5 ms | 362.9 ms | +34.3% |
| Document | 245.1 ms | 115.2 ms | +138.0% |

This candidate trades total drain time for lower waiting time for light tenants.
It is evidence for evaluating per-tenant concurrency separately from a global
worker count; it is not a recommendation to ship a universal one-job limit.
The current production outbox keeps its existing serial/FIFO behavior.

## Saturation and recovery

Each saturation case offers 24 heavy jobs followed by four from each light
tenant. The global waiting cap is 16 and the tenant waiting cap is eight.
Every strategy admits eight heavy and all eight light jobs and explicitly rejects
sixteen heavy jobs. The maximum observed waiting queue is **16**, maximum active
count **4**, and retained batch counters return to zero after every case.

The fair strategy's recorded per-tenant active peak is one. Admission remains
arrival-ordered: these caps do not reserve space for an arbitrary later tenant
once a queue is already full. Deterministic tests additionally verify capacity
recovery, bounded executor submission, failed-source/failed-sink acknowledgement
boundaries, resumed content equality, duplicate replay and conflicting or foreign
checkpoints. They do not use wall-clock thresholds to claim fairness.

## Decision and remaining evidence

Keep the existing production limits and default scheduling. The experiment
supports bounded batch consumption as a useful implementation target, while
showing that worker count, adapter overhead and tenant concurrency need separate
budgets. Production adoption must use the existing host's claim fencing,
checkpoint/audit transaction and policy owners; the benchmark's in-memory sink
and scheduler are not substitutes for those boundaries.

**NOT RUN:** live-provider performance, PostgreSQL driver capacity, durable sink
timing, production outbox fairness/backpressure, multi-worker deployment behavior,
SSO/private-network operation and hosted throughput/SLO acceptance. The original
S3/MinIO host tests remain separate functional evidence. REST and document source
adapters remain their own existing issue scopes.

## Artifacts

[`manifest.json`](manifest.json) records SHA-256 and byte sizes for all four data
artifacts. CI runs a fresh CLI smoke matrix, validates the checked experiment
matrices and regenerates each summary in memory to check equality; it does not
gate machine latency.

| Profile | Complete samples and provenance | Derived summary |
| --- | --- | --- |
| Representative | [report](representative.json.gz) | [summary](representative-summary.json) |
| Saturation | [report](saturation.json.gz) | [summary](saturation-summary.json) |

The source revision identifies the capture, while file hashes permit checking
that later documentation/artifact commits retain the measured implementation.
Historical evidence remains historical if the implementation changes later;
rerun the experiment before claiming a new revision's performance.
