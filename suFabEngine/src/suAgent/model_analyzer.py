"""
ModelAnalyzer — STL 模型几何特征分析器。

纯 VTK 实现，零外部依赖。
为智能工艺决策提供模型维度的数据支撑。
"""

import logging
import numpy as np
import vtk


class ModelAnalyzer:
    """3D 打印模型几何分析器。

    分析 VTK polydata（来自 STL 加载），
    输出包围盒尺寸、悬挑角度分布、薄壁检测、体积估算等几何特征。
    """

    @staticmethod
    def analyze(polydata) -> dict:
        """分析 VTK polydata，返回完整几何特征字典。

        Args:
            polydata: vtkPolyData 对象（stlReader.GetOutput()）

        Returns:
            dict: {
                "dimensions_mm": {"x", "y", "z"},
                "volume_mm3": float,
                "surface_area_mm2": float,
                "aspect_ratio": float,
                "overhang_analysis": {"max_overhang_deg", "severe_pct", "needs_support"},
                "wall_analysis": {"min_dimension_mm", "has_thin_walls", "recommended_nozzle"},
                "estimated_print_time_min": float,
                "estimated_material_g": float,
            }
        """
        bounds = polydata.GetBounds()
        dim_x = round(bounds[1] - bounds[0], 2)
        dim_y = round(bounds[3] - bounds[2], 2)
        dim_z = round(bounds[5] - bounds[4], 2)

        volume = ModelAnalyzer._compute_volume(polydata)
        surface_area = ModelAnalyzer._compute_surface_area(polydata)
        overhang = ModelAnalyzer._analyze_overhangs(polydata)
        wall = ModelAnalyzer._analyze_walls(polydata)

        # 粗略估算（PLA 基准）
        density_g_per_cm3 = 1.24  # PLA 密度
        estimated_material_g = round(volume / 1000 * density_g_per_cm3, 2)
        estimated_time_min = round(max(volume / 500, 2), 0)

        return {
            "dimensions_mm": {"x": dim_x, "y": dim_y, "z": dim_z},
            "volume_mm3": round(volume, 2),
            "surface_area_mm2": round(surface_area, 2),
            "aspect_ratio": round(max(dim_x, dim_y) / max(min(dim_x, dim_y), 0.01), 2),
            "overhang_analysis": overhang,
            "wall_analysis": wall,
            "estimated_print_time_min": estimated_time_min,
            "estimated_material_g": estimated_material_g,
        }

    @staticmethod
    def _compute_volume(polydata) -> float:
        """使用 VTK MassProperties 计算体积（散度定理）。"""
        try:
            mass = vtk.vtkMassProperties()
            mass.SetInputData(polydata)
            mass.Update()
            return abs(mass.GetVolume())
        except Exception:
            logging.debug("体积计算失败，返回 0")
            return 0.0

    @staticmethod
    def _compute_surface_area(polydata) -> float:
        """计算模型表面积。"""
        try:
            mass = vtk.vtkMassProperties()
            mass.SetInputData(polydata)
            mass.Update()
            return mass.GetSurfaceArea()
        except Exception:
            logging.debug("表面积计算失败，返回 0")
            return 0.0

    @staticmethod
    def _analyze_overhangs(polydata) -> dict:
        """分析模型悬挑面角度分布。

        计算每个三角形面法向量与 Z 轴 (0,0,1) 的夹角。
        夹角 > 45° 的面视为"严重悬挑"。
        """
        normals_filter = vtk.vtkPolyDataNormals()
        normals_filter.SetInputData(polydata)
        normals_filter.ComputePointNormalsOff()
        normals_filter.ComputeCellNormalsOn()
        normals_filter.Update()

        cell_normals = normals_filter.GetOutput().GetCellData().GetNormals()
        if not cell_normals:
            return {"max_overhang_deg": 0, "severe_pct": 0, "needs_support": False}

        n_cells = cell_normals.GetNumberOfTuples()
        max_angle = 0.0
        severe_count = 0

        for i in range(n_cells):
            nx = cell_normals.GetComponent(i, 0)
            ny = cell_normals.GetComponent(i, 1)
            nz = cell_normals.GetComponent(i, 2)

            # 与 Z 轴的夹角（只关心方向，取绝对值）
            dot = abs(nz)  # n · (0,0,1) = nz
            angle = np.degrees(np.arccos(np.clip(dot, 0.0, 1.0)))

            if angle > max_angle:
                max_angle = angle
            if angle > 45:
                severe_count += 1

        severe_pct = round(severe_count / n_cells * 100, 1) if n_cells > 0 else 0

        return {
            "max_overhang_deg": round(max_angle, 1),
            "severe_pct": severe_pct,
            "needs_support": severe_pct > 5,
        }

    @staticmethod
    def _analyze_walls(polydata) -> dict:
        """粗略薄壁检测——基于最小包围盒维度。"""
        bounds = polydata.GetBounds()
        dims = [
            bounds[1] - bounds[0],
            bounds[3] - bounds[2],
            bounds[5] - bounds[4],
        ]
        min_dim = round(min(dims), 2)

        return {
            "min_dimension_mm": min_dim,
            "has_thin_walls": min_dim < 1.0,
            "recommended_nozzle": round(min(min_dim * 0.5, 0.8), 2),
        }
