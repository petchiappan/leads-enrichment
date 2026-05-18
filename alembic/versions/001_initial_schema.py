"""Initial schema - all tables

Revision ID: 001_initial
Revises: None
Create Date: 2026-05-17

Creates:
- pgvector extension
- leads table
- pipeline_logs table
- admin_config table
- vector_embeddings table
- token_usage table
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── leads ──
    op.create_table(
        "leads",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("raw_input", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("enriched_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index("ix_leads_request_id", "leads", ["request_id"])
    op.create_index("ix_leads_status", "leads", ["status"])

    # ── pipeline_logs ──
    op.create_table(
        "pipeline_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("step_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="started"),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["leads.request_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pipeline_logs_request_id", "pipeline_logs", ["request_id"])

    # ── admin_config ──
    op.create_table(
        "admin_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("setting_key", sa.String(length=128), nullable=False),
        sa.Column("setting_value", sa.String(length=512), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("setting_key"),
    )
    op.create_index("ix_admin_config_setting_key", "admin_config", ["setting_key"])

    # Seed default config values
    op.execute(
        "INSERT INTO admin_config (setting_key, setting_value) VALUES "
        "('enable_redis_cache', 'true'), "
        "('max_retries', '3'), "
        "('fallback_agent_enabled', 'true')"
    )

    # ── vector_embeddings ──
    # Create table without the vector column first, then add via raw SQL
    # because Alembic doesn't natively support pgvector column types.
    op.create_table(
        "vector_embeddings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("content_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Add pgvector embedding column via raw SQL
    op.execute("ALTER TABLE vector_embeddings ADD COLUMN embedding vector(1536) NOT NULL")
    op.create_index("ix_vector_embeddings_lead_id", "vector_embeddings", ["lead_id"])

    # ── token_usage ──
    op.create_table(
        "token_usage",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("step_name", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["leads.request_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_token_usage_request_id", "token_usage", ["request_id"])


def downgrade() -> None:
    op.drop_table("token_usage")
    op.drop_table("vector_embeddings")
    op.drop_table("admin_config")
    op.drop_table("pipeline_logs")
    op.drop_table("leads")
    op.execute("DROP EXTENSION IF EXISTS vector")
