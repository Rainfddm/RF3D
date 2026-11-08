"""AI 终端路由：自然语言 → 结构化操作序列。"""

import json
import logging
import os

from flask import Blueprint, request, jsonify, current_app

from suFabEngine.pipeline_executor import PipelineExecutor
from suFabEngine.ai_agent import (
    DEFAULT_MODELS,
    PrintingControlAgent,
    resolve_provider,
)
from suFabEngine.pipeline_commands import PipelineDispatcher, STANDARD_PRECONDITIONS
from application.utils import get_latest_stl

ai_bp = Blueprint("ai", __name__)


def _safe_result(obj):
    """将 execute_cmd 返回值转为 JSON 可序列化格式。"""
    if obj is None:
        return "操作完成"
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _safe_result(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_result(item) for item in obj]
    if hasattr(obj, "tolist"):
        return obj.tolist()
    return str(obj)


@ai_bp.route("/ai-terminal", methods=["POST"])
def ai_terminal():
    try:
        print(">>> AI Terminal 被调用")
        data = request.get_json()
        user_input = data.get("input", "") if data else ""

        if not user_input:
            return jsonify({"status": "error", "message": "请输入内容"})

        # 统一走 PrintingControlAgent.run_cmd（内部：工艺决策引擎 → LLM → 参数校验）
        chat_agent = PrintingControlAgent("fab_commander_agent", "fab_agent")
        # 提供方与模型由环境变量决定：AI_PROVIDER / AI_MODEL，
        # 未设置时自动挑选第一个已配置 key 的提供方（deepseek → kimi）。
        provider = resolve_provider(os.environ.get("AI_PROVIDER") or None)
        model = os.environ.get("AI_MODEL") or DEFAULT_MODELS.get(provider, "deepseek-chat")
        chat_agent.use(provider, model, 1000)

        result_json = chat_agent.run_cmd(user_input)
        if not result_json:
            return jsonify({"status": "error", "message": "AI处理未返回有效结果"})

        operations = result_json.get("operations", [])

        operation_descriptions = [op.get("description", "") for op in operations]
        response_message = "已分析您的需求，将执行以下操作：\n" + "\n".join(operation_descriptions)

        executor = PipelineExecutor()

        model_path = get_latest_stl(current_app.config["UPLOAD_FOLDER"])
        if not model_path:
            return jsonify({"status": "error", "message": "请先上传STL模型文件"})

        execution_results = []

        if not executor.b_stl_loaded:
            load_result = executor.execute_cmd("load_model", file_path=model_path)
            execution_results.append(load_result)

        handler_map = {
            "slice": lambda **p: executor.execute_cmd("slice", **p),
            "generate_path": lambda **p: executor.execute_cmd("generate_path", **p),
            "generate_gcode": lambda **p: executor.execute_cmd("generate_gcode", **p),
        }

        for operation in operations:
            cmd = operation.get("command")
            params = operation.get("parameters", {})

            try:
                if cmd == "load_model":
                    result = executor.execute_cmd(cmd, file_path=model_path)
                elif cmd in handler_map:
                    result = PipelineDispatcher.dispatch(
                        executor, cmd, params, handler_map,
                        preconditions=STANDARD_PRECONDITIONS,
                    )
                else:
                    executor.update_params_from_request(params)
                    result = executor.execute_cmd(cmd, **params)

                execution_results.append({
                    "command": cmd,
                    "status": "ok",
                    "result": _safe_result(result),
                })
            except Exception as e:
                logging.exception("AI操作链 [%s] 执行失败: %s", cmd, e)
                execution_results.append({
                    "command": cmd,
                    "status": "error",
                    "error": str(e),
                })

        return jsonify({
            "status": "success",
            "message": response_message,
            "operations": operations,
            "execution_results": execution_results,
            "raw_response": json.dumps(result_json, ensure_ascii=False),
        })

    except Exception as e:
        logging.exception("AI处理错误: %s", e)
        return jsonify({"status": "error", "message": f"AI处理错误: {str(e)}"})
