"""Add proposal templates and generated sections

Revision ID: 0003
Revises: 0002
Create Date: 2025-01-06

This migration adds tables for AI-generated proposal templates:
- proposal_templates: Reusable templates with AI prompts
- generated_sections: AI-generated content for specific opportunities
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create proposal_templates table
    op.create_table(
        'proposal_templates',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),

        # Metadata
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('template_type', sa.String(50), nullable=False, index=True),

        # Target criteria
        sa.Column('target_naics_codes', sa.JSON(), nullable=True),
        sa.Column('target_agencies', sa.JSON(), nullable=True),
        sa.Column('target_keywords', sa.JSON(), nullable=True),

        # Content
        sa.Column('sections', sa.JSON(), nullable=True),
        sa.Column('variables', sa.JSON(), nullable=True),
        sa.Column('raw_content', sa.Text(), nullable=True),

        # AI settings
        sa.Column('ai_system_prompt', sa.Text(), nullable=True),
        sa.Column('use_company_profile', sa.Boolean(), default=True),
        sa.Column('use_past_performance', sa.Boolean(), default=True),
        sa.Column('use_capability_statement', sa.Boolean(), default=True),

        # Status
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_default', sa.Boolean(), default=False),
        sa.Column('is_public', sa.Boolean(), default=False),
        sa.Column('times_used', sa.Integer(), default=0),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create generated_sections table
    op.create_table(
        'generated_sections',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('template_id', sa.String(36), sa.ForeignKey('proposal_templates.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('opportunity_id', sa.String(36), sa.ForeignKey('opportunities.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),

        # Content
        sa.Column('section_key', sa.String(100), nullable=False),
        sa.Column('section_heading', sa.String(255), nullable=True),
        sa.Column('generated_content', sa.Text(), nullable=False),
        sa.Column('edited_content', sa.Text(), nullable=True),
        sa.Column('use_edited', sa.Boolean(), default=False),

        # Generation metadata
        sa.Column('generation_prompt', sa.Text(), nullable=True),
        sa.Column('generation_context', sa.JSON(), nullable=True),
        sa.Column('model_used', sa.String(100), nullable=True),
        sa.Column('tokens_input', sa.Integer(), nullable=True),
        sa.Column('tokens_output', sa.Integer(), nullable=True),

        # Feedback
        sa.Column('user_rating', sa.Integer(), nullable=True),
        sa.Column('feedback_notes', sa.Text(), nullable=True),

        # Timestamps
        sa.Column('generated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('edited_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create indexes
    op.create_index('ix_proposal_templates_user_type', 'proposal_templates', ['user_id', 'template_type'])
    op.create_index('ix_generated_sections_user_opportunity', 'generated_sections', ['user_id', 'opportunity_id'])


def downgrade() -> None:
    op.drop_index('ix_generated_sections_user_opportunity', table_name='generated_sections')
    op.drop_index('ix_proposal_templates_user_type', table_name='proposal_templates')
    op.drop_table('generated_sections')
    op.drop_table('proposal_templates')
