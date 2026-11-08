"""工具函数。"""

import os
import uuid

from werkzeug.utils import secure_filename

# 前端参数键名 → 后端 params 键名 的别名映射
_PARAM_ALIAS = {"nozzle_diameter": "nozzle_d", "filament_diameter": "filament_d"}

# 允许的模型扩展名（与 upload_model 的读取器分发保持一致）
MODEL_EXTENSIONS = (".stl", ".obj", ".3mf")


def secure_model_filename(original_name):
    """生成可安全落盘、且**保留扩展名**的模型文件名。

    werkzeug 的 `secure_filename` 只保留 ASCII，非 ASCII 字符被整段剥掉，
    连分隔符的点也一起丢：

        secure_filename("螺旋桨.stl")      -> "stl"
        secure_filename("无人机 螺旋桨.STL") -> "STL"

    存成 `uploads/stl` 之后，`get_latest_stl()` 按 `.stl` 后缀找不到它，
    用户看到「上传成功」，下一步却提示「请先上传STL模型文件」。
    这里把 stem 与扩展名分开处理：stem 清洗失败就退回随机名，扩展名始终保留。
    """
    stem, ext = os.path.splitext(os.path.basename(original_name or ""))
    ext = ext.lower()

    safe_stem = secure_filename(stem)
    # 纯中文/纯符号的文件名会被清洗成空串，或清洗后恰好等于扩展名本身
    if not safe_stem or safe_stem.lower() == ext.lstrip("."):
        safe_stem = uuid.uuid4().hex[:12]

    return f"{safe_stem}{ext}"


def normalize_params(data):
    """将前端参数键名归一化为后端 params 键名。"""
    if not isinstance(data, dict):
        return {}
    return {_PARAM_ALIAS.get(k, k): v for k, v in data.items()}


def get_latest_stl(upload_folder):
    """返回 uploads 目录中最新上传的 STL 文件路径，无则返回 None。"""
    try:
        model_files = [f for f in os.listdir(upload_folder) if f.lower().endswith(".stl")]
    except OSError:
        return None
    if not model_files:
        return None
    latest = sorted(
        model_files, key=lambda x: os.path.getmtime(os.path.join(upload_folder, x))
    )[-1]
    return os.path.join(upload_folder, latest)
