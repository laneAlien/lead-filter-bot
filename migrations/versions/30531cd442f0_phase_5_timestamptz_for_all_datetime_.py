"""phase 5: timestamptz for all datetime columns

Revision ID: 30531cd442f0
Revises: 8aaa353472e8
Create Date: 2026-06-12 18:20:34.263721

Converts every timestamp column from TIMESTAMP WITHOUT TIME ZONE to
TIMESTAMP WITH TIME ZONE. The code writes timezone-aware ``datetime.now(UTC)``
values; binding those to a naive column makes asyncpg raise DataError on
commit, which previously hung the qualification dialogue on "Анализирую...".

Existing rows hold naive UTC wall-clock values, so the upgrade interprets them
as UTC via ``... AT TIME ZONE 'UTC'``. The downgrade reverses the conversion,
projecting back to UTC wall-clock naive timestamps.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "30531cd442f0"
down_revision: str | Sequence[str] | None = "8aaa353472e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, column, nullable, has_server_default)
_COLUMNS = [
    ("users", "created_at", False, True),
    ("conversations", "started_at", False, True),
    ("conversations", "finished_at", True, False),
    ("messages", "created_at", False, True),
]

_DEFAULT = sa.text("(CURRENT_TIMESTAMP)")


def upgrade() -> None:
    """TIMESTAMP -> TIMESTAMP WITH TIME ZONE, treating stored values as UTC."""
    for table, column, nullable, has_default in _COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=nullable,
            existing_server_default=_DEFAULT if has_default else None,
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    """TIMESTAMP WITH TIME ZONE -> TIMESTAMP, projecting back to UTC wall-clock."""
    for table, column, nullable, has_default in _COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=nullable,
            existing_server_default=_DEFAULT if has_default else None,
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )
