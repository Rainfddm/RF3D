# -*- coding: utf-8 -*-
#######################################################
# main controller classes
#  - from src.controller import *
#  - example:
#     - 
#     - 
#######################################################
import os
# 获取当前文件所在目录
    
from suFabUI.core.ui_main_window import *

from suFabUI.core.GcodePaser import *
from suFabEngine.MeshSlicer.slicer import *
from suFabEngine.FermatsSpiral.pathengine import *
from suFabEngine.Utils.common import *
from suFabEngine.Pipeline import *
from suFabEngine.pipeline_executor import PipelineExecutor
from suFabEngine.DataProcessor import *
from suFabEngine.FermatsSpiral.suPath2D import *
import pyqtgraph as pg
import pyqtgraph.opengl as gl
import numpy as np
import traceback
import vtk

import time
#import threading

class Controller(object):
    def __init__(self, main_window):
        '''
        init global setting
        '''
        self.main_window = main_window        
        #self.load_setting()        
        self.clear()
        # 算法唯一真相源：复用 PipelineExecutor，不再独立 new Pipeline
        self.executor = PipelineExecutor()
        self.pipeline = self.executor.pipeline  # 兼容桥（suView 旧引用）

    def clear(self):
        self.gcode_file = None   
        self.port = None
        self.cur_path_id = 0
        self.path = None              
        self.triangle_list = []
        self.planes = []

        ## vtk data
        self.vtk_poly_data = None

    def load_setting(self):        
        '''
        load global settings
        '''
        self.main_window.refresh()        
        return
       
    def message(self, msg=""):
        logging.info(msg)
        pass
    
    def load_path(self, file_name):
        logging.info("loading {} ...".format(file_name))
        pts = np.loadtxt(file_name)
        logging.info("building opengl object...".format(file_name))
        plt = gl.GLLinePlotItem(pos=pts, color=pg.glColor('r'), width= 1, antialias=True)
        
        self.main_window.mode_view.items = []
        self.main_window.mode_view.addItem(plt)      
        self.main_window.mode_view.setBackgroundColor(pg.mkColor('w'))        
        
        pass        
    #####新增
    def get_layer_path(self, layer_index):
        """获取指定层的原始路径数据"""
        # 假设路径存储在 self.cur_layer_infill 中
        if hasattr(self, 'cur_layer_infill') and layer_index < len(self.cur_layer_infill):
            return self.cur_layer_infill[layer_index]
        return []
    #####
    
    @unimplemented
    def save_config(self):        
        pass
        
    @unimplemented
    def extruder_init(self):
        pass
        
    def get_model_path(self, ps):
        '''
        Combine multiple path
        Remove start and end
        '''
        cp = []
        for p in ps:
            cp = cp + p
        
        cp = [x for x in cp if x != [0,0,0]]
        cp = np.array(cp).reshape([len(cp), 3])
        
        return cp
        
    def load_stl(self, stl_file):        
        # Load stl to display and hold triangle data
        # Check if we are in UI mode or backend mode
        if hasattr(self.main_window, 'view3d') and self.main_window.view3d is not None:
            # UI mode - use view3d to load STL
            self.vtk_poly_data = self.main_window.view3d.loadSTL(stl_file)
        else:
            # Backend mode - directly load STL using VTK
            reader = vtk.vtkSTLReader()
            reader.SetFileName(stl_file)
            reader.Update()
            self.vtk_poly_data = reader.GetOutput()
        
        # 只放「文件路径」这类 Pipeline 自己读的配置；数字型工艺参数必须由
        # ProcessDecisionEngine.default_params（唯一真相源）与 suView 的
        # _update_process_params 提供。此处曾额外塞 printSpeed / layer_height /
        # nozzle_diameter —— 其中 printSpeed 无任何消费方、nozzle_diameter 是
        # 后端不认的键名，三者都会随引擎默认值漂移，已删除。
        self.pipeline.load_params({
            'start_gcode': 'process/configs/start.gcode',
            'end_gcode': 'process/configs/end.gcode',})
        return self.vtk_poly_data
    def load_gcode(self, gcode_file):
        """
        # todo: Add path gcode and do some visulization
        # ref:  https://github.com/grbl/grbl/blob/master/grbl/gcode.c
        # ref:  http://jherrm.com/gcode-viewer/
        # ref:  https://github.com/jonathanwin/yagv/blob/master/gcodeParser.py        
        """
        cwd = os.getcwd()
        self.gcode_file = os.path.join(cwd, "process", "examples", gcode_file)
        logging.info("装入" + self.gcode_file )
        logging.info("开始预处理...")
        self.main_window.repaint()
        
        parser = GcodeParser()
        model = parser.parseFile(self.gcode_file)
        
        logging.info(model)
        
        ps = model.getPath()
        logging.info("生成路径..")
        self.path = self.get_model_path(ps)
        
        #cx,cy,cz = model.bbox.cx(),model.bbox.cy(), model.bbox.cz()
        maxp = np.max(self.path, 0)
        minp = np.min(self.path,0)
        
        cx, cy, cz = minp + (maxp - minp)/2
        dialog_len = np.linalg.norm(maxp-minp)
         
        self.main_window.mode_view.items = []
        self.main_window.mode_view.setBackgroundColor((255,255,255))
        self.main_window.mode_view.setCameraPosition([0,0,-dialog_len])
        #for p in ps:
        #    pts = np.array(p).reshape([len(p), 3]) - [cx,cy,cz]
        #    plt = gl.GLLinePlotItem(pos=pts, color=(1.0, 1.0, 1.0, 0.1), width= 1, antialias=True)
            
            #self.main_window.mode_view.addItem(plt)
        #self.main_window.mode_view.setBackgroundColor(pg.mkColor('c'))        
        self.path = self.path - [cx,cy,cz]
        pts = self.path
        maxp = np.max(pts, 0)
        #pts = ([0,0,maxp[2]] - pts) * [-1,-1,1]
        plt = gl.GLLinePlotItem(pos=pts, color=(0.7, 0.7, 0.7, 0.1), width= 3, antialias=True)
        self.main_window.mode_view.addItem(plt)
        
        self.main_window.pb_start.setEnabled(True)     
        
        self.cur_path_id = 0  # reset simulation id
        
    def export_path(self, filename):
        if self.path is None:
            return
        logging.info("开始导出" + filename)
        np.savetxt(filename, self.path, fmt='%.4f')
        
        return
    
    @unimplemented  
    def gen_gcode(self):  
        #1 for l in layer:     
        #       generate path
        #        for p in path:
        #            gnerate layer_gcode

        #        connect each layer gcode_path
        #        add init code 
                # add end code

        self.load_gcode('cfr_hand.gcode')
    
    def slicing(self, params, polygons, srt = True, callback=None):
        """
        Read mesh from view3d
        """
        if self.vtk_poly_data != None:            
            #triangle_list = Controller.convert_vtk_poly_data_to_triangles(self.vtk_poly_data, callback)
            self.pipeline.load_params(params)
            self.pipeline.load(polygons)
            callback(0, "Slicing..")
            self.pipeline.slice()
            self.planes = self.pipeline.get_planes()
            callback(0, "Converting..")
            poly_lines = Controller.convert_to_vtk_polyline(self.planes, callback)
           
            return poly_lines   
    
    def fill_layer(self, params, iLayer, call_back=None):   
        self.clear() 
        self.cur_layer_infill = self.pipeline.fill_layer(iLayer)
        cur_layer_polylines = []

        for s in self.cur_layer_infill:
            logging.info(self.pipeline.layers_heights[iLayer])
            contour_poly_data = Controller.contours_to_vtkPolyData(s, self.pipeline.layers_heights[iLayer], callback=call_back)
            cur_layer_polylines.append(contour_poly_data)

        return cur_layer_polylines                  
    
    @unimplemented
    def gen_path(self):
        pass    

    # Data conversion
    @staticmethod
    def convert_vtk_poly_data_to_triangles(vtk_poly_data, callback=None):
        points = vtk_poly_data.GetPoints()
        triangle_list = []
        # for progress
        total_triangles = vtk_poly_data.GetNumberOfCells()

        for i in range(vtk_poly_data.GetNumberOfCells()):
            cell = vtk_poly_data.GetCell(i)
            if cell.GetCellType() == vtk.VTK_TRIANGLE:
                ids = [cell.GetPointId(j) for j in range(3)]
                vertices = [points.GetPoint(id) for id in ids]
                # Assuming you have a method to calculate normal or get it from vtkPolyData
                normal = Controller.calculate_normal(vertices)
                triangle = stltriangle(np.array(vertices[0]), 
                                       np.array(vertices[1]), 
                                       np.array(vertices[2]), 
                                       np.array(normal))
                triangle_list.append(triangle)

            # Update progress  
            if callback:
                progress = (i + 1) / total_triangles * 100
                callback(progress, "Vtk data")
        return triangle_list
    
    @staticmethod
    def calculate_normal(vertices):
        # Convert vertices to numpy arrays if they are not already
        v0, v1, v2 = [np.array(vertex) for vertex in vertices]

        # Compute two edge vectors: v1 - v0 and v2 - v0
        edge1 = v1 - v0
        edge2 = v2 - v0

        # Compute the cross product of the two edge vectors to get the normal
        normal = np.cross(edge1, edge2)

        # Normalize the normal vector to ensure it is a unit vector
        normal = normal / np.linalg.norm(normal)

        return normal
    
    @staticmethod
    def convert_to_vtk_polyline(Planes, callback=None):
        """
        Convert a list of polygon3f objects to a VTK PolyData object.
        Each polygon3f is a list of vertex3f objects.
        """
        points = vtk.vtkPoints()
        lines = vtk.vtkCellArray()
        total_planes = len(Planes)
        point_index = 0
        for j, P in enumerate(Planes):
            for polygon in P:
                line = vtk.vtkPolyLine()
                line.GetPointIds().SetNumberOfIds(len(polygon.vertices))

                for i, vertex in enumerate(polygon.vertices):
                    points.InsertNextPoint(vertex.coord[0], vertex.coord[1], vertex.coord[2])
                    line.GetPointIds().SetId(i, point_index)
                    point_index += 1

                lines.InsertNextCell(line)
                # Update progress  
                if callback:
                    progress = (j + 1) / total_planes * 100
                    callback(progress, "Rendering...")

        polyline = vtk.vtkPolyData()
        polyline.SetPoints(points)
        polyline.SetLines(lines)
        return polyline
    
    @staticmethod
    def contours_to_vtkPolyData(contour, z, callback= None):
        # @z is z coordinate of 2d vertice in contour
        # @contours2d is returned from pathEngine, it is an iso contour list, 
        # each is represented as c[i,j]
        points = vtk.vtkPoints()
        lines = vtk.vtkCellArray()   

        # for show progress
        algo_name = inspect.currentframe().f_code.co_name
        total_points = len(contour)
        point_index = 0
        for point in contour:
            points.InsertNextPoint(point[0], point[1], z)  # Add point
            if len(contour) > 1:
                line = vtk.vtkLine()
                line.GetPointIds().SetId(0, point_index)
                line.GetPointIds().SetId(1, (point_index + 1) % len(contour))
                lines.InsertNextCell(line)
            point_index += 1
            
            # Update progress  
            if callback:
                progress = point_index / total_points * 100
                callback(progress, algo_name)

        polyData = vtk.vtkPolyData()
        polyData.SetPoints(points)
        polyData.SetLines(lines)

        return polyData