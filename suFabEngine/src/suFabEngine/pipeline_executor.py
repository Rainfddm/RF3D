"""Qt-free 打印管线执行器。

从 app.py 的 CommandExecutor 抽离，去除所有 Qt（PyQt5 / pyqtgraph / Viewer / Controller）
依赖，直接持有 suFabEngine.Pipeline 实例，供 Web 端与桌面端共用。

对外接口与 CommandExecutor 保持兼容：execute_cmd(command_name, **params)
"""

import os
import time
import uuid
import logging
import inspect
import traceback
from typing import Any, Callable, Dict

import numpy as np
import vtk

from suFabEngine.Pipeline import Pipeline
from suAgent.process_decision_engine import ProcessDecisionEngine
from suFabEngine.GCoder.suGCoder import suGCoder


class PipelineExecutor:
    """Qt-free 的打印管线命令执行器（请求级实例，状态不跨请求共享）。"""

    # 区域间空走的回抽设置。头部 GCode 含 M83（相对挤出），
    # 因此回抽/回填用相对量，不影响后续按段计算的 E。
    TRAVEL_RETRACT_MM = 1.0      # 回抽长度（mm）
    TRAVEL_RETRACT_FEED = 200    # 回抽速度（mm/min）
    TRAVEL_PRIME_FEED = 1200     # 回填速度（mm/min），过快会产生冲击痕

    # 热床中心（mm）。曾错误地把「纤维沉积间距 offset」当作 center 传进去，
    # 导致改沉积间距会顺带移动整张图的原点。二者语义无关，必须分开。
    BED_CENTER = (150.0, 150.0)

    def __init__(self, output_dir=None):
        # 算法管线
        self.pipeline = Pipeline()

        # 状态
        self.b_stl_loaded = False
        self.b_stl_sliced = False
        self.vtk_poly_data = None
        self.params: Dict[str, Any] = {}
        # 参数写入被拒绝 / 被忽略的原因，供调用方（路由、UI）追溯，
        # 避免「非法参数静默丢弃」这类不可观测行为
        self.param_warnings: list = []

        # GCode 输出目录（默认项目根 uploads，normpath 归一化掉 ../ 段）
        self.output_dir = output_dir or os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "../../../uploads"
        ))
        os.makedirs(self.output_dir, exist_ok=True)

        # 命令注册表
        self.commands: Dict[str, Callable] = {}
        self._register_methods()

    def _register_methods(self):
        for name, method in inspect.getmembers(self, inspect.ismethod):
            if name.startswith("_execute"):
                command_name = name[len("_execute_"):]
                self.commands[command_name] = method
                logging.info("Registered command: %s", command_name)

    def execute_cmd(self, command_name: str, **params) -> Any:
        """执行指定命令。"""
        if command_name not in self.commands:
            raise ValueError(f"Unknown command: {command_name}")
        try:
            logging.info("Executing command: %s : %s", command_name, params)
            return self.commands[command_name](**params)
        except Exception as e:
            logging.error("Error executing %s: %s", command_name, e)
            raise RuntimeError(f"Error executing {command_name}: {e}")

    # ---------- 参数 ----------

    # 前端键名 → 后端 params 键名（与 application.utils._PARAM_ALIAS 保持一致）
    _PARAM_ALIASES = {"nozzle_diameter": "nozzle_d", "filament_diameter": "filament_d"}

    def _allowed_param_names(self):
        """参数白名单来自唯一真相源 ProcessDecisionEngine.default_params。"""
        return set(ProcessDecisionEngine().default_params.keys())

    def _validate_and_apply_params(self, kwargs, strict=True):
        """白名单 + 别名归一 + float 转换，全部通过才写入。

        之前 `_execute_set_params` 与 `_execute_slice` 都是直接
        `self.params[key] = value`：任意键名、任意类型都能写进去，
        拼错的键会静默变成死数据，非数字值要到 slice() 才炸。

        Args:
            kwargs: 待写入的参数
            strict: True  —— 任一参数非法则整体拒绝（返回错误描述，一个都不写）
                    False —— 尽力而为：合法的写入，非法的记入 param_warnings

        Returns:
            None 表示成功；strict=True 且失败时返回错误描述字符串。
        """
        allowed = self._allowed_param_names()
        errors = []
        pending = {}

        for key, value in kwargs.items():
            name = self._PARAM_ALIASES.get(key, key)
            if name not in allowed:
                errors.append(f"不支持的参数 {key}（可用：{', '.join(sorted(allowed))}）")
                continue
            try:
                pending[name] = float(value)
            except (TypeError, ValueError):
                errors.append(f"参数 {key} 的值不是数字：{value!r}")

        if errors and strict:
            return "；".join(errors)

        self.params.update(pending)
        if errors:
            self.param_warnings.extend(errors)
            for msg in errors:
                logging.warning("参数被忽略：%s", msg)
        return None

    def _update_process_params_backend(self):
        """后端版本的参数更新，不依赖 UI 组件。"""
        default_params = ProcessDecisionEngine().default_params
        for key, value in default_params.items():
            if key not in self.params:
                self.params[key] = value

    def update_params_from_request(self, request_data):
        """从请求数据更新参数（尽力而为：合法项生效，非法项记入 param_warnings）。

        这个入口不返回错误 —— 它有 4 个 Web 路由调用方且都不检查返回值。
        需要严格语义的地方（set_params / slice 命令）走
        `_validate_and_apply_params(strict=True)`。
        """
        self._update_process_params_backend()
        if not isinstance(request_data, dict):
            msg = f"请求参数不是 dict：{type(request_data).__name__}"
            self.param_warnings.append(msg)
            logging.warning("%s", msg)
            return self.params
        self._validate_and_apply_params(request_data, strict=False)
        return self.params

    def _execute_set_params(self, **kwargs):
        error = self._validate_and_apply_params(kwargs, strict=True)
        if error:
            return f"错误: {error}"
        return "参数设置成功"

    # ---------- 命令 ----------
    @staticmethod
    def center_model(vtk_poly_data):
        """模型平移到原点：XY 居中、Z 底部归零（与桌面端 VTKViewer.loadSTL 对齐）。

        仅依赖 vtk，无任何 Qt 依赖，供 Web 端与桌面端共用。
        """
        bounds = vtk_poly_data.GetBounds()
        transform = vtk.vtkTransform()
        transform.Translate(
            -(bounds[1] + bounds[0]) / 2.0,
            -(bounds[3] + bounds[2]) / 2.0,
            -bounds[4],
        )
        f = vtk.vtkTransformPolyDataFilter()
        f.SetInputData(vtk_poly_data)
        f.SetTransform(transform)
        f.Update()
        return f.GetOutput()

    def _execute_load_model(self, **kwargs):
        """加载 STL 模型（网页端仅支持 .stl）。"""
        file_path = kwargs.get("file_path", None)
        if not file_path:
            return "错误: 缺少 file_path 参数"

        ext_file = os.path.splitext(file_path)[1].lower()
        if ext_file != ".stl":
            return f"不支持的文件格式: {ext_file}（网页端仅支持 .stl）"

        try:
            reader = vtk.vtkSTLReader()
            reader.SetFileName(file_path)
            reader.Update()
            poly = reader.GetOutput()
            # vtkSTLReader 对不存在 / 畸形 / 0 字节文件不抛异常，只把错误写到 stderr，
            # GetOutput() 返回点数 0 的空 polydata（bounds 为 (1,-1,1,-1,1,-1)）。
            # 因此必须显式校验点数，否则会把坏文件判成「加载成功」。
            if poly is None or poly.GetNumberOfPoints() == 0:
                logging.error("STL 解析为空（点数为 0）: %s", file_path)
                self.b_stl_loaded = False
                return f"错误: 无法解析 STL（点数为 0）: {file_path}"
            self.vtk_poly_data = self.center_model(poly)
            self.b_stl_loaded = True
            # 换模型必须让旧切片失效：否则 b_stl_sliced 仍为 True、pipeline.planes
            # 仍是旧模型的层，后续 generate_path 会用旧 planes 产出新模型的路径。
            self.b_stl_sliced = False
            self.pipeline.planes = None
            self.pipeline.layers_heights = []
            print(f"[加载模型] 成功: {file_path}（{poly.GetNumberOfPoints()} 点）")
            return f"STL模型加载成功: {file_path}"
        except Exception as e:
            logging.error("模型加载错误: %s", e)
            self.b_stl_loaded = False
            return f"错误: {e}"

    def _execute_slice(self, **kwargs):
        """执行切片命令。"""
        try:
            # 与 set_params 共用同一套白名单校验：非法参数直接拒绝，不写库、不切片
            error = self._validate_and_apply_params(kwargs, strict=True)
            if error:
                logging.error("切片参数非法: %s", error)
                return f"错误: {error}"

            self._update_process_params_backend()

            if not self.b_stl_loaded:
                return "错误: 请先加载STL模型文件"
            if self.vtk_poly_data is None:
                return "错误: 无法获取模型数据"

            self.pipeline.load_params(self.params)
            self.pipeline.load(self.vtk_poly_data)
            self.pipeline.slice()

            planes = self.pipeline.get_planes()
            n_layer = (len(planes) - 1) if planes else 0
            layer_height = self.params.get("layer_height", "?")
            logging.info("Slicing %d layers", n_layer)
            print(f"[切片] 完成：{n_layer} 层，层高 {layer_height}mm")

            # 0 层不是「切片成功」：模型为空、超出切片范围、或 STL 没有封闭面时
            # 都会得到 0 层。以前照样置 b_stl_sliced=True 并返回「切片完成: 0 层」，
            # 上层只按关键词判错 → 用户看到 success，下一步才在路径生成时莫名失败。
            if n_layer <= 0:
                self.b_stl_sliced = False
                logging.error("切片结果为 0 层，模型可能为空或不在切片范围内")
                return "错误: 切片结果为 0 层（模型为空或不在切片范围内）"

            self.b_stl_sliced = True
            return f"切片完成: {n_layer} 层"
        except Exception as e:
            logging.error("切片处理失败: %s", e)
            traceback.print_exc()
            return f"切片处理失败: {str(e)}"

    @staticmethod
    def _convert_point(p):
        """递归转换潜在的自定义对象为坐标元组。"""
        if hasattr(p, "coord"):
            return (p.coord[0], p.coord[1], p.coord[2])
        elif isinstance(p, (list, tuple, np.ndarray)) and len(p) >= 3:
            return (float(p[0]), float(p[1]), float(p[2]))
        raise ValueError(f"无效路径点类型: {type(p)}, 值: {p}")

    def _build_validated_path(self, raw_path):
        """将原始路径转换为经过维度与数值校验的 (N,3) numpy 数组。"""
        validated_path = [self._convert_point(p) for p in raw_path]
        path = np.array(validated_path, dtype=np.float32)
        if path.ndim != 2 or path.shape[1] != 3:
            raise ValueError(f"路径数据维度错误，期望形状(N,3)，实际得到{path.shape}")
        # NaN / Inf 会被 np.float32 静默接受，一路传到 GCode 里变成 "Xnan"。
        # 必须在这里拦住，且调用点要把 ValueError 降级成可返回的错误（见各 _execute_*）。
        if not np.isfinite(path).all():
            bad_idx = int(np.argwhere(~np.isfinite(path))[0][0])
            raise ValueError(
                f"路径第 {bad_idx} 个点含非有限值(NaN/Inf): {path[bad_idx].tolist()}"
            )
        return path

    def _execute_generate_path(self, **kwargs):
        """执行路径生成命令。"""
        logging.info("执行路径生成命令，参数: %s", kwargs)

        # 应用调用方传入的参数：AI 终端会把 LLM 给出的 generate_path(...) 参数
        # 通过 execute_cmd(cmd, **params) 透传到这里（application/blueprints/ai.py:86）。
        # 非严格模式：未知键记入 param_warnings 后继续，避免 LLM 多吐一个键
        # 就让整条流水线中断。
        self._validate_and_apply_params(kwargs, strict=False)

        if not self.b_stl_loaded:
            logging.error("未加载模型，请先加载模型。")
            return None
        if not self.b_stl_sliced or not self.pipeline.planes:
            logging.error("未完成切片，请先执行切片。")
            return None

        self._update_process_params_backend()
        self.pipeline.load_params(self.params)

        raw_path = self.pipeline.generate_global_path(
            collision_dist_xy=30,
            collision_dist_z=3000,
            offset=self.params.get("offset", 0.8),
        )

        if raw_path is None or len(raw_path) == 0:
            logging.error("路径生成失败：generate_global_path 返回空数据")
            return None

        # 校验不通过时降级为可返回的错误，否则异常会穿透 execute_cmd
        # 被包成 RuntimeError，用户侧从「拿到坏 GCode」变成「500 报错」。
        try:
            path = self._build_validated_path(raw_path)
        except ValueError as exc:
            logging.error("路径校验失败: %s", exc)
            return f"错误: {exc}"
        n_points = path.shape[0]
        path_length = 0.0
        if n_points > 1:
            path_length = float(np.sum(np.sqrt(np.sum(np.diff(path, axis=0) ** 2, axis=1))))
        logging.info("路径数据验证通过，形状: %s", path.shape)
        print(f"[路径] 完成：点数 {n_points}，路径总长度 {path_length:.2f}mm")
        return path

    def build_gcode(self, path, callback=None, region_slices=None):
        """路径 → suGCoder 实例（纯逻辑，Web/桌面两端复用）。

        区域间转移（空走）必须发 G0 且不挤出。suGCoder 只看得到 (N,3) 点集、
        没有区域 ID，若靠「距离 > 阈值」猜，会被 simplify_path 抽稀出来的长直段
        误伤（把正常的连续纤维打印段判成空走）。因此这里按 Pipeline 记录的区域
        边界把路径切成若干块，逐块生成后拼接：每块的第一条移动天然是
        `G0 X.. Y.. Z..`（不带 E），正是从上一个区域空走到本区域起点。

        Args:
            path: (N,3) numpy 数组（已校验的路径点）
            callback: 进度回调 callback(value, total=100, algo_name=...)
            region_slices: [(start, end), ...]；默认取 self.pipeline.region_slices。
                为空或只有一块时退化为单块（保持旧行为）。

        Returns:
            suGCoder 实例（含 output_lines，可调用 save(filepath) 落盘）
        """
        path = np.asarray(path)
        if region_slices is None:
            region_slices = getattr(self.pipeline, "region_slices", None) or []

        n_points = len(path)
        slices = [
            (int(a), int(b))
            for a, b in region_slices
            if 0 <= int(a) < int(b) <= n_points
        ]

        def _make(sub_path):
            return suGCoder(
                input_data=sub_path,
                # center 是热床中心，不是纤维偏移量。它当前只被 suGCoder.to_location()
                # 使用，而该方法无调用方，故本次改动对 GCode 输出零影响（已逐字节比对）。
                center=self.BED_CENTER,
                nozzle_d=self.params["nozzle_d"],
                filament_d=self.params["filament_d"],
                layer_height=self.params["layer_height"],
                extruder_temp=self.params.get("extruder_temp", 200),
                bed_temp=self.params.get("bed_temp", 60),
            )

        # 单块（或未提供边界）：保持原有行为
        if len(slices) <= 1:
            gcode_generator = _make(path)
            gcode_generator.process(x0=150, y0=150, callback=callback)
            return gcode_generator

        # 多块：逐块生成，只保留首块的头、末块的尾，中间块只取运动行。
        # 每块 process() 的第一条运动指令都是 G0（prev 为空 → distance 0 → 不挤出）。
        total_points = sum(b - a for a, b in slices)
        done = [0]

        def _scaled_callback(value, total=100, algo_name="GCode生成中"):
            if callback is not None:
                callback(done[0] + value, total=total_points, algo_name=algo_name)

        generators = []
        for a, b in slices:
            sub = _make(path[a:b])
            sub.process(x0=150, y0=150, callback=_scaled_callback)
            generators.append(sub)
            done[0] += b - a

        header = generators[0].output_lines[0]
        footer = generators[-1].output_lines[-1]

        # 块间空走必须回抽，否则喷嘴残压会在空中拉丝。
        # 头部有 M83（相对挤出），所以这里用相对回抽/回填，不会打乱后续按段计算的 E。
        # 注意：output_lines 的元素自带换行，注入的行也必须带，否则会与相邻指令粘成一行。
        retract_line = f"G1 E-{self.TRAVEL_RETRACT_MM:.4f} F{self.TRAVEL_RETRACT_FEED}\n"
        prime_line = f"G1 E{self.TRAVEL_RETRACT_MM:.4f} F{self.TRAVEL_PRIME_FEED}\n"

        body = []
        for index, sub in enumerate(generators):
            motions = sub.output_lines[1:-1]
            if index == 0:
                body.extend(motions)
                continue
            # 每块的第一条运动是 G0（prev 为空 → 不挤出）→ 正是区域间空走
            body.append(retract_line)      # 在上一块收尾处回抽
            body.append(motions[0])        # G0 空走到新区域起点
            body.append(prime_line)        # 到达后回填，恢复喷嘴压力
            body.extend(motions[1:])

        composed = generators[0]
        composed.output_lines = [header, *body, footer]
        composed.input_data = path
        logging.info(
            "GCode 按 %d 个区域块生成，共 %d 点；块间为空走（G0 不挤出）+ 回抽/回填",
            len(slices),
            total_points,
        )
        return composed

    def _execute_generate_gcode(self, **kwargs):
        """执行 GCode 生成命令。"""
        logging.info("执行GCode生成命令，参数: %s", kwargs)

        # 同 _execute_generate_path：AI 终端下发的 speed / extruder_temp / bed_temp
        # 必须真正生效，否则用户在自然语言里说「速度 120」不会改变任何东西。
        self._validate_and_apply_params(kwargs, strict=False)

        self._update_process_params_backend()

        try:
            if not self.b_stl_loaded:
                return "错误: 请先加载STL模型文件"
            if not self.b_stl_sliced or not self.pipeline.planes:
                return "错误: 请先对模型进行切片"
            if len(self.pipeline.planes) <= 1:
                return "错误: 切片数据不足，无法生成GCode"

            self.pipeline.load_params(self.params)

            raw_path = self.pipeline.generate_global_path(
                collision_dist_xy=30,
                collision_dist_z=3000,
                offset=self.params.get("offset", 0.8),
            )
            if raw_path is None or len(raw_path) == 0:
                return "错误: 没有找到已生成的路径数据，请先执行路径生成操作"

            # 同 _execute_generate_path：校验失败必须降级为 dict 错误返回，
            # 不要把 ValueError 抛给 execute_cmd 变成 RuntimeError。
            try:
                path = self._build_validated_path(raw_path)
            except ValueError as exc:
                logging.error("路径校验失败: %s", exc)
                return {"status": "error", "message": f"错误: {exc}"}

            def dummy_callback(value, total=100, algo_name="GCode生成中"):
                percent = int(round((value / total) * 100))
                logging.info("%s: %d%%", algo_name, percent)

            gcode_generator = self.build_gcode(path, callback=dummy_callback)
            gcode_content = "".join(gcode_generator.output_lines)

            # 文件名必须跨请求唯一：PipelineExecutor 是请求级实例，进程内计数器
            # 每次新建都从 1 开始，两个同秒并发请求仍会撞名。用 uuid 后缀，
            # 与实例生命周期无关；时间戳前缀只用于人工按时间排序。
            timestamp = int(time.time())
            gcode_filename = f"gcode_output_{timestamp}_{uuid.uuid4().hex[:8]}.gcode"
            gcode_filepath = os.path.join(self.output_dir, gcode_filename)
            gcode_generator.save(gcode_filepath)
            logging.info("GCode文件已保存至: %s", gcode_filepath)
            print(f"[GCode] 生成完成，文件保存至：{gcode_filepath}")

            return {
                "status": "success",
                "message": "GCode生成完成",
                "gcode_length": len(gcode_content),
                "download_url": f"/uploads/{gcode_filename}",
                "gcode_filename": gcode_filename,
                "parameters_used": {
                    k: v for k, v in self.params.items()
                    if k in ["layer_height", "first_layer_height", "nozzle_d", "filament_d",
                             "offset", "reinforced_fiber_d", "base_fiber_d", "temperature", "bed_temp"]
                },
            }
        except Exception as e:
            traceback.print_exc()
            logging.error("GCode 生成失败: %s", e)
            return {"status": "error", "message": f"GCode生成失败: {e}"}

    def _execute_print(self, **kwargs):
        return "打印功能未实现（网页端暂不支持）"
