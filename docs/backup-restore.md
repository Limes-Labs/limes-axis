# Local Demo Backup And Restore

This runbook covers repeatable local demo backups for the Docker Compose
environment. It is intended for SME feedback sessions, design-partner demos and
enterprise evaluation walkthroughs where the same local Axis state must be
preserved or restored.

It is not a production disaster recovery design. Production HA, offsite
retention, WORM audit storage, restore drills, RPO/RTO targets and Kubernetes
operator procedures remain Enterprise work.

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
```

Live demo verification should be run after restore:

```bash
make demo-check-live
```

The runbook is deliberately conservative. If backup/restore commands, artifact
names or safety language are removed, repository tests should fail before a
demo process depends on stale instructions.
