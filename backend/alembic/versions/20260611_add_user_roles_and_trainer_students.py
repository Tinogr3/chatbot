"""Add user roles and trainer_students association.

Revision ID: 20260611_user_roles
Revises: 20260611_outcome_link
Create Date: 2026-06-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260611_user_roles"
down_revision: Union[str, None] = "20260611_outcome_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    user_columns = {col["name"] for col in sa.inspect(bind).get_columns("users")}
    if "role" not in user_columns:
        if dialect == "postgresql":
            op.execute(
                "ALTER TABLE users "
                "ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'alumno'"
            )
        else:
            with op.batch_alter_table("users", schema=None) as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "role",
                        sa.String(length=20),
                        nullable=False,
                        server_default="alumno",
                    )
                )

    if not sa.inspect(bind).has_table("trainer_students_association"):
        op.create_table(
            "trainer_students_association",
            sa.Column(
                "trainer_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "student_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                primary_key=True,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("trainer_students_association"):
        op.drop_table("trainer_students_association")

    user_columns = {col["name"] for col in sa.inspect(bind).get_columns("users")}
    if "role" in user_columns:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_column("role")
