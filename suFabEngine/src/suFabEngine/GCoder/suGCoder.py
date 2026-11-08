"""suGCoder — 连续纤维增强3D打印 GCode 生成器。

基于路径点集生成标准 FDM GCode，包含路径精简（Douglas-Peucker）、
挤出量计算、速度自适应控制（共线加速/拐角减速）等功能。
"""

import math
import logging
import numpy as np


class suGCoder:
    def __init__(self, input_data, center=(60, 70), N=12, initial_F=200,
                 fan_speed=130, extruder_temp=200, bed_temp=50,
                 nozzle_d=0.8, layer_height=0.2, filament_d=1.75,
                 reinforced_fiber_d=0.15, base_fiber_d=1.75):
        self.N = N
        self.prev_points = [(None, None, None) for _ in range(N)]
        self.prev_F = initial_F
        self.fan_speed = fan_speed
        self.extruder_temp = extruder_temp
        self.bed_temp = bed_temp
        self.output_lines = []
        self.center = center

        self.filament_d = filament_d
        self.nozzle_d = nozzle_d
        self.layer_height = layer_height
        self.reinforced_fiber_d = reinforced_fiber_d
        self.base_fiber_d = base_fiber_d
        self.input_data = input_data

        # 路径简化参数
        self.simplify_threshold = max(nozzle_d * 0.4, layer_height * 1)
        self.min_curve_angle = 3
        self.current_e = 0.0
        self.prev_e = 0.0

    # ── 文件 / 坐标 ──────────────────────────────────────────

    def read_file(self, file_path):
        """从文件读取坐标数据"""
        return np.loadtxt(file_path)

    def to_location(self):
        """将模型中心移动到指定热床位置"""
        x_coords, y_coords = self.input_data[:, 0], self.input_data[:, 1]
        original_center = (np.mean(x_coords), np.mean(y_coords))
        self.input_data[:, 0] += self.center[0] - original_center[0]
        self.input_data[:, 1] += self.center[1] - original_center[1]

    # ── 几何工具 ────────────────────────────────────────────

    def are_points_collinear(self, *points):
        """检查给定点是否共线（epsilon=1e-3，适配连续弯曲路径）"""
        if len(points) < 3:
            return False
        vectors = [(points[i + 1][0] - points[i][0],
                     points[i + 1][1] - points[i][1])
                   for i in range(len(points) - 1)]
        cross_products = [vectors[i][0] * vectors[i + 1][1]
                          - vectors[i][1] * vectors[i + 1][0]
                          for i in range(len(vectors) - 1)]
        return all(abs(cp) < 1e-3 for cp in cross_products)

    def perpendicular_distance(self, point, line_start, line_end):
        """点到直线垂直距离（数值稳定版）"""
        if np.all(line_start == line_end):
            return np.linalg.norm(point - line_start)

        line_vec = line_end - line_start
        point_vec = point - line_start

        line_len = np.linalg.norm(line_vec)
        if line_len < 1e-10:
            return np.linalg.norm(point_vec)

        projection = np.dot(point_vec, line_vec) / line_len
        norm_sq = np.linalg.norm(point_vec) ** 2
        distance_sq = max(norm_sq - projection ** 2, 0)
        return np.sqrt(distance_sq)

    # ── 路径精简 ────────────────────────────────────────────

    def douglas_peucker(self, points, epsilon):
        """Douglas-Peucker 路径精简算法"""
        if len(points) <= 2:
            return points

        dmax = 0.0
        index = 0
        for i in range(1, len(points) - 1):
            d = self.perpendicular_distance(points[i], points[0], points[-1])
            if d > dmax:
                index = i
                dmax = d

        if dmax > epsilon:
            left = self.douglas_peucker(points[:index + 1], epsilon)
            right = self.douglas_peucker(points[index:], epsilon)
            return np.vstack((left[:-1], right))
        return np.array([points[0], points[-1]])

    def should_keep_point(self, points, i):
        """判断是否应保留当前点（曲率检测）"""
        if i < 2 or i > len(points) - 3:
            return True

        p1, p2, p3 = points[i - 1], points[i], points[i + 1]
        v1, v2 = p2 - p1, p3 - p2
        dot = np.dot(v1, v2)
        det = v1[0] * v2[1] - v1[1] * v2[0]
        angle = np.degrees(np.arctan2(det, dot))
        return abs(angle) > self.min_curve_angle

    def is_critical_point(self, point, next_point):
        """检查是否为关键点（Z跳变 / 挤出状态切换）"""
        if abs(point[2] - next_point[2]) > 1e-5:
            return True
        if (self.prev_e == 0) != (self.current_e == 0):
            return True
        return False

    def simplify_path(self, points):
        """路径精简：Douglas-Peucker + 关键点/曲线点保护"""
        if len(points) < 50:
            return points

        simplified = self.douglas_peucker(points, self.simplify_threshold)

        final_points = [simplified[0]]
        for i in range(1, len(simplified) - 1):
            try:
                if self.is_critical_point(simplified[i - 1], simplified[i]):
                    final_points.append(simplified[i])
                elif self.should_keep_point(simplified, i):
                    final_points.append(simplified[i])
            except Exception:
                logging.debug("简化路径点 %d 时异常，保守保留", i)
                final_points.append(simplified[i])

        final_points.append(simplified[-1])
        return np.array(final_points)

    # ── GCode 生成 ──────────────────────────────────────────

    def process(self, x0=0, y0=0, callback=None):
        """从路径点集生成 GCode"""
        # GCode 头部
        self.output_lines.append(
            f"G90\nM83\n"
            f"M106 S{self.fan_speed} ;fan\n"
            f"M104 S{self.extruder_temp} T0 ;extruder temp\n"
            f"M140 S{self.bed_temp} ;set bed temp\n"
            f"M190 S{self.bed_temp} ;wait bed temp\n"
            f"M109 S{self.extruder_temp} T0 ;wait extruder temp\n"
            f"G28 ;home\n"
            f"G92 E0\n"
            f"G1 E5.00 F60\n"
            f"G1 Z0.3 F60\n"
        )

        # 路径精简
        try:
            if len(self.input_data) > 50:
                original_count = len(self.input_data)
                self.input_data = self.simplify_path(self.input_data)
                new_count = len(self.input_data)
                reduction = (1 - new_count / original_count) * 100
                logging.info("路径精简: %d → %d (减少 %.1f%%)",
                             original_count, new_count, reduction)
        except Exception:
            logging.exception("路径精简失败，使用原始路径")

        # 逐点生成 GCode
        total = len(self.input_data)
        for i, line in enumerate(self.input_data):
            try:
                x, y, z = line[0], line[1], line[2]

                # ── 段长计算（挤出量 + 速度判定共用）──
                if self.prev_points[0][0] is not None:
                    prev_x, prev_y, _ = self.prev_points[0]
                    distance = math.sqrt((x - prev_x) ** 2 + (y - prev_y) ** 2)
                    volume = distance * self.nozzle_d * self.layer_height
                    filament_area = math.pi * (self.filament_d / 2) ** 2
                    self.current_e = (
                        round(volume / filament_area, 5)
                        if filament_area > 1e-10 else 0.0
                    )
                else:
                    distance = 0.0
                    self.current_e = 0.0

                # ── 移动类型 + 速度 ──
                if self.current_e == 0:
                    move_command = "G0"
                    F = 1200
                else:
                    move_command = "G1"
                    # 段长 > 20mm 视为长直线，高速打印
                    F = 1200 if distance > 20 else 800

                # ── 输出 ──
                if self.current_e == 0:
                    output_line = (
                        f"{move_command} X{round(x + x0, 4)} "
                        f"Y{round(y + y0, 4)} Z{z} F{F}\n"
                    )
                else:
                    output_line = (
                        f"{move_command} X{round(x + x0, 4)} "
                        f"Y{round(y + y0, 4)} Z{z} "
                        f"E{self.current_e:.5f} F{F}\n"
                    )
                self.output_lines.append(output_line)

                if callback:
                    callback(i + 1, total=total, algo_name="GCode生成中")
                self.prev_points = [(x, y, z)] + self.prev_points[:-1]
                self.prev_e = self.current_e
                self.prev_F = F

            except Exception:
                logging.exception("处理点 %d 时出错，跳过", i)

        # GCode 尾部
        self.output_lines.append(
            "G92 E0\n"
            "G1 E -1.0000 F200\n"
            "G28 ;layer end\n"
            "M104 S0 ;turn off extruder\n"
            "M106 S0 ;turn off fan\n"
            "M140 S0 ;turn off bed\n"
            "M84 ;disable motors\n"
            "M0 ;turn off machine\n"
        )

    def save(self, filename=""):
        """保存 GCode 到文件"""
        try:
            with open(filename, "w") as outfile:
                outfile.writelines(self.output_lines)
        except Exception:
            logging.exception("GCode 保存失败: %s", filename)
