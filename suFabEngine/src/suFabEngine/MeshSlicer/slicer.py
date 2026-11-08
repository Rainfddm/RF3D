## @file Slicer of mesh of triangles.
#
# Implements the algorithms from:
#
#  [1] Rodrigo Minetto, Neri Volpato, Jorge Stolfi, Rodrigo M.M.H. Gregori, Murilo
#  V.G. da Silva. An optimal algorithm for 3D triangle mesh slicing,
#  Computer-Aided Design, Volume 92, 2017.
# 
#  Modified by Yao to read stl data from vtk
#  1. Use COUNTERCLOCKWISE for out contour
#  2  Use CLOCKWISE for inner contour
#  3. Use Ray tracing to determine point inside polygon

import math
import numpy as np


## Constant for X position.
X = 0
## Constant for Y position.
Y = 1
## Constant for Z position.
Z = 2

## Constant for polygon orientatio.
CLOCKWISE        = -1
## Constant for polygon orientatio.
COUNTERCLOCKWISE =  1

## Constant for point in polygon test.
INSIDE_POLYGON  = 1
## Constant for point in polygon test.
OUTSIDE_POLYGON = 0


## 3D vertex.
#
# A vertex of three coordinates (x,y,z).
class vertex3f:
    
    ## Constructor.
    #
    # Create an object with a vector of coordinates (x,y,z).
    #
    # @param x The x coordinate.
    # @param y The y coordinate.
    # @param z The z coordinate.
    def __init__(self, x, y, z):
        ## Array of coordinates.
        self.coord = np.array([x, y, z], dtype='float32')

    ## Subtract.
    #
    # Return vector from subtracting two vertices.
    #
    # @param Subtract vertices.
    def __sub__(self, v):

        # Subtract coordinates.
        coord = self.coord - v.coord

        return vertex3f(coord[X], coord[Y], coord[Z])
    
    ## Normalize.
    #
    # Normalize a vector.
    def normalize(self):
        self.coord = self.coord/np.linalg.norm(self.coord)

        
## 3D polygon.
#
# A polygon represented as a sequence of vertices.
class polygon3f:
    
    ## Constructor.
    #
    # Create an object with an empty polygon.
    def __init__(self):
        ## List of vertices.
        self.vertices = []

    ## Signed area.
    #
    # Return the signed area \f$ A \f$ of the polygon: \f$ A < 0 \f$ if
    # clockwise oriented polygon or \f$ A > 0 \f$ if counterclockwise oriented polygon.
    def signed_area(self):

        # Fix first vertex as anchor vertex.
        v = self.vertices[0]

        # Compute the area of all triangles fixed with v.
        A = 0
        for i in range(1,len(self.vertices)-1):
            A += triangle_signed_area(v, self.vertices[i], self.vertices[i+1])

        return A


    ## Orientation.
    #
    # Return the orientation (CLOCKWISE or COUNTERCLOCKWISE) of the polygon.
    def orientation(self):
        
        return COUNTERCLOCKWISE if self.signed_area() > 0.0 else CLOCKWISE
    
    ## Invert orientation.
    #
    # Invert the vertex sequence of the polygon.
    def invert_orientation(self):

        self.vertices = np.flip(self.vertices)

    
    ## Point in polygon.
    #
    # Check whether point p lies inside or outside the polygon.
    # @param p Point.
    # @return INSIDE_POLYGON or OUTSIDE_POLYGONS constants.
    def is_inside(self, p):
        
        winding_number = 0
        for i in range(0,len(self.vertices)):

            winding_number += vectors_angle(p, self.vertices[i], self.vertices[(i+1)%len(self.vertices)])

        return (INSIDE_POLYGON if np.fabs(winding_number-2.0*np.pi) < np.fabs(winding_number) else OUTSIDE_POLYGON)
    
    ## Point in polygon with Ray Cast
    #
    # is_inside is using Windnum, affected by the clockwise order
    # @param p Point.
    # @return INSIDE_POLYGON or OUTSIDE_POLYGONS constants.
    def is_point_inside_polygon(self, p):
        count = 0
        x, y = p.coord[0], p.coord[1]

        for i in range(len(self.vertices)):
            x1, y1 = self.vertices[i].coord[0], self.vertices[i].coord[1] 
            v      = self.vertices[(i + 1) % len(self.vertices)]
            x2, y2 = v.coord[0], v.coord[1]

            # Check if the edge intersects with the ray
            if y > min(y1, y2) and y <= max(y1, y2) and x <= max(x1, x2):
                if y1 != y2:
                    xinters = (y - y1) * (x2 - x1) / (y2 - y1) + x1
                if x1 == x2 or x <= xinters:
                    count += 1

        return (INSIDE_POLYGON if count % 2 != 0 else OUTSIDE_POLYGON)

