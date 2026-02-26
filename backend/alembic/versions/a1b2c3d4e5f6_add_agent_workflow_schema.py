"""add_agent_workflow_schema

Revision ID: a1b2c3d4e5f6
Revises: e7e9db004113
Create Date: 2026-02-25 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'e7e9db004113'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Update SourceType enum with new values
    # Use execution_options to avoid prepared statement caching issues with enum alterations
    conn = op.get_bind()
    conn.execute(
        sa.text("ALTER TYPE sourcetype ADD VALUE IF NOT EXISTS 'HTML_ARTICLE'").execution_options(autocommit=True)
    )
    conn.execute(
        sa.text("ALTER TYPE sourcetype ADD VALUE IF NOT EXISTS 'RSS_ENTRY'").execution_options(autocommit=True)
    )
    conn.execute(
        sa.text("ALTER TYPE sourcetype ADD VALUE IF NOT EXISTS 'GITHUB_REPO'").execution_options(autocommit=True)
    )
    conn.execute(
        sa.text("ALTER TYPE sourcetype ADD VALUE IF NOT EXISTS 'PRODUCT_HUNT'").execution_options(autocommit=True)
    )

    # Create ContentType enum
    content_type_enum = sa.Enum(
        'MODEL_RELEASE', 'BREAKING_NEWS', 'RESEARCH_PAPER', 'TOOL_LAUNCH',
        'MARKET_UPDATE', 'COMPANY_NEWS', 'COMMUNITY_POST', 'GENERAL',
        name='contenttype'
    )
    content_type_enum.create(op.get_bind())

    # Rename columns in crawled_contents
    op.alter_column('crawled_contents', 'summary_manual',
                    new_column_name='summary_hint')

    # Add new columns to crawled_contents
    op.add_column('crawled_contents',
                  sa.Column('content_hash', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('crawled_contents',
                  sa.Column('source_type', sa.Enum('RSS', 'PLAYWRIGHT', 'API', 'HTML_ARTICLE', 'RSS_ENTRY', 'GITHUB_REPO', 'PRODUCT_HUNT', name='sourcetype'), nullable=True))
    op.add_column('crawled_contents',
                  sa.Column('source_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('crawled_contents',
                  sa.Column('canonical_url', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('crawled_contents',
                  sa.Column('fetched_at', sa.DateTime(), nullable=True))
    op.add_column('crawled_contents',
                  sa.Column('author', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('crawled_contents',
                  sa.Column('image_positions', sa.JSON(), nullable=True))
    op.add_column('crawled_contents',
                  sa.Column('outbound_urls', sa.JSON(), nullable=True))
    op.add_column('crawled_contents',
                  sa.Column('content_type', content_type_enum, nullable=True))
    op.add_column('crawled_contents',
                  sa.Column('tags', sa.JSON(), nullable=True))
    op.add_column('crawled_contents',
                  sa.Column('language', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('crawled_contents',
                  sa.Column('raw_payload', sa.JSON(), nullable=True))

    # Set default values for new columns
    op.execute("UPDATE crawled_contents SET source_type = 'HTML_ARTICLE' WHERE source_type IS NULL")
    op.execute("UPDATE crawled_contents SET fetched_at = created_at WHERE fetched_at IS NULL")
    op.execute("UPDATE crawled_contents SET content_type = 'GENERAL' WHERE content_type IS NULL")
    op.execute("UPDATE crawled_contents SET language = 'en' WHERE language IS NULL")
    op.execute("UPDATE crawled_contents SET image_positions = '[]' WHERE image_positions IS NULL")
    op.execute("UPDATE crawled_contents SET outbound_urls = '[]' WHERE outbound_urls IS NULL")
    op.execute("UPDATE crawled_contents SET tags = '[]' WHERE tags IS NULL")
    op.execute("UPDATE crawled_contents SET raw_payload = '{}' WHERE raw_payload IS NULL")

    # Make certain columns NOT NULL after setting defaults
    op.alter_column('crawled_contents', 'source_type', nullable=False)
    op.alter_column('crawled_contents', 'fetched_at', nullable=False)
    op.alter_column('crawled_contents', 'content_type', nullable=False)
    op.alter_column('crawled_contents', 'language', nullable=False)

    # Create indexes on new columns
    op.create_index('ix_crawled_contents_content_hash', 'crawled_contents', ['content_hash'])
    op.create_index('ix_crawled_contents_content_type', 'crawled_contents', ['content_type'])
    op.create_index('ix_crawled_contents_fetched_at', 'crawled_contents', ['fetched_at'])

    # Create content_embeddings table
    op.create_table('content_embeddings',
        sa.Column('content_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('embedding', Vector(3072), nullable=False),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['content_id'], ['crawled_contents.id'], ),
        sa.PrimaryKeyConstraint('content_id')
    )

    # Skip vector index for now (pgvector has 2000-dimension limit, gemini-embedding-001 uses 3072)
    # Sequential scan is fine for development with small dataset
    # TODO: Add index later when scaling up (use different vector DB or smaller embedding model)
    pass


def downgrade() -> None:
    # Drop vector index
    op.execute('DROP INDEX IF EXISTS idx_embedding_vector')

    # Drop content_embeddings table
    op.drop_table('content_embeddings')

    # Drop indexes from crawled_contents
    op.drop_index('ix_crawled_contents_fetched_at', table_name='crawled_contents')
    op.drop_index('ix_crawled_contents_content_type', table_name='crawled_contents')
    op.drop_index('ix_crawled_contents_content_hash', table_name='crawled_contents')

    # Drop new columns from crawled_contents
    op.drop_column('crawled_contents', 'raw_payload')
    op.drop_column('crawled_contents', 'language')
    op.drop_column('crawled_contents', 'tags')
    op.drop_column('crawled_contents', 'content_type')
    op.drop_column('crawled_contents', 'outbound_urls')
    op.drop_column('crawled_contents', 'image_positions')
    op.drop_column('crawled_contents', 'author')
    op.drop_column('crawled_contents', 'fetched_at')
    op.drop_column('crawled_contents', 'canonical_url')
    op.drop_column('crawled_contents', 'source_name')
    op.drop_column('crawled_contents', 'source_type')
    op.drop_column('crawled_contents', 'content_hash')

    # Rename columns back
    op.alter_column('crawled_contents', 'summary_hint',
                    new_column_name='summary_manual')

    # Drop ContentType enum
    op.execute('DROP TYPE IF EXISTS contenttype')

    # Drop pgvector extension
    op.execute('DROP EXTENSION IF EXISTS vector')
