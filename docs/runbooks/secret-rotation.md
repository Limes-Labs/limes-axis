# Runbook: Secret Rotation

Playbook for rotating the Limes Axis runtime secrets in a Kubernetes
deployment using the repository's active/staged rehearsal tooling. It wraps
`services/api/scripts/rehearse_secret_rotation.py`, the
`deployment-secret-rotation-rehearsal` Make targets and the contract tests in
`services/api/tests/test_secret_rotation_rehearsal.py`. See also the secret
rotation section of [`docs/deployment.md`](../deployment.md).

This is an operational baseline for evaluation and hardening environments.
Upstream secret-manager rotation (Vault/KMS/ExternalSecrets source-of-truth
rotation) and customer-specific approval workflows are outside this runbook.

## What Rotates

The runtime Secret consumed by the API/worker workloads. The rehearsal
verifies these keys exist in both the active and staged Secrets:

- `AXIS_POSTGRES_DSN`
- `AXIS_TYPEDB_USERNAME`
- `AXIS_TYPEDB_PASSWORD`
- `AXIS_AUDIT_LEDGER_SIGNING_SECRET`
- `AXIS_CONNECTOR_EXPORT_S3_ACCESS_KEY`
- `AXIS_CONNECTOR_EXPORT_S3_SECRET_KEY`

## Safety Properties (Enforced By The Tooling)

- The rehearsal never prints, stores or exports raw secret values: evidence is
  redacted key status (`secret-rotation.keys`), SHA-256 fingerprints
  (`secret-rotation.sha256`) and a summary (`secret-rotation.summary.json`).
- Comparison runs `cmp -s` and `sha256sum` inside an isolated, non-root
  (`runAsUser 10001`, all capabilities dropped, `RuntimeDefault` seccomp)
  rehearsal pod that mounts both Secrets read-only.
- The staged Secret name is validated: it must differ from the active Secret
  and must not be the runtime Secret itself, so the rehearsal cannot be
  pointed at production state by accident.
- The staged Secret must carry the annotation
  `limes-axis.io/secret-rotation-target=staged`.
- Unsafe identifiers (namespaces, rotation ids, images) are rejected before
  any `kubectl` command is built. `--execute` refuses to run with the
  placeholder image; you must supply an image containing `sh`, `cmp` and
  `sha256sum`.

## Procedure

### 1. Stage the new secret

Create the staged Secret next to the active one (default names
`limes-axis-runtime` / `limes-axis-runtime-next`) with the new values for
every required key, and annotate it:

```bash
kubectl -n limes-axis annotate secret limes-axis-runtime-next \
  limes-axis.io/secret-rotation-target=staged
```

If ExternalSecrets manages the runtime Secret, stage through the external
store and let the operator materialize the staged Secret.

### 2. Review the rehearsal plan (no cluster access needed)

```bash
make deployment-secret-rotation-rehearsal-plan
```

This prints every `kubectl` step the execution would run: fetch both Secrets,
verify the staged annotation, launch the isolated comparison pod, confirm each
required key, compare values by fingerprint and collect evidence. Nothing is
executed.

### 3. Execute the rehearsal

```bash
AXIS_KUBE_CONTEXT=<kube-context> \
AXIS_SECRET_ROTATION_IMAGE=<image-with-sh-cmp-sha256sum> \
make deployment-secret-rotation-rehearsal
```

Pass extra script options through `AXIS_SECRET_ROTATION_ARGS`, for example
`--namespace`, `--active-secret`, `--staged-secret`, `--rotation-id`,
`--timeout`, `--allow-unchanged` or `--keep-pod` (see `--help` on
`services/api/scripts/rehearse_secret_rotation.py`).

Evidence lands under `.axis/secret-rotation/<rotation-id>/`. Review it:
every required key present in both Secrets, and changed keys showing new
fingerprints. By default an unchanged staged Secret fails the rehearsal
(`--allow-unchanged` overrides for partial rotations).

### 4. Promote

Update the workloads to consume the staged values (either point the chart's
secret reference at the staged Secret or copy the staged data over the active
Secret through your normal change process), then roll the deployments:

```bash
kubectl -n limes-axis rollout restart deployment -l app.kubernetes.io/name=limes-axis
kubectl -n limes-axis rollout status deployment -l app.kubernetes.io/name=limes-axis
```

Confirm `/ready` and `/deployment/readiness` are healthy afterwards.

### 5. Revoke and clean up

- Revoke the old credentials at their sources (Postgres role password, TypeDB
  user, object-store access keys) once the rollout is stable.
- Rotating `AXIS_AUDIT_LEDGER_SIGNING_SECRET` changes the signing key for new
  export bundles; keep the retired key id recorded so previously signed
  bundles remain verifiable.
- Delete the staged Secret (or re-stage it for the next cycle) and archive the
  evidence directory with your change ticket.

## Rollback

If the rollout degrades, point the workloads back at the previous Secret and
restart; do not revoke old credentials until the new ones are proven. The
rehearsal pod is removed automatically unless `--keep-pod` was set.

## Verification And Cadence

- `services/api/tests/test_secret_rotation_rehearsal.py` keeps the rehearsal
  contract honest in CI (step construction, non-root pod spec, unsafe-input
  rejection, no raw secret material in output).
- Rehearse on a fixed cadence and before any production rotation; record the
  rotation id and evidence location each time.
- For suspected credential exposure, treat rotation as part of
  [`docs/runbooks/incident-response.md`](./incident-response.md) (S1) rather
  than routine rotation.
