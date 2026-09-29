"""Add swarm fields to agent_plans

Revision ID: 0af097f6c55e
Revises: 5b4b63e1fd21
Create Date: 2026-09-01 14:32:19.949643

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0af097f6c55e'
down_revision: Union[str, Sequence[str], None] = '5b4b63e1fd21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # agent_plans
    op.add_column('agent_plans', sa.Column('max_agents', sa.Integer(), nullable=False, server_default='10'))
    op.add_column('agent_plans', sa.Column('max_depth', sa.Integer(), nullable=False, server_default='5'))
    op.add_column('agent_plans', sa.Column('max_delegations', sa.Integer(), nullable=False, server_default='15'))
    op.add_column('agent_plans', sa.Column('token_budget', sa.Integer(), nullable=False, server_default='100000'))
    
    # agent_plan_steps
    op.add_column('agent_plan_steps', sa.Column('agent_id', sa.String(length=100), nullable=True))
    op.add_column('agent_plan_steps', sa.Column('parent_step_id', sa.String(length=100), nullable=True))
    op.add_column('agent_plan_steps', sa.Column('input_reference', sa.Text(), nullable=True))
    op.add_column('agent_plan_steps', sa.Column('output_reference', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # agent_plan_steps
    op.drop_column('agent_plan_steps', 'output_reference')
    op.drop_column('agent_plan_steps', 'input_reference')
    op.drop_column('agent_plan_steps', 'parent_step_id')
    op.drop_column('agent_plan_steps', 'agent_id')
    
    # agent_plans
    op.drop_column('agent_plans', 'token_budget')
    op.drop_column('agent_plans', 'max_delegations')
    op.drop_column('agent_plans', 'max_depth')
    op.drop_column('agent_plans', 'max_agents')
