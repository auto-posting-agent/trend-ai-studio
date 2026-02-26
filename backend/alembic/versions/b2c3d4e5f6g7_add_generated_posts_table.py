"""add generated posts table

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-27 18:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6g7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'generated_posts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('content_id', sa.String(), nullable=False),
        sa.Column('thread_parts', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('generated_post', sa.String(), nullable=False),
        sa.Column('analysis_summary', sa.String(), nullable=True),
        sa.Column('web_search_results', sa.String(), nullable=True),
        sa.Column('hashtags', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('link', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('threads_post_id', sa.String(), nullable=True),
        sa.Column('threads_permalink', sa.String(), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('error', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['content_id'], ['crawled_contents.id'], ),
    )
    op.create_index(op.f('ix_generated_posts_content_id'), 'generated_posts', ['content_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_generated_posts_content_id'), table_name='generated_posts')
    op.drop_table('generated_posts')