## 3D line segment.
#
# A line segment defined by two vertices. 
class segment3f:
    
    ## Constructor.
    #
    # Create an object with a vector of coordinates (x,y,z).
    def __init__(self, x, y, z):
        ## Array of coordinates.
        self.coord = np.array([x, y, z], dtype='float32')

## Triangle signed area.
#
# Return the signed area of a triangle.
# @param v0 First vertex of the triangle.
# @param v1 Second vertex of the triangle.
# @param v2 Third vertex of the triangle.
# @return Signed area.
def triangle_signed_area(v0, v1, v2):

    x0 = v0.coord[X]
    y0 = v0.coord[Y]
    x1 = v1.coord[X]
    y1 = v1.coord[Y]
    x2 = v2.coord[X]
    y2 = v2.coord[Y]

    return (((x1-x0)*(y2-y0)-(x2-x0)*(y1-y0))/2.0)


## Angle between vertices.
#
# Return the angle of v1ov2.
# @param o Firts vertex (at vertex).
# @param v1 Second vertex of the triangle.
# @param v2 Third vertex of the triangle.
# @return Angle.
def vectors_angle(o, v1, v2):

    # Vectors with o.
    u = v1-o
    w = v2-o

    # Normalize vectors.
    u.normalize()
    w.normalize()

    # Return angle.
    cos_theta = np.minimum(np.dot(u.coord,w.coord),1.0) 
    cos_theta = np.maximum(cos_theta,-1.0) 
    return (np.arccos(cos_theta) if triangle_signed_area(o, v1, v2) >= 0.0 else -np.arccos(cos_theta))


## Triangle class for STL.
#
#  Class for a triangle.
class stltriangle:
    
    ## Constructor.
    # @param v0 First vertex.
    # @param v1 Second vertex.
    # @param v2 Third vertex.
    # @param normal Normal vector.
    def __init__(self, v0, v1, v2, normal):

        ## First vertex of the triangle.
        self.v0     = v0
        ## Second vertex of the triangle.
        self.v1     = v1
        ## Third vertex of the triangle.
        self.v2     = v2
        ## Normal of the triangle.
        self.normal = normal

    ## Minimum z coordinate.
    #
    # Return minimum z coordinate.
    #
    # @return Minimum z.
    def min_z(self):

        min_coordinate = self.v0[2]

        if min_coordinate > self.v1[2]:
            min_coordinate = self.v1[2]
        if min_coordinate > self.v2[2]:
            min_coordinate = self.v2[2]

        return min_coordinate
    
    ## Maximum z coordinate.
    #
    # Return maximum z coordinate.
    #
    # @return Maximum z.
    def max_z(self):

        max_coordinate = self.v0[2]

        if max_coordinate < self.v1[2]:
            max_coordinate = self.v1[2]
        if max_coordinate < self.v2[2]:
            max_coordinate = self.v2[2]

        return max_coordinate


