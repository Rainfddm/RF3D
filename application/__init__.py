"""应用工厂。"""

import logging
import os
import secrets

from flask import Flask, request, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import db, migrate
from .errors import error_response, APIError

_SQLITE_PREFIX = "sqlite:///"


def sqlite_dir_from_uri(uri):
    """从 SQLALCHEMY_DATABASE_URI 反推 SQLite 库文件所在目录。

    非 SQLite（或内存库）返回 None。相对路径按当前工作目录解析，
    与 SQLite/ SQLAlchemy 的实际行为保持一致。
    """
    if not uri or not uri.startswith(_SQLITE_PREFIX):
        return None

    path = uri[len(_SQLITE_PREFIX):]
    if not path or path == ":memory:" or path.startswith("file:"):
        return None

    if not os.path.isabs(path):
        path = os.path.abspath(path)
    return os.path.dirname(path) or None


def _ensure_sqlite_dir(app):
    """确保 SQLite 库文件所在目录存在，必须在 db.init_app() 之前调用。

    为什么不能靠 flask_sqlalchemy 自动建目录：SQLAlchemy 的 sqlite 驱动
    只负责打开文件，不会创建缺失的父目录。当 URI 是绝对路径
    （如 <root>/instance/rf3d_users.db）且 instance/ 不存在时，
    连接会直接失败：sqlite3.OperationalError: unable to open database file。
    全新解压的发布包没有 instance/，`flask db upgrade` 与首启都会踩到。
    """
    directory = sqlite_dir_from_uri(app.config.get("SQLALCHEMY_DATABASE_URI"))
    if directory:
        os.makedirs(directory, exist_ok=True)
    return directory


def create_app(config_class=Config):
    """创建并配置 Flask 应用实例。"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # SECRET_KEY 兜底：未通过环境变量设置时生成随机密钥并告警
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = secrets.token_hex(32)
        logging.warning(
            "FLASK_SECRET_KEY 未设置，已自动生成随机密钥。"
            "生产环境请务必通过环境变量设置！"
        )

    app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1)

    # 模板与静态文件路径
    app.template_folder = app.config["TEMPLATE_FOLDER"]
    app.static_folder = app.config["STATIC_FOLDER"]

    # 初始化数据库扩展
    # 注意顺序：必须先确保 SQLite 库文件目录存在，再 db.init_app()。
    # 全新解压的发布包没有 instance/，绝对路径的 sqlite URI 不会自动建目录。
    _ensure_sqlite_dir(app)
    db.init_app(app)
    migrate.init_app(app, db)

    # 确保必要目录存在
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["STATIC_FOLDER"], exist_ok=True)

    # URL 前缀（部署环境通过 ENABLE_URL_PREFIX=true 启用）
    _setup_url_prefix(app)

    # CORS 头
    _setup_cors(app)

    # 统一错误处理
    _setup_error_handlers(app)

    # 注册 blueprint
    from .blueprints import pipeline_bp, ai_bp, auth_bp, credit_bp, pages_bp

    app.register_blueprint(pipeline_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(credit_bp)
    app.register_blueprint(pages_bp)

    return app


def _setup_url_prefix(app):
    """按环境变量决定是否启用 URL 前缀。"""
    enable_prefix = os.environ.get("ENABLE_URL_PREFIX", "false").lower() == "true"

    if not enable_prefix:
        app.config["APPLICATION_ROOT"] = "/"
        print("运行在本地开发模式，可直接通过 http://localhost:5000 访问")
        return

    app.config["APPLICATION_ROOT"] = "/app/rf3d"

    class PrefixMiddleware(object):
        def __init__(self, inner, prefix=""):
            self.app = inner
            self.prefix = prefix

        def __call__(self, environ, start_response):
            if environ["PATH_INFO"].startswith(self.prefix):
                environ["PATH_INFO"] = environ["PATH_INFO"][len(self.prefix):]
                environ["SCRIPT_NAME"] = self.prefix
                return self.app(environ, start_response)
            start_response("404", [("Content-Type", "text/plain")])
            return ["This url does not belong to the app".encode()]

    app.wsgi_app = PrefixMiddleware(app.wsgi_app, "/app/rf3d")


def _setup_cors(app):
    """添加 CORS 头部以允许跨域请求。"""
    allowed_origins = app.config["CORS_ALLOWED_ORIGINS"]

    @app.after_request
    def after_request(response):
        origin = request.headers.get("Origin", "")
        if origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        if request.method == "OPTIONS":
            response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
            response.headers["Access-Control-Allow-Methods"] = "GET,PUT,POST,DELETE,OPTIONS"
        response.headers.add("X-Frame-Options", "SAMEORIGIN")
        return response


def _setup_error_handlers(app):
    """注册统一错误处理（RFC 7807 兼容层）。"""

    @app.errorhandler(APIError)
    def handle_api_error(e):
        return error_response(e.status, e.title, e.detail, **e.ext)

    @app.errorhandler(404)
    def handle_not_found(e):
        return error_response(404, "Not Found", "请求的资源不存在")

    @app.errorhandler(405)
    def handle_method_not_allowed(e):
        return error_response(405, "Method Not Allowed", "请求方法不被允许")

    @app.errorhandler(500)
    def handle_internal_error(e):
        return error_response(500, "Internal Server Error", "服务器内部错误")
