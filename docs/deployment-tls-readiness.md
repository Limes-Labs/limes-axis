# Deployment TLS Readiness Rehearsal

This runbook defines the first Kubernetes TLS readiness rehearsal for the Limes
Axis Helm deployment. It exercises the real `kubectl`, `dig +short`,
`openssl s_client` and `curl` path against operator-selected Ingress hosts.

The rehearsal exists to make TLS, DNS and cert-manager readiness observable
before customer production promotion. It is not certificate automation,
domain-control validation, a compliance certification, a penetration test or a
guarantee that renewal operations are production ready.

## Preconditions

Before running against a shared or customer-like cluster, confirm:

- the Kubernetes context is the intended target;
- the release was installed from `infra/helm/limes-axis` with
  `ingress.enabled=true`;
- the Ingress controller is healthy and assigned to the expected
  `ingress.className`;
- DNS records for each host point at the intended Ingress endpoint;
- `ingress.tls[]` references the expected Kubernetes TLS Secret;
- cert-manager and the selected Issuer or ClusterIssuer are installed when
  `ingress.certManager.enabled=true`;
- firewall, proxy and enterprise TLS inspection behavior are understood before
  interpreting external handshake failures.

## Plan Mode

Plan mode prints the exact steps without mutating the cluster:

```bash
make deployment-tls-readiness-plan
```

For a concrete target:

```bash
cd services/api
uv run python scripts/rehearse_tls_readiness.py \
  --repo-root ../.. \
  --plan \
  --release limes-axis \
  --namespace limes-axis \
  --context production-eu \
  --tls-secret axis-tls \
  --issuer-name letsencrypt-prod \
  --issuer-kind ClusterIssuer \
  --host axis.example.com=https://axis.example.com/ \
  --host api.axis.example.com=https://api.axis.example.com/ready
```

When no `--host` is provided, the plan uses the public example hosts from the
deployment guide:

- `axis.example.com=https://axis.example.com/`
- `api.axis.example.com=https://api.axis.example.com/ready`

## Execute Mode

Execute mode runs the real commands. The Make target requires
`AXIS_KUBE_CONTEXT` so accidental local-default context use fails fast.

```bash
AXIS_KUBE_CONTEXT=production-eu \
AXIS_DEPLOYMENT_TLS_ARGS="--release limes-axis --namespace limes-axis --tls-secret axis-tls --issuer-name letsencrypt-prod --host axis.example.com=https://axis.example.com/ --host api.axis.example.com=https://api.axis.example.com/ready" \
make deployment-tls-readiness
```

Equivalent direct command:

```bash
cd services/api
uv run python scripts/rehearse_tls_readiness.py \
  --repo-root ../.. \
  --execute \
  --release limes-axis \
  --namespace limes-axis \
  --context production-eu \
  --tls-secret axis-tls \
  --issuer-name letsencrypt-prod \
  --host axis.example.com=https://axis.example.com/ \
  --host api.axis.example.com=https://api.axis.example.com/ready
```

The script runs commands shaped like:

```bash
kubectl --context production-eu config current-context
kubectl --context production-eu -n limes-axis get ingress limes-axis -o wide
kubectl --context production-eu -n limes-axis describe ingress limes-axis
kubectl --context production-eu -n limes-axis get secret axis-tls -o 'jsonpath={.type}'
kubectl --context production-eu get clusterissuer letsencrypt-prod -o wide
kubectl --context production-eu -n limes-axis get certificate axis-tls -o wide
kubectl --context production-eu -n limes-axis wait --for=condition=Ready certificate/axis-tls --timeout=10m
dig +short axis.example.com
openssl s_client -servername axis.example.com -connect axis.example.com:443 -brief
curl --fail --silent --show-error --location --max-time 10 https://axis.example.com/
```

When a cert-manager Certificate is configured, the readiness gate includes
`kubectl wait --for=condition=Ready` for the Certificate resource before DNS
and external HTTPS checks are evaluated.

Use `--dns-server` when the rehearsal must query a specific resolver:

```bash
uv run python scripts/rehearse_tls_readiness.py \
  --repo-root ../.. \
  --plan \
  --dns-server 1.1.1.1
```

## Evidence To Save

For each rehearsal, save:

- the command and arguments used;
- current Kubernetes context;
- Ingress `get` and `describe` output;
- TLS Secret type output;
- cert-manager Issuer or ClusterIssuer output when configured;
- cert-manager Certificate `get`, `describe` and readiness wait output when a
  Certificate is configured;
- `dig +short` output for every host;
- `openssl s_client` handshake output for every host;
- `curl` status for every HTTPS URL;
- operator decision on whether TLS/DNS readiness passes the promotion gate.

## Limits

This TLS readiness rehearsal verifies observable Ingress, cert-manager, DNS,
TLS handshake and HTTPS reachability behavior. It does not automate certificate
issuance, prove DNS ownership, validate renewal before expiry, configure HSTS,
verify CDN or WAF policy, replace external penetration testing, or certify
customer production readiness.
