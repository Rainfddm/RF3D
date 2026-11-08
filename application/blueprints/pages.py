"""页面与文件下载路由。"""

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    send_from_directory,
    session,
    current_app,
)

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@pages_bp.route("/docs")
def docs():
    """API 文档（Swagger UI）。"""
    return send_from_directory(current_app.static_folder, "docs.html")


@pages_bp.route("/")
def index():
    if "user_id" in session:
        return render_template("index.html")
    return redirect(url_for("pages.login_page"))


@pages_bp.route("/login")
def login_page():
    return render_template("login.html")


@pages_bp.route("/register")
def register_page():
    return render_template("register.html")


@pages_bp.route("/recharge")
def recharge_page():
    if "user_id" not in session:
        return redirect(url_for("pages.login_page"))
    return render_template("recharge.html")
