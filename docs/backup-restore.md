# Local Demo Backup And Restore

This runbook covers repeatable local demo backups for the Docker Compose
environment. It is intended for SME feedback sessions, design-partner demos and
enterprise evaluation walkthroughs where the same local Axis state must be
preserved or restored.

It is not a production disaster recovery design. Production HA, offsite
retention, WORM audit storage, full Temporal persistence restore,
full-bucket object-store recovery, RPO/RTO targets and Kubernetes operator
procedures remain Enterprise work.

For Kubernetes environments, the deployment guide now includes a production
backup rehearsal path that captures a Postgres dump and validates its restore
catalog without exposing database connection secrets. That path is a rehearsal
gate, not a complete disaster recovery program.

The deployment guide also includes an isolated production restore rehearsal
path. It restores a captured Postgres dump into a separately configured target
Secret containing `AXIS_POSTGRES_RESTORE_DSN`, and that Secret must be marked
with `limes-axis.io/restore-target=isolated`. This proves the captured dump can
be restored into an isolated Postgres target, but it still does not establish
full production disaster recovery coverage.

The deployment guide also includes a TypeDB recovery rehearsal path. It uses
TypeDB Console `database export` to capture `typedb.schema.typeql` and
`typedb.data`, then uses `database import` against a separate restore target
Secret containing `AXIS_TYPEDB_RESTORE_DATABASE`. That Secret must be marked
with `limes-axis.io/typedb-restore-target=isolated`. This proves the graph
export/import path against an isolated target. Execution requires
`AXIS_TYPEDB_RECOVERY_IMAGE` to point to an operator-supplied image that
contains TypeDB Console. It still does not coordinate application write
quiescence, Temporal recovery, object storage recovery, offsite retention or
RPO/RTO commitments.

The deployment guide also includes an object storage recovery rehearsal path.
It uses MinIO Client `mc alias set`, `mc cp` and `mc cat` to write a bounded
probe object into the configured S3-compatible evidence bucket, copy it into an
isolated restore bucket and verify the restored bytes by checksum. Execution
requires `AXIS_OBJECT_STORAGE_RECOVERY_IMAGE` and an isolated restore target
Secret containing `AXIS_CONNECTOR_EXPORT_S3_RESTORE_BUCKET` plus endpoint and
credential keys. This proves the source-to-isolated-target object copy path,
but it still does not establish provider KMS review, customer bucket-policy
approval, full-bucket restore, legal operations or RPO/RTO commitments.

The deployment guide also includes a Temporal recovery rehearsal path. It uses
Temporal CLI `operator namespace describe`, `workflow list` and
`workflow show --output json` from an isolated non-root Pod to capture
checksummed cluster, namespace and selected workflow-history evidence.
Execution requires `AXIS_TEMPORAL_RECOVERY_IMAGE` and an isolated recovery
Secret containing `AXIS_TEMPORAL_RECOVERY_WORKFLOW_ID`, marked with
`limes-axis.io/temporal-recovery-target=isolated`. This proves a read-only
Temporal namespace/history evidence path, but it still does not restore
Temporal persistence, replay workflow code, validate archival or establish
RPO/RTO commitments.

The deployment readiness endpoint includes a public-safe
`production_dr_procedures` gate. It is ready only when the operator has
configured the presence of an approved DR runbook, RPO/RTO definition, rehearsal
evidence, restore ownership and customer approval through the `AXIS_DR_*`
settings in the Helm chart. The endpoint returns only booleans and does not
print runbook URLs, owner names, approval records, customer contacts or
customer-specific evidence locations.

## What Is Captured

The local backup command captures:

- `postgres.dump`: a custom-format `pg_dump` of the local Axis Postgres
  database. In the current Compose topology this also includes Temporal
  metadata because Temporal uses the same Postgres service.
- `minio-data.tar.gz`: a tar archive of the local MinIO `/data` volume.
- `typedb-data.tar.gz`: a tar archive of the local TypeDB `/var/lib/typedb/data`
  volume.
- `manifest.json`: artifact metadata with file sizes, SHA-256 checksums,
  schema version, Compose file path and restore warnings.

## Safety Rules

- Run this only against the local Docker Compose demo stack.
- Do not enter customer secrets into the demo stack before capturing artifacts.
- Quiesce API, worker and connector writes before backup or restore.
- Treat restore as destructive: it replaces local Postgres, MinIO and TypeDB
  demo state.
- Restart TypeDB and API processes after restoring local volume archives.
- Never present this runbook as production backup, restore or compliance
  evidence.

## Plan A Backup

Inspect the exact Docker commands and output paths without touching local data:

```bash
make demo-backup-plan
```

The command prints JSON with the planned backup directory, artifacts and Docker
Compose commands.

## Create A Local Backup

Start the local services and stop application writes before running:

```bash
make demo-stack-up
make demo-backup-local
```

By default, artifacts are written under `.axis/backups/<backup-id>/`. The
backup id is UTC time formatted as `YYYYMMDDTHHMMSSZ`.

The backup is successful only after `manifest.json` is written with checksums
for `postgres.dump`, `minio-data.tar.gz` and `typedb-data.tar.gz`.

## Restore A Local Backup

Restore requires an explicit backup directory and confirmation flag through the
Make target:

```bash
AXIS_BACKUP_DIR=.axis/backups/<backup-id> make demo-restore-local
```

The underlying script refuses to run without `--confirm-restore`.

Before restore:

- stop API, worker and web processes;
- keep the Docker Compose services available;
- confirm the selected `AXIS_BACKUP_DIR` is the intended backup.

After restore:

- restart TypeDB if it was running during the archive replacement;
- run `make demo-db-upgrade` to re-apply any migrations introduced after the
  backup was taken;
- start `make demo-api` and `make demo-web`;
- run `make demo-check-live`.

## Direct Script Usage

The Make targets call:

```bash
cd services/api
uv run python scripts/demo_backup_restore.py --repo-root ../.. plan
uv run python scripts/demo_backup_restore.py --repo-root ../.. backup
uv run python scripts/demo_backup_restore.py --repo-root ../.. restore \
  --backup-dir .axis/backups/<backup-id> \
  --confirm-restore
```

Use `restore --dry-run --confirm-restore` to inspect restore commands from a
manifest without writing local services.

## Verification

Static demo verification checks the runbook and Make targets:

```bash
make demo-check
```

Static deployment verification checks the production backup and restore
rehearsal targets:

```bash
make deployment-check
make deployment-backup-rehearsal-plan
make deployment-restore-rehearsal-plan
make deployment-typedb-recovery-rehearsal-plan
make deployment-object-storage-recovery-rehearsal-plan
make deployment-temporal-recovery-rehearsal-plan
```

Live demo verification should be run after restore:

```bash
make demo-check-live
```

The runbook is deliberately conservative. If backup/restore commands, artifact
names or safety language are removed, repository tests should fail before a
demo process depends on stale instructions.
