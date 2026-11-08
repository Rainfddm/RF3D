import json
import logging
import numbers
import os

import numpy as np
import scipy.spatial.distance as scid

from suFabEngine.DataProcessor import (
    X,
    Y,
    convert_to_triangles,
    group_contours,
    pathEngine,
    polygon3f,
    slicer,
)
from suFabEngine.Gcode import Gcode
from suFabEngine.Utils.suDataStructure import RDqueue
from suFabEngine.Utils.suGeometry import (
    area,
    compute_region_area,
    get_offset_contour,
    intersect_area,
)

class Pipeline(object):
    """
    A 3d printing pipeline manager for loading, slicing, path planning, gcode generation.
    @parameter list in self.param_json
    "start_gcode": """
    PATH_TYPE_ISO_CONTOUR = 0
    PATH_TYPE_FERMATS_SPIRAL = 1
    PATH_TYPE_CONTINUOUS_ZIGZAG = 2

    from enum import Enum
    class PathType(Enum):
        ISO_CONTOUR = 0
        FERMAT_SPIRAL = 1

    def __init__(self, scene=None):
        self.mesh = None  # triangle lists
        self.params = {}
        self.param_json = {}    #####
        self.planes = None  # includes contours, with format of MinettoSlicer.slicer
        self.layers_heights = []  # layer height list
        # 上一次 generate_global_path 产出的区域边界 [(start, end), ...]，
        # 供 build_gcode 把「区域间转移」发成 G0 空走（见 PipelineExecutor.build_gcode）
        self.region_slices = []

    def info(self):
        return 'A 3d printing pipeline manager for loading, slicing, path planning, gcode generation.'

    def load(self, vtk_poly_data, callback=None):
        # param vtk_poly_data is a triangle mesh return by vtk
        try:
            self.mesh = convert_to_triangles(vtk_poly_data, callback)

        except Exception as e:
            logging.exception("Pipeline load 失败: %s", e)
            raise RuntimeError(f"模型加载失败: {e}") from e

    def load_config(self, config_filename=None):
        # param config_filename includes all parameters in pipeline
        config_file = str(config_filename) if config_filename is not None else 'config.json'

        with open(config_file, 'r') as f:
            self.param_json = json.load(f)

    def load_params(self, data_dict):
        """把参数合并进 self.params（**合并语义，不是整体替换**）。

        早前这里是 `self.params = data_dict`：任何一个只传部分键的调用方
        （例如桌面端 load_stl 传 5 个键）都会把其余参数静默抹掉，
        后续 slice() 取 self.params['first_layer_height'] 就直接 KeyError。
        """
        if not isinstance(data_dict, dict):
            raise TypeError(
                f"load_params 需要 dict，实际收到 {type(data_dict).__name__}"
            )
        self.params.update(data_dict)

    def slice(self, callback=None):
        """
        Slice by Minetto's slicer
        Info only held in self.layers_heights, self.planes
        """
        delta = self.params['layer_height']
        first_delta = self.params['first_layer_height']

        # slicing
        mesh_slicer = slicer(self.mesh, delta, first_delta)
        mesh_slicer.incremental_slicing(callback)

        self.planes = mesh_slicer.planes
        self.layers_heights = mesh_slicer.P

    def gen_printing_region_sequence(self):
        """
        Generate a sequence of printing regions
        Input: planes
        return: R, S: R is a list of printing regions from plane 0 to plane N
                      S is a printing sequence of region list by [[i,j], ...]

        """
        R = []  # Closed region list: R = {r_ij}
        S = []  # sequence with [[i,j]......]

        N = len(self.planes)
        for p in self.planes:
            region = group_contours(p)  # region defined by multiple contours
            R.append(region)

        d = RDqueue(R)  # d = di = dj = deque()
        r, i, j = d.get_end()
        while d.size() != 0:
            if (i < N - 1) and (not self._is_interference_xyz(d, i, j, constraint_xy=10, constraint_z=1000)):
                S.append([i, j])
                d.remove_item(i, j)
                i = i + 1
                # 支撑判定阈值固定用形参默认值（ratio_thresh=0.6），
                # 不能用 -6 这类魔法数 —— `ratio > -6` 恒真会让过滤彻底失效。
                rs, js = self.find_supported_regions(d, r, i)

                if js == []:
                    r, i, j = d.get_end()
                    continue
                else:
                    j = js[0]
                    r = rs[0]
                    for idx in range(1, len(js)):
                        d.move_to_end(i, idx)

                if i == (N - 1):  # reach the top
                    if not self._is_interference_xyz(d, i, j, constraint_xy=10, constraint_z=100):
                        S.append([i, j])
                        d.remove_item(i, j)
                    r, i, j = d.get_end()
            else:
                r_next, i_next, j_next = d.get_end()
                if [i, j] == [i_next, j_next]:  # the extruder goes back and the region is not be appended
                    S.append([i, j])
                    d.remove_item(i, j)
                    r_next, i_next, j_next = d.get_end()
                else:
                    if i <= i_next:  # The new region is not lower than current,
                        S.append([i, j])  # so the nozzle doesn't need to go down.
                        d.remove_item(i, j)
                r = r_next
                i = i_next
                j = j_next

                # generate spiral and connect them
        # todo: connect path on the nearest point

        return R, S

    def get_plane(self, idx=0):
        """
        @return get idx_th plane
        """
        return self.planes[idx]

    def get_planes(self):
        return self.planes

    def fill_layer(self, idx=0, path_type=PATH_TYPE_FERMATS_SPIRAL):
        """
        return path of one layer
        @param idx is layer index. Here the IO is 
        @param path_type = PATH_TYPE_ISO_CONTOUR, PATH_TYPE_FERMATS_SPIRAL ...
        """
        spirals = []
        plane = self.planes[idx]
        group_contour = group_contours(plane)
        pe = pathEngine()
        offset = self.params["offset"]

        if path_type == self.PATH_TYPE_FERMATS_SPIRAL:

            for boundaries in group_contour:
                spiral = pe.fill_spiral_in_connected_region(boundaries, offset)
                spirals.append(spiral)

        elif path_type == self.PATH_TYPE_ISO_CONTOUR:

            for boundaries in group_contour:
                spiral = pe.fill_closed_region_with_iso_contours(boundaries, offset)
                spirals.append(spiral)

        return spirals

    def fill_region(self, boundaries, path_type=PATH_TYPE_FERMATS_SPIRAL):
        """
        return path of one layer
        @param boundaries include one outer and multiple inner boundaries
        @param path_type = PATH_TYPE_ISO_CONTOUR, PATH_TYPE_FERMATS_SPIRAL ...
        """
        spiral = []
        if path_type == self.PATH_TYPE_FERMATS_SPIRAL:
            pe = pathEngine()
            offset = self.params["offset"]
            spiral = pe.fill_spiral_in_connected_region(boundaries, offset)
        return spiral
    
    #####其他地方找不到get_pixel_size
    def get_pixel_size(self):
        """
        根据参数动态计算缩放因子（示例：层高作为缩放比例）
        """
        return self.params.get('layer_height', 0.5)
    #####

    def generate_global_path(self, collision_dist_xy=30, collision_dist_z=3000, offset=-4):
        """
        Generate the global continuous path based on the slicing results stored in self.planes.

        Args:
            collision_dist_xy (float): Maximum allowed collision distance in the XY plane (in mm).
            collision_dist_z (float): Maximum allowed collision distance in the Z direction (in mm).
            offset (float): Offset value for generating iso-contours (in mm).

        Note:
            ``offset`` 目前**不参与支撑判定**。曾有实现把它直接作为
            ``find_supported_regions`` 的第 4 个位置实参（形参是 ratio_thresh，
            无量纲比值），导致支撑过滤随 offset 的毫米值漂移。该耦合已解除，
            阈值固定使用 ``ratio_thresh`` 的默认值 0.6。
            若要让 offset 真正生效，应作用在
            ``get_offset_contour(r_t, offset)``（见 find_supported_regions 内注释），
            这会改变几何行为，需独立评估。

        Returns:
            numpy.ndarray: The generated global continuous path.
        """
        N = len(self.planes)
        z_list = self.layers_heights

        # Print sequence
        R = []  # R = {r_ij}
        S = []  # Sequence with [[i,j]......]
        pe = pathEngine()

        #获取每层的区域边界
        for i, plane in enumerate(self.planes):
            rs = self._get_region_boundaries_from_plane(plane, pe, True)
            R.append(rs)

        d = RDqueue(R)
        r, i, j = d.get_end()

        #构建无碰撞打印序列
        while d.size() != 0:
            if (i < N - 1) and (not self._is_interference_xyz(d, i, j, collision_dist_xy, collision_dist_z)):
                S.append([i, j])
                d.remove_item(i, j)
                i = i + 1
                # offset 的单位是 mm，而 find_supported_regions 的第 4 个形参是
                # ratio_thresh（无量纲比值，默认 0.6）。早前这里直接传 offset，
                # 使阈值随 offset 漂移：0.3→过宽松、0.8→漏判支撑、≥1→永不支撑。
                # 现改用形参默认值；offset 如何参与轮廓偏移是独立议题（见 TODO）。
                rs, js = self.find_supported_regions(d, r, i)

                if js == []:
                    r, i, j = d.get_end()
                    continue
                else:
                    j = js[0]
                    r = rs[0]
                    for idx in range(1, len(js)):
                        d.move_to_end(i, idx)

                if i == (N - 1):  # Reach the top
                    if not self._is_interference_xyz(d, i, j, collision_dist_xy, collision_dist_z):
                        S.append([i, j])
                        d.remove_item(i, j)
                    r, i, j = d.get_end()
            else:
                r_next, i_next, j_next = d.get_end()
                if [i, j] == [i_next, j_next]:  # The extruder goes back and the region is not be appended
                    S.append([i, j])
                    d.remove_item(i, j)
                    r_next, i_next, j_next = d.get_end()
                else:
                    if i <= i_next:  # The new region is not lower than current
                        S.append([i, j])  # So the nozzle doesn't need to go down
                        d.remove_item(i, j)
                r = r_next
                i = i_next
                j = j_next
        # Generate spiral and connect them# 生成最终三维路径坐标
        d = RDqueue(R)
        chunks = []
        region_slices = []
        cursor = 0
        z_list[-1] = z_list[-2] + self.params['layer_height'] if len(z_list) >= 2 else self.params.get('layer_height', 0.2)

        for i in range(len(S)):
            iLayer = S[i][0]
            r = d.get_item(iLayer, S[i][1])
