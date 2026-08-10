"""C2.4 guardrail columns on messages

Revision ID: 2b865b2b30ba
Revises: a08ba172d89e
Create Date: 2026-08-08

Adds the two columns card C2.4 introduced on ``messages``. PR #64 shipped these
in the model but had no migration framework to apply them, so its description
carried raw DDL for an operator to run by hand; this revision replaces that step.

``guardrail_categories`` is added nullable, backfilled to ``[]``, and only then
made NOT NULL — adding a NOT NULL column with no default to a table that already
has rows fails outright. ``guardrail_action`` stays nullable by design: a turn
written before C2.4, or one written while GUARDRAILS_ENABLED was off, is
genuinely unscreened, which is a different fact from having been screened and
allowed. The research evaluation needs to tell those apart.

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2b865b2b30ba'
down_revision: str | None = 'a08ba172d89e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('guardrail_action', sa.String(length=20), nullable=True))
    op.add_column('messages', sa.Column('guardrail_categories', sa.JSON(), nullable=True))
    op.execute("UPDATE messages SET guardrail_categories = '[]' WHERE guardrail_categories IS NULL")
    with op.batch_alter_table('messages') as batch_op:
        batch_op.alter_column('guardrail_categories', existing_type=sa.JSON(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('messages') as batch_op:
        batch_op.drop_column('guardrail_categories')
        batch_op.drop_column('guardrail_action')
