"""0002_add_anpr_records

Revision ID: 0002_add_anpr_records
Revises: 0001_initial_schema
Create Date: 2026-09-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002_add_anpr_records"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create anpr_records table
    op.create_table(
        "anpr_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("camera_id", sa.Integer(), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=True),
        sa.Column("plate_text", sa.String(length=50), nullable=False),
        sa.Column("quality", sa.String(length=30), nullable=False, default="HIGH"),
        sa.Column("confidence", sa.Float(), nullable=False, default=0.0),
        sa.Column("vehicle_type", sa.String(length=50), nullable=False, default="car"),
        sa.Column("vehicle_bbox_json", sa.String(length=100), nullable=False),
        sa.Column("plate_bbox_json", sa.String(length=100), nullable=True),
        sa.Column("evidence_path", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_anpr_records_id"), "anpr_records", ["id"], unique=False)
    op.create_index(op.f("ix_anpr_records_timestamp"), "anpr_records", ["timestamp"], unique=False)
    op.create_index(op.f("ix_anpr_records_camera_id"), "anpr_records", ["camera_id"], unique=False)
    op.create_index(op.f("ix_anpr_records_track_id"), "anpr_records", ["track_id"], unique=False)
    op.create_index(op.f("ix_anpr_records_plate_text"), "anpr_records", ["plate_text"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_anpr_records_plate_text"), table_name="anpr_records")
    op.drop_index(op.f("ix_anpr_records_track_id"), table_name="anpr_records")
    op.drop_index(op.f("ix_anpr_records_camera_id"), table_name="anpr_records")
    op.drop_index(op.f("ix_anpr_records_timestamp"), table_name="anpr_records")
    op.drop_index(op.f("ix_anpr_records_id"), table_name="anpr_records")
    op.drop_table("anpr_records")
