"""认证路由：登录、注册、登出、会话检查。"""

import logging
import re

from flask import Blueprint, request, jsonify, session

from application.extensions import db
from application.models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password) and user.is_active:
            session["user_id"] = user.id
            session["username"] = user.username
            return jsonify({
                "status": "success",
                "message": "登录成功",
                "redirect_url": "/",
            })
        else:
            return jsonify({"status": "error", "message": "用户名或密码错误"})
    except Exception:
        # 不把异常文本回传给客户端：可能泄露 SQL、文件路径等内部细节。
        # 具体原因留在服务端日志里排查。
        logging.exception("登录处理异常")
        return jsonify({"status": "error", "message": "登录失败，请稍后重试"})


@auth_bp.route("/api/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        username = data.get("username", "").strip()
        email = data.get("email", "").strip()
        password = data.get("password", "")

        if not username or len(username) < 2:
            return jsonify({"status": "error", "message": "用户名至少需要2个字符"}), 400
        if len(username) > 50:
            return jsonify({"status": "error", "message": "用户名不能超过50个字符"}), 400
        if not password or len(password) < 8:
            return jsonify({"status": "error", "message": "密码至少需要8个字符"}), 400
        if not email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            return jsonify({"status": "error", "message": "请输入有效的邮箱地址"}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({"status": "error", "message": "用户名已存在"})
        if User.query.filter_by(email=email).first():
            return jsonify({"status": "error", "message": "邮箱已被注册"})

        user = User(username=username, email=email, credit_points=100)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        return jsonify({"status": "success", "message": "注册成功"})
    except Exception:
        logging.exception("注册处理异常")
        return jsonify({"status": "error", "message": "注册失败，请稍后重试"})


@auth_bp.route("/api/logout", methods=["POST"])
def logout():
    try:
        session.pop("user_id", None)
        session.pop("username", None)
        return jsonify({"status": "success", "message": "退出登录成功"})
    except Exception:
        # 不把异常文本回传给客户端：可能泄露 SQL、文件路径等内部细节。
        # 具体原因留在服务端日志里排查。
        logging.exception("登录处理异常")
        return jsonify({"status": "error", "message": "登录失败，请稍后重试"})


@auth_bp.route("/api/check-session")
def check_session():
    if "user_id" in session:
        return jsonify({
            "logged_in": True,
            "username": session.get("username"),
        })
    return jsonify({"logged_in": False})
