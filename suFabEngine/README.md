# RF3D Engine

RF3D 连续纤维增强 3D 打印引擎 —— 覆盖 **STL 加载 → 切片 → 费马螺旋路径生成 → GCode 输出** 全流程的算法引擎包。

## 特性

- **Qt-free 核心**：纯 Python + VTK + NumPy，无 PyQt5 依赖，可 headless 部署
- **统一入口**：`PipelineExecutor` 请求级实例，一条命令链完成 load/slice/generate_path/generate_gcode
- **连续纤维路径**：费马螺旋（Fermat Spiral）路径生成 + 碰撞规避 + 路径优化
- **AI 参数推理**：`suAgent` 包内置工艺决策引擎（材料识别 / 纤维×基体组合 / 场景模板 / 参数约束校验）

## 安装

```bash
pip install rf3d-engine
```

> 注意：`vtk` 和 `torch` 依赖较重，首次安装会拉取较大体积。若只需切片/GCode 核心可忽略 AI 推理部分。

## 快速上手

```python
from suFabEngine.pipeline_executor import PipelineExecutor

ex = PipelineExecutor()          # 请求级独立实例

# 1. 加载模型（内部 vtkSTLReader 读取 + center_model 平移：XY 居中、Z 底归零）
ex.execute_cmd("load_model", file_path="model.stl")

# 2. 切片
ex.execute_cmd("slice", layer_height=0.4, first_layer_height=0.2, infill_density=30)

# 3. 生成路径 → (N,3) numpy 数组
path = ex.execute_cmd("generate_path")

# 4. 生成 GCode（存 uploads/gcode_output_{ts}.gcode）
result = ex.execute_cmd("generate_gcode", speed=60, extruder_temp=200, bed_temp=60)
print(result["gcode_filename"], result["download_url"])
```

## AI 自然语言链路

```python
from suFabEngine.ai_agent import PrintingControlAgent

agent = PrintingControlAgent("fab_commander_agent", "fab_agent")
agent.use("kimi", "moonshot-v1-8k", 1000)
result = agent.run_cmd("碳纤维无人机螺旋桨，轻量化")   # 自然语言 → 操作序列
```

## 包结构

```
suFabEngine/        # 算法引擎（Pipeline / PipelineExecutor / GCoder / PathOptimizer / MeshSlicer）
suAgent/            # AI 参数推理（material_reasoner / process_decision_engine / constraint_validator）
```

## License

Proprietary software. All rights reserved. 未经授权，不得复制、修改、分发或商用。
