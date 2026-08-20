# Backup strategy (card O4.5)

## What needs backing up

AfriMentor AI has two categories of durable state:

| Store | What's in it | Backup mechanism |
|---|---|---|
| Postgres (`pgdata` / `pgdata_staging` volume) | One database per service — `svc_auth`, `svc_intake`, `svc_chat`, `svc_persona`, `svc_rag`, `svc_goals`, `svc_progress`, `svc_insight`, `svc_feedback`, `svc_research`, `svc_voice`, `svc_notify`, `svc_mlflow` (see `infra/postgres/init-databases.sh`) | `scripts/backup/backup-postgres.sh` — `pg_dump --format=custom`, one file per database |
| ChromaDB (`chromadata` / `chromadata_staging` volume) | The RAG corpus's vector index | Not yet covered by a scripted backup — see "Gaps" below |

Everything else (RabbitMQ queues, Redis cache) is transient by design — losing it costs
in-flight events/cache warmth, not durable data, so it's out of scope for backup.

## Running a backup

```bash
scripts/backup/backup-postgres.sh              # dev stack (project "afrimentor")
scripts/backup/backup-postgres.sh afrimentor-staging   # staging stack
```

Writes one `<db>.dump` file per service database to `backups/<UTC timestamp>/`
(gitignored — these are real service data, never committed). There's no
automated schedule yet; running this is a manual step until a real cloud
environment exists to attach a cron/managed-backup job to (tracked as a Sprint
5 production-hardening gap, not part of this card).

## Restoring

```bash
scripts/backup/restore-postgres.sh backups/<timestamp>              # every database
scripts/backup/restore-postgres.sh backups/<timestamp> afrimentor svc_chat  # just one
```

Restores into the database of the same name it was dumped from, in the given
project's Postgres container (`--clean --if-exists` first, so restoring onto
a non-empty database — e.g. re-running a drill — doesn't fail on "already
exists"). Restoring into anything other than a disposable/staging instance is
a deliberate, one-off action, not something to script casually.

## Restore drill (tested 2026-08-19)

Ran a real drill against the dev stack's live `svc_chat` database (12
conversations, 14 messages from real end-to-end testing during this sprint,
not synthetic placeholder rows):

1. `scripts/backup/backup-postgres.sh afrimentor` — backed up all 13
   databases.
2. Recorded source row counts directly against the live database:
   `SELECT count(*) FROM conversations` → **12**, `SELECT count(*) FROM
   messages` → **14**.
3. Started a disposable, throwaway Postgres container (not part of any
   compose project — `docker run --name afrimentor-restore-drill-postgres-1
   postgres:16-alpine`), created an empty `svc_chat` database in it.
4. `scripts/backup/restore-postgres.sh backups/20260819T231501Z
   afrimentor-restore-drill svc_chat`.
5. Re-ran the same counts against the restored copy: **12** conversations,
   **14** messages — exact match. Spot-checked one message's content
   (`"Hi Chioma"`) round-tripped correctly, not just the row count.
6. Tore down the throwaway container (`docker rm -f
   afrimentor-restore-drill-postgres-1`) — the drill never touched the real
   running database, only a disposable copy.

This confirms the dump/restore mechanism itself is sound. It does not confirm
point-in-time recovery (no WAL archiving exists yet — see Gaps) or restoring
under production load.

## Gaps (tracked for Sprint 5, not blocking this card)

- **No backup schedule.** Running `backup-postgres.sh` is manual. Once a real
  cloud environment exists, this needs a cron job or the cloud provider's
  managed-Postgres backup feature, not a script someone has to remember to
  run.
- **No point-in-time recovery.** `pg_dump` captures a snapshot at the moment
  it runs — anything written after the last backup is unrecoverable. WAL
  archiving (or a managed database's continuous backup) closes this gap; not
  needed for the pilot's data volume, but a real requirement before general
  availability.
- **ChromaDB has no scripted backup.** The `chromadata` volume can be backed
  up at the Docker volume level (`docker run --rm -v
  afrimentor_chromadata:/data -v $(pwd)/backups:/backup alpine tar czf
  /backup/chromadata.tar.gz /data`) but this isn't wired into
  `backup-postgres.sh` yet, and the corpus is currently re-ingestible from
  source documents (`services/rag-corpus-service`'s ingest endpoint) if lost
  — lower urgency than the Postgres data, which has no equivalent
  regeneration path.
- **No offsite/cross-region copy.** Dumps currently land on local disk only.
