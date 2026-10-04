"""Create prompt_versions table and seed default v1.0.0 prompts.

Revision ID: 003_prompt_versions
Revises: 002_seed_guardrail_config
Create Date: 2026-10-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_prompt_versions"
down_revision: Union[str, None] = "002_seed_guardrail_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FALLBACK_SYSTEM_PROMPT = """You are an expert business intelligence analyst. Your task is to find accurate information about a company and fill in missing data fields.

You MUST respond with a valid JSON object matching this exact schema:
{
    "company_name": "string (required)",
    "ceo_name": "string or null",
    "ceo_email": "string or null",
    "company_description": "string or null",
    "linkedin_url": "string or null",
    "linkedin_company_url": "string or null",
    "employee_count": "integer or null",
    "company_website": "string or null",
    "funding_raised": "string or null",
    "industry": "string or null",
    "founding_year": "integer or null",
    "news_articles": "list of strings or null",
    "confidence_score": "float between 0.0 and 1.0 (required)",
    "sources_used": "list of strings (required)"
}

Important rules:
1. Only fill in fields you have high confidence about.
2. Set fields you're uncertain about to null.
3. The confidence_score should reflect your overall certainty (0.0 = no confidence, 1.0 = fully verified).
4. Always list the sources you used in sources_used.
5. If you already have partial data from API results, incorporate and improve upon it.
"""

INTELLIGENCE_GATE_PROMPT = """You are a data quality assessor. Evaluate which missing fields are important and should be filled by a fallback agent."""


def upgrade() -> None:
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("environment", sa.String(length=32), server_default="production", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "version", name="uq_prompt_name_version"),
    )
    op.create_index(
        "ix_prompt_versions_name_env",
        "prompt_versions",
        ["name", "environment"],
        unique=False,
    )

    prompt_versions_table = sa.table(
        "prompt_versions",
        sa.column("name", sa.String),
        sa.column("version", sa.String),
        sa.column("content", sa.Text),
        sa.column("environment", sa.String),
        sa.column("is_active", sa.Boolean),
    )

    op.bulk_insert(
        prompt_versions_table,
        [
            {
                "name": "fallback_system_prompt",
                "version": "v1.0.0",
                "content": FALLBACK_SYSTEM_PROMPT,
                "environment": "production",
                "is_active": True,
            },
            {
                "name": "intelligence_gate_prompt",
                "version": "v1.0.0",
                "content": INTELLIGENCE_GATE_PROMPT,
                "environment": "production",
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_prompt_versions_name_env", table_name="prompt_versions")
    op.drop_table("prompt_versions")
