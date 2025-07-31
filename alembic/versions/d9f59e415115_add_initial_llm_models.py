"""Add initial LLM models

Revision ID: d9f59e415115
Revises: 775bf7017229
Create Date: 2025-07-22 13:29:10.061006

"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9f59e415115'
down_revision: Union[str, None] = '775bf7017229'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'llm_models',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String, unique=True, index=True),
        sa.Column('provider', sa.String, nullable=False),
        sa.Column('model_name', sa.String, nullable=False),
        sa.Column('description', sa.String, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    llm_models_table = sa.table(
        'llm_models',
        sa.column('id', sa.Integer),
        sa.column('name', sa.String),
        sa.column('provider', sa.String),
        sa.column('model_name', sa.String),
        sa.column('description', sa.String),
        sa.column('created_at', sa.DateTime(timezone=True)),
    )

    op.bulk_insert(llm_models_table, [
        {
            "id": 1,
            "name": "Mistral Small 3.2 24B",
            "provider": "Mistral",
            "model_name": "mistralai/mistral-small-3.2-24b-instruct",
            "description": "Mistral's Small 3.2 24B model",
            "created_at": datetime.now(timezone.utc),
        },
        {
            "id": 2,
            "name": "Gemini 2.5 Flash Lite",
            "provider": "Google",
            "model_name": "google/gemini-2.5-flash-lite",
            "description": "Google's Gemini 2.5 Flash Lite model",
            "created_at": datetime.now(timezone.utc),
        },
        # Add more entries as needed
    ])


def downgrade() -> None:
    op.execute("DELETE FROM llm_models WHERE id IN (1, 2)")
