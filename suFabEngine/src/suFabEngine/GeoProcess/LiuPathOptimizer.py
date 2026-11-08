"""
2021/04/26 21:43 版本
跑大的图片速度较慢
"""
import os
import torch
import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial import KDTree, Voronoi
#####
# 获取当前文件所在目录
from suFabEngine.FermatsSpiral import css
#####
#####
#from . import CSS
#from build_connect_tree import path_show
from tqdm import tqdm
#####

losses = []

def show_contour_infor_weather_correct(path_boundary):
    """
    用来测试enhance_contour函数中对于边界提取是否准确
    如果准确，则图像能够正确显示轮廓
    """
    vision_data = path_boundary.numpy()
    plt.scatter(vision_data[:, 0], vision_data[:, 1], s=10)
    plt.plot(vision_data[:, 0], vision_data[:, 1])
    plt.show()

def time_used(func):
    """
    运行时间统计，优化函数时使用
    """

    def func_wrapper(*args, **kwargs):
        from time import time
        time_start = time()
        result = func(*args, **kwargs)
        time_end = time()
        time_spend = time_end - time_start
        print('%s cost time: %.3f s' % (func.__name__, time_spend))
        return result

    return func_wrapper

def calculate_E_distance(div, root_point, point):
    """
    给定一个点和一条角分线，计算其点到直线的距离
    :param root_point: 对应着X，起始点，查询点
    :param div: 角分线向量
    :param point: 直线之外的点
    :return: 返回Phat和Pstar
    """
    a = point - root_point
    b_norm = torch.norm(div)
    c = torch.dot(a, div) * div / (b_norm * b_norm)
    e = a - c
    return torch.norm(e)

def calculate_orientation(prePoint, rootPoint, point):
    """
    计算方向，是位于路径的左边还是右边，使用向量叉乘的方法
    :return:0：位于左边， 1：位于右边
    """
    a = rootPoint - prePoint
    b = point - prePoint
    e = a[0] * b[1] - a[1] * b[0]
    if e > 0:
        return 0
    else:
        return 1

def validation_phat_pstar(pathPoint, pstar, phat):
    """
    用来验证phat和pstar是否符合标准，是否能够找到对应点的可视化绘图
    :return:
    """
    plt.scatter(pathPoint[:, 0], pathPoint[:, 1])
    plt.scatter(pstar[:, 0], pstar[:, 1], s=10)
    plt.scatter(phat[:, 0], phat[:, 1], s=5)
    plt.plot(pathPoint[:, 0], pathPoint[:, 1], linestyle='-', color='blue', linewidth=0.5)
    plt.show()

def resample_eqd(interval, polygon: torch.tensor):
    """self path is always open"""
    next = torch.roll(polygon, dims=0, shifts=-1)
    diff = (next - polygon)
    distance = torch.norm(diff, dim=-1)
    length = torch.sum(distance)
    N = int(length / (interval * 0.5))
    diff_normal = diff / distance.unsqueeze(-1)
    assert polygon.shape[0] > 0
    resamplepl = torch.zeros((N, 2))
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
            cp = polygon[curr]
            cp1 = next[curr]
            resamplepl[i] = cp + diff_normal[curr] * _d
            i = i + 1
            dist = last_dist - _d
            while dist - resample_size > 1e-10:
                resamplepl[i] = resamplepl[i - 1] + diff_normal[curr] * resample_size
                dist -= resample_size
                i = i + 1
        curr = curr + 1
    return resamplepl.to(torch.float64)

