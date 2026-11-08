"""Core v3: ck_profiles_pool treats a NULL result as a violation.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-08
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_V2 = (
    "(age IS NULL AND pool IS NULL) OR (age < 18 AND pool = 'minor')"
    " OR (age >= 18 AND pool = 'adult')"
)
_V3 = f"COALESCE({_V2}, false)"


def upgrade() -> None:
    op.drop_constraint("ck_profiles_pool", "profiles", type_="check")
    op.create_check_constraint("ck_profiles_pool", "profiles", _V3)


def downgrade() -> None:
    op.drop_constraint("ck_profiles_pool", "profiles", type_="check")
    op.create_check_constraint("ck_profiles_pool", "profiles", _V2)
