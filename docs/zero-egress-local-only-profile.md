# Local-only egress profile: scoped DNS and declared local destinations

[#870](https://github.com/Limes-Labs/limes-axis/issues/870) (parent #473) adds
the opt-in strict egress profile to the Helm chart:
`networkPolicy.egressMode: local_only`, demonstrated by
[`infra/helm/limes-axis/profiles/local-only.yaml`](../infra/helm/limes-axis/profiles/local-only.yaml).
The service graph is derived from the #869 runtime dependency inventory
([`docs/runtime-dependencies.json`](runtime-dependencies.json) and
[`docs/runtime-dependencies.local-profile.json`](runtime-dependencies.local-profile.json)).

## The gap this closes

The chart had three egress modes. `offline` removed the generic external-port
rule but still rendered an unconditional TCP/UDP DNS egress rule with **no
destination selector**, and it did not model the required local dependencies as
an explicit service graph. Rendering `offline` was therefore not evidence of the
stricter #473 posture.

`local_only` renders no unrestricted DNS destination, no arbitrary port-only
egress rule and no all-address CIDR allow rule:

- DNS is scoped to the configured resolvers (TCP and UDP on `dnsPort`, IPv4 and
  IPv6 addresses are both expressible).
- Every other egress rule names an explicit local destination — a same-namespace
  `podSelector`, a `namespaceSelector` plus `podSelector`, or a bounded
  `ipBlock` — together with the ports it may reach.
- A missing or unbounded binding fails rendering with an actionable message
  instead of widening egress.

The ordinary `port_allowlist`, `restricted` and `offline` modes keep their
documented behavior. `local_only` is opt-in.

## Configuration

```yaml
networkPolicy:
  enabled: true
  egressMode: local_only
  localOnly:
    dns:
      mode: cluster            # cluster | node_local | explicit
      namespace: kube-system
      podSelector:
        k8s-app: kube-dns
      nodeLocalCidr: 169.254.20.10/32
      resolvers: []            # used when mode: explicit
    services:
      - name: operational-database
        state: local           # local | omitted
        podSelector:
          app.kubernetes.io/name: postgres
        ports:
          - protocol: TCP
            port: 5432
      - name: model-inference
        state: omitted
        reason: No compatible local inference runtime is qualified.
```

Each `services` entry is either `state: local` (a namespace, a same-namespace
`podSelector`, or a bounded `ipBlock`, plus at least one port) or `state:
omitted` with a written reason. The required names follow the #869 dependency
ids so the rendered graph stays traceable to the inventory:

| Required service          | #869 dependencies it represents                                  |
| ------------------------- | ---------------------------------------------------------------- |
| `identity-validation`     | `identity-validation`, `identity-token-exchange`, `identity-browser-navigation` |
| `operational-database`    | `operational-database`                                            |
| `workflow-engine`         | `workflow-engine`                                                 |
| `artifact-object-store`   | `artifact-object-store`                                           |
| `model-inference`         | `model-inference` (omitted in the sample local-only profile)      |

`distributed-rate-limit`, `ontology-store` and `telemetry-export` are optional
entries. A `podSelector` without `namespace` resolves to the release namespace;
services in another namespace must declare `namespace`, and off-cluster services
must declare a bounded `ipBlock`.

### DNS modes

- **`cluster`** (default): pins the cluster DNS service pods by namespace and
  pod label. No other DNS destination is reachable.
- **`node_local`**: pins node-local DNS pods and the documented link-local
  resolver address (`nodeLocalCidr`, default `169.254.20.10/32`). Use it only
  where the CNI and node network support node-local DNS.
- **`explicit`**: renders exactly the declared `resolvers`, each a namespace
  plus optional `podSelector`, or a bounded `ipBlock`. It fails when the list is
  empty.

## What rendering does not prove

Rendering the NetworkPolicy is a policy check, not evidence of isolation. Do not
treat a green `helm template` as air-gapping:

1. **CNI enforcement.** NetworkPolicies do nothing unless the CNI implements
   them. A cluster whose network plugin ignores policies, or whose
   node-network path bypasses the CNI, can still reach external addresses.
   Verify policy support and enforcement in the target cluster explicitly.
2. **Additive policies.** NetworkPolicies are additive: a second, broader policy
   selecting the same pods, or a default-allow policy in the namespace, can
   re-open egress. Enumerate every policy that selects the Axis pods. Do not
   change cluster-global DNS or firewall configuration automatically.
3. **Upstream resolver forwarding.** A resolver that forward-resolves public
   names re-introduces external reachability even when pods can reach only the
   resolver. This is an operator/runtime condition that cannot be proven from a
   pod policy: configure the local resolvers so they do not forward public names
   outside the isolated environment.
4. **Node-local DNS support.** `node_local` depends on the node network and CNI
   forwarding the link-local address. Where that is unsupported, use `cluster`
   or `explicit`.
5. **Unsupported node-network cases.** CNIs that implement policies only for
   certain address families, or that route pod egress outside the CNI data
   path, are out of scope of this profile. Cover supported IPv4 and IPv6
   destinations explicitly in `services` and `resolvers`.

## Reproducible checks

```bash
helm template limes-axis infra/helm/limes-axis \
  -f infra/helm/limes-axis/profiles/local-only.yaml
make deployment-profile-render-check
```

`deployment-profile-render-check` renders every shipped profile and, for the
local-only profile, parses the rendered `NetworkPolicy` to assert that no egress
rule is port-only, no `ipBlock` covers all addresses, DNS is scoped, every
declared local service is represented, and the smoke-test fixture only adds the
bounded intra-release rule (the local destinations survive with the fixture
disabled).

## Scope and follow-ups

This slice delivers the manifest/profile and the rendering checks it actually
ran. It does not run a live rehearsal and does not claim observed isolation:
[#871](https://github.com/Limes-Labs/limes-axis/issues/871) separates configured
posture from observed isolation in deployment readiness, and
[#872](https://github.com/Limes-Labs/limes-axis/issues/872) must demonstrate both
local connectivity and external denial in an isolated environment with bounded
evidence. Offline bundle production remains
[#474](https://github.com/Limes-Labs/limes-axis/issues/474), and the build and
install dependency inventory remains part of
[#869](https://github.com/Limes-Labs/limes-axis/issues/869).
