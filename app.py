"""Web 后端入口（薄入口，应用逻辑在 application/ 包内）。

发布包是 src 布局：suFabEngine/ 与 suFabUI/ 的源码分别在各自的 src/ 下。
这里把它们插入 sys.path，使发布包**不依赖 `pip install -e`** 即可运行。

数据库 schema 由 Flask-Migrate/Alembic 管理（migrations/ 目录），
首次运行必须先执行 `python -m flask --app app db upgrade`。
"""

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
_ENGINE_SRC = os.path.join(_ROOT, "suFabEngine", "src")
_UI_SRC = os.path.join(_ROOT, "suFabUI", "src")

for _path in (_ENGINE_SRC, _UI_SRC):
    if os.path.isdir(_path) and _path not in sys.path:
        sys.path.insert(0, _path)

from application import create_app  # noqa: E402  （必须在 sys.path 注入之后导入）

flask_app = create_app()

# 兼容旧引用（部分脚本可能 import app.UPLOAD_FOLDER）
UPLOAD_FOLDER = flask_app.config["UPLOAD_FOLDER"]
STATIC_FOLDER = flask_app.config["STATIC_FOLDER"]


def _assert_inside_release():
    """断言算法包确实来自本发布包，而不是外部的 .pth / editable 安装。

    如果环境里残留了指向源码仓库的 editable 安装，导入会悄悄落到别的目录，
    发布包看起来能跑，实际用的是另一份代码。这里在启动时硬拦。
    """
    import suFabEngine
    import suFabUI

    for module, expected_root in ((suFabEngine, _ENGINE_SRC), (suFabUI, _UI_SRC)):
        module_file = getattr(module, "__file__", None)
        if not module_file:
            raise RuntimeError(
                f"{module.__name__} 被解析成了命名空间包（无 __file__），"
                f"期望位于 {expected_root} 内"
            )
        resolved = os.path.abspath(module_file)
        if not resolved.startswith(os.path.abspath(expected_root)):
            raise RuntimeError(
                f"{module.__name__} 来自发布包之外：{resolved}\n"
                f"期望位于 {expected_root} 内。"
                "请检查是否残留了旧的 pip install -e 或 PYTHONPATH。"
            )


_assert_inside_release()


if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
