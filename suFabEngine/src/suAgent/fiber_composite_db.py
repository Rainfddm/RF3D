"""纤维×基体组合知识库 + 场景工艺模板（RF3D 核心，代码真相源）。

数据源自 database/references/material_params.md 与 process_templates.md，
以文档数值为权威。database/ 目录降级为人类可读参考，本模块是执行真相源。

三套知识库的关系：
- MATERIAL_DB（material_reasoner.py）：耗材级（单材料），供基础温度/速度推荐
- FIBER_MATRIX_DB（本文件）：纤维×基体组合级（RF3D 核心），补 offset/纤维直径
- SCENE_TEMPLATES（本文件）：场景级完整工艺方案
"""

# ============================================================
# 纤维×基体组合推荐参数（6 组）
# ============================================================
# 每个组合的推荐值区间 + RF3D 特有的纤维参数（offset/reinforced_fiber_d/base_fiber_d）
# ============================================================

FIBER_MATRIX_DB = {
    "cf+pla": {
        "name": "碳纤维增强PLA",
        "aliases": ["碳纤维pla", "碳纤维增强pla", "cf+pla", "碳纤pla", "碳纤维 pla"],
        "fiber": "碳纤维",
        "matrix": "PLA",
        "extruder_temp": (210, 230),
        "bed_temp": 60,
        "layer_height": (0.15, 0.25),
        "first_layer_height": (0.2, 0.3),
        "nozzle_d": (0.4, 0.6),
        "filament_d": 1.75,
        "offset": (0.6, 0.8),
        "reinforced_fiber_d": 1.0,
        "base_fiber_d": 1.0,
        "speed": (30, 60),
        "layup": "轮廓增强",
    },
    "cf+petg": {
        "name": "碳纤维增强PETG",
        "aliases": ["碳纤维petg", "碳纤维增强petg", "cf+petg"],
        "fiber": "碳纤维",
        "matrix": "PETG",
        "extruder_temp": (240, 260),
        "bed_temp": 75,
        "layer_height": (0.15, 0.25),
        "first_layer_height": (0.2, 0.3),
        "nozzle_d": (0.4, 0.6),
        "filament_d": 1.75,
        "offset": (0.6, 0.8),
        "reinforced_fiber_d": 1.0,
        "base_fiber_d": 1.0,
        "speed": (30, 50),
        "layup": "网格增强",
    },
    "cf+pa": {
        "name": "碳纤维增强尼龙",
        "aliases": ["碳纤维尼龙", "碳纤维pa", "cf+pa", "碳纤尼龙", "碳纤维增强尼龙"],
        "fiber": "碳纤维",
        "matrix": "PA",
        "extruder_temp": (260, 285),
        "bed_temp": 90,
        "layer_height": (0.15, 0.3),
        "first_layer_height": (0.25, 0.35),
        "nozzle_d": (0.5, 0.8),
        "filament_d": 1.75,
        "offset": (0.6, 0.8),
        "reinforced_fiber_d": 1.0,
        "base_fiber_d": 1.0,
        "speed": (25, 45),
        "layup": "各向同性",
        "note": "必须干燥",
    },
    "gf+pla": {
        "name": "玻璃纤维增强PLA",
        "aliases": ["玻璃纤维pla", "玻璃纤维增强pla", "gf+pla", "玻纤pla"],
        "fiber": "玻璃纤维",
        "matrix": "PLA",
        "extruder_temp": (210, 225),
        "bed_temp": 60,
        "layer_height": (0.2, 0.3),
        "first_layer_height": (0.25, 0.35),
        "nozzle_d": (0.5, 0.8),
        "filament_d": 1.75,
        "offset": (0.8, 1.2),
        "reinforced_fiber_d": 1.0,
        "base_fiber_d": 1.0,
        "speed": (35, 60),
        "layup": "轮廓增强",
    },
    "gf+petg": {
        "name": "玻璃纤维增强PETG",
        "aliases": ["玻璃纤维petg", "玻璃纤维增强petg", "gf+petg", "玻纤petg"],
        "fiber": "玻璃纤维",
        "matrix": "PETG",
        "extruder_temp": (240, 255),
        "bed_temp": 75,
        "layer_height": (0.2, 0.3),
        "first_layer_height": (0.25, 0.35),
        "nozzle_d": (0.5, 0.8),
        "filament_d": 1.75,
        "offset": (0.8, 1.2),
        "reinforced_fiber_d": 1.0,
        "base_fiber_d": 1.0,
        "speed": (30, 50),
        "layup": "网格增强",
    },
    "kf+pla": {
        "name": "芳纶纤维增强PLA",
        "aliases": ["芳纶pla", "芳纶纤维pla", "kf+pla", "凯夫拉pla", "芳纶纤维增强pla"],
        "fiber": "芳纶纤维",
        "matrix": "PLA",
        "extruder_temp": (205, 220),
        "bed_temp": 55,
        "layer_height": (0.15, 0.25),
        "first_layer_height": (0.2, 0.3),
        "nozzle_d": (0.4, 0.6),
        "filament_d": 1.75,
        "offset": (0.7, 1.0),
        "reinforced_fiber_d": 1.0,
        "base_fiber_d": 1.0,
        "speed": (30, 55),
        "layup": "自适应",
    },
}

