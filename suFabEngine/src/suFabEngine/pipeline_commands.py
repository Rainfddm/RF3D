"""统一打印管线命令调度器。

消除 CommandExecutor (app.py)、_auto_execute_pipeline (AiTerminal.py)、
Viewer (suView.py) 三处重复的 if-elif 命令分发和参数同步逻辑。
"""

import logging
from typing import Any, Callable, Dict

# 命令执行签名: executor(command_name, **params) -> result
CommandHandler = Callable[..., Any]


class PipelineDispatcher:
    """统一的打印管线命令调度与参数同步器。

    所有命令执行路径（Web API / AI终端 / 桌面端）通过一致的接口调度：
    - 参数自动同步到 executor.params
    - 前置条件统一校验
    - 错误信息标准化
    """

    # 命令名 → 执行前需要同步的参数键映射
    PARAM_SYNC_MAP: Dict[str, list] = {
        "slice": ["layer_height", "first_layer_height", "nozzle_d",
                   "filament_d", "infill_density"],
        "generate_path": ["speed", "nozzle_d", "filament_d", "offset",
                           "reinforced_fiber_d", "base_fiber_d"],
        "generate_gcode": ["speed", "extruder_temp", "bed_temp",
                            "layer_height", "nozzle_d", "filament_d"],
    }

    @staticmethod
    def sync_params(executor: Any, command: str, params: dict) -> None:
        """将用户参数同步到 executor 的 params 字典（含 viewer 双写）"""
        keys = PipelineDispatcher.PARAM_SYNC_MAP.get(command, [])
        for key in keys:
            if key in params:
                try:
                    executor.params[key] = float(params[key])
                except (ValueError, TypeError):
                    logging.warning("参数 %s 格式无效: %s", key, params[key])
                if hasattr(executor, 'viewer') and executor.viewer:
                    executor.viewer.params[key] = executor.params[key]

    @staticmethod
    def dispatch(executor: Any, command: str, params: dict,
                 handler_map: Dict[str, CommandHandler],
                 preconditions: Dict[str, Callable] | None = None) -> Any:
        """统一命令调度入口。

        Args:
            executor: 命令执行器实例 (CommandExecutor / Viewer)
            command: 命令名称 ("slice" / "generate_path" / ...)
            params: 命令参数字典
            handler_map: {命令名: 处理方法} 映射
            preconditions: {命令名: 前置检查函数} 映射，返回 str 错误或 None
        """
        if command not in handler_map:
            raise ValueError(f"未知命令: {command}")

        if preconditions and command in preconditions:
            error = preconditions[command](executor)
            if error:
                return error

        PipelineDispatcher.sync_params(executor, command, params)
        logging.info("执行命令: %s, 参数: %s", command, params)
        return handler_map[command](**params)


# ---------- 标准前置条件（供 app.py 和 AiTerminal.py 共用）----------

def _has_model(executor) -> str | None:
    if not getattr(executor, 'b_stl_loaded', False):
        return "错误: 请先加载STL模型文件"
    return None


def _has_sliced(executor) -> str | None:
    # 优先用 b_stl_sliced 标志（PipelineExecutor）
    if getattr(executor, 'b_stl_sliced', False):
        return None
    # 兼容 pipeline.planes（PipelineExecutor）或 controller.planes（旧 Controller）
    for holder_attr in ('pipeline', 'controller'):
        holder = getattr(executor, holder_attr, None)
        if holder is not None and getattr(holder, 'planes', None):
            return None
    return "错误: 请先对模型进行切片"


# 标准前置条件映射
STANDARD_PRECONDITIONS: Dict[str, Callable] = {
    "slice": _has_model,
    "generate_path": _has_sliced,
    "generate_gcode": _has_sliced,
}
