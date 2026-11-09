# RF3D — 连续纤维增强 3D 打印工艺生成系统

**R**einforced **F**ilament **3D** Printing：把 STL 模型转换成可打印的连续纤维增强路径与 GCode。

覆盖 **模型加载 → 切片 → 费马螺旋路径规划 → GCode 输出** 全流程，提供 Web 与桌面两种入口。

> 面向访客的项目介绍页：[`docs/index.html`](docs/index.html)。

---

## 目录

- [功能概览](#功能概览)
- [技术栈](#技术栈)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [使用示例](#使用示例)
- [Web API](#web-api)
- [工艺参数](#工艺参数)
- [AI 配置](#ai-配置)
- [测试](#测试)
- [已知限制](#已知限制)
- [第三方依赖](#第三方依赖)
- [许可证](#许可证)

---

## 功能概览

| 入口 | 启动方式 | 适用场景 |
|---|---|---|
| **Web 服务** | `python app.py` | 浏览器操作、远程部署、API 调用 |
| **桌面应用** | `python -m suFabUI.main` | 本地可视化调试、VTK 三维预览 |

两端共用同一套算法入口 `PipelineExecutor`（Qt-free），因此**同一模型在两端生成的 GCode 一致**。

主要能力：

- **切片**：基于 Minetto 等人三角形网格切片算法，按 Z 层生成闭合轮廓
- **路径规划**：轮廓等值线 → 费马螺旋连续路径（`gen_fermat_curve`），减少空走
- **路径精简**：Douglas-Peucker（阈值 `max(nozzle_d × 0.4, layer_height)`）+ 关键点保留
- **区域间转移**：分块生成，块间发 `G0` 空走且不挤出，并自动**回抽 → 空走 → 回填**，避免拉丝
- **AI 工艺助手**：自然语言 → 结构化操作序列（LLM + 材料知识库 + 物理约束校验）

---

## 技术栈

| 层 | 技术 |
|---|---|
| Web | Flask 2.3.3 · Flask-SQLAlchemy 3.0.5 · Flask-Migrate 4.1.0 |
| 几何/算法 | VTK 9.0.3 · NumPy 1.26 · SciPy 1.15 · pyclipper · shapely · scikit-learn |
| 桌面 | PyQt5 5.15.10 · VTK |
| 前端 | 原生 JS + Three.js（`static/js/three.min.js`） |
| AI | OpenAI 兼容协议（DeepSeek / Moonshot） |
| 测试 | pytest + pytest-cov |

**Python 3.10+**（本项目在 3.11 上验证）。

---

## 目录结构

```
RF3D/
├── app.py                    # Web 入口（应用逻辑在 application/）
├── wsgi.py                   # WSGI 生产入口
├── application/              # Web 应用包
│   ├── __init__.py           #   应用工厂 create_app()
│   ├── config.py             #   配置（SECRET_KEY / DATABASE_URL / CORS）
│   ├── models.py             #   User 模型
│   ├── errors.py             #   错误响应兼容层（旧字段 + RFC 7807）
│   ├── utils.py              #   参数归一化 / 文件名清洗
│   └── blueprints/           #   pipeline · ai · auth · credit · pages
├── templates/                # 4 个页面（login / register / index / recharge）
├── static/                   # 前端资源（js / css / docs.html / openapi.yaml）
├── process/configs/          # start.gcode · end.gcode 起止模板
├── migrations/               # Alembic 数据库迁移
├── database/                 # 材料/工艺参考文档（代码才是执行真相源）
├── deployment_config/        # nginx.conf
├── suFabEngine/              # 算法引擎（独立包，需 pip install -e）
│   ├── pyproject.toml
│   └── src/
│       ├── suFabEngine/      #   Pipeline · pipeline_executor · suGCoder · ai_agent
│       │   ├── FermatsSpiral/#     费马螺旋路径
│       │   ├── MeshSlicer/   #     网格切片
│       │   ├── PathOptimizer/#     路径优化
│       │   ├── GeoProcess/   #     几何处理
│       │   ├── GCoder/       #     GCode 生成
│       │   └── Utils/
│       └── suAgent/          #   参数推理（决策引擎 / 材料库 / 约束校验）
├── suFabUI/                  # 桌面端（独立包，需 pip install -e）
│   ├── setup.py · suFabUI.spec
│   └── src/suFabUI/          #   main.py + core/ + ui/ + common/
├── tests/                    # 发布包自检用例（源仓库另有 243 条完整测试）
└── uploads/                  # 运行时产物（上传的模型、生成的 GCode）
```


---

## 快速开始

> 以下 4 步顺序固定，**不要跳过第 3 步**。

### 1. 安装依赖

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -r requirements.txt
```

发布包是 src 布局，`suFabEngine/` 与 `suFabUI/` 的源码在各自 `src/` 下。
`app.py` 启动时会自动把这两个目录加入 `sys.path`，
**无需 `pip install -e`**，也不需要设置 `PYTHONPATH`。

### 2. 配置环境变量

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

编辑 `.env` 填入 API Key（AI 功能需要，见 [AI 配置](#ai-配置)）；
生产环境请务必设置 `FLASK_SECRET_KEY`。

### 3. 初始化数据库（必做）

```bash
python -m flask --app app db upgrade
```

这一步创建 `user` 表。**跳过它，后续所有账号相关接口都会报**
`sqlite3.OperationalError: no such table: user`（页面能打开，但注册/登录必失败）。

数据库默认落在 `instance/rf3d_users.db`；该目录由 `create_app()` 自动创建，
无需手工 `mkdir`。切 PostgreSQL/MySQL 时在 `.env` 里设 `DATABASE_URL`。

### 4. 启动

```bash
python app.py                    # → http://localhost:5000
python -m suFabUI.main           # 桌面端（需装 PyQt5，requirements 已含）
```

---

## 使用示例

### Web：完整流水线（curl）

```bash
# 1) 上传模型（STL / OBJ / 3MF）
curl -X POST http://localhost:5000/upload-model \
     -F "model_file=@propeller.stl"

# 2) 切片（只传想覆盖的参数，其余用引擎默认值）
curl -X POST http://localhost:5000/run-slice \
     -H "Content-Type: application/json" \
     -d '{"layer_height": 0.2, "infill_density": 30}'

# 3) 生成路径
curl -X POST http://localhost:5000/run-path-generation \
     -H "Content-Type: application/json" -d '{}'

# 4) 生成 GCode（返回下载地址 /uploads/gcode_output_*.gcode）
curl -X POST http://localhost:5000/generate-gcode \
     -H "Content-Type: application/json" \
     -d '{"speed": 60, "extruder_temp": 200, "bed_temp": 60}'
```

### Python：直接调用引擎

```python
from suFabEngine.pipeline_executor import PipelineExecutor

ex = PipelineExecutor()                       # 请求级实例，状态不跨请求共享

ex.execute_cmd("load_model", file_path="uploads/propeller.stl")
ex.execute_cmd("slice", layer_height=0.2, infill_density=30)
path = ex.execute_cmd("generate_path")        # (N,3) numpy 数组
result = ex.execute_cmd("generate_gcode", speed=60, extruder_temp=200)
print(result["gcode_filename"], result["download_url"])
```

### AI：自然语言驱动

```bash
curl -X POST http://localhost:5000/ai-terminal \
     -H "Content-Type: application/json" \
     -d '{"input": "用碳纤维打印一个无人机螺旋桨，轻量化"}'
```

链路：`ProcessDecisionEngine.decide()` 识别材料/场景 → 推荐参数注入 prompt →
LLM 输出 `operations` JSON → `ConstraintValidator` 校正 → 逐条执行。

---

## Web API

20 条路由（含 `/static`）。错误响应统一带 `status` / `message` 字段。

| 路由 | 方法 | 说明 |
|---|---|---|
| `/` `/login` `/register` `/recharge` | GET | 页面 |
| `/upload-model` | POST | 上传模型，返回顶点/面片与 `file_path` |
| `/list-models` | GET | 列出 `uploads/` 中的模型 |
| `/run-slice` | POST | 切片，返回 `layers`（层数）与层高 |
| `/run-path-generation` | POST | 生成路径，返回 `point_count` |
| `/generate-gcode` | POST | 生成 GCode，返回文件名与下载地址 |
| `/ai-terminal` | POST | 自然语言 → 操作序列并执行 |
| `/api/register` `/api/login` `/api/logout` | POST | 账户 |
| `/api/check-session` | GET | 会话校验 |
| `/api/get-credit-points` | GET | 查询信用点 |
| `/api/deduct-credit` `/api/recharge-credit` | POST | 扣减 / 充值 |
| `/uploads/<path:filename>` | GET | 下载 GCode 与模型 |
| `/docs` | GET | OpenAPI 说明页（`static/docs.html`） |

---

## 工艺参数

默认值定义在 `suAgent/process_decision_engine.py::default_params`，是**全项目唯一真相源**
（Web 表单、桌面端初值、AI prompt 均由此渲染）。

| 参数 | 默认值 | 含义 |
|---|---|---|
| `layer_height` | 0.2 | 层高 (mm) |
| `first_layer_height` | 0.2 | 首层高度 (mm) |
| `nozzle_d` | 0.8 | 喷嘴直径 (mm) |
| `filament_d` | 1.75 | 耗材直径 (mm) |
| `infill_density` | 30.0 | 填充密度 (%) |
| `speed` | 60 | 打印速度 (mm/s) |
| `extruder_temp` | 200 | 喷嘴温度 (°C) |
| `bed_temp` | 60 | 热床温度 (°C) |
| `offset` | 0.8 | 纤维沉积间距 (mm) |

物理约束由 `suAgent/constraint_validator.py` 校验（如 `layer_height ≤ nozzle_d`），
越界会被自动纠正或拒绝。

---

## AI 配置

三家提供方都走 OpenAI 兼容协议，只需在 `.env` 里配 Key：

| 提供方 | `AI_PROVIDER` | Key 环境变量 | 默认模型 |
|---|---|---|---|
| DeepSeek | `deepseek` | `DEEPSEEK_API_KEY` | `deepseek-chat` |
| Moonshot (Kimi) | `kimi` | `MOONSHOT_API_KEY` | `moonshot-v1-8k` |
| OpenAI | — | `OPENAI_API_KEY` | 需配 `AI_MODEL` |

```dotenv
AI_PROVIDER=deepseek
AI_MODEL=deepseek-chat
DEEPSEEK_API_KEY=sk-...
FLASK_SECRET_KEY=<生产环境必须设置>
# DATABASE_URL=postgresql://...
# CORS_ALLOWED_ORIGINS=http://localhost:5000
```

- 未设 `AI_PROVIDER` 时，`resolve_provider()` 自动挑选**第一个已配置 Key** 的提供方（deepseek → kimi），因此只配 Moonshot 的旧环境仍可用。
- 未配 `FLASK_SECRET_KEY` 时每进程随机生成，**多 worker 部署会导致登录随机失效**，生产必须显式设置。

---

## 测试

发布包只带一个**自检用例**（完整测试套件留在源仓库）：

```bash
PYTHONDONTWRITEBYTECODE=1 pytest tests/test_release_smoke.py -p no:cacheprovider
```

它验证 5 件事：全新副本删掉 `instance/` 后能自建目录、URI 反推目录与实际创建目录一致、
`suFabEngine` 导入落在包内（没走外部安装）、包内无 `.env`/`__pycache__`/`*.pyc`、
`create_app()` 成功且路由数 ≥ 20。

> `PYTHONDONTWRITEBYTECODE=1` 与 `-p no:cacheprovider` 是必须的：
> 否则 pytest 会在包里生成 `__pycache__`，自检项 4 会因此失败。

---

## 已知限制

| 项 | 现状 |
|---|---|
| 信用点体系 | **未强制**。充值无凭证校验，扣减接口前端未调用，仅作界面展示 |
| `/uploads/<path>` | 无归属鉴权，知道文件名即可下载（GCode 文件名带 uuid 后缀降低可猜性） |
| 桌面端 | 无自动化测试；切片/GCode 生成在**主线程**执行，长任务会阻塞界面 |
| 业务错误状态码 | 路由级错误返回 HTTP 200（前端依赖 `status` 字段判断），改动需前后端同步 |
| 依赖版本 | Flask 2.3.3 / Werkzeug 2.3.7 为较早版本，升级前需回归 |

---

## 第三方依赖

| 依赖 | 用途 |
|---|---|
| [MinettoSlicer](https://github.com/rminetto/slicing) | 三角形网格切片算法（`MeshSlicer/slicer.py`） |
| VTK 9.0.3 | 网格数据结构与桌面渲染 |
| PyQt5 5.15.10 | 桌面 GUI |
| Three.js | Web 端 3D 预览 |
| pyclipper / shapely | 轮廓布尔运算与几何计算 |
| PyTorch 2.1.2 | 桌面端路径优化器（`PathOptimizer` 模块级依赖；Web 端不需要） |

---

## 许可证

本项目为专有软件（Proprietary），保留所有权利（All Rights Reserved）。
未经授权，不得复制、修改、分发或用于商业用途。
