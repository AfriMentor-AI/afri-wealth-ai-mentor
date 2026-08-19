# Admin Research Console roles (card O4.2)

The Admin Research Console (`apps/admin-research-console`) implements the
RAG Corpus Admin and Persona Consistency Dashboard screens from the Stitch
design system. Both screens hit admin-only backend endpoints, so access is
gated by role.

## Roles

`auth-user-service`'s `users.roles` column is a free-text, comma-separated
list (`User.role_list`, `services/auth-user-service/app/models.py`) — no
schema migration was needed to add new role values. Three roles are
recognized by the console's gate:

| Role | Who | Notes |
|------|-----|-------|
| `admin` | Existing role, pre-O4.2 | Already used to gate `rag-corpus-service`'s admin endpoints (card O3.5). |
| `researcher` | Research & Evaluation team | Read/audit access: persona consistency dashboard, drift alerts, session audit log. |
| `lead_architect` | Engineering leads | Same access as `researcher`, plus corpus-admin write operations (ingest/delete documents). |

The backend does not currently distinguish `researcher` from
`lead_architect` at the endpoint level — both are accepted anywhere `admin`
is (see `_require_admin`/`_CONSOLE_ROLES` in
`services/research-evaluation-service/app/main.py` and
`services/rag-corpus-service/app/api/routes.py`). The two role names exist so
the console UI and audit trail can distinguish who did what; a
finer-grained write/read split can be added later if the pilot needs it —
not required by O4.2's acceptance criteria.

## Granting a role

There is no self-service role-grant endpoint. At pilot scale (a handful of
known accounts) that's deliberate — it avoids building an admin-role-management
API the tickets don't ask for. Grant a role with:

```bash
cd services/auth-user-service
DATABASE_URL=<target-env-database-url> python scripts/grant_console_role.py <email> <role>
```

`<role>` is one of `admin`, `researcher`, `lead_architect`. The script is
idempotent — granting a role a user already has is a no-op.

## How the gate is enforced

Role checks happen at the **service** layer, not the frontend. The API
gateway forwards the caller's verified JWT roles as `X-User-Roles`
(`api-gateway/app/auth.py`); each service's `_require_admin` dependency reads
that header and 403s if none of `admin`/`researcher`/`lead_architect` are
present. The console frontend also redirects unauthorized users away from
gated routes, but that's UX only — someone hitting the API directly without
one of these roles gets a 403 regardless of what the frontend does.
