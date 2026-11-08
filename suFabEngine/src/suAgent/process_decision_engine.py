"""
ProcessDecisionEngine — 不依赖 LLM 的确定性工艺决策引擎。

核心设计：双层架构
  Layer 1（本模块）：基于规则的确定性参数推荐
    - GeometryToParamMapper  : 模型几何特征 → 参数约束
    - IntentToStrategyMapper : 用户意图关键词 → 打印策略
    - MultiObjectiveOptimizer: 候选参数组合 → 加权评分 → 最优解

  Layer 2（agents.py）    ：LLM 审查 + 解释
    - 系统推荐的参数注入 prompt
    - LLM 解释选择理由、调整边界case

这样即使 LLM API 不可用，系统仍然能给出合理的工艺方案。
"""

import logging
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


# ============================================================
# 策略枚举
# ============================================================

class PrintStrategy(Enum):
    """打印策略 — 由用户意图推导"""
    LOW_WEIGHT = "low_weight"           # 轻量化（无人机、航模）
    HIGH_STRENGTH = "high_strength"     # 高强度（结构件、受力件）
    FAST_PROTOTYPE = "fast_prototype"   # 快速成型（原型验证）
    SURFACE_QUALITY = "surface_quality" # 表面质量（展示件）
    HEAT_RESISTANT = "heat_resistant"   # 耐热（工程件、高温环境）
    BALANCED = "balanced"               # 均衡（默认）


# ============================================================
# 策略权重表 — 用于多目标优化
# ============================================================

STRATEGY_WEIGHTS = {
    PrintStrategy.LOW_WEIGHT:       {"strength": 0.15, "speed": 0.30, "cost": 0.55},
    PrintStrategy.HIGH_STRENGTH:    {"strength": 0.60, "speed": 0.20, "cost": 0.20},
    PrintStrategy.FAST_PROTOTYPE:   {"strength": 0.15, "speed": 0.65, "cost": 0.20},
    PrintStrategy.SURFACE_QUALITY:  {"strength": 0.25, "speed": 0.25, "cost": 0.50},
    PrintStrategy.HEAT_RESISTANT:   {"strength": 0.55, "speed": 0.15, "cost": 0.30},
    PrintStrategy.BALANCED:         {"strength": 0.35, "speed": 0.35, "cost": 0.30},
}

# ============================================================
# 策略 → 参数目标方向
# ============================================================

STRATEGY_PARAM_DIRECTION = {
    PrintStrategy.LOW_WEIGHT: {
        "infill_density":   (10, 25),
        "wall_count":       2,
        "layer_height_dir": "higher",
        "speed_dir":        "moderate",
        "preferred_materials": ["碳纤维pla", "玻璃纤维pla"],
    },
    PrintStrategy.HIGH_STRENGTH: {
        "infill_density":   (40, 65),
        "wall_count":       4,
        "layer_height_dir": "lower",
        "speed_dir":        "lower",
        "preferred_materials": ["碳纤维pla", "尼龙"],
    },
    PrintStrategy.FAST_PROTOTYPE: {
        "infill_density":   (10, 20),
        "wall_count":       2,
        "layer_height_dir": "higher",
        "speed_dir":        "higher",
        "preferred_materials": ["pla"],
    },
    PrintStrategy.SURFACE_QUALITY: {
        "infill_density":   (15, 25),
        "wall_count":       3,
        "layer_height_dir": "lower",
        "speed_dir":        "lower",
        "preferred_materials": ["pla", "petg"],
    },
    PrintStrategy.HEAT_RESISTANT: {
        "infill_density":   (40, 65),
        "wall_count":       3,
        "layer_height_dir": "lower",
        "speed_dir":        "lower",
        "preferred_materials": ["abs", "尼龙"],
    },
    PrintStrategy.BALANCED: {
        "infill_density":   (20, 40),
        "wall_count":       3,
        "layer_height_dir": "moderate",
        "speed_dir":        "moderate",
        "preferred_materials": ["pla", "petg"],
    },
}


# ============================================================
# 几何 → 参数映射规则
# ============================================================

