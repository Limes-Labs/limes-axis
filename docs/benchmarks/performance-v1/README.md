# Initial performance baseline — 2026-09-07

This capture measures current API overhead with the
[versioned local workload contract](../../performance-baseline.md). Application
code is unchanged by this issue. Results are local ASGI/SQLite observations,
with explicit identity/provider/workflow fixtures, and not production SLO proof.

The three-trial [initial SME capture](before-sme.json.gz) retains all individual
arrivals, query timing, resource samples and source hashes. Eleven of its twelve
journey phases meet the local budgets; the third console phase records one late
arrival and therefore fails. That failed observation is retained. The machine
also had concurrent system and Python workloads during this capture; an idle
machine comparison cannot be claimed.

The complete enterprise, duration and profiling evidence is being collected in
the implementation PR. This report will record those artifacts and the final
comparison outcome before the issue is closed. Deployment SLOs and the
unimplemented full-text search journey remain `NOT RUN`.
