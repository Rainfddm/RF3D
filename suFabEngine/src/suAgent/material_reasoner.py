"""
MaterialReasoner — 材料知识库与工艺参数推荐引擎。

从用户自然语言输入中识别材料类型和使用场景，
返回针对该材料的推荐工艺参数范围。
"""

import logging

# ============================================================
# 材料数据库
# ============================================================
# 每种材料的推荐工艺参数范围：
#   nozzle_temp: (min, max) ℃
#   bed_temp:    (min, max) ℃
#   speed:       (min, max) mm/s
#   layer_height:(min, max) mm
#   retraction:  回抽距离 mm
#   summary:     材料特性简述
# ============================================================

MATERIAL_DB = {
    "碳纤维pla": {
        "aliases": ["碳纤维", "carbon fiber pla", "cf-pla", "碳纤pla", "碳纤"],
        "nozzle_temp": (210, 230),
        "bed_temp": (50, 70),
        "speed": (30, 60),
        "layer_height": (0.15, 0.25),
        "retraction": 1.5,
        "summary": "高强度高刚性，推荐使用硬化钢喷嘴，耐磨性优于普通PLA",
    },
    "玻璃纤维pla": {
        "aliases": ["玻璃纤维", "glass fiber pla", "gf-pla", "玻纤pla", "玻纤"],
        "nozzle_temp": (200, 240),
        "bed_temp": (50, 65),
        "speed": (40, 80),
        "layer_height": (0.1, 0.3),
        "retraction": 2.0,
        "summary": "中等强度，成本低于碳纤维PLA，适合原型验证",
    },
    "pla": {
        "aliases": ["聚乳酸", "pla pro", "pla+", "pla plus"],
        "nozzle_temp": (190, 220),
        "bed_temp": (40, 60),
        "speed": (50, 100),
        "layer_height": (0.1, 0.32),
        "retraction": 4.0,
        "summary": "通用易打印，生物降解材料，适合日常原型和装饰件",
    },
    "petg": {
        "aliases": ["petg", "pet-g"],
        "nozzle_temp": (220, 250),
        "bed_temp": (70, 85),
        "speed": (40, 70),
        "layer_height": (0.1, 0.28),
        "retraction": 3.0,
        "summary": "韧性强耐冲击，耐化学腐蚀，透明性好，适合功能性零件",
    },
    "abs": {
        "aliases": ["abs", "丙烯腈"],
        "nozzle_temp": (230, 260),
        "bed_temp": (90, 110),
        "speed": (40, 80),
        "layer_height": (0.1, 0.3),
        "retraction": 2.0,
        "summary": "耐热耐冲击，需封闭腔体防翘曲，适合工程零件",
    },
    "尼龙": {
        "aliases": ["nylon", "pa", "聚酰胺", "pa6", "pa12"],
        "nozzle_temp": (240, 280),
        "bed_temp": (70, 100),
        "speed": (30, 60),
        "layer_height": (0.1, 0.25),
        "retraction": 1.5,
        "summary": "高韧性高耐热，需严格干燥储存，适合耐磨损零件",
    },
    "tpu": {
        "aliases": ["tpu", "柔性", "flex", "弹性体"],
        "nozzle_temp": (210, 240),
        "bed_temp": (30, 60),
        "speed": (15, 40),
        "layer_height": (0.1, 0.25),
        "retraction": 6.0,
        "summary": "柔弹性材料，需慢速打印，减少回抽，适合密封圈/缓冲件",
    },
}

# ============================================================
# 使用场景 → 优化方向映射
# ============================================================
# 当用户意图包含关键词时，自动调整参数偏好
# direction: "low"=偏下限 / "high"=偏上限 / "moderate"=取中间
# ============================================================

USECASE_PRIORITIES = {
    "轻量化": {
        "layer_height": "moderate",
        "infill_density": "low",
        "speed": "moderate",
        "priority_desc": "优先减小材料用量，平衡打印效率",
    },
    "高强度": {
        "layer_height": "low",
        "infill_density": "high",
        "speed": "low",
        "priority_desc": "优先层间结合强度，降低速度保证熔融充分",
    },
    "快速成型": {
        "layer_height": "high",
        "infill_density": "low",
        "speed": "high",
        "priority_desc": "优先打印速度，可接受粗糙表面",
    },
    "表面质量": {
        "layer_height": "low",
        "infill_density": "moderate",
        "speed": "moderate",
        "priority_desc": "优先表面光洁度，使用薄层高",
    },
    "耐热": {
        "layer_height": "low",
        "infill_density": "high",
        "speed": "low",
        "priority_desc": "优先耐热性能，高温材料+致密填充",
    },
    "无人机": {
        "layer_height": "low",
        "infill_density": "low",
        "speed": "moderate",
        "priority_desc": "飞行器轻量化，低填充高层间结合",
    },
    "螺旋桨": {
        "layer_height": "low",
        "infill_density": "moderate",
        "speed": "moderate",
        "priority_desc": "旋转件动平衡，中低填充兼顾强度与重量",
    },
}