#####5.19改
            filled_path = self.fill_region(r)
            if isinstance(filled_path, list):
                filled_path = np.array(filled_path)

            # 跳过空路径区域（避免 hstack/vstack 形状不匹配）
            if len(filled_path) == 0:
                continue

            cs = filled_path
            # cs = self.fill_region(r) * self.get_pixel_size()
#####
            z = [z_list[iLayer]] * len(cs)
            z = np.array(z).reshape([len(z), 1])

            # 拼接三维路径（按区域收集，同时记录每个区域在总路径里的起止索引）
            chunk = np.hstack([cs, z])
            region_slices.append((cursor, cursor + len(chunk)))
            chunks.append(chunk)
            cursor += len(chunk)

        # 区域边界是「区域间转移 = 空走」的唯一可靠信号：
        # suGCoder 只拿到 (N,3) 点集，没有区域 ID，若靠距离阈值猜，
        # 会被 simplify_path 抽稀出来的长直段误伤。把边界暴露给 build_gcode。
        self.region_slices = region_slices
        if not chunks:
            return np.empty((0, 3))
        return np.vstack(chunks)
 
    def _get_region_boundaries_from_plane(self, plane, pe, is_reverse=False):
        cs_region_list = []
        for polygon_group in plane:
            if not isinstance(polygon_group, list):
                polygon_group = [polygon_group]
            
            region = []
            for polygon in polygon_group:
                if isinstance(polygon, polygon3f):
                    # 提取多边形顶点坐标（仅XY）
                    coords = [[v.coord[X], v.coord[Y]] for v in polygon.vertices]
                    region.append(np.array(coords, dtype=np.float32))
                else:
                    # 处理其他可能的格式（如numpy数组）
                    region.append(np.array(polygon, dtype=np.float32))
            
            if region:
                cs_region_list.append(region)
        
        return cs_region_list
    def _is_interference_xyz(self, d, i, j, constraint_xy, constraint_z):
        """
        Check if there is interference between the current region and other regions, considering both XY and Z dimensions.

        Args:
            d (RDqueue): The queue of regions.
            i (int): The current layer index.
            j (int): The current region index.
            constraint_xy (float): Maximum allowed collision distance in the XY plane (in mm).
            constraint_z (float): Maximum allowed collision distance in the Z direction (in mm).

        Returns:
            bool: True if there is interference, False otherwise.
        """
        is_interfere = False
        r1 = d.get_item(i, j)
        rs, js = d.get_items(i)
        for idx in range(len(rs)):
            if js[idx] != j:
                pid_c1, pid_c2, min_dist = self._get_min_dist(r1, rs[idx])
                if min_dist <= constraint_xy:
                    r_bot, i_bot, j_bot = d.get_end()
                    z_dif = 0
                    for iLayer in range(i_bot, i):
                        z_dif += self.layers_heights[iLayer]
                    if z_dif <= constraint_z:
                        return True
        return False
    
    #####从Gcodeprocessor来
    def find_supported_regions(self, d, r, layer_id, ratio_thresh=0.6):
            """
            Identifies regions in the layer directly above a specified region ('r') that are supported by it,
            based on the intersection area between the two.

            Parameters:
            - d: An instance of RDqueue, containing regions organized by layer indices.
            - r: The specified region to consider.
            - layer_id: The layer index of the reference region 'r'.
            - ratio_thresh: The minimum ratio of intersection_area(r_bottom, r_top) / area(r_top) for the top region to be considered supported (default: 0.6).

            Returns:
            - rs: A list of regions in the layer directly above 'r' that are supported by 'r'.
            - js: The j-indices of the supported regions.

            Method:
            - For each region in the same layer as 'r', the function calculates the intersection area with 'r'.
            - A region in the layer above 'r' is considered supported if the ratio of the intersection area to its own area is above 'ratio_thresh'.
            - Supported regions are returned along with their indices.

            Note: Assumes functions for calculating intersection areas and region areas are defined elsewhere.
            """
            rs = []  # List to hold supported regions
            js = []  # List to hold j-indices of supported regions
            rem_group = []  # List to keep track of regions for potential removal

            for idx in range(len(d.di)):
                ii = d.di[idx]
                id_up_layer = layer_id + 1
                if ii == id_up_layer:  # Looking at regions in the layer directly above
                    jj = d.dj[idx]
                    r_t = d.d[idx]  # The region in the layer above to check for support

                    # Optional: Modify r_t based on 'offset', if applicable
                    # r_t = get_offset_contour(r_t, offset)  # Uncomment if offset contours are needed

                    inter_sec = intersect_area(r, r_t)  # Calculate the intersection area
                    if inter_sec is None:
                        rem_group.append([ii, jj])
                        continue

                    ratio = 0
                    if len(inter_sec) != 0:
                        inter_area = compute_region_area(inter_sec)
                        top_area = compute_region_area(r_t)
                        # 面积为 0 / 非有限值时无法证明该区域被支撑，一律按「不支撑」处理。
                        # 注意：轮廓是 np.ndarray 时 compute_region_area 返回 numpy 标量，
                        # 除法会得到 inf 而**不抛** ZeroDivisionError ——
                        # 只加 try/except 拦不住，必须显式判有限性。
                        if not np.isfinite(top_area) or abs(top_area) < 1e-9:
                            ratio = 0.0
                        else:
                            ratio = abs(float(inter_area) / float(top_area))
                            if not np.isfinite(ratio):
                                ratio = 0.0
                    else:
                        ratio = 0  # Corrected variable name from 'ration' to 'ratio'

                    if ratio > ratio_thresh:
                        rs.append(r_t)
                        js.append(jj)

            # Remove items marked during processing
            for idx in rem_group:
                d.remove_item(idx[0], idx[1])

            return rs, js
    #####
    def _get_min_dist(self, b1, b2):
        """
        Calculate the minimum distance between two contours.

        Args:
            b1 (list[numpy.ndarray]): The first contour, represented as a list of numpy.ndarray.
            b2 (list[numpy.ndarray]): The second contour, represented as a list of numpy.ndarray.

        Returns:
            tuple: (pid_c1, pid_c2, min_dist)
                pid_c1 (int): The index of the point in b1 that is closest to b2.
                pid_c2 (int): The index of the point in b2 that is closest to b1.
                min_dist (float): The minimum distance between the two contours.
        """

        def combine_contour(b):
            cs = []
            for idx in range(len(b)):
                if len(cs) == 0:
                    cs = b[idx]
                else:
                    cs = np.vstack((cs, b[idx]))
            return cs

        b1 = combine_contour(b1)
        b2 = combine_contour(b2)

        dist = scid.cdist(b1, b2, 'euclidean')
        min_dist = np.min(dist)
        gId = np.argmin(dist)
        pid_c1 = int(gId / dist.shape[1])
        pid_c2 = gId - dist.shape[1] * pid_c1

        return pid_c1, pid_c2, min_dist
