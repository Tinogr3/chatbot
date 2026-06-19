"""Add trainer_projects and trainer_project_students tables.

Revision ID: 20260611_trainer_projects
Revises: 20260611_user_roles
Create Date: 2026-06-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260611_trainer_projects"
down_revision: Union[str, None] = "20260611_user_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("trainer_projects"):
        op.create_table(
            "trainer_projects",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("trainer_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("session_id", sa.String(length=255), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["trainer_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id"),
        )
        op.create_index(
            op.f("ix_trainer_projects_trainer_id"),
            "trainer_projects",
            ["trainer_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_trainer_projects_session_id"),
            "trainer_projects",
            ["session_id"],
            unique=True,
        )

    if not inspector.has_table("trainer_project_students"):
        op.create_table(
            "trainer_project_students",
            sa.Column("trainer_project_id", sa.Integer(), nullable=False),
            sa.Column("student_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["trainer_project_id"], ["trainer_projects.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("trainer_project_id", "student_id"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("trainer_project_students"):
        op.drop_table("trainer_project_students")

    if inspector.has_table("trainer_projects"):
        op.drop_index(op.f("ix_trainer_projects_session_id"), table_name="trainer_projects")
        op.drop_index(op.f("ix_trainer_projects_trainer_id"), table_name="trainer_projects")
        op.drop_table("trainer_projects")
