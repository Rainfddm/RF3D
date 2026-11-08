"""数据模型。"""

from datetime import datetime

from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # nullable=False + server_default 与迁移 4c7a9e2b1d30 保持一致：
    # 仅靠 ORM 的 default=True 时，直接 SQL/批量导入写入的 NULL 会让该账号
    # 在 `user and user.is_active` 处被当作 False，永远登录不上。
    is_active = db.Column(
        db.Boolean, nullable=False, default=True, server_default=db.text("true")
    )
    credit_points = db.Column(db.Integer, default=100)  # 信用点，默认 100

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"