class optimizer:
    def __init__(self, path, boundary, interval, weight):
        """
        :param path: 路径信息
        :param boundary: 边界信息
        :param interval: 沉积间距
        :param weight: 偏重指数
        """
        self.loss = None
        self.std_list = None
        self.pstar = None
        self.phat = None
        self.kdTree = None
        self.div_vector = None
        self.root = None
        self.interval = interval
        self.path = path
        self.boundary = boundary
        self.weight = weight
        self.mask = None

    def enhance_contour(self):
        """
        通过最邻近关系查找path中代表轮廓的点，对path进行维度扩展，增加一层mask，若新增加的维度中的值为0则代表为轮廓上的点，如果值为1则代表轮廓内路径上的点。
        优点：在优化时可以直接判断是否对当前点进行优化
        方法为构建了path的KD-Tree，通过遍历搜索轮廓上的最临近点，找到相应的轮廓。此方法对于路径与轮廓重合的情况不适用，因为会出现少许错误的选择的轮廓点
        """
        # 使用KD-Tree进行查找路径中的轮廓点
        self.kdTree = KDTree(self.path)
        temp_point = torch.tensor([])
        path_boundary = []

        for boundary_point in self.boundary:
            dd, ii = self.kdTree.query(boundary_point, k=[1])
            if temp_point.tolist() != self.path[ii][0].tolist():
                temp_point = self.path[ii][0]
                path_boundary.append(self.path[ii][0])

        # 清洗重复点后的路径中的点的边界点
        path_boundary = torch.stack(path_boundary, dim=0)

        # 检查轮廓信息是否准确
        # show_contour_infor_weather_correct(path_boundary)

        # 对于self.path进行维度扩充，增加一层mask
        self.mask = torch.ones((self.path.shape[0], 1))
        for contour_point in path_boundary:
            for i, path_point in enumerate(self.path):
                if contour_point.tolist() == path_point.tolist():
                    self.mask[i] = 0
        self.mask = self.mask.view(-1)  # 展平为一维张量方便后续loss相乘

    def angular_div(self):
        """
        创建角分线
        找到其前驱后继点，使用向量的方法进行创建角分线向量，暂时不考虑转化单位向量
        :return: None
        """
        pre_vector = torch.roll(self.path, 2) - self.path
        sub_vector = torch.roll(self.path, -2) - self.path
        self.div_vector = pre_vector + sub_vector
        self.div_vector = self.div_vector[1:-1]

    def find_phat_pstar(self):
        """
        通过KD-tree的方法进行查找phat和pstar，判断是否为前驱后继，如果不是则考虑为phat和pstar的可能性更高
        先采用所有点遍历寻找，最后乘上mask层，若为轮廓点，则mask层为0，若为内部路径点则mask层为1。
        使用pstar和phat乘以mask层
        :return: phat:0和pstar:1
        """
        self.angular_div()  # 先得到角分线向量，self.div_vector为张量形式
        ball_points = self.kdTree.query_ball_point(self.path, self.interval * 2)  # 获得两倍沉积间距半径的区域
        self.phat = torch.zeros(len(self.path))
        self.pstar = torch.zeros(len(self.path))
        for i, point_list in enumerate(ball_points[1:-1]):  # 去掉开头第一个和最后一个，因为没计算其角分线
            distance_phat = 0
            distance_pstar = 0
            for neighbor_point in point_list:
                if abs(neighbor_point - i) > 2:
                    distance = calculate_E_distance(self.div_vector[i - 1], self.path[i], self.path[neighbor_point])
                    orientation = calculate_orientation(self.path[i - 1], self.path[i], self.path[neighbor_point])
                    if orientation == 0:
                        if distance_phat == 0 or distance < distance_phat:
                            distance_phat = distance
                            self.phat[i] = neighbor_point
                    else:
                        if distance_pstar == 0 or distance < distance_pstar:
                            distance_pstar = distance
                            self.pstar[i] = neighbor_point
            # print(f"第{i}个点:","phat:",self.phat[i], "pstar", self.pstar[i])

        self.pstar = self.path[self.pstar.tolist()]
        self.phat = self.path[self.phat.tolist()]
        # validation_phat_pstar(self.path, self.pstar, self.phat)

    def voronoi_std(self):
        """
        使用泰森多边形方法对整个填充区域进行均匀化，主要使用标准差的方法，对于点到多边形点的欧氏距离计算标准差，最后计算总的标准差的和，目的是点和点之间的距离尽可能的均匀化
        :return:因为计算的是方差所以产生的损失值较小，需要使用系数进行调配，让优化器更加注意到标准差的作用
        """
        vor = Voronoi(self.path)
        vor_point = vor.vertices
        point_list = self.mask
        # 清洗数据点，只计算内部的路径问题

        for i in range(len(self.mask)):
            point_list[i] = point_list[i] * i
            region = vor.regions[vor.point_region[i]]
            for elem in region:
                if elem == -1:
                    point_list[i] = 0
                    break

        std_list = []
        point_list = [int(x) for x in point_list.tolist()]
        for point in point_list:
            if point != 0:
                region = vor.regions[vor.point_region[point]]
                region_points = torch.from_numpy(vor_point[region])
                distances = torch.norm(self.path[point] - region_points, dim=1)
                distance_std = torch.std(distances)
                std_list.append(distance_std)
            else:
                std_list.append(torch.tensor(0, dtype=torch.float64))
        self.std_list = torch.stack(std_list)
        # nonzero_indices = torch.nonzero(self.std_list).squeeze()
        # self.std_list = self.std_list[nonzero_indices]
        # print(self.std_list)

    def loss_function(self):
        """
        :return: loss
        """
        self.loss = torch.sum((torch.norm(self.path - self.pstar, dim=-1) * self.mask - self.interval) ** 2 + (
                torch.norm(self.path - self.phat, dim=-1) * self.mask - self.interval) ** 2)
        # vLoss = torch.sum(self.std_list)
        # print(vLoss)
        # print(torch.log(pLoss) / torch.log(torch.tensor(10-self.weight)), torch.log(vLoss)/torch.log(torch.tensor(self.weight)))
        # self.loss = torch.log(pLoss) / torch.log(torch.tensor(10-self.weight)) + torch.log(vLoss)/torch.log(torch.tensor(self.weight))

        # losses.append(vLoss.item())  # for draw loss
        losses.append(self.loss.item())  # for draw loss
        return self.loss

    def optimize(self, lambada):
        self.path.requires_grad = True
        # 不同的优化器
        optimizer = torch.optim.Adam([self.path], lr=lambada)
        # optimizer = torch.optim.SGD([self.path], lr=lambada)
        # optimizer = torch.optim.Adagrad([self.path], lr=lambada)
        # optimizer = torch.optim.Adadelta([self.path], lr=lambada)
        # optimizer = torch.optim.RMSprop([self.path], lr=lambada, alpha=0.9)

        f = self.loss_function()
        optimizer.zero_grad()
        f.backward()
        optimizer.step()
        self.path = self.path.detach()
        self.path = resample_eqd(self.interval, self.path)

    def run(self, lambada):
        self.enhance_contour()
        # self.voronoi_std()
        self.find_phat_pstar()
        self.optimize(lambada)

    def start(self, times=10, lambada=0.017):
        progress_bar = tqdm(total=times, desc='Training', unit='step', dynamic_ncols=True)

        for _ in range(times):
            self.run(lambada)
            formatted_loss = "{:.2f}".format(self.loss.item())

            # 更新 tqdm 进度条
            progress_bar.set_postfix({'Loss': formatted_loss}, refresh=True)
            progress_bar.update()

    def test(self):
        self.enhance_contour()
        self.find_phat_pstar()
        self.voronoi_std()

