"""打印管线路由：上传、切片、路径生成、GCode 生成。"""

import os
import logging

import numpy as np
import vtk
from flask import Blueprint, request, jsonify, current_app

from suFabEngine.pipeline_executor import PipelineExecutor
from application.utils import (
    MODEL_EXTENSIONS,
    get_latest_stl,
    normalize_params,
    secure_model_filename,
)

pipeline_bp = Blueprint("pipeline", __name__)


def _upload_folder():
    return current_app.config["UPLOAD_FOLDER"]


@pipeline_bp.route("/run-slice", methods=["POST"])
def run_slice_route():
    try:
        data = request.get_json() or {}

        model_path = get_latest_stl(_upload_folder())
        if not model_path:
            return jsonify({"status": "error", "message": "请先上传STL模型文件"})

        executor = PipelineExecutor()
        load_result = executor.execute_cmd("load_model", file_path=model_path)
        if isinstance(load_result, str) and load_result.startswith("错误"):
            return jsonify({"status": "error", "message": load_result})

        executor.update_params_from_request(normalize_params(data))
        params = executor.params

        slice_result = executor.execute_cmd("slice", **params)
        if isinstance(slice_result, str) and ("失败" in slice_result or "错误" in slice_result):
            return jsonify({"status": "error", "message": f"切片失败: {slice_result}"})

        # 不要只看返回字符串：真实层数就在这里，以前被整段丢弃，
        # 上层只能回一句「层高: xx mm」，用户与前端都拿不到层数。
        planes = executor.pipeline.get_planes()
        n_layer = (len(planes) - 1) if planes else 0
        if n_layer <= 0:
            return jsonify({
                "status": "error",
                "message": "切片失败: 生成了 0 层，模型可能为空或不在切片范围内",
            })

        logging.info("切片处理完成，共 %d 层", n_layer)
        return jsonify({
            "status": "success",
            "message": f"切片处理完成，共 {n_layer} 层，层高: {params.get('layer_height')}mm",
            "layers": n_layer,
            "layer_height": params.get("layer_height"),
        })

    except Exception as e:
        return jsonify({"status": "error", "message": f"服务器内部错误: {str(e)}"})


@pipeline_bp.route("/run-path-generation", methods=["POST"])
def run_generate_path_route():
    try:
        data = request.get_json() or {}

        model_path = get_latest_stl(_upload_folder())
        if not model_path:
            return jsonify({"status": "error", "message": "请先上传STL模型文件"})

        executor = PipelineExecutor()
        load_result = executor.execute_cmd("load_model", file_path=model_path)
        if isinstance(load_result, str) and load_result.startswith("错误"):
            return jsonify({"status": "error", "message": load_result})

        executor.update_params_from_request(normalize_params(data))
        slice_result = executor.execute_cmd("slice")
        if isinstance(slice_result, str) and ("失败" in slice_result or "错误" in slice_result):
            return jsonify({"status": "error", "message": f"切片失败: {slice_result}"})

        path_result = executor.execute_cmd("generate_path")
        if path_result is None:
            return jsonify({"status": "error", "message": "路径生成失败：模型未加载或切片未完成"})
        elif isinstance(path_result, np.ndarray):
            logging.info("路径生成完成，共 %d 个路径点", len(path_result))
            return jsonify({
                "status": "success",
                "message": f"路径生成完成，共 {len(path_result)} 个路径点",
                "point_count": len(path_result),
            })
        else:
            return jsonify({"status": "error", "message": f"路径生成失败: {str(path_result)[:200]}"})

    except Exception as e:
        logging.error(f"路径生成错误: {str(e)}")
        return jsonify({"status": "error", "message": f"服务器内部错误: {str(e)}"})


@pipeline_bp.route("/list-models", methods=["GET"])
def list_models():
    try:
        upload_folder = _upload_folder()
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder, exist_ok=True)
            return jsonify({"models": []})

        model_files = [f for f in os.listdir(upload_folder) if f.endswith((".stl", ".obj", ".3mf"))]
        return jsonify({"models": model_files})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@pipeline_bp.route("/upload-model", methods=["POST"])