# ============================================================
# 场景 → 完整工艺模板（5 个）
# ============================================================
# 供场景级精准匹配（用户说"无人机螺旋桨"→ cf-lightweight 完整方案）
# ============================================================

SCENE_TEMPLATES = {
    "cf-structural": {
        "name": "碳纤维增强结构件",
        "fiber_matrix": "cf+pla",
        "keywords": ["高强度", "承重", "结构件", "刚性"],
        "params": {
            "layer_height": 0.2, "first_layer_height": 0.3,
            "nozzle_d": 0.4, "filament_d": 1.75, "offset": 0.8,
            "reinforced_fiber_d": 1.0, "base_fiber_d": 1.0,
            "extruder_temp": 220, "bed_temp": 60, "speed": 45,
            "path_type": "fermat_spiral",
        },
    },
    "gf-shell": {
        "name": "玻璃纤维增强壳体",
        "fiber_matrix": "gf+petg",
        "keywords": ["外壳", "绝缘", "电子设备", "保护"],
        "params": {
            "layer_height": 0.25, "first_layer_height": 0.3,
            "nozzle_d": 0.6, "filament_d": 1.75, "offset": 1.0,
            "reinforced_fiber_d": 1.0, "base_fiber_d": 1.0,
            "extruder_temp": 245, "bed_temp": 75, "speed": 40,
            "path_type": "fermat_spiral",
        },
    },
    "cf-lightweight": {
        "name": "轻量化填充结构",
        "fiber_matrix": "cf+pla",
        "keywords": ["轻量", "减重", "无人机", "薄壁", "螺旋桨"],
        "params": {
            "layer_height": 0.15, "first_layer_height": 0.2,
            "nozzle_d": 0.4, "filament_d": 1.75, "offset": 0.6,
            "reinforced_fiber_d": 1.0, "base_fiber_d": 1.0,
            "extruder_temp": 210, "bed_temp": 55, "speed": 50,
            "path_type": "fermat_spiral",
        },
    },
    "cf-load-bearing": {
        "name": "高强度承载件",
        "fiber_matrix": "cf+pa",
        "keywords": ["承载", "连接", "工具", "最高强度", "夹具"],
        "params": {
            "layer_height": 0.3, "first_layer_height": 0.35,
            "nozzle_d": 0.6, "filament_d": 1.75, "offset": 0.8,
            "reinforced_fiber_d": 1.0, "base_fiber_d": 1.0,
            "extruder_temp": 270, "bed_temp": 90, "speed": 35,
            "path_type": "fermat_spiral",
        },
    },
    "kf-damping": {
        "name": "防震减振件",
        "fiber_matrix": "kf+pla",
        "keywords": ["减振", "防震", "缓冲", "抗冲击"],
        "params": {
            "layer_height": 0.2, "first_layer_height": 0.25,
            "nozzle_d": 0.4, "filament_d": 1.75, "offset": 0.8,
            "reinforced_fiber_d": 1.0, "base_fiber_d": 1.0,
            "extruder_temp": 215, "bed_temp": 55, "speed": 40,
            "path_type": "fermat_spiral",
        },
    },
}


def identify_fiber_matrix(user_text: str) -> dict | None:
    """从用户输入识别纤维×基体组合。

    返回 FIBER_MATRIX_DB 中的组合（含 RF3D 参数），未识别返回 None。
    """
    text = user_text.lower()
    for key, info in FIBER_MATRIX_DB.items():
        for alias in info["aliases"]:
            if alias in text:
                return {"key": key, **info}
    return None


def identify_scene_template(user_text: str) -> dict | None:
    """从用户输入识别场景工艺模板。

    返回 SCENE_TEMPLATES 中的模板（含完整参数），未识别返回 None。
    """
    for key, info in SCENE_TEMPLATES.items():
        for kw in info["keywords"]:
            if kw in user_text:
                return {"key": key, **info}
    return None
