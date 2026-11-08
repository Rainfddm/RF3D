# RF3D 工艺模板预设方案

## 模板 1：碳纤维增强结构件

**适用场景**：需要高刚度和高强度的结构件、承载件、机械零件

**纤维铺设方式**：轮廓增强（纤维沿外轮廓连续铺设）

```json
{
  "template_id": "cf-structural",
  "name": "碳纤维增强结构件",
  "fiber_type": "carbon_fiber",
  "matrix_type": "PLA",
  "parameters": {
    "layer_height": 0.2,
    "first_layer_height": 0.3,
    "nozzle_d": 0.4,
    "filament_d": 1.75,
    "offset": 0.8,
    "reinforced_fiber_d": 1.0,
    "base_fiber_d": 1.0,
    "extruder_temp": 220,
    "bed_temp": 60,
    "speed": 45,
    "collision_dist_xy": 30,
    "collision_dist_z": 3000,
    "path_type": "fermat_spiral"
  },
  "notes": "最常用的碳纤维打印方案。温度略高于纯PLA以补偿纤维冷却效应。偏移0.8mm适合0.4mm喷嘴的碳纤维铺设。",
  "tips": [
    "建议使用 hardened steel 喷嘴，碳纤维会加速黄铜喷嘴磨损",
    "第一层速度建议降至20mm/s增强附着力",
    "冷却风扇建议降至30-50%，过高冷却会导致层间结合力下降"
  ]
}
```

## 模板 2：玻璃纤维增强壳体

**适用场景**：电子设备外壳、保护壳、绝缘件

**纤维铺设方式**：网格增强（纤维双向交叉铺设形成网格）

```json
{
  "template_id": "gf-shell",
  "name": "玻璃纤维增强壳体",
  "fiber_type": "glass_fiber",
  "matrix_type": "PETG",
  "parameters": {
    "layer_height": 0.25,
    "first_layer_height": 0.3,
    "nozzle_d": 0.6,
    "filament_d": 1.75,
    "offset": 1.0,
    "reinforced_fiber_d": 1.0,
    "base_fiber_d": 1.0,
    "extruder_temp": 245,
    "bed_temp": 75,
    "speed": 40,
    "collision_dist_xy": 30,
    "collision_dist_z": 3000,
    "path_type": "fermat_spiral"
  },
  "notes": "玻璃纤维束较粗，建议使用0.6mm喷嘴。偏移量1.0mm适合玻纤间距。PETG基体提供良好韧性和耐化性。",
  "tips": [
    "玻璃纤维对喷嘴磨损小于碳纤维，但仍建议steel喷嘴",
    "PETG打印建议关闭冷却风扇或降至10-20%",
    "玻璃纤维不导电，适合电子设备外壳",
    "可考虑0°/90°交替铺设角度"
  ]
}
```

## 模板 3：轻量化填充结构

**适用场景**：无人机部件、运动器材、轻量壳体

**纤维铺设方式**：各向同性（多角度均匀铺设）

```json
{
  "template_id": "cf-lightweight",
  "name": "轻量化填充结构",
  "fiber_type": "carbon_fiber",
  "matrix_type": "PLA",
  "parameters": {
    "layer_height": 0.15,
    "first_layer_height": 0.2,
    "nozzle_d": 0.4,
    "filament_d": 1.75,
    "offset": 0.6,
    "reinforced_fiber_d": 1.0,
    "base_fiber_d": 1.0,
    "extruder_temp": 210,
    "bed_temp": 55,
    "speed": 50,
    "collision_dist_xy": 30,
    "collision_dist_z": 3000,
    "path_type": "fermat_spiral"
  },
  "notes": "0.15mm细层高+0.6mm小偏移实现轻量化。较小的偏移量意味着更少的纤维用量但更精细的铺放。费马螺旋路径连续性最佳。",
  "tips": [
    "细层高(0.15mm)打印时间较长，但表面质量极佳",
    "偏移0.6mm是碳纤维的最小推荐值，再小可能无法完成完整铺放",
    "可在关键区域用轮廓增强，非关键区域用较疏填充",
    "打印速度可适当提高到60mm/s缩短时间"
  ]
}
```

