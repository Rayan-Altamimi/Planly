"""add parent_task_id to tasks

Revision ID: bbc6d0d7e7f6
Revises: b96febb7bf69
Create Date: 2026-08-20 14:16:48.640705

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bbc6d0d7e7f6'
down_revision: Union[str, Sequence[str], None] = 'b96febb7bf69'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.add_column(sa.Column('parent_task_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_tasks_parent_task_id', 'tasks', ['parent_task_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.drop_constraint('fk_tasks_parent_task_id', type_='foreignkey')
        batch_op.drop_column('parent_task_id')
