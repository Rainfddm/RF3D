"""统一错误格式（RFC 7807 Problem Details）。

采用「兼容层」策略：错误响应同时保留旧字段（status / message）与
RFC 7807 标准字段（type / title / detail），前端可渐进迁移。
"""

from flask import jsonify


def error_response(status, title, detail, **ext):
    """构造统一错误响应（兼容旧前端 + RFC 7807）。"""
    body = {
        # 旧字段（前端现有代码依赖）
        "status": "error" if status >= 400 else "success",
        "message": detail,
        # RFC 7807 标准字段
        "type": "about:blank",
        "title": title,
        "detail": detail,
    }
    body.update(ext)
    return jsonify(body), status


class APIError(Exception):
    """携带 HTTP 状态码与 ProblemDetails 字段的业务异常。"""

    def __init__(self, status=400, title="Bad Request", detail="", **ext):
        self.status = status
        self.title = title
        self.detail = detail
        self.ext = ext
        super().__init__(detail)