## Slicer class.
#
#  Class for slicing a mesh of triangles.
class slicer:
    
    # Constructor.
    # @param vtk_poly_data .
    # @param delta Offset between planes for slices (regular slicing). 
    # @param first_layer_delta First layer thickness, if 0, use uniformed slicer
    # @param srt True if planes are sorted, False otherwise.
    # @return List of planes/slices with polygons.
    def __init__(self, triangle_list, delta=0.2, first_layer_delta=0, srt=True):
        # Final planes. Each element is a single plane: consist of a list of polygon3f
        self.planes = []
        # Segments. A list, each element corresponds to a particular slicing plane that
        #                   include a list of segment(v_start, v_end)
        self.segments = []
        # Mesh triangles.
        self.T = triangle_list
        # Slicing planes.
        self.P = []
        # delta
        self.delta = delta
        self.first_layer_delta = first_layer_delta
        # Sorted.
        self.srt = srt
        # Rounding eps.
        self.eps = 0.0004

        # Round coordinates of triangles to even multiples of eps.
        self.roundTrianglesEven()
        
        # Round delta to even multiple of eps.
        self.delta = self.mround(self.delta, self.eps, 2, 0)

        # Create planes.
        if first_layer_delta == 0:
            # Create uniform planes to odd multiples of eps.
            self.uniformPlanes()
        if first_layer_delta > 0:
            self.uniformPlanes_with_specified_first_layer()
        


    # Incremental slicing
    #
    # Algorithm 1 in [1].
    def incremental_slicing(self, callback=None):

        # Split triangle list.
        L = self.build_triangle_list()

        # Plane sweeping
        A = []

        # For progress
        total_planes = len(self.P)
        for i in range(len(self.P)):

            self.segments.append([])
            A.extend(L[i])

            t = 0
            while t < len(A):
                if self.T[A[t]].max_z() < self.P[i]:
                    A.pop(t)
                else:
                    I = self.compute_intersection(self.T[A[t]],self.P[i])
                    if I[0] != None and I[1] != None:
                        self.segments[i].append(I)
                    t += 1
        # Update progress
        if callback:
            progress = (i + 1) / total_planes * 100
            callback(progress, "Slicing..")

        # Buil oriented polygons from segments.
        self.contour_construction()    


    ## List of triangles.
    #
    # Build list of triangles for each plane. Algorithm 2 in [1].
    #
    # @todo Implement pre-sorted part of algorithm.
    def build_triangle_list(self):
    
        L = []
        for i in range(len(self.P)+1):
            L.append([])

        # Uniform slicing.
        if self.delta > 0.0:
            for t in range(len(self.T)):
                if self.T[t].min_z() < self.P[0]: i = 0
                elif self.T[t].min_z() > self.P[-1]: i = len(self.P)
                else: i = math.floor((self.T[t].min_z()-self.P[0])/self.delta)+1
                L[i].append(t)
        # Pre-sorted triangles.
        #elif self.srt:
        # General case.
        else:
            for t in range(len(self.T)):
                i = self.binary_search(t)
                L[i].append(t)

        return L

    ## Binary seach
    #
    # Search for the plane of a triangle.
    def binary_search(self, t):

        min_z = self.T[t].min_z()

        if min_z > self.P[len(self.P)-1]:
            return len(self.P)
        
        if min_z < self.P[0]:
            return 0

        l = 0
        r = len(self.P)-1
        while r-l > 1:
            m = math.floor((l+r)/2.0)
        
            if min_z > self.P[m]:
                l = m
            else:
                r = m

        return r

    ## Compute intersection.
    #
    # Compute the segment intersection of a triangle and a plane.
    #
    # @param t Triangle.
    # @param p Plane.
    # @return endpoints of the intersection segment.
    def compute_intersection(self,t,p):
       
        intersection = [None,None]
        n = 0 # Index intersection positions to copy vertices.
        
        # First edge v0-v1.
        v = t.v1-t.v0
        if math.fabs(v[2]) > 0.0:
            alpha = (p-t.v0[2])/v[2]
            if alpha >= 0.0 and alpha <= 1.0:
                intersection[n] = vertex3f(t.v0[0]+alpha*v[0], t.v0[1]+alpha*v[1], p)
                n += 1
         
        # Second edge v0-v2.
        v = t.v2-t.v0
        if math.fabs(v[2]) > 0.0:
            alpha = (p-t.v0[2])/v[2]
            if alpha >= 0.0 and alpha <= 1.0:
                intersection[n] = vertex3f(t.v0[0]+alpha*v[0], t.v0[1]+alpha*v[1], p)
                n += 1

        # Third edge v1-v2.
        v = t.v2-t.v1
        if math.fabs(v[2]) > 0.0:
            alpha = (p-t.v1[2])/v[2]
            if alpha >= 0.0 and alpha <= 1.0:
                intersection[n] = vertex3f(t.v1[0]+alpha*v[0], t.v1[1]+alpha*v[1], p)
                n += 1
                
        return intersection


    ## Create contours.
    #
    # Set oriented group of segments to form a polygon.
    def contour_construction(self):

        # Iterate planes.
        for i in range(len(self.segments)):

            # New plane to fill with polygons.
            self.planes.append([])
        
            # Round x and y coordinates (z is already rounded).
            #eps = 1.0/128.0
            for seg in self.segments[i]:
            #    seg[0].coord[0:2] = np.round(seg[0].coord[0:2]/eps)*eps
            #    seg[1].coord[0:2] = np.round(seg[1].coord[0:2]/eps)*eps
                seg[0].coord[0:2] = self.mround(seg[0].coord[0:2], self.eps, 2, 1)
                seg[1].coord[0:2] = self.mround(seg[1].coord[0:2], self.eps, 2, 1)

            # Fill hash table (dictionary).
            H = {}
            for seg in self.segments[i]:
                if np.linalg.norm(seg[0].coord-seg[1].coord) > 0.0001:
                    if seg[0].coord.tobytes() in H:
                        H[seg[0].coord.tobytes()].append(seg[1])
                    else:
                        H[seg[0].coord.tobytes()] = [seg[0]] # save for future reference as current vertex
                        H[seg[0].coord.tobytes()].append(seg[1])
                    if seg[1].coord.tobytes() in H:
                        H[seg[1].coord.tobytes()].append(seg[0])
                    else:
                        H[seg[1].coord.tobytes()] = [seg[1]] # save for future reference as current vertex
                        H[seg[1].coord.tobytes()].append(seg[0])

            while len(H) > 0:
                # Init polygon.
                polygon = polygon3f()

                # Choose first returned key.
                u_key    = list(H.keys())[0]
                u_vertex = H[u_key][0]

                # Set final and next (v) keys and vertices.
                entry = H[u_key]
                if len(entry) < 3:
                    # 悬空边/开放边，无法形成闭环轮廓，跳过
                    H.pop(u_key)
                    continue
                final_key    = entry[2].coord.tobytes() 
                final_vertex = entry[2] 
                v_key        = entry[1].coord.tobytes()
                v_vertex     = entry[1] 

                # Not needed anymore.
                H.pop(u_key)

                # Insert vertex to polygon.
                polygon.vertices.append(u_vertex)

                while u_key != final_key:
                    
                    # Get next.
                    last_key    = u_key
                    last_vertex = u_vertex

                    u_key    = v_key
                    u_vertex = H[u_key][0]

                    v_key   = H[u_key][1].coord.tobytes()
                    if v_key != last_key:
                        v_vertex = H[u_key][1] 
                    else:
                        v_key    = H[u_key][2].coord.tobytes()
                        v_vertex = H[u_key][2] 
                        
                    H.pop(u_key)
                
                    # Insert vertex to polygon.
                    polygon.vertices.append(u_vertex)

                # Insert polygon to plane.
                self.planes[i].append(polygon)

        # Compute proper orientation for polygons.
        for plane in self.planes:
            for p1 in range(len(plane)):
                orientation = COUNTERCLOCKWISE
                for p2 in range(len(plane)):
                    if p1 != p2:
                        # Here change is_inside to is_point_inside_polygon
                        if plane[p2].is_point_inside_polygon(plane[p1].vertices[0]):
                            orientation = CLOCKWISE
                
                if orientation != plane[p1].orientation():
                    plane[p1].invert_orientation()


    ## OpenGL data for planes.
    #
    # Create data array to draw planes in OpenGL.
    def OpenGLPlanesData(self,mmin,mmax,bmin,bmax):
        
        # Normalize planes.
        planes = (self.P-mmin)/(mmax-mmin)*(bmax-bmin)+bmin

        step = 2
        # Lines * columns * 2 triangles * planes 
        ntriangles = (2.0/step)*(2.0/step)*2.0*len(planes)
        nvertices  = int(ntriangles*3.0)
        # Data elements = nvertices*(3 coordinates + 3 normal coordinates)
        data = np.zeros(nvertices*6, dtype='float32')

        l = 0
        for p in planes:
            for j in range(-1,1,step):
                for k in range(-1,1,step):
                    data[l:l+6] = [j, k, p, 0, 1, 0]
                    l += 6
                    data[l:l+6] = [j, k+step, p, 0, 1, 0]
                    l += 6
                    data[l:l+6] = [j+step, k, p, 0, 1, 0]
                    l += 6
                    data[l:l+6] = [j, k+step, p, 0, 1, 0]
                    l += 6
                    data[l:l+6] = [j+step, k+step, p, 0, 1, 0]
                    l += 6
                    data[l:l+6] = [j+step, k, p, 0, 1, 0]
                    l += 6

        return data,nvertices

    ## OpenGL data for polygons.
    #
    # Create data array to draw polygons in OpenGL.
    def OpenGLPolygonsData(self,mmin,mmax,bmin,bmax):

        # Number of segments
        nsegments = 0
        for plane in self.planes:
            for polygon in plane:
                nsegments += 2*len(polygon.vertices)
       
        # Number of vertices
        nvertices = nsegments*2
        
        # Create data array of size nsegments*2 vertices*(3 coordinates + 3 colors)
        data = np.zeros(nsegments*2*6, dtype='float32')

        # Copy segments to data array.
        j = 0
        for plane in self.planes:
            for polygon in plane:

                if polygon.orientation() == COUNTERCLOCKWISE:
                    color = np.array([0.0, 1.0, 0.0], dtype='float32')
                else:
                    color = np.array([0.0, 0.0, 1.0], dtype='float32')

                for v in range(len(polygon.vertices)):
                    data[j:j+3] = (polygon.vertices[v].coord-mmin)/(mmax-mmin)*(bmax-bmin)+bmin
                    j += 3
                    data[j:j+3] = color
                    j += 3
                    data[j:j+3] = (polygon.vertices[(v+1)%len(polygon.vertices)].coord-mmin)/(mmax-mmin)*(bmax-bmin)+bmin
                    j += 3
                    data[j:j+3] = color
                    j += 3

        return data,nvertices

       
    ## OpenGL data.
    #
    # Create data array to draw segments in OpenGL.
    def OpenGLData(self,mmin,mmax,bmin,bmax):
       
        # Number of segments
        nsegments = 0
        for l in self.segments:
            nsegments += len(l)

        # Number of vertices
        nvertices = nsegments*2
        
        # Create data array of size nsegments*2 vertices*3coordinates
        data = np.zeros(nsegments*2*3, dtype='float32')

        # Copy segments to data array.
        j = 0
        for l in self.segments:
            for s in l:
                data[j:j+3] = (s[0:3]-mmin)/(mmax-mmin)*(bmax-bmin)+bmin
                j += 3
                data[j:j+3] = (s[3:6]-mmin)/(mmax-mmin)*(bmax-bmin)+bmin
                j += 3

        return data,nvertices

    ## Round
    #
    #
    def mround(self, v, eps, mod, rem):
        y = np.round(v/(mod*eps))
        z = (y*mod+rem)*eps;
        return z

    ## Round coordinates of triangles.
    #
    # round the coordinates of triangles to even multiples of eps.
    def roundTrianglesEven(self):
        
        for t in self.T:
            t.v0 = self.mround(t.v0, self.eps, 2, 0)
            t.v1 = self.mround(t.v1, self.eps, 2, 0)
            t.v2 = self.mround(t.v2, self.eps, 2, 0)
            
            
    ## Return a vector of minimum values for coordinates in the mesh.
    def min_coordinates(self):
        
        Mval = np.ones(3, dtype='float32')*np.finfo(np.float32).max
        for t in self.T: 
            Mval = np.minimum(Mval,t.v0)
            Mval = np.minimum(Mval,t.v1)
            Mval = np.minimum(Mval,t.v2)

        return Mval
    
    ## Return a vector of maximum values for coordinates in the mesh.
    def max_coordinates(self):
        
        Mval = np.ones(3, dtype='float32')*np.finfo(np.float32).min
        for t in self.T: 
            Mval = np.maximum(Mval,t.v0)
            Mval = np.maximum(Mval,t.v1)
            Mval = np.maximum(Mval,t.v2)

        return Mval

    ## Create uniform planes.
    #
    # Create planes at odd multiples of delta.
    def uniformPlanes(self):

        z_min = self.min_coordinates()[2]
        z_max = self.max_coordinates()[2]
        
        # First plane.
        P0 = self.mround(z_min - self.delta, self.eps, 2, 1)

        # Compute planes.
        self.P = []
        i = 1
        Pi = P0 + i * self.delta
        while Pi < z_max:
            if Pi > z_min:
                self.P.append(Pi)
            i += 1
            Pi = P0 + i * self.delta
    
    # Create planes with specified first layer height and delta.
    def uniformPlanes_with_specified_first_layer(self):

        z_min = self.min_coordinates()[2]
        z_max = self.max_coordinates()[2]
        
        # First plane.
        P0 = self.mround(z_min + self.first_layer_delta, self.eps, 2, 1)

        # Compute planes.
        self.P = [P0]
        i = 1
        Pi = P0 + i * self.delta
        while Pi < z_max:
            if Pi > z_min:
                self.P.append(Pi)
            i += 1
            Pi = P0 + i * self.delta

    @staticmethod
    def group_contours(plane):
        # Convert contours in a plane into groups of contour that can be used
        # to define regions. We can use pathEngine to generate path
        # @plane is returned from the elment of MinettoSlicer.slicer.planes

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