@dataclass
class GeometryParamRule:
    """单条几何→参数映射规则"""
    condition_desc: str
    param: str
    value_formula: str
    reason: str

    def evaluate(self, model_analysis: dict) -> Optional[Tuple[str, float, str]]:
        """评估规则，返回 (参数名, 值, 理由) 或 None"""
        raise NotImplementedError


class GeometryToParamMapper:
    """模型几何特征 → 参数推荐。

    不依赖 LLM，纯确定性规则。
    每条规则有可追溯的条件和理由。
    """

    # 所有规则定义
    RULES = [
        # ── 层高规则 ──
        {
            "param": "layer_height",
            "condition": lambda ma: (
                ma.get("wall_analysis", {}).get("min_dimension_mm", 999) < 1.0
            ),
            "value": lambda ma: round(
                max(0.1, ma["wall_analysis"]["min_dimension_mm"] * 0.5), 2
            ),
            "reason_tpl": "模型最小维度仅 {min_dim}mm，层高自动调整为 {value}mm（≤ 最小维度×0.5）",
        },
        {
            "param": "layer_height",
            "condition": lambda ma: (
                "z" in ma.get("dimensions_mm", {})
                and ma.get("dimensions_mm", {}).get("z", 0) < 10
            ),
            "value": lambda ma: 0.12,
            "reason_tpl": "模型Z高度仅 {z}mm（<10mm），降低层高至 0.12mm 以保证细节精度",
        },
        # ── 喷嘴直径规则 ──
        {
            "param": "nozzle_d",
            "condition": lambda ma: (
                ma.get("wall_analysis", {}).get("min_dimension_mm", 999) < 0.6
            ),
            "value": lambda ma: 0.4,
            "reason_tpl": "模型最小维度仅 {min_dim}mm（<0.6mm），喷嘴直径需降至 0.4mm",
        },
        # ── 填充密度规则 ──
        {
            "param": "infill_density",
            "condition": lambda ma: (
                ma.get("volume_mm3", 0) > 100_000  # >100cm³
            ),
            "value": lambda ma: 15.0,
            "reason_tpl": "模型体积 {vol}cm³（>100cm³），大件默认降低填充至 15% 以节约材料",
        },
        {
            "param": "infill_density",
            "condition": lambda ma: (
                0 < ma.get("volume_mm3", 0) <= 10_000  # ≤10cm³
            ),
            "value": lambda ma: 30.0,
            "reason_tpl": "模型体积 {vol}cm³（≤10cm³），小件默认填充 30% 保证强度",
        },
        # ── 热床附着规则 ──
        {
            "param": "brim_recommended",
            "condition": lambda ma: (
                ma.get("aspect_ratio", 1) > 3.0
            ),
            "value": lambda ma: True,
            "reason_tpl": "模型长宽比 {ratio}:1（>3:1），热床接触面窄，建议启用 Brim 防翘曲",
        },
        # ── 速度规则（大件降速） ──
        {
            "param": "speed_scale",
            "condition": lambda ma: (
                ma.get("dimensions_mm", {}).get("z", 0) > 100
            ),
            "value": lambda ma: 0.8,
            "reason_tpl": "模型Z高度 {z}mm（>100mm），建议速度降至 80% 防止高层晃动",
        },
        # ── 悬挑规则 ──
        {
            "param": "needs_support",
            "condition": lambda ma: (
                ma.get("overhang_analysis", {}).get("needs_support", False)
            ),
            "value": lambda ma: True,
            "reason_tpl": "严重悬挑面占比 {severe_pct}%，建议启用支撑结构",
        },
    ]

    @classmethod
    def apply(cls, model_analysis: dict) -> dict:
        """评估所有几何规则，返回推荐的参数调整。

        Args:
            model_analysis: ModelAnalyzer.analyze() 的输出

        Returns:
            dict: {
                "recommended_params": {"layer_height": 0.12, ...},
                "warnings": ["模型最小维度...", ...],
                "rule_count": int,
            }
        """
        recommended = {}
        warnings_list = []

        # 无几何分析数据时（decide 未收到 model_analysis）跳过所有几何规则。
        # 否则 condition 里的默认值会误触发——例如 dimensions_mm.z 缺失时
        # get("z", 0) 返回 0，而 0 < 10 为真，导致层高被错误降到 0.12。
        has_geometry = bool(
            model_analysis.get("dimensions_mm")
            or model_analysis.get("wall_analysis")
        )
        if not has_geometry:
            return {"recommended_params": {}, "warnings": [], "rule_count": 0}

        for rule in cls.RULES:
            condition = rule["condition"]
            value_fn = rule["value"]
            param = rule["param"]
            reason_tpl = rule["reason_tpl"]

            try:
                if condition(model_analysis):
                    val = value_fn(model_analysis)

                    # 填充模板变量
                    dims = model_analysis.get("dimensions_mm", {})
                    wall = model_analysis.get("wall_analysis", {})
                    overhang = model_analysis.get("overhang_analysis", {})
                    vol = round(model_analysis.get("volume_mm3", 0) / 1000, 1)

                    reason = reason_tpl.format(
                        min_dim=wall.get("min_dimension_mm", "?"),
                        value=val,
                        z=dims.get("z", "?"),
                        vol=vol,
                        ratio=model_analysis.get("aspect_ratio", "?"),
                        severe_pct=overhang.get("severe_pct", "?"),
                    )

                    recommended[param] = val
                    warnings_list.append(reason)

                    logging.info("几何规则触发: [%s] → %s", param, reason)
            except Exception:
                logging.debug("几何规则评估跳过: %s", rule.get("param", "?"))

        return {
            "recommended_params": recommended,
            "warnings": warnings_list,
            "rule_count": len(recommended),
        }


