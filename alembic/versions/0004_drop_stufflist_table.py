import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index(op.f("ix_stufflist_name"), table_name="stufflist")
    op.drop_table("stufflist")


def downgrade():
    op.create_table(
        "stufflist",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stufflist_name"), "stufflist", ["name"], unique=False)
