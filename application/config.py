"""应用配置。

集中管理 Flask 配置项，避免散落在入口文件。
"""

import os


def _project_root():
    """返回项目根目录（application/ 的上一级）。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Config:
    """基础配置。"""

    # SECRET_KEY 从环境变量读取（生产环境必须设置，未设置时由 create_app 兜底生成）
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")

    # 数据库 URI 从环境变量读取（默认 SQLite；切 PostgreSQL/MySQL 只需设 DATABASE_URL）
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(_project_root(), "instance", "rf3d_users.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(_project_root(), "uploads")
    TEMPLATE_FOLDER = os.path.join(_project_root(), "templates")
    STATIC_FOLDER = os.path.join(_project_root(), "static")

    # CORS 白名单（本地开发默认允许 localhost）
    CORS_ALLOWED_ORIGINS = [
        o.strip()
        for o in os.environ.get(
            "CORS_ALLOWED_ORIGINS",
            "http://localhost:5000,http://127.0.0.1:5000,http://localhost:3000",
        ).split(",")
        if o.strip()
    ]
