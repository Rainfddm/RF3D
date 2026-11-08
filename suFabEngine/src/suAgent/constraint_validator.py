"""
ConstraintValidator — 3D 打印物理约束验证与自动修正。

独立于 LLM 的规则引擎，对工艺参数执行硬约束检查，
确保每个参数都在物理可行范围内。
"""

import logging

# ============================================================
# 全局物理约束
# ============================================================
# 每个参数的合法范围、描述、以及与其他参数的依赖关系
# ============================================================

PHYSICAL_CONSTRAINTS = {
    "layer_height": {
        "min": 0.05,
        "max": 0.4,
        "rule": "层高应介于 {min}-{max}mm 之间",
        "depends_on": "nozzle_d",
        "dependency_rule": "层高不得超过喷嘴直径 (layer_height ≤ nozzle_d)",
    },
    "first_layer_height": {
        "min": 0.1,
        "max": 0.5,
        "rule": "首层高度应介于 {min}-{max}mm 之间",
    },
    "nozzle_d": {
        "min": 0.2,
        "max": 1.2,
        "rule": "喷嘴直径应介于 {min}-{max}mm 之间（常用 0.4/0.6/0.8mm）",
    },
    "filament_d": {
        "min": 1.65,
        "max": 3.0,
        "rule": "耗材直径应介于 {min}-{max}mm 之间（标准 1.75mm 或 2.85mm）",
    },
    "extruder_temp": {
        "min": 170,
        "max": 300,
        "rule": "挤出温度应介于 {min}-{max}℃ 之间",
    },
    "bed_temp": {
        "min": 0,
        "max": 120,
        "rule": "热床温度应介于 {min}-{max}℃ 之间",
    },
    "speed": {
        "min": 5,
        "max": 200,
        "rule": "打印速度应介于 {min}-{max}mm/s 之间",
    },
    "infill_density": {
        "min": 0,
        "max": 100,
        "rule": "填充密度应介于 {min}-{max}% 之间",
    },
    "offset": {
        "min": 0.1,
        "max": 20.0,
        "rule": "偏移量应介于 {min}-{max}mm 之间",
    },
}


class ConstraintValidator:
    """3D 打印参数约束验证器。

    接收用户/LLM 输出的工艺参数，
    逐项检查是否在物理可行范围内，
    对越界参数自动给出修正建议。
    """

    @staticmethod
    def validate(params: dict,
                 material_recommendations: dict | None = None) -> dict:
        """验证所有参数是否符合物理约束。

        Args:
            params: {"layer_height": 0.2, "nozzle_d": 0.8, ...}
            material_recommendations: MaterialReasoner 的输出（可选，用于材料温度约束）

        Returns:
            dict: {
                "valid": bool,
                "violations": [{"param", "value", "issue", "rule", "auto_correct"}],
                "corrected_params": {"param": corrected_value, ...},
                "warning_count": int,
            }
        """
        violations = []
        corrected = {}

        for param_name, raw_value in params.items():
            if param_name not in PHYSICAL_CONSTRAINTS:
                continue

            constraint = PHYSICAL_CONSTRAINTS[param_name]

            # 类型转换
            try:
                value = float(raw_value)
            except (ValueError, TypeError):
                violations.append({
                    "param": param_name,
                    "value": raw_value,
                    "issue": f"无法将 '{raw_value}' 转换为数值",
                    "rule": constraint["rule"].format(**constraint),
                    "auto_correct": None,
                })
                continue

            # 范围检查
            if value < constraint["min"]:
                violations.append({
                    "param": param_name,
                    "value": value,
                    "issue": f"值 {value} 小于最小值 {constraint['min']}",
                    "rule": constraint["rule"].format(**constraint),
                    "auto_correct": constraint["min"],
                })
                corrected[param_name] = constraint["min"]
            elif value > constraint["max"]:
                violations.append({
                    "param": param_name,
                    "value": value,
                    "issue": f"值 {value} 大于最大值 {constraint['max']}",
                    "rule": constraint["rule"].format(**constraint),
                    "auto_correct": constraint["max"],
                })
                corrected[param_name] = constraint["max"]

        # ── 依赖约束：layer_height ≤ nozzle_d ──
        lh = corrected.get("layer_height") or params.get("layer_height")
        nd = corrected.get("nozzle_d") or params.get("nozzle_d")
        if lh is not None and nd is not None:
            try:
                lh_val = float(lh)
                nd_val = float(nd)
                if lh_val > nd_val:
                    violations.append({
                        "param": "layer_height",
                        "value": lh_val,
                        "issue": f"层高 ({lh_val}mm) 不能超过喷嘴直径 ({nd_val}mm)",
                        "rule": "layer_height ≤ nozzle_d",
                        "auto_correct": nd_val,
                    })
                    corrected["layer_height"] = nd_val
            except (ValueError, TypeError):
                pass  # 类型错误已在上面处理

        # ── 材料温度范围约束 ──
        if material_recommendations and "nozzle_temp_range" in material_recommendations:
            et = corrected.get("extruder_temp") or params.get("extruder_temp")
            if et is not None:
                try:
                    et_val = float(et)
                    temp_range = material_recommendations["nozzle_temp_range"]
                    if et_val < temp_range[0] or et_val > temp_range[1]:
                        optimal = material_recommendations.get("recommended_nozzle_temp", 200)
                        corrected["extruder_temp"] = optimal
                except (ValueError, TypeError):
                    pass

        result = {
            "valid": len(violations) == 0,
            "violations": violations,
            "corrected_params": corrected,
            "warning_count": len(violations),
        }

        if violations:
            logging.warning(
                "参数约束校验: %d 项违规", len(violations)
            )
            for v in violations:
                logging.warning(
                    "  %s = %s → %s (自动修正: %s)",
                    v["param"], v["value"], v["issue"], v.get("auto_correct", "N/A"),
                )

        return result

    @staticmethod
    def apply_corrections(original_params: dict,
                          corrections: dict) -> dict:
        """将自动修正应用到参数集。

        Returns:
            dict: 修正后的参数（原始参数 + 修正覆盖）
        """
        corrected = dict(original_params)
        corrected.update(corrections)
        return corrected
