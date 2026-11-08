import numpy as np
import vtk
#####
import os
# 获取当前文件所在目录
from suFabEngine.MeshSlicer.slicer import *
import logging
from serial.tools.list_ports import comports as list_serial_ports
#####

def resample_path(path):       #####对输入路径进行重采样，目的是去除路径中的共线点。
    vert_start = path[0]
    
    new_path = [vert_start]
    vert_midle = path[1]
    for i in range(2, len(path)):
        vert_end = path[i]
            
        v1 = vert_start - vert_midle
        v2 = vert_end - vert_midle
        v1v2 = (np.linalg.norm(v1)*np.linalg.norm(v2))
        if v1v2 == 0:
            continue
        angle = np.dot(v1,v2)/v1v2

        #is on a line?
        if abs(angle-1) > 0.000001 and abs(angle + 1) > 0.000001:
            new_path.append(vert_midle)
            vert_start = vert_midle
            vert_midle = vert_end
        else:
            vert_midle=vert_end

    new_path.append(path[-1])

    return np.array(new_path)

def create_vtk_polyline(Planes):           #####将输入的平面对象转换为 VTK PolyData 对象。

    """
    Convert a list of plane objects to a VTK PolyData object.
    Each P(plain) is a list of vertex3f objects.
    """
    points = vtk.vtkPoints()
    lines = vtk.vtkCellArray()

    point_index = 0
    for P in Planes:
        for polygon in P:
            line = vtk.vtkPolyLine()
            line.GetPointIds().SetNumberOfIds(len(polygon.vertices))

            for i, vertex in enumerate(polygon.vertices):
                points.InsertNextPoint(vertex.coord[0], vertex.coord[1], vertex.coord[2])
                line.GetPointIds().SetId(i, point_index)
                point_index += 1

            lines.InsertNextCell(line)

    polyline = vtk.vtkPolyData()
    polyline.SetPoints(points)
    polyline.SetLines(lines)
    return polyline

if __name__ == '__main__':    
    cwd = os.getcwd()
    print('current dir is ' + cwd)
    new_path = os.path.join(cwd, "nw")
    print('new dir is ' + new_path)
    
    logging.basicConfig(level=logging.INFO)
    logging.info(list_serial_ports())
    
    curve = np.loadtxt("r:/curvespiral.txt")
    print(curve.shape)
    c = resample_path(curve) 
    np.savetxt("r:/curvespiral-resample.txt", c, fmt='%.4f')
    print(c)
    
