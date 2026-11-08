"""AI 打印控制 Agent（Qt-free）。

从 AiTerminal.py 抽离，供 Web 端与桌面端共用。
负责将自然语言指令转换为结构化操作序列，并对参数做物理约束校验。
"""

import json
import os
import time
import logging

import openai

from suAgent.constraint_validator import ConstraintValidator
from suAgent.process_decision_engine import ProcessDecisionEngine


def _fmt_param(value) -> str:
    """把参数值渲染成紧凑文本（30.0 → 30，0.2 → 0.2），用于 prompt 展示。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:g}"


# 示例 JSON 覆盖哪些命令、每个命令带哪些参数。
# 只列 ProcessDecisionEngine.default_params 里存在的键 —— 不存在的键会被跳过，
# 因此新增/删除默认参数时 prompt 自动跟随，不需要再同步维护一份副本。
_EXAMPLE_COMMAND_PARAMS = {
    "slice": ("layer_height", "first_layer_height", "infill_density"),
    "generate_path": ("nozzle_d", "filament_d", "offset"),
    "generate_gcode": ("speed", "extruder_temp", "bed_temp"),
}

_PARAM_LABELS = {
    "layer_height": ("层高", "mm"),
    "first_layer_height": ("首层高度", "mm"),
    "infill_density": ("填充密度", "%"),
    "nozzle_d": ("喷嘴", "mm"),
    "filament_d": ("耗材", "mm"),
    "offset": ("偏移", "mm"),
    "speed": ("速度", "mm/s"),
    "extruder_temp": ("喷嘴温度", "°C"),
    "bed_temp": ("热床", "°C"),
}


def _describe_params(params: dict) -> str:
    """把参数渲染成中文说明，如「层高0.2mm，填充密度30%」。"""
    parts = []
    for key, value in params.items():
        label, unit = _PARAM_LABELS.get(key, (key, ""))
        parts.append(f"{label}{_fmt_param(value)}{unit}")
    return "，".join(parts)


def _build_example_operations(defaults: dict) -> list:
    """用真相源的数值构造示例 operations，保证示例与默认值永不矛盾。"""
    operations = []
    for command, keys in _EXAMPLE_COMMAND_PARAMS.items():
        params = {key: defaults[key] for key in keys if key in defaults}
        if not params:
            continue
        operations.append(
            {
                "command": command,
                "parameters": params,
                "description": _describe_params(params),
            }
        )
    return operations


def strip_json_fence(text):
    """去掉 LLM 返回里的 markdown 围栏与前后说明，只留 JSON 对象。

    模型极常见地把结果包成 ```` ```json ... ``` ````，甚至前后再加一句
    「好的，结果如下：」。直接 json.loads 会抛 JSONDecodeError，
    用户侧表现为「AI 没反应」，日志里只有一行解析失败。
    """
    if not isinstance(text, str):
        return text

    stripped = text.strip()

    # 1) 有围栏：取围栏内部的第一个 JSON 块
    if "```" in stripped:
        blocks = stripped.split("```")
        for block in blocks[1::2]:  # 奇数下标才是围栏内容
            body = block.strip()
            if body[:4].lower() == "json":
                body = body[4:].strip()
            if body.startswith("{"):
                return body

    # 2) 无围栏或围栏里没找到 JSON：截取第一个 { 到最后一个 }
    start, end = stripped.find("{"), stripped.rfind("}")
    if start != -1 and end > start:
        return stripped[start : end + 1]

    return stripped


# 可重试的临时性故障（认证/参数错误不重试）
_RETRYABLE_API_ERRORS = tuple(
    err
    for err in (
        openai.RateLimitError,
        getattr(openai, "APITimeoutError", None),
        openai.APIConnectionError,
    )
    if err is not None
)


# ── LLM 提供方配置 ────────────────────────────────────────────
# 三家都走 OpenAI 兼容协议，差别只在 base_url 与 API Key 的环境变量名。
_API_BASE_URLS = {
    "kimi": "https://api.moonshot.cn/v1",
    "moonshot": "https://api.moonshot.cn/v1",
    "deepseek": "https://api.deepseek.com/v1",
}

# 按顺序尝试，第一个非空的就是要用的 key
_API_KEY_ENVS = {
    "kimi": ("MOONSHOT_API_KEY", "OPENAI_API_KEY"),
    "moonshot": ("MOONSHOT_API_KEY", "OPENAI_API_KEY"),
    "deepseek": ("DEEPSEEK_API_KEY", "OPENAI_API_KEY"),
}

DEFAULT_MODELS = {
    "kimi": "moonshot-v1-8k",
    "moonshot": "moonshot-v1-8k",
    "deepseek": "deepseek-chat",
}

# 未显式指定提供方时，按这个顺序挑第一个配了 key 的
_PROVIDER_PREFERENCE = ("deepseek", "kimi")


def _resolve_api_key(provider):
    """取指定提供方的 API Key；都找不到返回 None。"""
    env_names = _API_KEY_ENVS.get(provider, ("OPENAI_API_KEY",))
    for name in env_names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def resolve_provider(preferred=None):
    """决定本次使用哪个 LLM 提供方。

    显式指定优先；否则挑第一个已配好 key 的（deepseek → kimi），
    都没配时回落到 deepseek，让报错信息指向真正该配的那一项。
    """
    if preferred:
        return preferred
    for name in _PROVIDER_PREFERENCE:
        if _resolve_api_key(name):
            return name
    return "deepseek"


def _load_dotenv():
    """从项目根 .env 加载环境变量（不依赖第三方库）。"""
    _dotenv_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "../../../", ".env"
    )
    if not os.path.exists(_dotenv_path):
        return
    with open(_dotenv_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip()
            if key and val and key not in os.environ:
                os.environ[key] = val


_load_dotenv()


class PrintingControlAgent:
    def __init__(self, agent_id: str, agent_type: str):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.beliefs = {}
        self.available_commands = {
            "load_model": "装入3D模型文件",
            "slice": "将3D模型切片",
            "generate_path": "生成打印路径",
            "generate_gcode": "生成GCode",
            "print": "执行打印操作"
        }

        # 初始化API相关属性
        self.api_type = None
        self.model_name = None
        self.max_tokens = None

    def use(self, api_type: str, model_name: str, max_tokens: int):
        """设置使用的API和模型"""
        self.api_type = api_type
        self.model_name = model_name
        self.max_tokens = max_tokens

    def update_belief(self, key: str, value):
        """更新信念状态"""
        self.beliefs[key] = value

    def validate_and_adjust_parameters(self, parameters: dict,
                                       material_recommendations: dict | None = None) -> dict:
        """
        验证并自动调整不合理的打印参数（物理约束 + 可选的材料温度约束）。
        """
        result = ConstraintValidator.validate(parameters, material_recommendations)
        adjusted_params = ConstraintValidator.apply_corrections(
            parameters, result["corrected_params"]
        )
        if result["violations"]:
            logging.info("AI自动参数调整: %s", result["violations"])
        return adjusted_params

    def execute_intentions(self):
        """调用LLM API执行自然语言指令解析"""
        api_key = _resolve_api_key(self.api_type)
        if not api_key:
            logging.error(
                "未找到 %s 的 API Key（已尝试环境变量：%s）",
                self.api_type,
                "、".join(_API_KEY_ENVS.get(self.api_type, ("OPENAI_API_KEY",))),
            )
            return None

        # base_url 为 None 时 openai SDK 用官方地址；kimi / deepseek 走各自的兼容端点
        client = openai.OpenAI(api_key=api_key, base_url=_API_BASE_URLS.get(self.api_type))

        prompt = self.beliefs.get("prompt", [])

        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                completion = client.chat.completions.create(
                    model=self.model_name,
                    messages=prompt,
                    temperature=0.3,
                    max_tokens=self.max_tokens
                )
                return completion.choices[0].message.content

            except _RETRYABLE_API_ERRORS as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logging.warning(
                        "API 暂时性失败（%s），%ds 后重试 (%d/%d)",
                        type(e).__name__,
                        wait_time,
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(wait_time)
                else:
                    logging.error("达到最大重试次数，API调用失败: %s", e)
                    return None

            except openai.AuthenticationError as e:
                logging.error("API认证错误: %s", e)
                return None
            except Exception as e:
                logging.error("API调用异常: %s: %s", type(e).__name__, e)
                return None

        return None

    def make_prompt(self, query: str, decision=None) -> None:
        """构建 LLM 调用的消息 prompt。

        Args:
            query: 用户自然语言输入
            decision: ProcessDecisionEngine.decide() 的返回（可选）。
                      非 None 时把工艺决策引擎的推荐参数注入 system prompt。

        注意：prompt 里的【参数默认值】与【示例】全部由
        `ProcessDecisionEngine().default_params` 动态渲染，不得再写字面量。
        历史上这里抄过一份副本，结果是默认值写 0.4、同一段示例里又写 0.8，
        模型同时看到两个喷嘴直径。
        """
        defaults = ProcessDecisionEngine().default_params
        defaults_line = ", ".join(
            f"{key}={_fmt_param(value)}" for key, value in defaults.items()
        )
        example_json = json.dumps(
            {"operations": _build_example_operations(defaults)}, ensure_ascii=False
        )

        system_prompt = (
            "你是一个专业的3D打印控制助手，负责将自然语言指令转换为结构化操作序列。\n\n"
            "【可用命令】\n"
            "- load_model(file_path)：装入3D模型文件\n"
            "- slice(layer_height, first_layer_height, infill_density)：切片，参数为层高(mm)、首层高度(mm)、填充密度(%)\n"
            "- generate_path(nozzle_d, filament_d, offset)：生成连续打印路径\n"
            "- generate_gcode(speed, extruder_temp, bed_temp)：生成GCode，参数为打印速度(mm/s)、喷嘴温度(°C)、热床温度(°C)\n"
            "- print(gcode_file)：执行打印操作\n\n"
            "【参数默认值】\n"
            f"{defaults_line}\n\n"
            "【输出格式】\n"
            "仅输出合法 JSON，结构如下（不要包含任何额外文字）：\n"
            '{"operations": [{"command": "<命令名>", "parameters": {<参数键值对>}, "description": "<中文说明>"}]}\n\n'
            "【示例】\n"
            '输入: "切片并生成路径，层高0.2mm，喷嘴直径0.8mm，耗材1.75mm，速度60mm/s，温度200°C"\n'
            f"输出: {example_json}\n\n"
            "【注意事项】\n"
            "1. 操作顺序必须遵循依赖关系：load_model → slice → generate_path → generate_gcode → print\n"
            "2. 未指定的参数使用上方默认值\n"
            "3. 参数值必须符合物理约束（如 layer_height ≤ nozzle_d）\n"
            "4. 仅输出 JSON，不要有多余的分析文字"
        )

        if decision is not None:
            context_blocks = [decision.llm_context]

            # 补充材料工艺参数范围（温度/速度），让 LLM 能"查到"具体数值
            mr = getattr(decision, "material_recommendation", None)
            if mr and "error" not in mr:
                extra = []
                if mr.get("nozzle_temp_range"):
                    lo, hi = mr["nozzle_temp_range"]
                    extra.append(
                        f"喷嘴温度: {lo}-{hi}℃（推荐 {mr.get('recommended_nozzle_temp', '?')}℃）"
                    )
                if mr.get("bed_temp_range"):
                    lo, hi = mr["bed_temp_range"]
                    extra.append(
                        f"热床温度: {lo}-{hi}℃（推荐 {mr.get('recommended_bed_temp', '?')}℃）"
                    )
                if mr.get("speed_range"):
                    lo, hi = mr["speed_range"]
                    extra.append(
                        f"打印速度: {lo}-{hi}mm/s（推荐 {mr.get('recommended_speed', '?')}mm/s）"
                    )
                if extra:
                    context_blocks.append("【材料工艺参数范围】\n  " + "\n  ".join(extra))

            system_prompt += (
                "\n\n【工艺决策引擎推荐参数】（已根据材料/使用场景/模型几何自动计算）\n"
                + "\n".join(context_blocks)
                + "\n\n【参数使用规则】\n"
                "1. 优先采用上述推荐参数，除非用户明确指定了其他值\n"
                "2. 用户明确指定的参数以用户为准\n"
                "3. 所有参数最终仍需满足物理约束\n"
            )

        prompt = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
        self.update_belief("prompt", prompt)

    def run_cmd(self, query: str) -> dict | None:
        """执行自然语言指令并返回操作序列字典。

        流程：工艺决策引擎（材料/场景/几何 → 推荐参数）→ LLM 微调 →
        参数校验（物理约束 + 材料温度约束）。
        """
        try:
            # Step 0: 工艺决策引擎（确定性，识别材料/场景/几何，产出推荐参数）
            decision = None
            try:
                decision = ProcessDecisionEngine().decide(query)
            except Exception:
                logging.exception("工艺决策引擎失败，降级为纯 LLM 模式")
                decision = None

            self.make_prompt(query, decision)
            response = self.execute_intentions()
            if not response:
                return None

            result_dict = json.loads(strip_json_fence(response))
            logging.debug("AI原始响应: %s", response)

            # 对每个操作的参数进行验证和调整（含材料温度约束）
            material_rec = decision.material_recommendation if decision else None
            if "operations" in result_dict:
                for op in result_dict["operations"]:
                    if "parameters" in op:
                        original_params = op["parameters"].copy()
                        op["parameters"] = self.validate_and_adjust_parameters(
                            op["parameters"], material_rec
                        )
                        if original_params != op["parameters"]:
                            logging.info("参数已调整: %s -> %s", original_params, op["parameters"])

            return result_dict
        except json.JSONDecodeError:
            logging.exception("JSON解析失败")
            return None
        except Exception:
            logging.exception("指令执行异常")
            return None
