import time
import torch
from sklearn.neighbors import NearestNeighbors
from sklearn.neighbors import KDTree

#####
# 获取当前文件所在目录
from suFabEngine.PathOptimizer.CSS import *
from suFabEngine.PathOptimizer.VtkAdaptor import *
from suFabEngine.PathOptimizer.build_connect_tree import *  ###原path_show

import numpy as np

import matplotlib.pyplot as plt 

losses = [] 

class optimizer:

    def __init__(self, total, path_length, num_boundary, interval, radius):
        self.oPL = path_length
        self.path = total[:path_length]
        self.oT = total
        self.interval = interval
        self.radius = radius
        self.boundary = []
        self.num_path = None
        self.num_boundary = num_boundary
        self.total = None
        self.Phat = None
        self.Pstar = None
        self.X = None
        self.num_path = self.path.shape[0]
        for index in self.num_boundary:
            # organize each segment of boudary with each length in num_boundary
            self.boundary.append(self.oT[self.oPL:self.oPL + index])
            self.oPL = self.oPL+index

    def init_segment(self):
        tensor_start_list = []
        tensor_end_list = []
        tensor_direction_list = []
        segment_start = torch.clone(self.path)
        segment_end = torch.roll(segment_start, dims=0, shifts=-1)
        boundary_start = self.boundary[0].clone()
        boundary_end = torch.roll(boundary_start, dims=0, shifts=-1)
        for i in range(1, len(self.boundary)):
            temp_bs = torch.clone(self.boundary[i])
            temp_be = torch.roll(temp_bs, dims=0, shifts=-1)
            boundary_start = torch.cat((boundary_start, temp_bs), dim=0)
            boundary_end = torch.cat((boundary_end, temp_be), dim=0)

        for i in range(self.path.shape[0]):
            if i == 0:
                delete_index = [self.path.shape[0]-1, i]
            else:
                delete_index = [i - 1, i]
            temp_seg_start = torch.index_select(segment_start, 0, torch.tensor(list(set([ i for i in range(self.path.shape[0])]) - set(delete_index))))
            temp_seg_end = torch.index_select(segment_end, 0, torch.tensor(
                list(set([i for i in range(self.path.shape[0])]) - set(delete_index))))
            temp_seg_start = torch.cat((temp_seg_start, boundary_start), dim=0)
            temp_seg_end = torch.cat((temp_seg_end, boundary_end), dim=0)
            tensor_start_list.append(temp_seg_start)
            tensor_end_list.append(temp_seg_end)
            tensor_direction_list.append(temp_seg_end-temp_seg_start)
        return torch.stack(tensor_start_list), torch.stack(tensor_end_list), torch.stack(tensor_direction_list)

    def square_distance(slef, src, dst):
        """
        Calculate Euclid distance between each two points.

        src^T * dst = xn * xm + yn * ym + zn * zm；
        sum(src^2, dim=-1) = xn*xn + yn*yn + zn*zn;
        sum(dst^2, dim=-1) = xm*xm + ym*ym + zm*zm;
        dist = (xn - xm)^2 + (yn - ym)^2 + (zn - zm)^2
             = sum(src**2,dim=-1)+sum(dst**2,dim=-1)-2*src^T*dst

        Input:
            src: source points, [B, N, C]
            dst: target points, [B, M, C]
        Output:
            dist: per-point square distance, [B, N, M]
        """
        B, N, _ = src.shape
        _, M, _ = dst.shape
        dist = -2 * torch.matmul(src, dst.permute(0, 2, 1))
        dist += torch.sum(src ** 2, -1).view(B, N, 1)
        dist += torch.sum(dst ** 2, -1).view(B, 1, M)
        return dist

    def ball_query(self, radius, nsamples, xyzs, new_xyz):
        """
            Input:
                radius: local region radius
                nsample: max sample number in local region
                xyz: all points, [B, N, 3], but here xyzs is a list?
                new_xyz: query points, [B, S, 3]
            Return:
                group_idx: grouped points index, [B, S, nsample]
            """        
        # save start and end point of segments
        segment_start = []
        segment_end = []
        # Loop over current point clouds
        for i in range(len(xyzs)):
            xyz = xyzs[i]
            nsample = nsamples[i]
            
            B, N, C = xyz.shape  # B: Batch size, N: Number of points, C: Number of channel
            _, S, _ = new_xyz.shape # S: Number of ponts in point clouds
            # Creates a tensor group_idx with dimensions [B, S, N], 
            # initially filled with indices of all points.
            group_idx = torch.arange(N, dtype=torch.long).cuda().view(1, 1, N).repeat([B, S, 1])
            # Calculates squared distances between each query point and all other points.
            sqrdists = self.square_distance(new_xyz, xyz)
            # Points further away than radius are marked with N in group_idx.
            group_idx[sqrdists > radius ** 2] = N
            # Sorting and Truncation: 
            # The indices in group_idx are sorted based on distance, 
            # and only the nearest nsample points are kept.
            group_idx = group_idx.sort(dim=-1)[0][:, :, :nsample]
            # Adjusts group_idx for edge cases where there are not enough points within the radius.
            temp_group_idx = group_idx.squeeze()
            # If it's not the first iteration, 
            # it combines the current result with the previous segments.
            if i != 0:
                mask_ = torch.all(torch.eq(temp_group_idx, N * torch.ones(temp_group_idx.shape).cuda()), dim=1)
            group_first = group_idx[:, :, 0].view(B, S, 1).repeat([1, 1, nsample])
            mask = group_idx == N
            group_idx[mask] = group_first[mask]
            group_idx = group_idx.squeeze()
            xyz = xyz.squeeze()
            group_idx_next = group_idx + 1
            mask = group_idx_next >= N
            group_idx_next[mask] = 0
            mask = group_idx == N
            group_idx[mask] = N - 1
            index_start = group_idx.reshape(-1)
            index_end = group_idx_next.reshape(-1)
            start_result = torch.reshape(xyz.index_select(0, index_start), (group_idx.shape[0], group_idx.shape[1], xyz.shape[-1]))
            end_result = torch.reshape(torch.index_select(xyz, 0, index_end),
                                         (group_idx_next.shape[0], group_idx_next.shape[1], xyz.shape[-1]))
            # If it's not the first iteration, 
            # it combines the current result with the previous segments.
            if i != 0:
                start_result[mask_, :, :] = segment_start[0][mask_, :nsample, :]
                end_result[mask_, :, :] = segment_end[0][mask_, :nsample, :]
            segment_start.append(start_result)
            segment_end.append(end_result)
        # Concatenates segment_start and segment_end across all point clouds to get the final results.
        segment_start = torch.cat(segment_start, dim=1)
        segment_end = torch.cat(segment_end, dim=1)
        # Computes the direction of each segment.
        segment_direction = segment_end - segment_start
        return segment_start, segment_end, segment_direction

    def Gen_seg(self):
        temp_path = self.path.unsqueeze(dim=0)
        temp_boundary = []
        temp_boundary.append(temp_path)
        nsamples = []
        if temp_path.shape[1] >= 150:
            nsamples.append(150)
        else:
            nsamples.append(int(temp_path.shape[1]/2))
        for i in range(len(self.boundary)):
            temp_boundary.append(self.boundary[i].unsqueeze(dim=0))
            if self.boundary[i].shape[1]>=10:
                nsamples.append(10)
            else:
                nsamples.append(int(self.boundary[i].shape[1]))

        return self.ball_query(self.radius, nsamples, temp_boundary, temp_path)

    def CacIp(self):
        A, B, v2 = self.Gen_seg()
        AB, N_AB = self.GenAB()
        P2 = A
        P1 = torch.reshape(self.path, (A.shape[0], 1, 3))
        P2diffP1 = P2 - P1
        v1 = torch.reshape(AB, (A.shape[0], 1, 3))
        v1 = v1.expand(-1, v2.shape[1], -1)
        # 注意，全都等于inf的时候，argmin会出错，所以要考虑这种情况。
        self.Phat, mask_Phat = self.CalPoint (P1, P2, v1,    v2, P2diffP1)
        self.Pstar, mask_Pstar = self.CalPoint(P1, P2, (-v1), v2, P2diffP1)
        mask = mask_Pstar + mask_Phat
        return mask

    def show_neighbors(self, prepoint, center, nextpoint):
        va = VtkAdaptor.VtkAdaptor()
        va.showPolyline(self.path).GetProperty().SetColor(0, 0, 1)
        va.showPoint(prepoint).GetProperty().SetColor(1, 0, 1)
        va.showPoint(center).GetProperty().SetColor(0, 0, 1)
        va.showPoint(nextpoint).GetProperty().SetColor(1, 0, 0)
        va.display()

    def CalPoint(self, P1, P2, v1, v2, P2diffP1):
        "caculate the Phat and Pstar"
        denominator = torch.cross(v1, v2)
        denominator_de = torch.norm(denominator, dim=-1) ** 2
        parallel_mask = denominator_de <= 1e-8
        m = torch.cat(
            (torch.unsqueeze(P2diffP1, dim=2), torch.unsqueeze(v2, dim=2), torch.unsqueeze(denominator, dim=2)), dim=2)
        sm = torch.cat(
            (torch.unsqueeze(P2diffP1, dim=2), torch.unsqueeze(v1, dim=2), torch.unsqueeze(denominator, dim=2)), dim=2)
        t = torch.det(m) / denominator_de
        s = torch.det(sm) / denominator_de
        t_mask = t <= 1e-5
        s_mask1 = s <= -1e-5
        s_mask2 = s >= 1+1e-4
        total_mask = t_mask + s_mask1 + s_mask2 + parallel_mask
        ip = P1 + torch.unsqueeze(t, dim=-1) * v1
        distance = torch.norm((ip - P1), dim=-1)
        distance = distance.masked_fill(total_mask, torch.inf)
        inf = torch.inf * torch.ones(distance.shape).cuda()
        mask = torch.all(torch.eq(distance, inf), dim=1)
        result = torch.argmin(distance, dim=-1)
        ips = ip[torch.arange(ip.shape[0]).cuda(), result]
        ips[mask] = self.path[mask] + self.interval*v1[mask][:, 0, :]
        return ips[:, :2], mask

    def is_row_inf(self, tensor, i):
        return torch.all(torch.isinf(tensor[i]))

    def is_row_nan(self, tensor, i):
        return torch.all(torch.isnan(tensor[i]))

    def is_row_zere(self, tensor, i):
        return torch.all(torch.eq(tensor[i], 0))

    def GenAB(self):
        xyz = self.path
        pre = torch.roll(xyz, shifts=-1, dims=0)
        next = torch.roll(xyz, shifts=1, dims=0)
        pre_direction = (pre - xyz) / torch.norm(pre - xyz, dim=-1, keepdim=True)
        next_direction = (next - xyz) / torch.norm(next - xyz, dim=-1, keepdim=True)
        A = (pre_direction + next_direction)
        mask = torch.all(torch.eq(A, torch.zeros(A.shape).cuda()), dim=-1)
        neg_pre = pre_direction.clone()
        neg_pre[:, 1] = neg_pre[:, 1] * -1
        neg_pre[:, [0, 1]] = neg_pre[:, [1, 0]]
        A[mask] = neg_pre[mask]
        AngleBisector = A / torch.norm(A, dim=-1, keepdim=True)
        N_AB = -AngleBisector.clone()

        return AngleBisector, N_AB

    def scale_norm_path(self):
        self.path = torch.from_numpy(self.path)
        up = torch.unsqueeze(self.path, 0)
        up_float32 = up.to(torch.float32)
        layernorm = torch.nn.LayerNorm([up.shape[0], up.shape[1], up.shape[2]])
        self.path = torch.squeeze(layernorm(up_float32))
        self.Visual()

    def scale_norm_total(self):
        pass

    def Visual(self):
        va = VtkAdaptor.VtkAdaptor()
        va.showPolyline(self.path).GetProperty().SetColor(0, 0, 1)
        va.display()

    def Visual_test(self, point, center, point1):
        va = VtkAdaptor.VtkAdaptor()
        va.showPolyline(self.path).GetProperty().SetColor(0, 0, 1)
        va.showPoint(point).GetProperty().SetColor(1, 0, 0)
        va.showPoint(center).GetProperty().SetColor(0, 0, 1)
        va.showPoint(point1).GetProperty().SetColor(1, 0, 1)
        for bound in self.boundary:
            va.showPolyline(bound).GetProperty().SetColor(0, 0, 1)
        va.display()

    def init_kd_tree_radius(self, data):
        kd = NearestNeighbors(radius=self.radius)
        kd.fit(data)
        return kd

    def init_kd_tree(self, data):
        kd = KDTree(data)
        return kd

    def query_neighbours_radius(self, point, tree):
        idx = tree.radius_neighbors(point, sort_results=True)[1][0]
        return idx

    def resample_eqd(self, polygon:torch.tensor):
        "self path is always open"
        next = torch.roll(polygon, dims=0, shifts=-1)
        diff = (next - polygon)
        distance = torch.norm(diff, dim=-1)
        length = torch.sum(distance)
        N = int(length /(self.interval*0.5))
        diff_normal = diff/distance.unsqueeze(-1)
        assert polygon.shape[0] > 0
        resamplepl = torch.zeros((N, 3))
        resamplepl[0] = polygon[0]
        resample_size = length / N
        curr = 0
        dist = 0.0
        i = 1
        while i < N:
            last_dist = distance[curr]
            dist = dist + last_dist
            if dist >= resample_size:
                _d = last_dist - (dist - resample_size)
                cp  = polygon[curr]
                cp1 = next[curr]
                resamplepl[i] = cp + diff_normal[curr]*_d
                i = i + 1
                dist = last_dist - _d
                while dist - resample_size > 1e-10:
                    resamplepl[i] = resamplepl[i-1] + diff_normal[curr]*resample_size
                    dist -= resample_size
                    i = i + 1
            curr = curr + 1
        return resamplepl.to(torch.float64)

    def build_function(self):
        loss = torch.sum((torch.norm(self.X - self.Pstar, dim=-1) - self.interval)**2 + (torch.norm(self.X - self.Phat, dim=-1) - self.interval)**2)
        losses.append(loss.item())  # for draw loss 
        return loss

    def optimize(self, lamada, mask):
        self.X = self.path[:, :2].clone()
        self.path_pre = self.path.clone()  # backup old path
        self.X.requires_grad = True
        
        optimizer = torch.optim.Adam([self.X], lr=lamada)
        # optimizer = torch.optim.SGD([self.X], lr=lamada)
        f = self.build_function()
        optimizer.zero_grad()
        f.backward()
        optimizer.step()

        self.path[:, :2] = self.X.detach()
        self.path[mask] = self.path_pre[mask] # recover path by mask
        self.path = self.path.cpu()
        self.path = self.resample_eqd(self.path)
        self.path = self.path.cuda()

    def start(self, times=10, lamada=0.017):
        start_time = time.time()
        for _ in range(times):
            mask = self.CacIp()
            self.optimize(lamada, mask)
        end_time = time.time()
        total_time = print("One iteration uses: {} seconds".format(end_time - start_time))
        self.path = self.path.cpu()
        return self.path

def optimize_path(connective_path, interval = 0.65, iter_times=10, lamda=0.01):
    
    path = torch.from_numpy(connective_path)
    boundary = path[:3].clone()
    padding_b_vector = torch.zeros((boundary.shape[0], 1))
    boundary = torch.cat((boundary, padding_b_vector), dim=-1)
    
    # Store each length of the out-contours
    boundary_length_list = [boundary.shape[0]]
    
    # Convert 2D to 3D
    padding_vector = torch.zeros((path.shape[0], 1))    
    path = torch.cat((path, padding_vector), dim=-1)
    
    path_length = path.shape[0]
    
    # Concatenating:  path + boundary
    total = torch.cat((path, boundary), dim=0).cuda()
    test = optimizer(total, path_length, boundary_length_list, interval, interval * 4)
    
    return test.start(iter_times, lamda) # iter time & lambda
 