"""Add deduplication company_key, enriched_at, review_audit, and seed configs.

Revision ID: 005_advanced_enrichment
Revises: 004_pipeline_logs_llm_timing
Create Date: 2026-10-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "005_advanced_enrichment"
down_revision: Union[str, None] = "004_pipeline_logs_llm_timing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add company_key and enriched_at to leads
    op.add_column("leads", sa.Column("company_key", sa.String(length=512), nullable=True))
    op.add_column("leads", sa.Column("enriched_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index(
        "ix_leads_company_key",
        "leads",
        ["company_key"],
        unique=False,
    )

    # 2. Create review_audit table
    op.create_table(
        "review_audit",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("reviewer", sa.String(length=256), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["leads.request_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_audit_request_id", "review_audit", ["request_id"], unique=False)

    # 3. Seed Phase 5 configuration settings
    op.execute(
        """
        INSERT INTO admin_config (setting_key, setting_value)
        VALUES
            ('enrichment.dedup_enabled', 'true'),
            ('enrichment.freshness_ttl_days', '30'),
            ('guardrail.pii_redaction_enabled', 'true')
        ON CONFLICT (setting_key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_review_audit_request_id", table_name="review_audit")
    op.drop_table("review_audit")

    op.drop_index("ix_leads_company_key", table_name="leads")
    op.drop_column("leads", "enriched_at")
    op.drop_column("leads", "company_key")

    op.execute(
        """
        DELETE FROM admin_config
        WHERE setting_key IN (
            'enrichment.dedup_enabled',
            'enrichment.freshness_ttl_days'
        )
        """
    )
