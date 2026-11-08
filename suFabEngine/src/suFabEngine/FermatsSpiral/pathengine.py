"""
This module provides functions about filling path generation
# 1. extract contours tree from mask image [simulating a layer of slices in STL model].
import logging
# 2. for each seperated region, generate iso-contours.
# 3. connect iso-contour to fermal spirals.
example:
          pe = pathEngine()
          im, contours, areas, hiearchy, root_contour_idx = pe.generate_contours_from_img(filename, isRevertBlackWhite)  
          contour_tree = pe.convert_hiearchy_to_PyPolyTree()
          pe.traversing_PyPolyTree(contour_tree)
          group_contour = get_contours_from_each_connected_region(contour_tree, '0')
          for e in group_contour.values():
              ePath = gen_isocontours(e)
              ePath = gen_fermat_curve(ePath)

In 3D printing path generation,   
"""

import numpy as np
import pyclipper
import scipy.spatial.distance as scid
from scipy.signal import savgol_filter
#####
# 获取当前文件所在目录
from suFabEngine.FermatsSpiral import suPath2D
from suFabEngine.FermatsSpiral import suGraph
#####
    
class pathEngine:
    """
    Class pathEngine provide all necessary functions to build continous path.
    """
    def __init__(self):
        self.offset = 0.4
        self.im = None
        self.contours = None
        self.areas = None
        self.hiearchy = None 
        self.path2d = suPath2D.suPath2D()
        self.root_of_region_contour = None
        self.iso_contours_of_a_region = []
        return

    def recusive_add_node(self, node, idx):
        """
        This function  recursively add a child node add a brother node 
        into current node based on the hiearchy matrix. The detail 
        can be refered to https://docs.opencv.org/trunk/d9/d8b/tutorial_py_contours_hierarchy.html
        return 
        @cur_node: current node, first input is a empty root node
        @idx: current index   
        Note: In each node, the shape of contour from opencv is converted from (x,1,2) to (x,2)
        """
       
        if idx >= self.hiearchy.shape[1]:
            return
        Next, Previous, First_Child, Parent = self.hiearchy[0][idx]   
        new_node = pyclipper.PyPolyNode()
        new_node.IsOpen = False
        new_node.IsHole = False   
        # add new node
        if First_Child != -1:
            new_node.Contour = self.contours[First_Child].reshape((-1,2)) # (x rows, 1, 2) -> (x rows, 2)               
            new_node.Parent = node
            node.Childs.append(new_node)
            self.recusive_add_node(new_node, First_Child)
        if Next != -1:
            new_node.Contour = self.contours[Next].reshape((-1,2))
            if node.Parent is not None:
                new_node.Parent = node.Parent
                node.Parent.Childs.append(new_node)
            self.recusive_add_node(new_node, Next)    
        return   

    def convert_plane_to_PyPolyTree(self, plane):
        """
        Build a poly tree by a deep first search(DSF):
         - Construct a relation matrix from plane
         - Build a root node and find first level node in plane, then add these node to root
         - Recursively add node 
        """      
        def ConvertVertices2NumpyArray(vertices):
            N = len(vertices)
            verts_arr = np.zeros([N,2])  
            for i, v in enumerate(vertices):
                verts_arr[i] = v.coord[:2]
            return verts_arr   
                
        root = pyclipper.PyPolyNode()
        N = len(plane)
        if(N==0):
            return root
            
        # construct matrix R
        R = np.zeros([N,N])        
        for i in range(N):
            for j in range(N):
                if i != j:
                    if plane[j].is_inside(plane[i].vertices[0]):
                        R[i,j] = 1  # is child
                        
        ## analyzing matrix R
        acc_by_row = R.sum(axis= 1)              
        
        S = {}
        n_level = int(np.max(acc_by_row))+1
        for i in range(n_level):
            S[i] = set()
                       
        for i in range(len(acc_by_row)):            
            S[acc_by_row[i]].add(i)    
            
        def DSF(node, depth, idx):
            cur_depth = depth + 1
            if cur_depth not in S:
                return
            
            for i in S[cur_depth]:    # each contour in level depth+1
                if R[i, idx] == 1:  # i is idx's child
                    child_node = pyclipper.PyPolyNode()
                    child_node.Parent = node
                    child_node.Contour = ConvertVertices2NumpyArray(plane[i].vertices)
                    child_node.IsOpen = False                    
                    # Consider bugs in Minetto's slicer, here using tree info to determine being holes or not.
                    child_node.IsHole = True if cur_depth % 2 == 1 else False #plane[i].orientation() == 1 else True   # CLOCKWISE = -1   | COUNTERCLOCKWISE =  1    
                    if (child_node.IsHole):
                        if(plane[i].orientation() == 1):
                            logging.debug("convert to cw")
                            child_node.Contour = np.flip(child_node.Contour, 0)                    
                    
                    logging.debug("%d orientation: %d, isHole: %s, ccw: %s", i, plane[i].orientation(), child_node.IsHole, suPath2D.suPath2D.ccw(child_node.Contour))
                    DSF(child_node, cur_depth, i)
                    node.Childs.append(child_node)
                    
        ## recursively add node
        for i in S[0]:
            ## for each node in level 0, added itself to root
            node = pyclipper.PyPolyNode()
            node.Parent = root        
            node.Contour = ConvertVertices2NumpyArray(plane[i].vertices)  #  -> (x rows, 2)                   
            node.IsOpen = False
            node.IsHole = False #if plane[i].orientation() == 1 else True   # CLOCKWISE = -1   | COUNTERCLOCKWISE =  1   
            DSF(node, 0, i)
            root.Childs.append(node)   
            
        return root 
        
    def convert_hiearchy_to_PyPolyTree(self):
        """
        Build a root node and find first level node in hiearchy, then add these node to root. 
        Finally, use recusive_add_node(node,0) to generate hiearchy tree.
        Return contour tree (in PyPolyNode)
        ref: http://www.angusj.com/delphi/clipper/documentation/Docs/Units/ClipperLib/Classes/PolyTree/_Body.htm
        ref: https://stackoverflow.com/questions/32182544/pyclipper-crash-on-trivial-case-terminate-called-throwing-an-exception  
        """
        if self.hiearchy is None:
            return
        # find first contour in hiearchy-0
        root = pyclipper.PyPolyNode()
        idx = -1
        for row in self.hiearchy[0]:
            Next, Previous, First_Child, Parent = row
            if Previous == -1 and Parent == -1:
                idx += 1
                node = pyclipper.PyPolyNode()
                node.Parent = root        
                node.Contour = self.contours[idx].reshape((-1,2))  # (x rows, 1, 2) -> (x rows, 2)                   
                node.IsOpen = False
                node.IsHole = False               
                root.Childs.append(node)
                self.recusive_add_node(node, idx)
                break
        self.root_of_region_contour = root
        return root  
   
    def get_contours_from_each_connected_region(self, polyTreeNode, sId = '0'):
        """
        for each seperated region on a slice
        - return contour group to represent boundaries of a connected region
          each seperated region represents a region with connected area.
        @polyTreeNode is used to hold region boundary. Typically, the boundaries
                    stored in the current node represent external contours, and
                    the contours stored in the child nodes represent the internal
                    contours, such as holes. If child nodes have their own children
                    that will represent new seperated regions. We can deal these cases
                    by the recursive process.
        @sId is the id of polyTreeNode, eg. 0(root), 0-1(first child of root),
                    0-1-2(second grandson of root)
        @return a dict, @contour_group, each key-value represents a seperate regon KEY
                    and its boundary contours.
        
        examples:   contour_group = get_contours_from_each_connected_region(root, '0')
                    contour_group = get_contours_from_each_connected_region(node, '0-1-1')
        """
        root = polyTreeNode
        contour_group = {}  # eg. contour_group[id] holds all inner and outter contours in a seperated region.
        nDeep = sId.count('-')                       
        #for root node
        if (nDeep == 0):
            iChild = 0
            for n in polyTreeNode.Childs:
                cur_id = sId + '-' + str(iChild)
                cGroup = self.get_contours_from_each_connected_region(n, cur_id)
                # merge dict to contour_group
                contour_group.update(cGroup)  
                iChild += 1
        #for layer contains outer contour
        if (nDeep % 2 == 1):
            iChild = 0       
            contours = []
            contours.append(polyTreeNode.Contour) #outer contour
            #for layers contains inner contour
            for n in polyTreeNode.Childs:
                cur_id = sId + '-' + str(iChild)
                contours.append(n.Contour)
                iChild += 1           
                #next layer
                ii = 0
                for c in n.Childs:
                        child_id = cur_id + '-' + str(ii)
                        cGroup = self.get_contours_from_each_connected_region(n, cur_id)
                        # merge dict to contour_group
                        contour_group.update(cGroup) 
                        ii += 1               
            contour_group[sId] = contours       
           
        return contour_group   
   
    def traversing_PyPolyTree(self, root, func=None, order=0):
        """
        A function for test.
        Traversing a PyPolyTree
        @root: root of tree
        @func: function(contour, Children_list)
        @order: 0-deep first, 1-breath first(TODO)
        
        """
        if (func != None):           
            func(root)
        else:
            if(root.Parent is None):
                logging.debug("-----")
            msg = "Node has %d child node(s)" % len(root.Childs)
            logging.debug(msg)
             
        if (order == 0 ):  # deep first
            for n in root.Childs:
                self.traversing_PyPolyTree(n, func, 0)
        return  
   
    def get_nodes_by_layer(self, node, depth):
        """
        A test function(not used again)
        Get all nodes that depth = nDepth from a PyPolyTree
        @depth: depth of node
        return a list of node where node.depth = depth   
        """
        node_list = []       
        def traverse(node,depth, node_list):
            for n in node.Childs:
                if (n.depth == depth):
                    node_list.append(n)
                    continue
                else:
                    traverse(n,depth,node_list)
            return
             
        traverse(node, depth, node_list)
        return node_list
           
    def fill_closed_region_with_iso_contours(self, input_contours, offset):
        """
        fill a region with iso contours
        add all contours into self.iso_contours_of_a_region
        return @iso_contours_of_a_region, which inclues
        an iso contour list, each is represented as c[i,j]
        example:
              pe = pathEngine()
              pe.generate_contours_from_img(filepath, True)
              contour_tree = pe.convert_hiearchy_to_PyPolyTree() 
              group_contour = pe.get_contours_from_each_connected_region(contour_tree, '0')
              for cs in group_contour.values():
                  pe.iso_contours_of_a_region.clear()
                  iso_contours = pe.fill_closed_region_with_iso_contours(cs, offset)
        
        """
        #####
        boundary_2d = []
        for path in boundary_2d:
            path_2d = [[p[0], p[1]] for p in path if len(p) >= 2]
            boundary_2d.append(path_2d)

        # Now safely pass to Pyclipper
        pco = pyclipper.PyclipperOffset()
        pco.AddPaths(boundary_2d, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
        #####
        self.offset = offset
        iso_contours_of_a_region = []
        contours = input_contours.copy()
        
        # multiply 10 for hold precision, divide by 10 before return
        for i, c in enumerate(contours):
            contours[i] = c * 10
        offset = abs(offset) * (-10)
            
        iso_contours_of_a_region.append(input_contours)
        while len(contours) != 0:
            pco = pyclipper.PyclipperOffset()
            pco.AddPaths(contours, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
            contours = pco.Execute(offset)   
            iso_contours_of_a_region.append(contours)
            
        for i in range(1, len(iso_contours_of_a_region)):
            for j in range(len(iso_contours_of_a_region[i])):                
                iso_contours_of_a_region[i][j] = np.array(iso_contours_of_a_region[i][j])/10
               
        return iso_contours_of_a_region

    def find_nearest_point_idx(self, point, contour):
        """
        given a point, find the nearest index of point in a contour
        @point(a value, not index) is a vertex
        @contours 
        return the index of a nearest point
        """
        idx = -1
        distance = float("inf")   
        for i in range(0, len(contour)-1):        
            d = np.linalg.norm(point-contour[i])
            if d < distance:
                distance = d
                idx = i
        return idx   
    
    def find_point_index_by_distance(self, cur_point_index, cur_contour, T, ori=1):
        """
        find an index of point from current point, which distance larger than T
        @in: current index of point, current contour, 
        @in: T is a distance can be set to offset or offset/2 or 2 * offset
        @ori: orientation ori = 1 prev order, ori = 0 next order
        """
        T = abs(T)
        start_point = cur_contour[cur_point_index]
        
        if (ori):
            idx_end_point = suPath2D.suPath2D.prev_idx(cur_point_index, cur_contour)
        else:
            idx_end_point = suPath2D.suPath2D.next_idx(cur_point_index, cur_contour)
        end_point=[]        
        for ii in range(0,len(cur_contour)-1):
            end_point = cur_contour[idx_end_point]
            distance=np.linalg.norm(start_point-end_point)            
            if distance > T:           
                break
            else:           
                #idx_end_point = suPath2D.suPath2D.prev_idx(idx_end_point, cur_contour) 
                if (ori):
                    idx_end_point = suPath2D.suPath2D.prev_idx(idx_end_point, cur_contour)
                else:
                    idx_end_point = suPath2D.suPath2D.next_idx(idx_end_point, cur_contour)                
        return idx_end_point    
    
    def contour2spiral(self, contours, idx_start_point, offset):
        """
        Connect all contours of a pocket. The key idea is divide contours 
        into two sets, and run the connection process twice, one for in
        the other for out. Then connect them again.
        @contours: iso contours, index of start point, offset
        @idx_start_point: start connect at idx_start_point-th point on contours[0] 
        """
        offset = abs(offset)
        cc = [] # contour for return
        N = len(contours)
        for i in range(N):
            contour1 = contours[i]        
            
            ## find end point(e1)
            idx_end_point = self.find_point_index_by_distance(idx_start_point, contour1, offset*2)
            end_point = contour1[idx_end_point]
                
            # add contour segment to cc
            idx = idx_start_point
            while idx != idx_end_point:
                cc.append(contour1[idx])
                idx = suPath2D.suPath2D.next_idx(idx, contour1)   
            
            if(i == N-1): 
                break          
            
            ## find s2   
            idx_start_point2 = self.find_nearest_point_idx(end_point, contours[i+1])  
            # go forward a distance to avoid interference
            idx_start_point2 = self.find_point_index_by_distance(idx_start_point2, contours[i+1], offset/2, 0)
            
            idx_start_point = idx_start_point2                  
            #cv2.circle(self.im, tuple(contours[i][idx_end_point].astype(int)), 5, (255,0,0), -1)                      
        return cc     
    
    def connect_spiral(self, first_spiral, second_spiral, is_flip=True):
        """
        Connect two spiral
        @is_flip means if the orientation of second contour needs to be changed.
        Commonly, we reverse the orientation of second contour, then connect it
        with the first one.                
        """
        s = []
        if is_flip:
            second_spiral = np.flip(second_spiral, 0)
            
        for i in range(len(first_spiral)):
            s.append(first_spiral[i])                 
        for i in range(len(second_spiral)):
            s.append(second_spiral[i])
        return s
    # return contours 2d list

    def init_isocontour_graph(self, iso_contours):
        """
        Generate 2d iso contour list and a graph by distance relationship matrix
        @param iso_contours: the list of iso contours indexed by (i, j),
                             where i represents the distance to outer boundary
                             and j represents the contour index of current group
        @return: the iso_contours_2D and graph

        Update:
          1. Use resample iso_contours_2D to compute distance between the two contours: inter_size = offset * 0.35
          2. Remove the coupling between distance threshold and the interpolate distance.
        """
        iso_contours_2D = []
        dist_th = abs(self.offset) * 2.5    # threshold for determine adjacent relationship
        inter_size = self.offset * 0.35         # equal distance for resampling

        # resample and convert 2D list of contours to clockwise 1-d list of contours
        for i in range(len(iso_contours)):
            for j in range(len(iso_contours[i])):
                # resample && convert to np.array  (by np.asarray)
                iso_contours[i][j] = suPath2D.suPath2D.resample_curve_by_equal_dist(iso_contours[i][j], inter_size)
                iso_contours_2D.append(iso_contours[i][j])
        suPath2D.suPath2D.convto_cw(iso_contours_2D)

        # @R is the relationship matrix
        num_contours = len(iso_contours_2D)
        R = np.zeros((num_contours, num_contours)).astype(int)
        for i, cs in enumerate( iso_contours[:-1]):  # for each group contour[i], where i*offset represents the distance from boundaries
            for j1, c1 in enumerate(cs):
                c1_id = suPath2D.suPath2D.get_contour_id(i, j1, iso_contours)

                c1 = iso_contours_2D[c1_id]

                for j2, c2 in enumerate(iso_contours[i + 1]):
                    c2_id = suPath2D.suPath2D.get_contour_id(i + 1, j2, iso_contours)
                    c2 = iso_contours_2D[c2_id]
                    dist = scid.cdist(c1, c2, 'euclidean')
                    min_dist = np.min(dist)
                    if (min_dist < dist_th):
                        R[c1_id][c2_id] = 1

        # visualize
        print(R)
        print(R.shape)
        print(len(iso_contours_2D))
        graph = suGraph.suGraph()
        graph.init_from_matrix(R)
        return iso_contours_2D, graph

    def init_isocontour_graph_by_Hosdoff(self, iso_contours):
        """
        Generate 2d iso contour list and a graph by distance relationship matrix
        @iso_contours includes list of contours[i,j] 
        return
        @iso_contours_2D
        @graph
        """
        iso_contours_2D = []
        # contour distance threshold between adjacent layers
        dist_th = abs(self.offset) * 5.5 # Adjusted as needed

        for i in range(len(iso_contours)):
            for j in range(len(iso_contours[i])):
                # resample && convert to np.array                
                iso_contours[i][j] = suPath2D.suPath2D.resample_curve_by_equal_dist(iso_contours[i][j], abs(self.offset)) 
                iso_contours_2D.append(iso_contours[i][j])               
        suPath2D.suPath2D.convto_cw(iso_contours_2D)
        # @R is the relationship matrix
        num_contours = len(iso_contours_2D)
        R = np.zeros((num_contours, num_contours)).astype(int)    
        i = 0
        for cs in iso_contours[:-1]:     # for each group contour[i], where i*offset represents the distance from boundaries      
            j1 = 0           
            for c1 in cs:               
                c1_id = suPath2D.suPath2D.get_contour_id(i, j1, iso_contours)  

                j2 = 0
                for c2 in iso_contours[i+1]:
                    # Calculate the Hausdorff distance in both directions and take the maximum
                    hausdorff_dist = max(scid.directed_hausdorff(c1, c2)[0], scid.directed_hausdorff(c2, c1)[0])
                    if hausdorff_dist < dist_th:
                        c2_id = suPath2D.suPath2D.get_contour_id(i+1, j2, iso_contours)
                        R[c1_id][c2_id] = 1

                    j2 += 1
                j1 += 1
            i += 1
        print(R)
        graph = suGraph.suGraph()  
        graph.init_from_matrix(R)        
        return iso_contours_2D, graph  
        
    def reconnect_from_leaf_node(self, graph, iso_contours, dist_thresh):
        """
        if graph not connected, find new edge from leaf nodes.
        return true if the re-connection is successful
        Method: Just add a new edge, if the graph is connected, then return
        example:
            ret = reconnect_from_lear_node(graph, iso_contours)
        """
        layer = range(len(iso_contours)-1)
        layer = list(layer)
        layer.reverse()
        for l in layer: # check from leaf nodes
            cs = iso_contours[l]
            D, i, j = suPath2D.suPath2D.find_distance_matrix(cs)
            if(D[i,j] < dist_thresh):
                global_ind_i = suPath2D.suPath2D.get_contour_id(l, i, iso_contours)
                global_ind_j = suPath2D.suPath2D.get_contour_id(l, j, iso_contours)
                graph.nodes[global_ind_i].next.append(global_ind_j)
                graph.nodes[global_ind_j].pre.append (global_ind_i)
                graph.update_matrix()
                if(graph.is_connected()):                
                    return True
        return  False    
    
    def connect_two_pockets(self, fc1, fc2, offset):
        """
        connect to the next contour then going back
        connect points:
                        start                    end
           fc1:    pid_c1(closest)         goning forward with distance offset (from start)
           fc2:    pid_c2(closest)         going forward and contrary to the dir of fc1, end near the start of fc1 
        """        
        pid_c1, pid_c2, min_d = suPath2D.suPath2D.find_nearest_point_for_css(fc1, fc2, offset)
        if(min_d > abs(offset) * 1.1):
            pid_c1, pid_c2, min_d = suPath2D.suPath2D.find_closest_point_pair(fc1,fc2)
        
        # check orientation
        # not precise, todo: use log func to estimate
        n_forward = 1
        #if(len(fc1) > 1000 and len(fc2) > 1000):
            #n_forward = 1.
        nid_c1 = self.path2d.next_idx_n(pid_c1, n_forward, fc1)
        nid_c2 = self.path2d.next_idx_n(pid_c2, n_forward,fc2)
        dir_fc1 = fc1[nid_c1] - fc1[pid_c1]
        dir_fc2 = fc2[nid_c2] - fc2[pid_c2]
        angle = suPath2D.suPath2D.angle_between(dir_fc1, dir_fc2)
        
        fc = []
        #find return point with distance to pid_c1 = offset
        pid_c1_return = self.find_point_index_by_distance(pid_c1, fc1, offset, 0)
                
        #fc1 from 0 to pid_c1
        #for i in range(pid_c1+1):
            #fc.append(fc1[i]) 
        fc = fc + list(fc1)[0:pid_c1+1]
        #get returned index from fc2
        pid_c2_near_return = self.find_nearest_point_idx(fc1[pid_c1_return], fc2)
        
            #if (idx_end == pid_c2):
                #print(">>>>")
                #idx_end = suPath2D.suPath2D.next_idx(idx_end, fc2)
        
        #test
        #cv2.circle(self.im, tuple(fc1[pid_c1].astype(int)), 2, (0,0,255))          
        #cv2.circle(self.im, tuple(fc2[pid_c2_near_return].astype(int)), 2, (255,0,0)) 
        
        idx = pid_c2
        if angle > 90:
            # different orientaton: 
            if (pid_c2_near_return == pid_c2):
                #print("-------------------------------------------")
                #cv2.circle(self.im, tuple(fc2[idx_end].astype(int)), 2, (0,0,255)) 
                pid_c2_near_return = self.find_point_index_by_distance(pid_c2_near_return, fc2, offset, 1)            
            while idx != pid_c2_near_return:  
                fc.append(fc2[idx])
                idx = self.path2d.next_idx(idx, fc2)            
        else:
            if (pid_c2_near_return == pid_c2):
                #print("-------------------------------------------")
                
                pid_c2_near_return = self.find_point_index_by_distance(pid_c2_near_return, fc2, offset, 0)            
            while idx != pid_c2_near_return:  
                fc.append(fc2[idx])
                idx = self.path2d.prev_idx(idx, fc2)            
                
        fc.append(fc2[pid_c2_near_return])
        # 3        
        fc = fc + list(fc1[pid_c1_return:])
            
        return np.asarray(fc)    
    
    def dfs_connect_path_from_bottom(self, i, nodes, iso_contours_2D, spirals, offset):
            node = nodes[i]  
            msg = '{} make spiral {}'.format(i+1, np.asarray(node.data) + 1)
            print(msg)  
            cs = []
            for ii in node.data:
                cs.append(iso_contours_2D[ii])
            spirals[i] = self.build_spiral_for_pocket(cs, False) 
    
            #if(i ==7):
            #    suPath2D.suPath2D.draw_line(spirals[i], self.im, [255,255,0],1)
            if(len(node.next) > 0): 
                for ic in node.next:
                    self.dfs_connect_path_from_bottom(ic, nodes, iso_contours_2D, spirals, offset)                    
    
                    if (len(spirals[ic]) / len(spirals[i]) > 2):
                        spirals[i] = self.connect_two_pockets(spirals[ic],spirals[i], abs(offset))
                        msg = '{} insert {}'.format(ic+1, i+1)
                        print(msg)                        
                    else:
                        if (len(spirals[ic])) > 0:
                            spirals[i] = self.connect_two_pockets(spirals[i],spirals[ic], abs(offset))
                            msg = '{} insert {}'.format(i+1, ic+1)
                            print(msg)                        
    
            return
    def fill_spiral_in_connected_region(self, boundary, offset):
        
        iso_contours = self.fill_closed_region_with_iso_contours(boundary, offset)
        # init contour graph for iso contour by a distance relationaship matrix  
        #iso_contours_2D, graph = self.init_isocontour_graph_by_Hosdoff(iso_contours)     
        #iso_contours_2D, graph = self.init_isocontour_graph(iso_contours)
        iso_contours_2D, graph = self.init_isocontour_graph(iso_contours)
        graph.to_Mathematica("")

        if not graph.is_connected():
            print("not connected")
            ret = self.reconnect_from_leaf_node(graph, iso_contours, abs(offset * 1.2))
            if(ret):
                print("re-connect...")
                graph.to_Mathematica("")

        # generate a minimum-weight spanning tree
        graph.to_reverse_delete_MST()
        graph.to_Mathematica("")
        # generate a minimum-weight spanning tree
        pocket_graph = graph.gen_pockets_graph()
        pocket_graph.to_Mathematica("")
        # generate spiral for each pockets
        # deep first search
        spirals = {}
        self.dfs_connect_path_from_bottom(0, pocket_graph.nodes, iso_contours_2D, spirals, offset) 

        return spirals[0]        
    
    def _convert_vtk_to_numpy(self, polydata):
        points = polydata.GetPoints()
        num_points = points.GetNumberOfPoints()
        arr = np.zeros((num_points, 3))
        for i in range(num_points):
            arr[i] = points.GetPoint(i)
        return arr
    def smooth_curve_by_savgol(self, c, filter_width=5, polynomial_order=1):
        #N = 10
        last_vert = c[-1]
        c = np.array(c)
        y = c[:, 1]
        x = c[:, 0]
        x2 = savgol_filter(x, filter_width, polynomial_order)
        y2 = savgol_filter(y, filter_width, polynomial_order)
        c = np.transpose([x2,y2])
        c = np.vstack((c,last_vert))
            
        return c    
   
    @staticmethod
    def check_pocket_ratio_by_pca(cs,offset=4):
        """
        return ratio, start_point_idx by Principal Component Analysis(PCA)    
        @ratio = second component / first component
        @start_point_idx speicify an entrance position by PCA
        input
        @cs: contour list in pockets
        @offset: to determin distance of interpolation 
        """
        from sklearn.decomposition import PCA
        verts = []
        for c in cs:
            for p in c:
                verts.append(p)
        verts = np.array(verts).reshape([len(verts),2])    
        pca = PCA(n_components=2)
        pca.fit(verts)
    
        v = []
        l = []
        for length, vector in zip(pca.explained_variance_, pca.components_):
            sqrt_len = np.sqrt(length) 
            v.append(vector * 3 * sqrt_len)
            l.append(sqrt_len)
        ratio = l[1] / l[0]     
        # find a index of point in cs[0] that is nearest to axes <pca.mean, pca.mean + v[1]>
        # interpolation on line <pca.mean, pca.mean + v[1]>
        ax1 = []
        ax1.append(pca.mean_)
        ax1.append(pca.mean_ + v[1])
        ax1 = suPath2D.suPath2D.resample_curve_by_equal_dist(ax1, abs(offset)/2)
        pid_c1, pid_c2, d = suPath2D.suPath2D.find_closest_point_pair(cs[0],ax1)
        
        return ratio, pid_c1    
    def build_spiral_for_pocket(self, iso_contours, use_PCA = False):
        """
        Split contours into two groups(by odd/even), connect each then join these two spirals.
        @iso_contours: input iso contours of a pocket  
        return a spiral path
        """
        if (len(iso_contours) == 1):
            return iso_contours[0]        
        in_contour_groups = []
        out_contour_groups = []
        for idx in range(len(iso_contours)):
            if (idx % 2 == 0):
                in_contour_groups.append(iso_contours[idx])
            else:
                out_contour_groups.append(iso_contours[idx])
    
        #test
        start_id = 0
        if use_PCA:
            ratio, entrance_id = pathEngine.check_pocket_ratio_by_pca(in_contour_groups, self.offset)        
            if (ratio < 0.8):
                start_id = entrance_id
        #cv2.circle(self.im, tuple(in_contour_groups[0][start_id].astype(int)), 5, (0,0,255)) 
        
        cc_in = self.contour2spiral(in_contour_groups,start_id, self.offset )
        output_index = self.find_nearest_point_idx(in_contour_groups[0][start_id], out_contour_groups[0]) 
        
        #test
        #cv2.circle(self.im, tuple(out_contour_groups[0][output_index].astype(int)), 5, (0,0,255)) 
        
        cc_out = self.contour2spiral(out_contour_groups, output_index, self.offset )
    
        ## connect two spiral
        fspiral = self.connect_spiral(cc_in, cc_out)
        ## set out point
        out_point_index = self.find_point_index_by_distance(start_id, in_contour_groups[0], self.offset/2)
        fspiral.append(in_contour_groups[0][out_point_index])     
        return np.array(fspiral)    
           
############################
# compute hausdorff distance
############################

def compute_hausdorff_distance(c1, c2):
    u = np.array(c1)
    v = np.array(c2)
    return scid.directed_hausdorff(u, v)[0]   

if __name__ == '__main__':   
    pass