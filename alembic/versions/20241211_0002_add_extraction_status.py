"""Add extraction status to opportunity attachments

Revision ID: 0002
Revises: 0001
Create Date: 2024-12-11

This migration adds fields to track PDF text extraction status:
- extraction_status: pending/extracted/failed/skipped
- extracted_at: timestamp of last extraction attempt
- extraction_error: error message if extraction failed
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add extraction tracking columns to opportunity_attachments
    op.add_column(
        'opportunity_attachments',
        sa.Column('extraction_status', sa.String(20), server_default='pending', index=True)
    )
    op.add_column(
        'opportunity_attachments',
        sa.Column('extracted_at', sa.DateTime(), nullable=True)
    )
    op.add_column(
        'opportunity_attachments',
        sa.Column('extraction_error', sa.String(500), nullable=True)
    )

    # Create index for efficient querying of pending extractions
    op.create_index(
        'ix_opportunity_attachments_extraction_status',
        'opportunity_attachments',
        ['extraction_status']
    )


def downgrade() -> None:
    op.drop_index('ix_opportunity_attachments_extraction_status', table_name='opportunity_attachments')
    op.drop_column('opportunity_attachments', 'extraction_error')
    op.drop_column('opportunity_attachments', 'extracted_at')
    op.drop_column('opportunity_attachments', 'extraction_status')
