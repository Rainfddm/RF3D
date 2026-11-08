import numpy as np
import math
import scipy.spatial.distance as scid

#####
# 获取当前文件所在目录
from suFabEngine.FermatsSpiral import css
#####

class suPath2D:
    """
    Hold data structure and tool functions for 2D path
    """    
    def __init__(self):        
        self.contour_tree      = None
        self.group_boundary    = []
        self.group_isocontours = []  #containts iso contours list
        self.group_isocontours_2D = []
        self.group_relationship_matrix = []
        
        return 

    @staticmethod
    def get_contour_id(i,j,iso_contours):
        """
        Get a 1D global index from iso_contours list contour(i,j), where
        i is the distance to the boundary, there are many contours(j=0...n-1).  
        Thus we can generate a index matrix for building a graph that can
        be visualized in different tools. Eg.
        Mathematica:
           GraphPlot[{{1, 1, 1, 0}, {1, 0, 0, 0}, {0, 1, 0, 0}, {1, 1, 0, 1}},
                     SelfLoopStyle -> True, MultiedgeStyle -> True,
                     VertexLabeling -> True, DirectedEdges -> True]
        """
        id = 0 
        ii = 0
        for cs in iso_contours:
            if ii == i: break
            for c in cs:
                id += 1
            ii += 1           
        id += j # indexed from 0
        return id   
    @staticmethod
    def prev_idx(idx, contour):
        """ Returns next point id for a closed contour.  """
        if idx > 0:
            return idx - 1
        if idx == 0:
            return len(contour) -1
    @staticmethod
    def next_idx(idx, contour):
        """ Returns previous point id for a closed contour.  """
        if idx < len(contour)-1:
            return idx + 1
        if idx == len(contour) - 1:
            return 0
    @staticmethod
    def next_idx_n(idx, n, contour):
        for i in range(n):
            idx = suPath2D.next_idx(idx, contour)
        return idx
    @staticmethod
    def prev_idx_n(idx, n, contour):
        for i in range(n):
            idx = suPath2D.prev_idx(idx, contour)
        return idx    
    @staticmethod
    def unit_vector(vector):
        """ Returns the unit vector of the vector.  """
        return vector / np.linalg.norm(vector)  
    @staticmethod
    def angle_between(v1, v2):
        """ 
        Returns the angle in dgree between vectors 'v1' and 'v2'
    
        example:
            angle_between((1, 0, 0), (0, 1, 0))
            90.0
            angle_between((1, 0, 0), (1, 0, 0))
            0.0            
        """
        v1_u = suPath2D.unit_vector(v1)
        v2_u = suPath2D.unit_vector(v2)
        return np.arccos(np.clip(np.dot(v1_u, v2_u), -1.0, 1.0)) / math.pi * 180
    
    @staticmethod
    def convto_cw(contours):
        for i in range(len(contours)):
            if( suPath2D.ccw(contours[i]) ):
                contours[i] = np.flip(contours[i], 0)
    @staticmethod
    def find_distance_matrix(cs):
        """ 
        compute distance matrix and min distance among a group of contours
        return distance matrix and the index of the min value
        
        example:
             D, i,j= find_distance_matrix(contours)
        """ 
        n = len(cs)
        D = np.zeros([n,n])
        d = float("inf")
        idx_i, idx_j = 0, 0
        
        for i in range(n):
            for j in range(n):
                if(i != j):
                    t1,t2,D[i][j] = suPath2D.find_closest_point_pair(cs[i],cs[j])
                    if D[i][j] < d:
                        d = D[i][j]
                        idx_i, idx_j = i, j
        return D, idx_i, idx_j          
    @staticmethod
    def resample_curve_by_equal_dist(contour, size=2, is_open = False):
        """ 
        Resample a curve by Roy's method
        Refer to "http://www.morethantechnical.com/2012/12/07/resampling-smoothing-and-interest-points-of-curves-via-css-in-opencv-w-code/"
        @contour: input contour
        @size: sample size on the contour
        @is_open: True means openned polyline, False means closed polylien
        example:
             c = suPath2D.resample_curve_by_equal_dist( c, offset)     
        """ 
        resample_c = []
        ## compute length of contour
        contour_length = 0;  
        contour = np.asarray(contour)
        for i in range(len(contour) - 1):
            d = np.linalg.norm(contour[i+1]-contour[i])
            contour_length += d
           
        if is_open == False:
            d = np.linalg.norm(contour[0] - contour[-1])
            contour_length += d
       
        resample_size = size 
        N = int(contour_length / resample_size)
        if (N < 10):  #avoid lost in smooth
            N = 10
            resample_size = contour_length / 4
       
        dist = 0             # dist = cur_dist_to_next_original_point + last_original_dist
        cur_id = 0           # for concise
        resample_c.append(contour[0])
       
        nCount = len(contour) - 1
        if is_open == False:     
            nCount = len(contour)
           
        for i in range(nCount):
            next_id = suPath2D.next_idx(cur_id, contour)
            last_dist = np.linalg.norm(contour[next_id]-contour[i])
            dist += last_dist    #current length
            if(dist >= resample_size):
                #put a point on line
                d_ = last_dist - (dist - resample_size)    #reserve size
                dir_ = contour[next_id] - contour[cur_id]
               
                new_point = contour[cur_id] + d_ * dir_ / np.linalg.norm(dir_)
                resample_c.append(new_point)
               
                dist = last_dist - d_  #remaining dist
               
                #if remaining dist to next point needs more sampling...
                while (dist - resample_size > 1e-3):
                    new_point = resample_c[-1] + resample_size * dir_ / np.linalg.norm(dir_)
                    resample_c.append(new_point)               
                    dist -= resample_size              
                   
            cur_id = next_id
        #print(resample_c)  
        return  np.asarray(resample_c)   
    @staticmethod
    def find_closest_point_pair(c1, c2):
        """
        Return two indice of the closest pair of points.
        
        example:
            id1, id2, min_d = find_closest_point_pair(c1,c2)
        """
        dist = scid.cdist(c1, c2, 'euclidean')
        min_dist = np.min(dist)    
        gId = np.argmin(dist)
        pid_c1 = int(gId / dist.shape[1])
        pid_c2 = gId - dist.shape[1] * pid_c1            
        return pid_c1, pid_c2, min_dist

    @staticmethod
    def ccw(contour):
        """
        check a contour is (counter clockwise)CCW or CW
        return CCW: True   CW: False
        refer to https://stackoverflow.com/questions/1165647/how-to-determine-if-a-list-of-polygon-points-are-in-clockwise-order
        Note: In version 1, we use openCV image coordinate, like HTML5 canvas, y axes points down
              Now we use the Cartesian coordinate system, the determination is conversed
        """
        l = np.asarray(contour)
        ls = np.roll(l, -1, axis=0)
        
        # signed area
        # a = np.sum((ls[:, 0] - l[:, 0]) * (ls[:, 1] + l[:, 1]))
        a = np.sum(l[:, 0] * ls[:, 1] - ls[:, 0] * l[:, 1])
        return a > 0

    @staticmethod
    def find_nearest_point_for_css(c1, c2, offset, window_size = 4):
        """
        find CSS points on c1
        make a polyline by above points
        find nearest pair of index
        @c1 is the first contour
        @c2 is the second contour
        @windows_size is \alpha of CSS
        """
        id1 = id2 = -1
        kappa, smooth = css.compute_curve_css(c1, 4)  
        css_idx = css.find_css_point(kappa)   
        c = []
        for i in css_idx:
            c.append(c1[i])
        #debug
        #print("len[c]={}, len[c2]={}".format(len(c),len(c2)))
        if len(c) == 0:  #if no css point
            c = c1
            id1, id2, min_d = suPath2D.find_closest_point_pair(c,c2)
            return id1, id2, min_d 
        id1, id2, min_d = suPath2D.find_closest_point_pair(c,c2)
        return css_idx[id1], id2, min_d 
    
