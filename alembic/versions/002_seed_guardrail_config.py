"""Seed guardrail configuration keys into admin_config.

Revision ID: 002_seed_guardrail_config
Revises: 001_initial
Create Date: 2026-10-04

Data-only migration — no schema changes.
Inserts default guardrail thresholds that can be overridden via the admin UI
at /admin/settings or via the API at POST /api/admin/config.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "002_seed_guardrail_config"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO admin_config (setting_key, setting_value)
        VALUES
            ('guardrail.min_confidence_threshold', '0.3'),
            ('guardrail.max_company_name_length',  '256'),
            ('guardrail.pii_redaction_enabled',    'false'),
            ('guardrail.block_on_invalid_email',   'false')
        ON CONFLICT (setting_key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM admin_config
        WHERE setting_key IN (
            'guardrail.min_confidence_threshold',
            'guardrail.max_company_name_length',
            'guardrail.pii_redaction_enabled',
            'guardrail.block_on_invalid_email'
        )
        """
    )
