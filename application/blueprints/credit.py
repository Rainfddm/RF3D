"""信用点路由：查询、扣除、充值。"""

from flask import Blueprint, request, jsonify, session

from application.extensions import db
from application.models import User

credit_bp = Blueprint("credit", __name__)


@credit_bp.route("/api/get-credit-points", methods=["GET"])
def get_credit_points():
    """获取当前用户的信用点数。"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "用户未登录"})

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"status": "error", "message": "用户不存在"})

    return jsonify({"status": "success", "credit_points": user.credit_points})


@credit_bp.route("/api/deduct-credit", methods=["POST"])
def deduct_credit():
    """扣除信用点（每次 AI 生成方案消耗 1 点）。

    必须用「条件原子 UPDATE」而不是 `user.credit_points -= 1`：
    后者是读-改-写，并发时多个请求都基于同一个旧余额各自扣一次，
    成功次数可以超过可用点数（实测 16 线程 / 5 点全部返回 success）。
    条件 `credit_points > 0` 由数据库在一条语句内保证「检查 + 扣减」不可分割。
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "用户未登录"})

    updated = (
        db.session.query(User)
        .filter(User.id == user_id, User.credit_points > 0)
        .update(
            {"credit_points": User.credit_points - 1}, synchronize_session=False
        )
    )

    if not updated:
        db.session.rollback()
        # rowcount 为 0 有两种可能：用户不存在，或余额已耗尽。用一次只读查询区分，
        # 查完立即 rollback 释放读事务，避免与并发写形成锁升级死锁。
        exists = db.session.query(User.id).filter(User.id == user_id).first()
        db.session.rollback()
        message = "用户不存在" if exists is None else "信用点不足"
        return jsonify({"status": "error", "message": message})

    db.session.commit()
    remaining = (
        db.session.query(User.credit_points).filter(User.id == user_id).scalar()
    )
    return jsonify({"status": "success", "remaining_points": remaining})


@credit_bp.route("/api/recharge-credit", methods=["POST"])
def recharge_credit():
    """充值信用点。

    与扣减同理：`user.credit_points += amount` 是读-改-写，并发充值会互相覆盖
    （实测 16 次 +10 只到账 3 次，丢失 130 点）。改为数据库端自增。
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "用户未登录"})

    data = request.get_json(silent=True) or {}
    amount = data.get("amount", 0)
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return jsonify({"status": "error", "message": "充值金额必须是数字"})
    # credit_points 是 Integer 列：接受 10.5 会把 REAL 写进去，
    # 之后以 1 为步长扣减会得到 9.5 / 8.5 ...，永远无法精确归零。
    if amount != int(amount):
        return jsonify({"status": "error", "message": "充值金额必须是整数"})
    amount = int(amount)
    if amount <= 0:
        return jsonify({"status": "error", "message": "充值金额必须大于0"})

    updated = (
        db.session.query(User)
        .filter(User.id == user_id)
        .update(
            {"credit_points": User.credit_points + amount}, synchronize_session=False
        )
    )

    if not updated:
        db.session.rollback()
        return jsonify({"status": "error", "message": "用户不存在"})

    db.session.commit()
    new_points = (
        db.session.query(User.credit_points).filter(User.id == user_id).scalar()
    )
    return jsonify({"status": "success", "new_points": new_points})
