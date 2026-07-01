# Deployment Rollout Rehearsal

This runbook defines the first repeatable Kubernetes rollout rehearsal for the
Limes Axis Helm chart. It exercises the real `helm` and `kubectl` path against
an operator-selected cluster context. It is not a production certification.

The rehearsal exists to make upgrade and rollback behavior observable before a
customer production promotion. It checks that the chart renders, that the API
and web Deployments complete rollout, that the API `/ready` endpoint can be
checked through an operator-provided URL, and that `helm rollback` can return
the release to a previous revision when requested.

## Preconditions

Before running against a shared or customer-like cluster, confirm:

- the Kubernetes context is the intended target;
- external Postgres, TypeDB, Temporal, OIDC and S3-compatible object storage
  dependencies are reachable;
- `secrets.existingSecret` has been created or is synced by External Secrets
  Operator;
- API and web image tags point to scanned, signed and approved images for the
  environment;
- Ingress, DNS and TLS are configured if `--ready-url` uses an external
  hostname;
- rollback criteria and ownership are written down before the rehearsal starts.

## Plan Mode

Plan mode prints the exact steps without mutating the cluster:

```bash
make deployment-rollout-rehearsal-plan
```

For a concrete target:

```bash
cd services/api
uv run python scripts/rehearse_deployment_rollout.py \
  --repo-root ../.. \
  --plan \
  --release limes-axis \
  --namespace limes-axis \
  --context production-eu \
  --ready-url https://api.axis.example.com/ready \
  --rollback \
  --rollback-revision 3
```

The plan includes `helm upgrade --install`, `kubectl rollout status` for the
API and web Deployments, Helm status capture, optional API `/ready` polling and
optional `helm rollback`.

## Execute Mode

Execute mode runs the real commands. The Make target requires
`AXIS_KUBE_CONTEXT` so accidental local-default context use fails fast.

```bash
AXIS_KUBE_CONTEXT=production-eu \
AXIS_DEPLOYMENT_ROLLOUT_ARGS="--release limes-axis --namespace limes-axis --ready-url https://api.axis.example.com/ready --rollback --rollback-revision 3" \
make deployment-rollout-rehearsal
```

Equivalent direct command:

```bash
cd services/api
uv run python scripts/rehearse_deployment_rollout.py \
  --repo-root ../.. \
  --execute \
  --release limes-axis \
  --namespace limes-axis \
  --context production-eu \
  --values ../../ops/production-values.yaml \
  --set api.image.tag=0.1.0 \
  --set web.image.tag=0.1.0 \
  --ready-url https://api.axis.example.com/ready \
  --rollback \
  --rollback-revision 3
```

The script runs:

```bash
kubectl config current-context
helm lint infra/helm/limes-axis
helm upgrade --install limes-axis infra/helm/limes-axis --namespace limes-axis --create-namespace --wait --timeout 10m
kubectl -n limes-axis rollout status deployment/limes-axis-api --timeout=10m
kubectl -n limes-axis rollout status deployment/limes-axis-web --timeout=10m
helm status limes-axis --namespace limes-axis
helm rollback limes-axis 3 --namespace limes-axis --wait --timeout 10m
```

When `--ready-url` is set, the script also polls the URL and requires a
successful HTTP status before the rehearsal continues.

## Evidence To Save

For each rehearsal, save:

- the command and arguments used;
- current Kubernetes context;
- Helm release status before and after rollback;
- API and web `kubectl rollout status` output;
- pod inventory after upgrade and after rollback;
- API `/ready` result when an external URL is available;
- operator decision on whether the observed behavior passes the promotion gate.

## Limits

This rehearsal verifies deployment mechanics. It does not replace production
load testing, cluster failover testing, data backup/restore drills, SSO
hardening, secret rotation, object-store retention review, support operations
or penetration testing.
