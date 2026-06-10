"""Initial schema with users, documents, chat, and citations

Revision ID: 001_initial
Revises:
Create Date: 2026-06-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON
from pgvector.sqlalchemy import Vector

revision: str = "001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial schema with vector extension and all tables."""

    # Create pgvector extension for embeddings
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # users table
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )
    op.create_index('ix_users_email', 'users', ['email'])

    # source_documents table
    op.create_table(
        'source_documents',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('ticker', sa.String(10), nullable=False),
        sa.Column('filing_type', sa.String(20), nullable=False),
        sa.Column('filing_year', sa.Integer, nullable=False),
        sa.Column('filing_date', sa.DateTime, nullable=False),
        sa.Column('url', sa.String(512), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )
    op.create_index('ix_source_documents_ticker', 'source_documents', ['ticker'])

    # document_chunks table with vector embedding
    op.create_table(
        'document_chunks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('document_id', UUID(as_uuid=True), nullable=False),
        sa.Column('text', sa.Text, nullable=False),
        sa.Column('embedding', Vector(1536), nullable=False),
        sa.Column('chunk_metadata', JSON, nullable=True),
        sa.Column('search_vector', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['source_documents.id']),
    )
    op.create_index('ix_document_chunks_document_id', 'document_chunks', ['document_id'])

    # Create HNSW index for vector similarity search
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding_hnsw ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    # Create GIN index for full-text search on search_vector
    op.execute(
        "CREATE INDEX ix_document_chunks_search_vector_gin ON document_chunks "
        "USING gin (to_tsvector('english'::regconfig, search_vector))"
    )

    # chat_threads table
    op.create_table(
        'chat_threads',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index('ix_chat_threads_user_id', 'chat_threads', ['user_id'])

    # chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('thread_id', UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(['thread_id'], ['chat_threads.id']),
    )
    op.create_index('ix_chat_messages_thread_id', 'chat_messages', ['thread_id'])

    # message_citations table
    op.create_table(
        'message_citations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('message_id', UUID(as_uuid=True), nullable=False),
        sa.Column('chunk_id', UUID(as_uuid=True), nullable=False),
        sa.Column('page_number', sa.Integer, nullable=True),
        sa.Column('section', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(['message_id'], ['chat_messages.id']),
        sa.ForeignKeyConstraint(['chunk_id'], ['document_chunks.id']),
    )
    op.create_index('ix_message_citations_message_id', 'message_citations', ['message_id'])

    # Enable RLS (Row-Level Security) on chat-related tables
    op.execute("ALTER TABLE chat_threads ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE message_citations ENABLE ROW LEVEL SECURITY")

    # RLS policy: Users can only see their own chat threads
    op.execute("""
        CREATE POLICY "Users see only their own chat threads"
        ON chat_threads FOR SELECT
        USING (auth.uid() = user_id)
    """)

    # RLS policy: Users can only see messages in their own threads
    op.execute("""
        CREATE POLICY "Users see only messages in their own threads"
        ON chat_messages FOR SELECT
        USING (
            thread_id IN (
                SELECT id FROM chat_threads WHERE user_id = auth.uid()
            )
        )
    """)

    # RLS policy: Users can only see citations for messages in their threads
    op.execute("""
        CREATE POLICY "Users see only citations in their own threads"
        ON message_citations FOR SELECT
        USING (
            message_id IN (
                SELECT id FROM chat_messages
                WHERE thread_id IN (
                    SELECT id FROM chat_threads WHERE user_id = auth.uid()
                )
            )
        )
    """)


def downgrade() -> None:
    """Drop all tables and extensions."""

    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS \"Users see only their own chat threads\" ON chat_threads")
    op.execute("DROP POLICY IF EXISTS \"Users see only messages in their own threads\" ON chat_messages")
    op.execute("DROP POLICY IF EXISTS \"Users see only citations in their own threads\" ON message_citations")

    # Drop tables (cascade will handle foreign keys)
    op.drop_table('message_citations')
    op.drop_table('chat_messages')
    op.drop_table('chat_threads')
    op.drop_table('document_chunks')
    op.drop_table('source_documents')
    op.drop_table('users')

    # Drop vector extension
    op.execute("DROP EXTENSION IF EXISTS vector")
