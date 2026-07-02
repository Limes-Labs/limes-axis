# Deployment HA Restart Rehearsal

This runbook defines the first repeatable Kubernetes workload restart
rehearsal for the Limes Axis Helm deployment. It exercises the real `kubectl`
and `helm test` path against an operator-selected cluster context. It is not a
production certification, load test or failover attestation.

The rehearsal exists to make restart behavior observable before customer
production promotion. It captures API and web workload inventory, optionally
requires HPA and PDB resources, restarts the API and web Deployments one at a
time, waits for rollout status and Kubernetes `Available` condition, optionally
polls the API `/ready` endpoint after each restart, and then runs the Helm smoke
test hook.

## Preconditions

Before running against a shared or customer-like cluster, confirm:

- the Kubernetes context is the intended target;
- the release was installed from `infra/helm/limes-axis`;
- external Postgres, TypeDB, Temporal, OIDC and S3-compatible object storage
  dependencies are reachable;
- `secrets.existingSecret` has been created or is synced by External Secrets
  Operator;
- API and web images are scanned, signed and approved for the environment;
- HPA and PDB resources are enabled when the rehearsal is used as a production
  availability gate;
- Ingress, DNS and TLS are configured if `--ready-url` uses an external
  hostname;
- rollback, incident ownership and customer communication criteria are written
  down before the rehearsal starts.

## Plan Mode

Plan mode prints the exact steps without mutating the cluster:

```bash
make deployment-ha-rehearsal-plan
```

For a concrete target:

```bash
cd services/api
uv run python scripts/rehearse_ha_restart.py \
  --repo-root ../.. \
  --plan \
  --release limes-axis \
  --namespace limes-axis \
  --context production-eu \
  --timeout 10m \
  --ready-url https://api.axis.example.com/ready \
  --require-hpa \
  --require-pdb
```

The plan includes deployment and pod inventory capture, optional
`HorizontalPodAutoscaler` and `PodDisruptionBudget` presence checks,
`kubectl rollout restart`, `kubectl rollout status`,
`kubectl wait --for=condition=available`, optional API `/ready` polling after
each workload restart and `helm test`.

## Execute Mode

Execute mode runs the real commands. The Make target requires
`AXIS_KUBE_CONTEXT` so accidental local-default context use fails fast.

```bash
AXIS_KUBE_CONTEXT=production-eu \
AXIS_DEPLOYMENT_HA_ARGS="--release limes-axis --namespace limes-axis --ready-url https://api.axis.example.com/ready --require-hpa --require-pdb" \
make deployment-ha-rehearsal
```

Equivalent direct command:

```bash
cd services/api
uv run python scripts/rehearse_ha_restart.py \
  --repo-root ../.. \
  --execute \
  --release limes-axis \
  --namespace limes-axis \
  --context production-eu \
  --timeout 10m \
  --ready-url https://api.axis.example.com/ready \
  --require-hpa \
  --require-pdb
```

The script runs commands shaped like:

```bash
kubectl --context production-eu -n limes-axis get deployment/limes-axis-api deployment/limes-axis-web -o wide
kubectl --context production-eu -n limes-axis get pods -l app.kubernetes.io/instance=limes-axis -o wide
kubectl --context production-eu -n limes-axis get hpa/limes-axis-api hpa/limes-axis-web
kubectl --context production-eu -n limes-axis get pdb/limes-axis-api pdb/limes-axis-web
kubectl --context production-eu -n limes-axis rollout restart deployment/limes-axis-api
kubectl --context production-eu -n limes-axis rollout status deployment/limes-axis-api --timeout=10m
kubectl --context production-eu -n limes-axis wait --for=condition=available deployment/limes-axis-api --timeout=10m
kubectl --context production-eu -n limes-axis rollout restart deployment/limes-axis-web
kubectl --context production-eu -n limes-axis rollout status deployment/limes-axis-web --timeout=10m
kubectl --context production-eu -n limes-axis wait --for=condition=available deployment/limes-axis-web --timeout=10m
helm test limes-axis --namespace limes-axis --timeout 10m --kube-context production-eu
```

When `--ready-url` is set, the script also polls the URL after each workload
restart and requires a successful HTTP status before continuing.

## Evidence To Save

For each rehearsal, save:

- the command and arguments used;
- current Kubernetes context;
- deployment inventory before and after restart;
- pod inventory before and after restart;
- HPA and PDB output when those checks are required;
- API and web `kubectl rollout status` output;
- API and web `kubectl wait --for=condition=available` output;
- API `/ready` result after each restart when an external URL is available;
- `helm test` output for in-cluster API `/ready` and web checks;
- operator decision on whether the observed behavior passes the promotion gate.

## Limits

This rehearsal verifies controlled restart mechanics. It does not replace load
testing, node failure tests, zone failure tests, database failover drills,
Temporal persistence recovery, object-store disaster recovery, SSO hardening,
secret-manager rotation, incident response drills, customer communication
procedures or penetration testing.