def upload_model():
    if "model_file" not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400

    file = request.files["model_file"]
    if file.filename == "":
        return jsonify({"status": "error", "message": "No selected file"}), 400

    # 先校验扩展名再落盘：不合格的文件不该在 uploads/ 里出现哪怕一瞬
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in MODEL_EXTENSIONS:
        return jsonify({
            "status": "error",
            "message": "Unsupported file format. Only STL, OBJ, and 3MF files are supported.",
        }), 400

    upload_folder = _upload_folder()
    os.makedirs(upload_folder, exist_ok=True)

    # secure_filename 会把中文名整段剥掉连扩展名一起丢（"螺旋桨.stl" -> "stl"），
    # 这里改用保留扩展名的版本，否则存下来的文件 get_latest_stl 找不到。
    safe_name = secure_model_filename(file.filename)
    file_path = os.path.join(upload_folder, safe_name)
    file.save(file_path)

    try:
        reader = None
        if ext == ".stl":
            reader = vtk.vtkSTLReader()
        elif ext == ".obj":
            reader = vtk.vtkOBJReader()
        else:
            # pip 安装的 vtk 默认未编译 IO3MF 模块，vtk3MFReader 可能不存在。
            # 直接调用会 AttributeError → 500，这里显式降级为 400 并说明原因。
            if not hasattr(vtk, "vtk3MFReader"):
                if os.path.exists(file_path):
                    os.remove(file_path)
                return jsonify({
                    "status": "error",
                    "message": "当前 VTK 构建不支持 3MF，请改用 STL 或 OBJ",
                }), 400
            reader = vtk.vtk3MFReader()

        reader.SetFileName(file_path)
        reader.Update()
        polydata = reader.GetOutput()

        if polydata.GetNumberOfPoints() == 0:
            if os.path.exists(file_path):
                os.remove(file_path)
            return jsonify({"status": "error", "message": "Invalid 3D model file: no points found"}), 400

        points = polydata.GetPoints()
        verts = []
        for i in range(points.GetNumberOfPoints()):
            p = points.GetPoint(i)
            verts.append([p[0], p[2], p[1]])

        faces = []
        polys = polydata.GetPolys()
        polys.InitTraversal()
        id_list = vtk.vtkIdList()
        while polys.GetNextCell(id_list):
            face = [id_list.GetId(j) for j in range(id_list.GetNumberOfIds())]
            faces.append(face)

        model_data = {
            "vertices": verts,
            "faces": faces,
            "bounds": polydata.GetBounds(),
            "file_path": file_path,
        }

        return jsonify({
            "status": "success",
            "message": f"模型上传成功: {file.filename}",
            "model_data": model_data,
            "file_path": file_path,
        }), 200

    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({"status": "error", "message": f"Error processing file: {str(e)}"}), 500


@pipeline_bp.route("/generate-gcode", methods=["POST"])
def generate_gcode():
    try:
        data = request.get_json() or {}

        model_path = get_latest_stl(_upload_folder())
        if not model_path:
            return jsonify({"status": "error", "message": "请先上传STL模型文件"})

        executor = PipelineExecutor()
        load_result = executor.execute_cmd("load_model", file_path=model_path)
        if isinstance(load_result, str) and load_result.startswith("错误"):
            return jsonify({"status": "error", "message": load_result})

        executor.update_params_from_request(normalize_params(data))
        slice_result = executor.execute_cmd("slice")
        if isinstance(slice_result, str) and ("失败" in slice_result or "错误" in slice_result):
            return jsonify({"status": "error", "message": f"切片失败: {slice_result}"})

        path_result = executor.execute_cmd("generate_path")
        if path_result is None:
            return jsonify({"status": "error", "message": "路径生成失败"})

        result = executor.execute_cmd("generate_gcode")
        if isinstance(result, dict):
            return jsonify(result)
        return jsonify({"status": "error", "message": str(result)})

    except Exception as e:
        return jsonify({"status": "error", "message": f"服务器内部错误: {str(e)}"})
