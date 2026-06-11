"""Añade learning_outcome_id a learning_units (enlace cuadrante ↔ competencias).

Revision ID: 20260611_outcome_link
Revises:
Create Date: 2026-06-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260611_outcome_link"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("learning_units", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("learning_outcome_id", sa.Integer(), nullable=True)
        )
        batch_op.create_index(
            "ix_learning_units_outcome",
            ["learning_outcome_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_learning_units_learning_outcome_id",
            "learning_outcomes",
            ["learning_outcome_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("learning_units", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_learning_units_learning_outcome_id",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_learning_units_outcome")
        batch_op.drop_column("learning_outcome_id")
