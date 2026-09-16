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

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password  # noqa: E402

ALLOWED_ROLES = {"admin", "researcher", "lead_architect"}


def grant(email: str, role: str, password: str | None = None) -> None:
    if role not in ALLOWED_ROLES:
        raise SystemExit(f"Unknown role {role!r} — expected one of {sorted(ALLOWED_ROLES)}")

    # Ensure tables exist in dev/test SQLite databases
    init_db()

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one_or_none()
        if user is None:
            if password:
                user = User(
                    email=email,
                    password_hash=hash_password(password),
                    roles=role,
                    name=email.split("@")[0],
                )
                db.add(user)
                db.commit()
                print(f"Created new user {email} with role {role!r}")
                return

            raise SystemExit(
                f"No user found with email {email!r}.\n"
                f"To create the user now with this role, provide a password:\n"
                f"    python scripts/grant_console_role.py {email} {role} --password <password>\n"
                f"Or register first through the UI / API and re-run."
            )

        roles = set(user.role_list)
        if role in roles:
            print(f"{email} already has role {role!r} (current roles: {sorted(roles)})")
            return

        roles.add(role)
        user.roles = ",".join(sorted(roles))
        db.commit()
        print(f"Granted {role!r} to {email} (roles now: {sorted(roles)})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Grant console role to an account (or create one)")
    parser.add_argument("email", help="User email address")
    parser.add_argument("role", choices=sorted(ALLOWED_ROLES), help="Role to grant")
    parser.add_argument("--password", "-p", help="Optional password to create user if they do not exist yet")
    args = parser.parse_args()

    grant(args.email, args.role, password=args.password)

