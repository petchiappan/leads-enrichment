"""Seed observability configuration into admin_config.

Revision ID: 004_pipeline_logs_llm_timing
Revises: 003_prompt_versions
Create Date: 2026-10-04
"""

from typing import Sequence, Union

from alembic import op

revision: str = "004_pipeline_logs_llm_timing"
down_revision: Union[str, None] = "003_prompt_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO admin_config (setting_key, setting_value)
        VALUES
            ('observability.log_level', 'INFO'),
            ('observability.structured_json', 'true')
        ON CONFLICT (setting_key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM admin_config
        WHERE setting_key IN (
            'observability.log_level',
            'observability.structured_json'
        )
        """
    )