class MaterialReasoner:
    """材料推理引擎。

    从用户自然语言中：
    1. 识别材料类型（碳纤维PLA / 玻纤PLA / PLA / PETG / ABS / 尼龙 / TPU）
    2. 识别使用场景（轻量化 / 高强度 / 快速成型 / 表面质量 / 耐热）
    3. 返回针对性的参数推荐
    """

    # ----------------------------------------------------------
    # 材料识别
    # ----------------------------------------------------------

    @staticmethod
    def identify_material(user_text: str) -> str | None:
        """从用户输入中识别材料名称。

        匹配优先级：精确匹配 > 别名匹配。
        """
        text_lower = user_text.lower()
        for mat_name, info in MATERIAL_DB.items():
            if mat_name in text_lower:
                return mat_name
        for mat_name, info in MATERIAL_DB.items():
            for alias in info["aliases"]:
                if alias in text_lower:
                    return mat_name
        return None

    # ----------------------------------------------------------
    # 场景识别
    # ----------------------------------------------------------

    @staticmethod
    def detect_usecase(user_text: str) -> list:
        """从用户输入中检测使用场景（可命中多个）。

        Returns:
            list: 命中的场景关键词列表
        """
        hits = []
        for keyword in USECASE_PRIORITIES:
            if keyword in user_text:
                hits.append(keyword)
        return hits

    # ----------------------------------------------------------
    # 参数推荐
    # ----------------------------------------------------------

    @staticmethod
    def get_recommendations(material_name: str,
                            usecases: list | None = None) -> dict:
        """根据材料和场景获取推荐工艺参数。

        Args:
            material_name: 材料名称（如 "碳纤维pla"）
            usecases: 使用场景关键词列表

        Returns:
            dict: {
                "material": str,
                "material_summary": str,
                "recommended_nozzle_temp": int,
                "nozzle_temp_range": (int, int),
                "recommended_bed_temp": int,
                "bed_temp_range": (int, int),
                "recommended_speed": int,
                "speed_range": (int, int),
                "recommended_layer_height": float,
                "layer_height_range": (float, float),
                "retraction_mm": float,
                "usecase_priorities": dict | None,
            }
        """
        usecases = usecases or []
        mat_key = material_name.lower()

        # 查找材料
        if mat_key not in MATERIAL_DB:
            # 别名反查
            for k, v in MATERIAL_DB.items():
                if mat_key in v["aliases"]:
                    mat_key = k
                    break
            else:
                return {
                    "error": f"未知材料 '{material_name}'",
                    "default_material": "pla",
                    "recommended_nozzle_temp": 200,
                    "recommended_bed_temp": 50,
                    "recommended_speed": 60,
                    "recommended_layer_height": 0.2,
                }

        mat = MATERIAL_DB[mat_key]

        # 基础推荐（取范围中值）
        rec = {
            "material": material_name,
            "material_summary": mat["summary"],
            "recommended_nozzle_temp": (mat["nozzle_temp"][0] + mat["nozzle_temp"][1]) // 2,
            "nozzle_temp_range": mat["nozzle_temp"],
            "recommended_bed_temp": (mat["bed_temp"][0] + mat["bed_temp"][1]) // 2,
            "bed_temp_range": mat["bed_temp"],
            "recommended_speed": (mat["speed"][0] + mat["speed"][1]) // 2,
            "speed_range": mat["speed"],
            "recommended_layer_height": round(
                (mat["layer_height"][0] + mat["layer_height"][1]) / 2, 2
            ),
            "layer_height_range": mat["layer_height"],
            "retraction_mm": mat["retraction"],
            "usecase_priorities": None,
        }

        # 场景微调
        if usecases:
            priorities_merged = {}
            for uc in usecases:
                if uc in USECASE_PRIORITIES:
                    priorities_merged.update(USECASE_PRIORITIES[uc])

            # 应用场景优先级
            for param, direction in priorities_merged.items():
                if param == "speed":
                    if direction == "low":
                        rec["recommended_speed"] = mat["speed"][0]
                    elif direction == "high":
                        rec["recommended_speed"] = mat["speed"][1]
                elif param == "layer_height":
                    if direction == "low":
                        rec["recommended_layer_height"] = round(mat["layer_height"][0], 2)
                    elif direction == "high":
                        rec["recommended_layer_height"] = round(mat["layer_height"][1], 2)

            rec["usecase_priorities"] = priorities_merged

        logging.info(
            "材料推荐: %s | 场景: %s | 喷嘴%d℃/速度%dmm/s/层高%.2fmm",
            material_name, usecases,
            rec["recommended_nozzle_temp"],
            rec["recommended_speed"],
            rec["recommended_layer_height"],
        )
        return rec

    # ----------------------------------------------------------
    # 辅助方法
    # ----------------------------------------------------------

    @staticmethod
    def list_all_materials() -> list:
        """列出所有支持的材料（供前端展示）。"""
        return [
            {
                "name": k,
                "aliases": v["aliases"],
                "summary": v["summary"],
                "nozzle_temp_range": v["nozzle_temp"],
            }
            for k, v in MATERIAL_DB.items()
        ]
