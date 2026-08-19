"""Grant an Admin Research Console role to an existing account (card O4.2).

The console is gated to admin/researcher/lead_architect roles (see
docs/deployment/rbac-console-roles.md). There's no self-service role-grant
endpoint by design — pilot scale is a handful of known accounts, so a one-off
script run against the target database is simpler and has a smaller attack
surface than a new admin API.

Usage (from services/auth-user-service, with DATABASE_URL pointed at the
target environment):
    python scripts/grant_console_role.py researcher@afrimentor.ai researcher
    python scripts/grant_console_role.py lead@afrimentor.ai lead_architect
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402

ALLOWED_ROLES = {"admin", "researcher", "lead_architect"}


def grant(email: str, role: str) -> None:
    if role not in ALLOWED_ROLES:
        raise SystemExit(f"Unknown role {role!r} — expected one of {sorted(ALLOWED_ROLES)}")

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one_or_none()
        if user is None:
            raise SystemExit(f"No user found with email {email!r}")

        roles = set(user.role_list)
        if role in roles:
            print(f"{email} already has role {role!r} (current roles: {sorted(roles)})")
            return

        roles.add(role)
        user.roles = ",".join(sorted(roles))
        db.commit()
        print(f"Granted {role!r} to {email} (roles now: {sorted(roles)})")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    grant(sys.argv[1], sys.argv[2])