# ============================================================
# 意图 → 策略映射
# ============================================================

INTENT_KEYWORD_MAP = {
    PrintStrategy.LOW_WEIGHT: [
        "轻量化", "轻量", "减重", "无人机", "航模", "飞行器",
        "四轴", "穿越机", "fpv", "drone", "uav",
    ],
    PrintStrategy.HIGH_STRENGTH: [
        "高强度", "受力", "结构件", "承重", "耐冲击", "加强",
        "强度优先", "结构强度", "力学", "承载",
    ],
    PrintStrategy.FAST_PROTOTYPE: [
        "快速", "原型", "验证", "打样", "试制", "快速成型",
        "速度优先", "赶时间", "越快越好", "prototype",
    ],
    PrintStrategy.SURFACE_QUALITY: [
        "表面", "光滑", "外观", "展示", "美观", "精度",
        "光洁度", "细纹", "陈列", "模型展示",
    ],
    PrintStrategy.HEAT_RESISTANT: [
        "耐热", "高温", "耐温", "工程", "发动机", "排气",
        "散热", "隔热", "heat",
    ],
}


class IntentToStrategyMapper:
    """用户自然语言意图 → 打印策略。

    基于关键词匹配，不依赖 LLM。
    支持多策略合并（取最严格的约束）。
    """

    @classmethod
    def classify(cls, user_text: str) -> PrintStrategy:
        """从用户输入中识别主要打印策略。

        优先级：命中第一个匹配的策略。
        如果多个命中，取权重最高的（高强度 > 耐热 > 轻量化 > 表面质量 > 快速成型）。
        """
        text_lower = user_text.lower()
        hits = []

        for strategy, keywords in INTENT_KEYWORD_MAP.items():
            for kw in keywords:
                if kw in text_lower:
                    hits.append(strategy)
                    break

        if not hits:
            return PrintStrategy.BALANCED

        if len(hits) == 1:
            return hits[0]

        # 多策略命中 → 按优先级选取
        priority = [
            PrintStrategy.HIGH_STRENGTH,
            PrintStrategy.HEAT_RESISTANT,
            PrintStrategy.LOW_WEIGHT,
            PrintStrategy.SURFACE_QUALITY,
            PrintStrategy.FAST_PROTOTYPE,
        ]
        for p in priority:
            if p in hits:
                return p

        return PrintStrategy.BALANCED

    @classmethod
    def get_strategy_params(cls, strategy: PrintStrategy) -> dict:
        """获取策略对应的参数方向和建议。"""
        return dict(STRATEGY_PARAM_DIRECTION.get(strategy, STRATEGY_PARAM_DIRECTION[PrintStrategy.BALANCED]))

    @classmethod
    def get_weights(cls, strategy: PrintStrategy) -> dict:
        """获取策略对应的多目标优化权重。"""
        return dict(STRATEGY_WEIGHTS.get(strategy, STRATEGY_WEIGHTS[PrintStrategy.BALANCED]))


