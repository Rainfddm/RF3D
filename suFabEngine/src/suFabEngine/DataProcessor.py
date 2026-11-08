## Convert data between vtk and different engines.
# 1. convert_to_triangles: vtk to triangle list
# 2. group_contours: planes to group of contours, each contour is a n*2 numpy array 
import inspect
import numpy as np
import vtk
# 获取当前文件所在目录

from suFabEngine.FermatsSpiral.pathengine import *
from suFabEngine.MeshSlicer.slicer import *

# Function to convert 2d iso_contours to vtkPolyData to display
def contours_to_vtkPolyData(contour, z=0, callback= None):
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
            if(progress % 10) == 0:
                callback(progress, algo_name)

    polyData = vtk.vtkPolyData()
    polyData.SetPoints(points)
    polyData.SetLines(lines)

    return polyData


def convert_to_triangles(vtk_poly_data, callback=None):
    # convert vtk to trianles
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
            normal = calculate_normal(vertices)
            triangle = stltriangle(np.array(vertices[0]), 
                                    np.array(vertices[1]), 
                                    np.array(vertices[2]), 
                                    np.array(normal))
            triangle_list.append(triangle)

        # Update progress  
        if callback:
            current_frame = inspect.currentframe()
            function_name = current_frame.f_code.co_name 
            progress = (i + 1) / total_triangles * 100
            callback(progress, function_name)

    return triangle_list

# to be deprecated: Based on test, no speed up.
def convert_to_triangles_optimized(vtk_poly_data, callback=None):
    # Get cell data
    cells = vtk_poly_data.GetPolys()
    n_cells = cells.GetNumberOfCells()

    # Get point data
    points = vtk_poly_data.GetPoints()
    n_points = points.GetNumberOfPoints()

    # Create arrays to store data
    triangle_list = []

    # Iterate through cells
    cell_array = cells.GetData()
    points_array = points.GetData()

    idx = 0
    while idx < cell_array.GetNumberOfTuples():
        n_points_in_cell = cell_array.GetValue(idx)
        if n_points_in_cell == 3:  # It's a triangle
            p1 = np.array(points_array.GetTuple3(cell_array.GetValue(idx + 1)))
            p2 = np.array(points_array.GetTuple3(cell_array.GetValue(idx + 2)))
            p3 = np.array(points_array.GetTuple3(cell_array.GetValue(idx + 3)))

            # Calculate normal
            v1 = p2 - p1
            v2 = p3 - p1
            normal = np.cross(v1, v2)
            normal = normal / np.linalg.norm(normal)

            # Create triangle
            triangle = stltriangle(p1, p2, p3, normal)
            triangle_list.append(triangle)

        idx += n_points_in_cell + 1

    return triangle_list

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

# Data conversion for vtk
class STLProcessor:
    def __init__(self):        
        self.triangle_list = []
        self.filename = ""

    def read_stl(self, filename):
        # Get the current directory
        reader = vtk.vtkSTLReader()
        reader.SetFileName(filename)
        reader.Update()
        return reader.GetOutput()

    def convert_to_triangles(self, callback=None):
        vtk_poly_data = self.vtk_poly_data
        points = vtk_poly_data.GetPoints()
        triangle_list = []
        # for progress
        algo_name = self.__class__.__name__
        total_triangles = vtk_poly_data.GetNumberOfCells()

        for i in range(vtk_poly_data.GetNumberOfCells()):
            cell = vtk_poly_data.GetCell(i)
            if cell.GetCellType() == vtk.VTK_TRIANGLE:
                ids = [cell.GetPointId(j) for j in range(3)]
                vertices = [points.GetPoint(id) for id in ids]
                # Assuming you have a method to calculate normal or get it from vtkPolyData
                normal = self.calculate_normal(vertices)
                triangle = stltriangle(np.array(vertices[0]), 
                                       np.array(vertices[1]), 
                                       np.array(vertices[2]), 
                                       np.array(normal))
                triangle_list.append(triangle)

            # Update progress  
            if callback:
                progress = (i + 1) / total_triangles * 100
                callback(progress, algo_name)
        return triangle_list

    def translate_to_center(self, new_center):
        # Calculate the current geometric center of the model
        center = np.mean([vertex for triangle in self.triangle_list for vertex in triangle['vertices']], axis=0)

        # Calculate the translation vector to the new center
        translation_vector = np.array(new_center) - center

        # Apply translation to each vertex in every triangle
        for triangle in self.triangle_list:
            triangle['vertices'] = [np.array(vertex) + translation_vector for vertex in triangle['vertices']]
def group_contours(plane):
    # Convert contours in a plane into groups of contour that can be used
    # to define regions. We can use pathEngine to generate path
    # @plane is returned from the element of MinettoSlicer.slicer.planes

    # Identify outer and inner contours
    outer_contours = []
    inner_contours = []
    for contour in plane:

        if contour.orientation() == COUNTERCLOCKWISE:
            outer_contours.append(contour)
        else:
            inner_contours.append(contour)

    # Grouping contours
    groups = []
    for outer in outer_contours:
        group = []
        # Convert outer contour vertices to numpy array and add to group
        outer_np = np.array([[vertex.coord[0], vertex.coord[1]] for vertex in outer.vertices], dtype='float32')
        group.append(outer_np)

        for inner in inner_contours:
            if outer.is_inside(inner.vertices[0]) == INSIDE_POLYGON:
                # Convert inner contour vertices to numpy array and add to group
                inner_np = np.array([[vertex.coord[0], vertex.coord[1]] for vertex in inner.vertices], dtype='float32')
                group.append(inner_np)

        groups.append(group)

    return groups