if __name__ == '__main__':
    import unittest
    import matplotlib.pyplot as plt

    def create_noisy_contour(num_points=50, noise_level=0.1):
        """
        Create a noisy circular contour for testing.
        
        :param num_points: Number of points in the contour.
        :param noise_level: Magnitude of noise to add.
        :return: Noisy contour as a numpy array.
        """
        t = np.linspace(0, 2*np.pi, num_points)
        x = np.cos(t) + noise_level * np.random.randn(num_points)
        y = np.sin(t) + noise_level * np.random.randn(num_points)
        return np.column_stack((x, y))
    def create_circle_contour(center, radius, num_points=100, noise_level=0.05):
        """
        Create a circular contour.

        :param center: Center of the circle (x, y).
        :param radius: Radius of the circle.
        :param num_points: Number of points in the contour.
        :return: Circular contour as a numpy array.
        """
        t = np.linspace(0, 2 * np.pi, num_points)
        x = center[0] + radius * np.cos(t) + noise_level * np.random.randn(num_points)  
        y = center[1] + radius * np.sin(t) + noise_level * np.random.randn(num_points)  
        return np.column_stack((x, y))

    class TestSuPath2D(unittest.TestCase):
    
        def test_get_contour_id(self):
            iso_contours = [[[1, 2], [3, 4]], [[5, 6], [7, 8], [9, 10]]]
            result = suPath2D.get_contour_id(1, 2, iso_contours)
            self.assertEqual(result, 4)  # Expected result should be calculated manually

        def test_prev_idx(self):
            contour = [[1, 2], [3, 4], [5, 6]]
            result = suPath2D.prev_idx(0, contour)
            self.assertEqual(result, 2)

        def test_next_idx(self):
            contour = [[1, 2], [3, 4], [5, 6]]
            result = suPath2D.next_idx(2, contour)
            self.assertEqual(result, 0)

        def test_unit_vector(self):
            vector = [4, 3]
            result = suPath2D.unit_vector(vector)
            expected = np.array([0.8, 0.6])
            np.testing.assert_array_almost_equal(result, expected)

        def test_angle_between(self):
            v1 = [1, 0]
            v2 = [0, 1]
            result = suPath2D.angle_between(v1, v2)
            self.assertAlmostEqual(result, 90.0)

        def test_resample_curve_vy_equal_dist(self):
            # Create a noisy contour
            noisy_contour = create_noisy_contour()
            # Resample the contour using the function
            resampled_contour = suPath2D.resample_curve_by_equal_dist(noisy_contour, size=0.1, is_open=False)

            # Plot the noisy contour
            plt.figure(figsize=(6,6))
            plt.plot(noisy_contour[:,0], noisy_contour[:,1], marker='o')
            # Plot resampled contour
            plt.plot(resampled_contour[:, 0], resampled_contour[:, 1], marker='x', color='red', label='Resampled Contour')

            plt.title("Comparison of Original and Resampled Contours")
            plt.xlabel("X-axis")
            plt.ylabel("Y-axis")
            plt.grid(True)
            plt.show()       

        def test_find_nearest_pair(self):
            # Generate a list of iso contours
            iso_contours = [
                create_circle_contour(center=(0, 0), radius=1),
                create_circle_contour(center=(0, 0), radius=1.4),
                create_circle_contour(center=(0, 0), radius=1.8)
            ]
            # Find and display the closest points between each pair of contours
            for i in range(len(iso_contours)):
                for j in range(i + 1, len(iso_contours)):
                    c1, c2 = iso_contours[i], iso_contours[j]
                    pid_c1, pid_c2, min_dist = suPath2D.find_closest_point_pair(c1, c2)
                    print(f"Closest points between contour {i} and {j}:")
                    print(f"Point in contour {i}: {c1[pid_c1]}")
                    print(f"Point in contour {j}: {c2[pid_c2]}")
                    print(f"Minimum Distance: {min_dist}\n")

            # Optional: Plot the contours and closest points
            plt.figure(figsize=(8, 8))
            for contour in iso_contours:
                plt.plot(contour[:, 0], contour[:, 1])

            # Highlight closest points
            for i in range(len(iso_contours)):
                for j in range(i + 1, len(iso_contours)):
                    c1, c2 = iso_contours[i], iso_contours[j]
                    pid_c1, pid_c2, _ = suPath2D.find_closest_point_pair(c1, c2)
                    plt.scatter(*c1[pid_c1], color='red')
                    plt.scatter(*c2[pid_c2], color='red')

            plt.title("Iso Contours and Closest Points")
            plt.xlabel("X-axis")
            plt.ylabel("Y-axis")
            plt.grid(True)
            plt.show()

    unittest.main()

