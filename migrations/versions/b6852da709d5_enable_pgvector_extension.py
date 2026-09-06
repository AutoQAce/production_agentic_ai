"""enable pgvector extension

Revision ID: b6852da709d5
Revises: 
Create Date: 2026-09-06 16:30:27.413914

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6852da709d5'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make the vector type available in this database.

    Not a table -- which is precisely why it has to live here rather than in a SQLModel class.
    `SQLModel.metadata.create_all()` builds tables from Python classes and has no way to express
    `CREATE EXTENSION`, a GRANT, or a row-level-security policy. Most of the 🔴-finance controls in
    Step 2 (append-only audit table with no UPDATE/DELETE grants, per-tenant RLS) are the same shape:
    enforced by the database, expressible only in a migration.

    IF NOT EXISTS so re-running against an already-migrated database is a no-op, and so this works
    against the pgvector image where the extension may already be present.
    """
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """Drop the extension.

    Plain DROP, not CASCADE: if a later migration has created a vector column, this must fail loudly
    rather than silently delete that column and its data as collateral.
    """
    op.execute("DROP EXTENSION IF EXISTS vector")