def optimize_path(connective_path, boundary=None, interval=0.65, iter_times=10, lamda=0.01):
    path = torch.from_numpy(connective_path)
    boundary = path[:3].clone()
    #padding_b_vector = torch.zeros((boundary.shape[0], 1))
    #boundary = torch.cat((boundary, padding_b_vector), dim=-1)

    # Store each length of the out-contours
    #boundary_length_list = [boundary.shape[0]]

    # Convert 2D to 3D
    #padding_vector = torch.zeros((path.shape[0], 1))
    #path = torch.cat((path, padding_vector), dim=-1)

    path_length = path.shape[0]

    # Concatenating:  path + boundary
    total = torch.cat((path, boundary), dim=0).cuda()
    #op = optimizer(total, path_length, boundary_length_list, interval, interval * 3)

    op = optimizer(path, boundary, interval, weight=1)
    torch.set_printoptions(threshold=float('inf'))

    op.start(iter_times, lamda)  # iter time & lambda
    return op.path

if __name__ == '__main__':
    # 演示数据取自包内 PathOptimizer/test.txt_*.txt，避免硬编码本机路径
    _demo_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "PathOptimizer")
    file_boundary_path = os.path.join(_demo_dir, "test.txt_contour_0.txt")
    # file_boundary_path = 'data\\small.txt_contour_0-0_0.txt'
    # file_path = "data\\small.txt_spiral_0.txt"
    file_path = os.path.join(_demo_dir, "test.txt_spiral_0.txt")
    # file_path = 'cat.txt'
    boundaryData = torch.from_numpy(np.loadtxt(file_boundary_path))
    boundaryData = resample_eqd(interval=4,polygon=boundaryData)

    pathData = torch.from_numpy(np.loadtxt(file_path))
    pathData = resample_eqd(interval=4, polygon=pathData)
    # show_contour_infor_weather_correct(boundaryData)
    path = pathData

    test = optimizer(pathData, boundaryData, interval=4, weight=1.5)
    torch.set_printoptions(threshold=float('inf'))
    # test.test()
    test.start(50, 0.01)

    # 指定要保存的文件路径
    file_path = "star.txt"

    # 将张量写入txt文件
    np.savetxt(file_path, test.path, fmt='%.4f')

    print("优化路径信息已成功写入文件optimize_path_data.txt")
    # 绘图
    # 绘制原始路径
    pathData = CSS.Array_To_polygon(path, 0)
    path_show([pathData])
    # 绘制优化路径
    pathData = CSS.Array_To_polygon(test.path, 0)
    path_show([pathData])

    plt.figure(figsize=(14, 7))
    plt.plot(losses)
    plt.xlabel("Iteration times")
    plt.ylabel("loss")
    plt.show()

    with open('lossesstar.txt', 'w') as f:
        for loss in losses:
            f.write(str(loss) + '\n')