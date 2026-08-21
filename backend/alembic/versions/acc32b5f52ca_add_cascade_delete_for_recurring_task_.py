"""add cascade delete for recurring task instances

Revision ID: acc32b5f52ca
Revises: bbc6d0d7e7f6
Create Date: 2026-08-21 15:19:10.652325

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'acc32b5f52ca'
down_revision: Union[str, Sequence[str], None] = 'bbc6d0d7e7f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.drop_constraint(op.f('fk_tasks_parent_task_id'), 'tasks', type_='foreignkey')
    op.create_foreign_key('fk_tasks_parent_task_id', 'tasks', 'tasks', ['parent_task_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    op.drop_constraint('fk_tasks_parent_task_id', 'tasks', type_='foreignkey')
    op.create_foreign_key(op.f('fk_tasks_parent_task_id'), 'tasks', 'tasks', ['parent_task_id'], ['id'])