if __name__ == '__main__':
    import os
    import vtk

    def progress_callback(value, algo_name="进度：", bar_length=40):
        """
        Display a text-based progress bar.
        
        :param progress: Current progress as a percentage.
        :param bar_length: Length of the progress bar in characters.
        """
        filled_length = int(round(bar_length * value / 100))
        bar = '#' * filled_length + '-' * (bar_length - filled_length)
        
        # \r is used to move the cursor back to the start of the line
        print(f'\r {algo_name}: |{bar}| {value:.2f}%', end='')

        # Print a new line when progress is complete
        if value == 100:
            print()

    def convert_to_vtk_polyline(Planes, callback=None):
        """
        Convert a list of polygon3f objects to a VTK PolyData object.
        Each polygon3f is a list of vertex3f objects.
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
                normal = calculate_normal(vertices)
                triangle = stltriangle(np.array(vertices[0]), 
                                       np.array(vertices[1]), 
                                       np.array(vertices[2]), 
                                       np.array(normal))
                triangle_list.append(triangle)

            # Update progress  
            if callback:
                progress = (i + 1) / total_triangles * 100
                callback(progress, "Vtk conversion:")
        return triangle_list
    
    # Optimized version
    def convert_vtk_poly_data_to_triangles_ver1(vtk_poly_data, callback=None):
        points = vtk_poly_data.GetPoints()
        normals = vtk_poly_data.GetPointData().GetNormals()
        triangle_list = []
        total_triangles = vtk_poly_data.GetNumberOfCells()

        for i in range(total_triangles):
            cell = vtk_poly_data.GetCell(i)
            if cell.GetCellType() == vtk.VTK_TRIANGLE:
                ids = [cell.GetPointId(j) for j in range(3)]
                vertices = [points.GetPoint(id) for id in ids]

                if normals is not None:
                    # Use existing normal if available
                    normal = np.mean([normals.GetTuple(id) for id in ids], axis=0)
                else:
                    # Calculate normal otherwise
                    normal = calculate_normal(vertices)

                triangle = stltriangle(np.array(vertices[0]), 
                                    np.array(vertices[1]), 
                                    np.array(vertices[2]), 
                                    np.array(normal))
                triangle_list.append(triangle)

            # Update progress  
            if callback:
                progress = (i + 1) / total_triangles * 100
                callback(progress, "Vtk conversion")

        return triangle_list

    
    # Test
    filename = "../../../Models/bunny.stl"
    # Get the current directory
    current_dir = os.getcwd()
    # Combine the current directory with the relative path
    filename = os.path.join(current_dir, filename)
    print(filename)

    # 1. read stl by vtk
    reader = vtk.vtkSTLReader()
    reader.SetFileName(filename)
    reader.Update()  # Ensure the reader reads the STL file

    # 2. data conversion
    vtk_poly_data = reader.GetOutput()
    triangle_list = convert_vtk_poly_data_to_triangles(vtk_poly_data, progress_callback)
    delta = 1
    srt = True

    mesh_slicer = slicer(triangle_list,delta, 0.3)
    mesh_slicer.incremental_slicing(progress_callback)
    print("Slice {} layers".format(len(mesh_slicer.P)))
    for l in mesh_slicer.P:
        print(l)

    for id, plane in enumerate(mesh_slicer.planes):
        for poly_id, polygon in enumerate(plane):
            ori_text = lambda ori: "CLOCKWISE" if ori == CLOCKWISE else "COUNTERCLOCKWISE"
            print(f"Plane {id}: polygon-{poly_id} Orientation: {ori_text(polygon.orientation())}")
    
    
    # Render
    vtk_polydata = convert_to_vtk_polyline(mesh_slicer.planes)
    
    # Create a renderer, render window, and interactor
    renderer = vtk.vtkRenderer()
    renderWindow = vtk.vtkRenderWindow()
    renderWindow.AddRenderer(renderer)
    renderWindowInteractor = vtk.vtkRenderWindowInteractor()
    renderWindowInteractor.SetRenderWindow(renderWindow)

    # Create a mapper and actor for the polyline
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(vtk_polydata)

    actor = vtk.vtkActor()
    actor.SetMapper(mapper)

    # Add the actor to the scene
    renderer.AddActor(actor)
    renderer.SetBackground(0.1, 0.2, 0.4)  # Background color

    # Render and start interaction
    renderWindow.Render()
    renderWindowInteractor.Start()







    


