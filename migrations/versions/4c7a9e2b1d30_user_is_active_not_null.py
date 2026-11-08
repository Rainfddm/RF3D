"""user.is_active 收紧为 NOT NULL 并加服务端默认值

Revision ID: 4c7a9e2b1d30
Revises: 8fcae8593bef
Create Date: 2026-11-09 00:30:00

背景：初始迁移里 is_active 是 nullable=True，SQL 层允许写入 NULL。
模型层虽有 default=True，但那只在 ORM 插入时生效；直接 SQL、批量导入、
或早期版本写入的行都可能是 NULL。而登录判断是 `user and ... and user.is_active`，
NULL 会被当成 False → 这类账号永远登录不了，且没有任何报错线索。

修正分两步，顺序不能反：
1. 回填存量 NULL → true（否则第 2 步加 NOT NULL 会因存量数据失败）；
2. 收紧为 NOT NULL 并给服务端默认值 true（绕过 ORM 的写入也能拿到合法值）。
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4c7a9e2b1d30'
down_revision = '8fcae8593bef'
branch_labels = None
depends_on = None


def upgrade():
    # 1) 回填：把历史 NULL 视为「启用」。
    #    "user" 用双引号包裹 —— user 在 PostgreSQL 里是保留字。
    #    true 在 SQLite 3.23+ 与 PostgreSQL 都合法。
    op.execute('UPDATE "user" SET is_active = true WHERE is_active IS NULL')

    # 2) 收紧约束。SQLite 不支持 ALTER COLUMN，batch 模式会重建表并保留数据。
    with op.batch_alter_table('user') as batch_op:
        batch_op.alter_column(
            'is_active',
            existing_type=sa.Boolean(),
            nullable=False,
            server_default=sa.text('true'),
        )


def downgrade():
    with op.batch_alter_table('user') as batch_op:
        batch_op.alter_column(
            'is_active',
            existing_type=sa.Boolean(),
            nullable=True,
            server_default=None,
        )
    # 不回填回去：降级只放开约束，本来就没有「原来的 NULL」可还原。