# ============================================================
# 多目标优化器
# ============================================================

@dataclass
class ParamCandidate:
    """一组候选工艺参数"""
    layer_height: float
    nozzle_d: float
    infill_density: float
    speed: float
    extruder_temp: float
    source: str  # 来源标识: "material" | "geometry" | "default"

    def to_dict(self) -> dict:
        return {
            "layer_height": self.layer_height,
            "nozzle_d": self.nozzle_d,
            "infill_density": self.infill_density,
            "speed": self.speed,
            "extruder_temp": self.extruder_temp,
        }


class MultiObjectiveOptimizer:
    """多目标优化器。

    对多组候选参数进行加权评分，选最优。
    三个维度：强度、速度、成本。
    """

    @staticmethod
    def _score_strength(candidate: ParamCandidate) -> float:
        """强度得分（越高越好）"""
        score = 0.0
        # 低层高 → 高结合强度
        if candidate.layer_height <= 0.15:
            score += 0.4
        elif candidate.layer_height <= 0.25:
            score += 0.2
        # 高填充 → 高整体强度
        if candidate.infill_density >= 50:
            score += 0.35
        elif candidate.infill_density >= 30:
            score += 0.15
        # 小喷嘴 → 精细 → 层间结合好（可接受）
        # 高温 → 层间熔融更好
        if candidate.extruder_temp >= 240:
            score += 0.25
        elif candidate.extruder_temp >= 210:
            score += 0.15
        return min(score, 1.0)

    @staticmethod
    def _score_speed(candidate: ParamCandidate) -> float:
        """速度得分（越高越好）"""
        score = 0.0
        # 高层高 → 少层数 → 快
        if candidate.layer_height >= 0.25:
            score += 0.3
        elif candidate.layer_height >= 0.2:
            score += 0.15
        # 高速度
        if candidate.speed >= 80:
            score += 0.35
        elif candidate.speed >= 50:
            score += 0.2
        # 低填充
        if candidate.infill_density <= 15:
            score += 0.35
        elif candidate.infill_density <= 30:
            score += 0.2
        return min(score, 1.0)

    @staticmethod
    def _score_cost(candidate: ParamCandidate) -> float:
        """成本得分（越高越省钱）"""
        score = 0.0
        # 高填充 → 多耗材 → 成本高 → 得分低
        if candidate.infill_density <= 15:
            score += 0.4
        elif candidate.infill_density <= 30:
            score += 0.25
        elif candidate.infill_density <= 50:
            score += 0.1
        # 低温 → 省电
        if candidate.extruder_temp <= 200:
            score += 0.3
        elif candidate.extruder_temp <= 230:
            score += 0.15
        # 高层高 → 少时间 → 省电
        if candidate.layer_height >= 0.25:
            score += 0.3
        elif candidate.layer_height >= 0.2:
            score += 0.15
        return min(score, 1.0)

    @classmethod
    def optimize(cls,
                 candidates: List[ParamCandidate],
                 strategy: PrintStrategy) -> ParamCandidate:
        """从候选参数中选出加权评分最优的一个。

        Args:
            candidates: 候选参数列表（至少 1 个）
            strategy: 打印策略

        Returns:
            最优 ParamCandidate
        """
        if not candidates:
            raise ValueError("候选参数列表不能为空")
        if len(candidates) == 1:
            return candidates[0]

        weights = STRATEGY_WEIGHTS[strategy]
        best_candidate = candidates[0]
        best_score = -1.0

        for c in candidates:
            s_strength = cls._score_strength(c)
            s_speed = cls._score_speed(c)
            s_cost = cls._score_cost(c)

            total = (
                weights["strength"] * s_strength
                + weights["speed"] * s_speed
                + weights["cost"] * s_cost
            )

            logging.debug(
                "候选 [%s] 评分: strength=%.2f speed=%.2f cost=%.2f total=%.3f",
                c.source, s_strength, s_speed, s_cost, total,
            )

            if total > best_score:
                best_score = total
                best_candidate = c

        logging.info(
            "多目标优化完成: 策略=%s, 最优来源=%s, 分数=%.3f",
            strategy.value, best_candidate.source, best_score,
        )
        return best_candidate


