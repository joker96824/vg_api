"""initial card tables

Revision ID: 001
Revises: 
Create Date: 2024-03-06 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建卡牌类型枚举
    op.execute("CREATE TYPE card_type AS ENUM ('normal', 'trigger', 'g_unit', 'order', 'marker')")
    op.execute("CREATE TYPE trigger_type AS ENUM ('none', 'critical', 'front', 'heal', 'draw', 'stand')")

    # 创建卡牌表
    op.create_table(
        'cards',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('card_code', sa.String(length=50), nullable=False),
        sa.Column('card_link', sa.String(length=255), nullable=True),
        sa.Column('card_number', sa.String(length=50), nullable=True),
        sa.Column('card_rarity', sa.String(length=50), nullable=True),
        sa.Column('name_cn', sa.String(length=100), nullable=False),
        sa.Column('name_jp', sa.String(length=100), nullable=True),
        sa.Column('nation', sa.String(length=100), nullable=True),
        sa.Column('clan', sa.String(length=100), nullable=True),
        sa.Column('grade', sa.Integer(), nullable=True),
        sa.Column('skill', sa.String(length=500), nullable=True),
        sa.Column('card_power', sa.Integer(), nullable=True),
        sa.Column('shield', sa.Integer(), nullable=True),
        sa.Column('critical', sa.Integer(), nullable=True),
        sa.Column('special_mark', sa.String(length=50), nullable=True),
        sa.Column('card_type', postgresql.ENUM('normal', 'trigger', 'g_unit', 'order', 'marker', name='card_type'), nullable=False),
        sa.Column('trigger_type', postgresql.ENUM('none', 'critical', 'front', 'heal', 'draw', 'stand', name='trigger_type'), nullable=True),
        sa.Column('ability', sa.String(length=1000), nullable=True),
        sa.Column('card_alias', sa.String(length=100), nullable=True),
        sa.Column('card_group', sa.String(length=100), nullable=True),
        sa.Column('ability_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('card_code')
    )
    op.create_index(op.f('ix_cards_card_code'), 'cards', ['card_code'], unique=True)
    op.create_index(op.f('ix_cards_name_cn'), 'cards', ['name_cn'], unique=False)

    # 创建卡牌稀有度表
    op.create_table(
        'card_rarities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('pack_name', sa.String(length=100), nullable=True),
        sa.Column('card_number', sa.String(length=50), nullable=True),
        sa.Column('release_info', sa.String(length=100), nullable=True),
        sa.Column('quote', sa.String(length=500), nullable=True),
        sa.Column('illustrator', sa.String(length=100), nullable=True),
        sa.Column('image_url', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_card_rarities_illustrator'), 'card_rarities', ['illustrator'], unique=False)


def downgrade() -> None:
    # 删除表
    op.drop_index(op.f('ix_card_rarities_illustrator'), table_name='card_rarities')
    op.drop_table('card_rarities')
    op.drop_index(op.f('ix_cards_name_cn'), table_name='cards')
    op.drop_index(op.f('ix_cards_card_code'), table_name='cards')
    op.drop_table('cards')

    # 删除枚举类型
    op.execute('DROP TYPE trigger_type')
    op.execute('DROP TYPE card_type') 