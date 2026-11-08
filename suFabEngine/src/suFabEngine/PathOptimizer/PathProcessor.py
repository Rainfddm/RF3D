#
import numpy as np
import torch
import time
from sklearn.neighbors import NearestNeighbors

class PathSmoother():
    def __init__(self, path, boundaries, offset, radius):
        self.path = path
        self.boundaries = boundaries
        self.offset = offset
        self.radius = radius

        self.X = None
        self.Pstar = None
        self.Phat = None
        
        self.kd_tree = self.build_kd_tree(path)
        self.losses = []

    def build_kd_tree(self):    
        # Use NearestNeighbors to build a kd-tree for efficient neighbor search
        # @points is n-by-dim array
        points = self.path
        dim = points.shape[1]
        self.kd_tree = NearestNeighbors(n_neighbors=dim, algorithm='kd_tree').fit(points)
    
    def query_neighbors_within_radius(self, query_point, radius):
        # Query the kd-tree to find points within a radius
        # This will return the distances to the neighbors and their indices
        distances, indices = self.kd_tree.radius_neighbors([query_point], radius=radius)    
        return distances, indices
    
    def loss_function(self):
        # loss function
        loss = torch.sum((torch.norm(self.X - self.Pstar, dim=-1) - self.offset)**2 + (torch.norm(self.X - self.Phat, dim=-1) - self.offset)**2)
        self.losses.append(loss.item())  # for draw loss 
        return loss
    
    def optimize(self, lamada):
        #@param lamda is learning rate
        self.X = self.path[:, :2]
        self.X.requires_grad = True
        
        optimizer = torch.optim.Adam([self.X], lr=lamada)
        # optimizer = torch.optim.SGD([self.X], lr=lamada)
        f = self.loss_function()
        optimizer.zero_grad()
        f.backward()
        optimizer.step()
        self.path[:, :2] = self.X.detach()
        self.path = self.path.cpu()
        self.path = self.resample_eqd(self.path)
        self.path = self.path.cuda()  

    # feature functions
    # -----------------
    def gen_bisector_vector(self):
        #Generate normal bisector vector for each vertices in self.path
        xyz = self.path
        pre = torch.roll(xyz, shifts=-1, dims=0)
        next = torch.roll(xyz, shifts=1, dims=0)
        pre_direction = (pre - xyz) / torch.norm(pre - xyz, dim=-1, keepdim=True)
        next_direction = (next - xyz) / torch.norm(next - xyz, dim=-1, keepdim=True)
        A = (pre_direction + next_direction)
        AngleBisector = A / torch.norm(A, dim=-1, keepdim=True)
    
    
    def find_intersection(self, P1, D, A, B):
        # Unpack the points and the direction vector
        x1, y1 = P1
        dx, dy = D
        ax, ay = A
        bx, by = B

        # Calculate denominators
        denominator = dx * (by - ay) - dy * (bx - ax)

        # Check if line and segment are parallel
        if denominator == 0:
            return None  # No intersection (parallel or overlapping)

        # Calculate numerators for t and u
        t_numerator = (ax - x1) * (by - ay) - (ay - y1) * (bx - ax)
        u_numerator = (ax - x1) * dy - (ay - y1) * dx

        # Calculate t and u
        t = t_numerator / denominator
        u = u_numerator / denominator

        # Check if the intersection point is on the line segment
        if 0 <= u <= 1:
            # Calculate the intersection point
            intersection_x = x1 + t * dx
            intersection_y = y1 + t * dy
            return (intersection_x, intersection_y)
        else:
            return None  # No intersection within the line segment bounds
        
    def nearest_two_intersections(self, P1, D, segments):
        closest_positive = (float('inf'), None)  # Closest intersection in the positive direction of D
        closest_negative = (float('inf'), None)  # Closest intersection in the negative direction of D

        for A, B in segments:
            intersection = self.find_intersection(P1, D, A, B)
            if intersection:
                ix, iy = intersection
                # Calculate vector from P1 to intersection point
                vix, viy = ix - P1[0], iy - P1[1]
                # Dot product with direction vector D
                dot_product = vix * D[0] + viy * D[1]
                distance = (ix - P1[0])**2 + (iy - P1[1])**2  # Euclidean distance squared

                if dot_product > 0 and distance < closest_positive[0]:
                    closest_positive = (distance, intersection)
                elif dot_product < 0 and distance < closest_negative[0]:
                    closest_negative = (distance, intersection)

        return closest_positive[1], closest_negative[1]

    
    # Rmove repeated query point in the neighbour set
    def remove_query_id(query_list, query_id):
        b = query_list[0].flatten()
        a = set(b)
        indices = a - {query_id}
        return list(indices)
    
    # Traverse the path and find all Phat and Pstar
    def calc_features(self):
        # Query all points within the radius alpha * 4
        alpha = 4
        radius=alpha*self.offset
        for cur_id, v in enumerate(self.path):
            # get segs
            
            distances,indices = self.query_neighbors_within_radius(v, radius)
            indices = self.remove_query_id(indices, cur_id)
            selected_points = self.path[indices]
            
            # Separate the x and y coordinates   
            x_coords, y_coords   = inter_path[:, 0], inter_path[:, 1]
            x1_coords, y1_coords = selected_points[:, 0], selected_points[:, 1]
            
            # Update plot data        
            curve.set_data(x_coords, y_coords)
            points.set_offsets(np.column_stack((x1_coords.reshape(x1_coords.shape[0],1),
                                                y1_coords.reshape(y1_coords.shape[0],1))))
            
            # get bisectors
            # get two points

    def run(self, times=10, lamada=0.017):
        # @param times is iterate times
        # @param lamda is learning rate
        # return smoothed path
        start_time = time.time()
        self.kd_tree = self.build_kd_tree()

        for _ in range(times):
            self.calc_features()
            self.optimize(lamada)
        end_time = time.time()
        total_time = print("One iteration uses: {} seconds".format(end_time - start_time))
        return self.path.cpu() 
    
if __name__ == '__main__':

    path = np.loadtxt('test.txt_spiral_0.txt')
    p = PathSmoother()