# ============================================================
# 顶层决策引擎
# ============================================================

@dataclass
class DecisionResult:
    """决策引擎输出"""
    # 推荐参数
    params: dict
    # 元信息
    strategy: PrintStrategy
    strategy_desc: str
    # 几何推导的参数（可能被合并覆盖）
    geometry_params: dict
    geometry_warnings: list
    # 材料推荐
    material_recommendation: dict
    # 候选列表 + 最优来源
    candidate_source: str
    # 规则触发数
    rule_count: int
    # 给 LLM 的上下文（精简版）
    llm_context: str


class ProcessDecisionEngine:
    """顶层决策引擎 — 无 LLM 的确定性工艺决策。

    使用示例::

        engine = ProcessDecisionEngine()
        result = engine.decide(
            user_text="碳纤维无人机螺旋桨，轻量化",
            model_analysis=model_analysis_dict,
        )
        # result.params → {"layer_height": 0.15, "nozzle_d": 0.6, ...}
        # result.llm_context → 可供 LLM 审查的结构化文本
    """

    # 策略中文描述
    STRATEGY_DESCRIPTIONS = {
        PrintStrategy.LOW_WEIGHT:      "轻量化策略 — 低填充、薄壁、优先碳纤/玻纤材料",
        PrintStrategy.HIGH_STRENGTH:   "高强度策略 — 高填充、低层高、优先碳纤/尼龙材料",
        PrintStrategy.FAST_PROTOTYPE:  "快速成型策略 — 高层高、低填充、优先PLA材料",
        PrintStrategy.SURFACE_QUALITY: "表面质量策略 — 低层高、中填充、优先PLA/PETG材料",
        PrintStrategy.HEAT_RESISTANT:  "耐热策略 — 高填充、高温、优先ABS/尼龙材料",
        PrintStrategy.BALANCED:        "均衡策略 — 中等参数、通用PLA材料",
    }

    def __init__(self):
        # 可从外部注入的默认值
        self.default_params = {
            "layer_height": 0.2,
            "first_layer_height": 0.2,
            "nozzle_d": 0.8,
            "filament_d": 1.75,
            "infill_density": 30.0,
            "speed": 60,
            "extruder_temp": 200,
            "bed_temp": 60,
            "offset": 0.8,
        }

    def decide(self,
               user_text: str,
               model_analysis: dict | None = None) -> DecisionResult:
        """执行确定性工艺决策。

        Args:
            user_text: 用户自然语言输入
            model_analysis: ModelAnalyzer.analyze() 的输出（可选）

        Returns:
            DecisionResult
        """
        model_analysis = model_analysis or {}

        # ── Step 1: 意图分类 + 策略选择 ──
        strategy = IntentToStrategyMapper.classify(user_text)
        strategy_params = IntentToStrategyMapper.get_strategy_params(strategy)

        logging.info("决策引擎: 意图分析 → 策略=%s", strategy.value)

        # ── Step 2: 几何分析 → 参数调整 ──
        geo_result = GeometryToParamMapper.apply(model_analysis)

        # ── Step 3: 材料推荐 ──
        from suAgent.material_reasoner import MaterialReasoner

        material_name = MaterialReasoner.identify_material(user_text)
        material_rec = {}
        if material_name:
            material_rec = MaterialReasoner.get_recommendations(material_name)
        elif strategy_params.get("preferred_materials"):
            # 无材料关键词 → 取策略首选材料
            fallback_mat = strategy_params["preferred_materials"][0]
            material_rec = MaterialReasoner.get_recommendations(fallback_mat)

        # ── Step 3.5: 纤维×基体组合 + 场景模板识别（RF3D 核心参数）──
        from suAgent.fiber_composite_db import identify_fiber_matrix, identify_scene_template

        fiber_matrix = identify_fiber_matrix(user_text)
        scene_template = identify_scene_template(user_text)
        if fiber_matrix:
            logging.info("决策引擎: 纤维组合=%s（铺设方式=%s）", fiber_matrix["name"], fiber_matrix["layup"])
        if scene_template:
            logging.info("决策引擎: 场景模板=%s", scene_template["name"])

        # ── Step 4: 构建候选参数列表 ──
        candidates = self._build_candidates(
            strategy=strategy,
            strategy_params=strategy_params,
            geo_result=geo_result,
            material_rec=material_rec,
        )

        # ── Step 5: 多目标优化选最优 ──
        best = MultiObjectiveOptimizer.optimize(candidates, strategy)

        # ── Step 6: 合并最终参数 ──
        final_params = self._merge_params(
            best_candidate=best,
            geo_result=geo_result,
            material_rec=material_rec,
            fiber_matrix=fiber_matrix,
            scene_template=scene_template,
        )

        # ── Step 7: 构建 LLM 上下文 ──
        llm_context = self._build_llm_context(
            strategy=strategy,
            strategy_params=strategy_params,
            geo_result=geo_result,
            material_rec=material_rec,
            fiber_matrix=fiber_matrix,
            scene_template=scene_template,
            best_candidate=best,
            final_params=final_params,
        )

        return DecisionResult(
            params=final_params,
            strategy=strategy,
            strategy_desc=self.STRATEGY_DESCRIPTIONS.get(strategy, ""),
            geometry_params=geo_result["recommended_params"],
            geometry_warnings=geo_result["warnings"],
            material_recommendation=material_rec,
            candidate_source=best.source,
            rule_count=geo_result["rule_count"],
            llm_context=llm_context,
        )

    # ── 私有方法 ────────────────────────────────────────────

    def _build_candidates(self,
                          strategy: PrintStrategy,
                          strategy_params: dict,
                          geo_result: dict,
                          material_rec: dict) -> List[ParamCandidate]:
        """构建候选参数组合列表。"""
        candidates = []
        geo = geo_result.get("recommended_params", {})

        # 候选 1: 材料推荐
        if material_rec and "error" not in material_rec:
            candidates.append(ParamCandidate(
                layer_height=material_rec.get("recommended_layer_height", 0.2),
                nozzle_d=geo.get("nozzle_d", self.default_params["nozzle_d"]),
                infill_density=(
                    geo.get("infill_density")
                    or self.default_params["infill_density"]
                ),
                speed=material_rec.get("recommended_speed", 60),
                extruder_temp=material_rec.get("recommended_nozzle_temp", 200),
                source="material",
            ))

        # 候选 2: 几何约束优先
        if geo:
            candidates.append(ParamCandidate(
                layer_height=(
                    geo.get("layer_height")
                    or self.default_params["layer_height"]
                ),
                nozzle_d=geo.get("nozzle_d", self.default_params["nozzle_d"]),
                infill_density=(
                    geo.get("infill_density")
                    or self.default_params["infill_density"]
                ),
                speed=self.default_params["speed"],
                extruder_temp=self.default_params["extruder_temp"],
                source="geometry",
            ))

        # 候选 3: 策略方向 + 默认值
        candidates.append(ParamCandidate(
            layer_height=self._dir_layer_height(
                strategy_params.get("layer_height_dir", "moderate")
            ),
            nozzle_d=self.default_params["nozzle_d"],
            infill_density=self._dir_infill(
                strategy_params.get("infill_density", (20, 40))
            ),
            speed=self._dir_speed(
                strategy_params.get("speed_dir", "moderate")
            ),
            extruder_temp=self.default_params["extruder_temp"],
            source="strategy",
        ))

        return candidates

    @staticmethod
    def _dir_layer_height(direction: str) -> float:
        if direction == "lower":
            return 0.12
        elif direction == "higher":
            return 0.28
        return 0.2

    @staticmethod
    def _dir_infill(infill_range: tuple) -> float:
        return float(infill_range[0] + infill_range[1]) / 2

    @staticmethod
    def _dir_speed(direction: str) -> float:
        if direction == "lower":
            return 40.0
        elif direction == "higher":
            return 90.0
        return 60.0

    def _merge_params(self,
                      best_candidate: ParamCandidate,
                      geo_result: dict,
                      material_rec: dict,
                      fiber_matrix: dict | None = None,
                      scene_template: dict | None = None) -> dict:
        """合并最优候选 + 几何约束 + 材料推荐 + RF3D 纤维参数 → 最终参数。

        合并优先级：几何硬约束 > 材料推荐 > 策略方向 > 默认值
        """
        merged = dict(self.default_params)
        geo = geo_result.get("recommended_params", {})

        # 几何硬约束（最高优先级）
        for key in ("nozzle_d", "layer_height", "infill_density"):
            if key in geo:
                merged[key] = geo[key]

        # 材料推荐（覆盖）
        if material_rec and "error" not in material_rec:
            for key in ("recommended_speed", "recommended_nozzle_temp",
                         "recommended_bed_temp", "recommended_layer_height"):
                mapped = key.replace("recommended_", "")
                if mapped == "nozzle_temp":
                    mapped = "extruder_temp"
                if key in material_rec:
                    # 只有几何没覆盖的才用材料推荐
                    if mapped not in geo:
                        merged[mapped] = material_rec[key]

        # 最优候选（覆盖未被几何约束的字段）
        candidate_dict = best_candidate.to_dict()
        for key, val in candidate_dict.items():
            if key not in geo:
                merged[key] = val

        # 首层高度基于层高
        merged["first_layer_height"] = max(merged.get("layer_height", 0.2), 0.2)

        # RF3D 纤维参数补全（offset / reinforced_fiber_d / base_fiber_d）
        # 优先用场景模板的完整参数，否则用纤维组合区间取中值
        fiber_params = {}
        if scene_template and "params" in scene_template:
            fiber_params = scene_template["params"]
        elif fiber_matrix:
            fiber_params = {
                "offset": round(
                    (fiber_matrix["offset"][0] + fiber_matrix["offset"][1]) / 2, 2
                ),
                "reinforced_fiber_d": fiber_matrix["reinforced_fiber_d"],
                "base_fiber_d": fiber_matrix["base_fiber_d"],
            }
        for key in ("offset", "reinforced_fiber_d", "base_fiber_d"):
            if key in fiber_params and key not in geo:
                merged[key] = fiber_params[key]

        return merged

    def _build_llm_context(self,
                           strategy: PrintStrategy,
                           strategy_params: dict,
                           geo_result: dict,
                           material_rec: dict,
                           best_candidate: ParamCandidate,
                           final_params: dict,
                           fiber_matrix: dict | None = None,
                           scene_template: dict | None = None) -> str:
        """构建供 LLM 审查的结构化上下文。"""
        lines = []

        lines.append("【系统自动决策结果】")
        lines.append(f"打印策略: {self.STRATEGY_DESCRIPTIONS.get(strategy, '未知')}")
        lines.append(f"参数来源: {best_candidate.source}（经多目标优化）")

        lines.append("\n【系统推荐参数（已应用所有物理约束）】")
        lines.append(f"  层高: {final_params.get('layer_height', '?')}mm")
        lines.append(f"  首层高度: {final_params.get('first_layer_height', '?')}mm")
        lines.append(f"  喷嘴直径: {final_params.get('nozzle_d', '?')}mm")
        lines.append(f"  填充密度: {final_params.get('infill_density', '?')}%")
        lines.append(f"  打印速度: {final_params.get('speed', '?')}mm/s")
        lines.append(f"  喷嘴温度: {final_params.get('extruder_temp', '?')}℃")
        lines.append(f"  热床温度: {final_params.get('bed_temp', '?')}℃")

        if geo_result.get("recommended_params"):
            geom = geo_result["recommended_params"]
            lines.append("\n【几何分析触发的参数调整】")
            for k, v in geom.items():
                lines.append(f"  {k}: {v}（{','.join(g for g in geo_result['warnings'] if k in g)[:80]}）")

        if material_rec and "error" not in material_rec:
            lines.append("\n【材料推荐】")
            lines.append(f"  {material_rec.get('material', '?')}: {material_rec.get('material_summary', '')}")

        # RF3D 纤维组合 / 场景模板信息
        if scene_template:
            lines.append("\n【场景工艺模板】")
            lines.append(f"  {scene_template.get('name', '?')}（纤维铺设方式见模板）")
        elif fiber_matrix:
            lines.append("\n【纤维组合】")
            lines.append(f"  {fiber_matrix.get('name', '?')}：铺设方式={fiber_matrix.get('layup', '?')}，"
                         f"纤维偏移={fiber_matrix.get('offset', '?')}mm")

        return "\n".join(lines)