## 模板 4：高强度承载件

**适用场景**：机械连接件、受力支撑件、工具夹具

**纤维铺设方式**：各向同性（全方向均匀铺设，充分利用纤维强度）

```json
{
  "template_id": "cf-load-bearing",
  "name": "高强度承载件",
  "fiber_type": "carbon_fiber",
  "matrix_type": "PA",
  "parameters": {
    "layer_height": 0.3,
    "first_layer_height": 0.35,
    "nozzle_d": 0.6,
    "filament_d": 1.75,
    "offset": 0.8,
    "reinforced_fiber_d": 1.0,
    "base_fiber_d": 1.0,
    "extruder_temp": 270,
    "bed_temp": 90,
    "speed": 35,
    "collision_dist_xy": 30,
    "collision_dist_z": 3000,
    "path_type": "fermat_spiral"
  },
  "notes": "最高性能组合。PA基体提供极佳韧性与纤维的结合力。0.6mm大喷嘴确保纤维顺畅通过。慢速保证纤维浸润质量。",
  "tips": [
    "PA必须充分干燥（80°C真空烘箱4h以上），含水>0.2%会导致气泡和层间分离",
    "建议使用all-metal热端，PTFE热端在260°C以上会释放有害气体",
    "封闭打印仓可减少翘曲和层间开裂",
    "层高0.3mm较粗，但配合0.6mm喷嘴可获得高强度",
    "第一层建议降至20mm/s并提高热床到100°C"
  ]
}
```

## 模板 5：防震减振件

**适用场景**：减振垫、防护壳、运动缓冲部件

**纤维铺设方式**：自适应（根据应力方向动态调整纤维路径）

```json
{
  "template_id": "kf-damping",
  "name": "防震减振件",
  "fiber_type": "aramid_fiber",
  "matrix_type": "PLA",
  "parameters": {
    "layer_height": 0.2,
    "first_layer_height": 0.25,
    "nozzle_d": 0.4,
    "filament_d": 1.75,
    "offset": 0.8,
    "reinforced_fiber_d": 1.0,
    "base_fiber_d": 1.0,
    "extruder_temp": 215,
    "bed_temp": 55,
    "speed": 40,
    "collision_dist_xy": 30,
    "collision_dist_z": 3000,
    "path_type": "fermat_spiral"
  },
  "notes": "芳纶纤维(凯夫拉)抗冲击性极佳，适合需要吸收能量的应用。PLA基体提供刚性支撑，芳纶纤维提供韧性保护。",
  "tips": [
    "芳纶纤维切割困难，建议使用sharp新喷嘴",
    "芳纶纤维的黄色外观可能不适合需要特定颜色的应用",
    "如需更高韧性，可将基体换为PETG（温度245°C，热床75°C）",
    "防震件建议偏移量适中(0.8mm)，过密影响弹性"
  ]
}
```

---

## 快速场景匹配

当用户提到以下关键词时，自动匹配模板：

| 关键词 | 匹配模板 | 模板ID |
|--------|----------|--------|
| 高强度、承重、结构件、刚性 | 碳纤维增强结构件 | cf-structural |
| 外壳、绝缘、电子设备、保护 | 玻璃纤维增强壳体 | gf-shell |
| 轻量、减重、无人机、薄壁 | 轻量化填充结构 | cf-lightweight |
| 承载、连接、工具、最高强度 | 高强度承载件 | cf-load-bearing |
| 减振、防震、缓冲、抗冲击 | 防震减振件 | kf-damping |
| 碳纤维 + PLA | 碳纤维增强结构件 | cf-structural |
| 碳纤维 + 尼龙 | 高强度承载件 | cf-load-bearing |
| 玻璃纤维 | 玻璃纤维增强壳体 | gf-shell |
| 芳纶/凯夫拉 | 防震减振件 | kf-damping |
