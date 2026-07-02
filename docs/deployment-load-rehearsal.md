# Deployment Load Rehearsal

This runbook defines the first bounded Kubernetes load rehearsal for the Limes
Axis Helm deployment. It exercises the real `kubectl create job`,
`kubectl wait`, `kubectl logs` and cleanup path against an operator-selected
cluster context by running short-lived `fortio` Jobs inside the release
namespace.

The rehearsal exists to make basic API and web behavior observable under a
controlled request stream before customer production promotion. It is not a
production certification, capacity plan, denial-of-service test, node failover
attestation or SLO proof.

## Preconditions

Before running against a shared or customer-like cluster, confirm:

- the Kubernetes context is the intended target;
- the release was installed from `infra/helm/limes-axis`;
- API and web pods are healthy before the rehearsal starts;
- the namespace can pull the configured Fortio image;
- network policies allow the Job pod to reach the target service URLs;
- the QPS, connection count and duration have been approved for the
  environment;
- API rate limiting expectations are known for the selected target URLs;
- incident ownership and rollback criteria are written down before execute
  mode starts.

## Plan Mode

Plan mode prints the exact steps without mutating the cluster:

```bash
make deployment-load-rehearsal-plan
```

For a concrete target:

```bash
cd services/api
uv run python scripts/rehearse_load.py \
  --repo-root ../.. \
  --plan \
  --release limes-axis \
  --namespace limes-axis \
  --context production-eu \
  --duration 90s \
  --qps 25 \
  --connections 5 \
  --target api-ready=http://limes-axis-api:8000/ready \
  --target web-home=http://limes-axis-web:3000/
```

When no `--target` is provided, the script targets the in-cluster API `/ready`
and web home service URLs for the release name:

- `http://<release>-api:8000/ready`
- `http://<release>-web:3000/`

## Execute Mode

Execute mode runs the real commands. The Make target requires
`AXIS_KUBE_CONTEXT` so accidental local-default context use fails fast.

```bash
AXIS_KUBE_CONTEXT=production-eu \
AXIS_DEPLOYMENT_LOAD_ARGS="--release limes-axis --namespace limes-axis --duration 90s --qps 25 --connections 5" \
make deployment-load-rehearsal
```

Equivalent direct command:

```bash
cd services/api
uv run python scripts/rehearse_load.py \
  --repo-root ../.. \
  --execute \
  --release limes-axis \
  --namespace limes-axis \
  --context production-eu \
  --duration 90s \
  --qps 25 \
  --connections 5
```

The script runs commands shaped like:

```bash
kubectl --context production-eu config current-context
kubectl --context production-eu -n limes-axis delete job limes-axis-load-api-ready --ignore-not-found=true
kubectl --context production-eu -n limes-axis create job limes-axis-load-api-ready --image=fortio/fortio:1.69.3 -- load -quiet -qps 25 -c 5 -t 90s http://limes-axis-api:8000/ready
kubectl --context production-eu -n limes-axis wait --for=condition=complete job/limes-axis-load-api-ready --timeout=10m
kubectl --context production-eu -n limes-axis logs job/limes-axis-load-api-ready
kubectl --context production-eu -n limes-axis delete job limes-axis-load-api-ready
```

The same lifecycle is repeated for every configured target. Jobs are deleted
after logs are collected by default. Use `--keep-jobs` only when an operator
needs to preserve Kubernetes Job objects for cluster-side debugging.

## Evidence To Save

For each rehearsal, save:

- the command and arguments used;
- current Kubernetes context;
- target names and URLs;
- configured image, duration, QPS, connection count and timeout;
- `kubectl create job` output for every target;
- `kubectl wait --for=condition=complete` output for every target;
- `kubectl logs` output for every Fortio Job;
- any rate-limit or error behavior observed in API logs;
- operator decision on whether the observed behavior passes the promotion gate.

## Limits

This load rehearsal verifies a bounded request stream through Kubernetes Job
execution and service reachability. It does not replace customer-profile load
testing, autoscaler tuning, capacity planning, sustained soak tests,
interrupted rollout-drain exercises, node failure tests, zone failure tests,
database failover drills, incident response drills or penetration testing.
