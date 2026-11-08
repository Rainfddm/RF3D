import copy
import itertools
import numpy as np
import pyclipper
from pyclipper import *

#####
# 获取当前文件所在目录

from suFabEngine.PathOptimizer.GeomBase import *
from suFabEngine.PathOptimizer.Line import *
from suFabEngine.PathOptimizer.GeomAIgo import *
from suFabEngine.PathOptimizer.Polyline import *
from suFabEngine.PathOptimizer.ClipperAdaptor import *
from suFabEngine.PathOptimizer.VtkAdaptor import *
from suFabEngine.PathOptimizer.GenHatch import *
#####

class Tree:
    def __init__(self, Contour: Polyline, interval):
        self.root = Node(Contour)
        self.interval = interval
        self.Total_ys = self.To_Intersect_ys(self.root)

    def Build_Spt_Tree(self, root):
        pass

    #找到轮廓之间的总的扫描线
    def To_Intersect_ys(self, root):
        ys, yMin, yMax = [], float('inf'), float('-inf')
        for pt in root.data.points:
            yMin, yMax = min(yMin, pt.y), max(yMax, pt.y)
        y = yMin + self.interval
        while yMax - y >= 1e-10:
            ys.append(y)
            y += self.interval
        ys.sort(reverse=1)
        return ys

class Node:
    def __init__(self, Contour: Polyline,total_ys):
        self.data = Contour
        self.numP = {} #该轮廓节点ys扫描线与其与轮廓的交点。
        self.rtp = None #该轮廓节点真正的凹峰点 只有一个。
        self.child = [] #该轮廓节点分割后的子节点其中child[0]永远是最上面那个
        self.ys = []#该轮廓节点的扫描线
        self.total_ys = total_ys#总轮廓的总扫描线

    def get_ys(self):  # 在总ys中抽取每个轮廓中的扫描线
        yMin, yMax = float('inf'), float('-inf')
        for pt in self.data.points:
            yMin, yMax = min(yMin, pt.y), max(yMax, pt.y)
        front = -1
        behind = -1
        for i in range(len(self.total_ys)):
            if yMax - self.total_ys[i] >= 1e-10:
                front = i
                break
        if front != -1:
            for j in range(len(self.total_ys) - 1, front, -1):  # 从len(total_ys)-1开始到front为止，不包括front的整数。
                if self.total_ys[j] - yMin >= 1e-10:
                    behind = j
                    break
            if behind == -1:
                self.ys = self.total_ys[front]
        else:
            self.ys = []
        self.ys = self.total_ys[front:behind + 1]

    # calculate the numbers of the intersection point
    def get_ips(self):
        segs = []
        ipses = []
        poly = self.data
        for i in range(poly.count() - 1):
            seg = Segment(poly.point(i), poly.point(i + 1))
            seg.yMin = min(seg.A.y, seg.B.y)
            seg.yMax = max(seg.A.y, seg.B.y)
            segs.append(seg)
        segs.sort(key=lambda seg: seg.yMin)
        k, sweep = 0, SweepLine()
        for y in self.ys:
            for i in range(len(sweep.segs) - 1, -1, - 1):
                if sweep.segs[i].yMax < y:
                    del sweep.segs[i]
            for i in range(k, len(segs)):
                if segs[i].yMin < y and segs[i].yMax >= y:
                    sweep.segs.append(segs[i])
                elif segs[i].yMin >= y:
                    k = i
                    break
            resultList = []
            for item in sweep.segs:
                if not item in resultList:
                    resultList.append(item)
            sweep.segs = resultList
            if len(sweep.segs) > 0:
                ips = sweep.intersect(y)
                self.numP[y] = len(ips)
                ipses.append(ips)
        return ipses

    def Check_contour(self): #检测结点轮廓需不需要分割，如果为1不需要分割。
        ipses = self.get_ips()
        for ips in ipses:
            if len(ips) != 2:
                return 0
        return 1

    def findTurnPoints(self):  # 计算轮廓凹峰点
        vx = Vector3D(1, 0, 0)
        turnPts = []
        for i in range(self.data.count() - 1):
            pts = self.data.points
            v1 = pts[-2 if (i == 0) else (i - 1)].pointTo(pts[i])
            v2 = pts[i].pointTo(pts[i + 1])
            if v1.crossProduct(vx).dz * v2.crossProduct(vx).dz <= 0:
                if v1.crossProduct(v2).dz < 0:
                    turnPts.append(pts[i])

        return turnPts

    def findLRPoints(self, pt, ptses):
        for pts in ptses:
            if len(pts) > 0 and pts[0].y == pt.y:
                for i in range(len(pts) - 1):
                    if pt.x > pts[i].x and pt.x < pts[i + 1].x:
                        return pts[i], pts[i + 1]
        return None, None

    def get_turnPoint(self, root):
        pass

class SplitRegion:
    def __init__(self, polygons, interval, adjustPolyDirs = False):
        self.interval = interval
        self.polygons = polygons
        self.ys = self.outputys()
        if adjustPolyDirs:
            adjustPolygonDirs(self.polygons)
        self.splitPolygons = self.split()

    def add(self,x, y):
        p0c0 = 0, {}
        p1c0 = 1, {}
        p0c1 = 0, {}
        p1c1 = 1, {}

        # 各进程状态之间的转换
        p0c0[1].update({(0, 0): p0c0, (1, 0): p1c0,
                        (0, 1): p1c0, (1, 1): p0c1})
        p1c0[1].update({(0, 0): p0c0, (1, 0): p1c0,
                        (0, 1): p1c0, (1, 1): p0c1})
        p0c1[1].update({(0, 0): p1c0, (1, 0): p0c1,
                        (0, 1): p0c1, (1, 1): p1c1})
        p1c1[1].update({(0, 0): p1c0, (1, 0): p0c1,
                        (0, 1): p0c1, (1, 1): p1c1})

        x = map(int, reversed(x))
        y = map(int, reversed(y))
        z = []
        # 模拟自动机
        value, transition = p0c0
        for r, s in itertools.zip_longest(x, y, fillvalue=0):
            value, transition = transition[r, s]
            z.append(value)

        z.append(transition[0, 0][0])
        z.reverse()
        return z

    def genScanYs(self, polygons):
        yuzhi = 1e-9
        ys, yMin, yMax =[], float('inf'), float('-inf')
        for poly in polygons:
            for pt in poly.points:
             yMin, yMax = min(yMin, pt.y), max(yMax, pt.y)
        y = yMin + self.interval
        while yMax - y >= 1e-10:
            ys.append(y)
            y += self.interval
        return ys

    def jugdegturnPoints(self, polygons, ys):
        segs = []
        for poly in polygons:
            for i in range(poly.count() - 1):
                seg = Segment(poly.point(i), poly.point(i + 1))
                seg.yMin = min(seg.A.y, seg.B.y)
                seg.yMax = max(seg.A.y, seg.B.y)
                segs.append(seg)
        segs.sort(key=lambda seg: seg.yMin)
        k, sweep = 0, SweepLine()
        ipses = []
        ipi = {}
        for y in ys:
            for i in range(len(sweep.segs) - 1, -1, - 1):
                if sweep.segs[i].yMax < y:
                    del sweep.segs[i]
            for i in range(k, len(segs)):
                if segs[i].yMin < y and segs[i].yMax >= y:
                    sweep.segs.append(segs[i])
                elif segs[i].yMin >= y:
                    k = i
                    break
            resultList = []
            for item in sweep.segs:
                if not item in resultList:
                    resultList.append(item)
            sweep.segs = resultList
            if len(sweep.segs) > 0:
                ips = sweep.intersect(y)
                # if len(ips)>2:
                #    ips.sort(key=lambda x:x.x)
                #    ips=[ips[0],ips[-1]]
                # if len(ips)<2:
                #    ips.sort(key=lambda x:x.x)
                #    ips=[ips[0],ips[-1]]
        return ips

    def OutputYs(self):
        return self.genScanYs(self.polygons)
    def selecttpt(self, turnPts):
        realturnpt=[]
        y = self.genScanYs(self.polygons)
        if len(turnPts) != 0:
            tempturnpt = copy.deepcopy(turnPts)
            for pt in tempturnpt:
                y.sort(key=lambda p: abs(p-pt.y))
                if (y[0] < pt.y and y[1] < pt.y) or (y[0] > pt.y and y[1] > pt.y): ##判断凹峰点在上方或者下方没有扫描线的情况下是否为合理的凹峰点
                    if len(self.jugdegturnPoints(self.polygons, [y[0]])) == 2:
                        turnPts.remove(pt)
                else:
                    if len(self.jugdegturnPoints(self.polygons, [y[0]])) == len(
                            self.jugdegturnPoints(self.polygons, [y[1]])): #有可能需要加上一个等于== 2
                        turnPts.remove(pt)

        real = copy.deepcopy(turnPts)
        y.sort()
        if len(real) != 0:
            real.sort(key=lambda p: p.y)
            realturnpt.append(real[0])
            for i in range(1, len(real)):
                if abs(real[i].y - realturnpt[-1].y) >= 2e-6:
                    realturnpt.append(real[i])
        #for i in range(len(y)-1):
        #    for pt1 in real:
        #        if pt1.y<y[i+1] and pt1.y>y[i]:
        #            temp.append(pt1)
        #    if len(temp) != 0:
        #        realturnpt.append(temp[0])
        #        temp.clear()

        return realturnpt

    def checkminpoly(self,polygons):
        test = []
        yMin, yMax = float('inf'), float('-inf')
        for poly in polygons:
            for pt in poly.points:
                yMin, yMax = min(yMin, pt.y), max(yMax, pt.y)
                dis = yMax - yMin
            test.append(dis)
            test.sort()
        return test[0]

    def list_to_Str(self, z: list):
        result = str(int(z[0]))
        for i in range(1, len((z))):
            result = result + str(int(z[i]))
        return result

    def split(self):
        testPolyslist = []
        testdis = []
        turnPts = self.findTurnPoints()
        turnPts = self.selecttpt(turnPts)
        if len(turnPts) != 0:
            ys = []
            for pt in turnPts:
                ys.append(pt.y)
            ys.sort()
            hatchPtses = calcHatchPoints(self.polygons, ys)
            splitters = []
            for i in range(len(turnPts)):
                lPt, rPt = self.findLRPoints(turnPts[i], hatchPtses)
                if lPt is not None and rPt is not None:
                    splitter = self.createSplitter(lPt, rPt)
                    splitters.append(splitter)
            if len(splitters) != 0:
                #########################################################
                clipper, ca = pyclipper(), ClipperAdaptor()
                clipper.AddPaths(ca.toPaths(self.polygons), pyclipper.PT_SUBJECT)  ##有改动
                clipper.AddPaths(ca.toPaths(splitters), pyclipper.PT_CLIP)
                sln = clipper.Execute(pyclipper.CT_DIFFERENCE)
                a = ca.toPolys(sln, turnPts[0].z)
                return a
        return self.polygons

    def split_test(self):
        testPolyslist = []
        testdis = []
        turnPts = self.findTurnPoints()
        turnPts = self.selecttpt(turnPts)
        if len(turnPts) !=0:
            ys=[]
            for pt in turnPts:
                ys.append(pt.y)
            ys.sort()
            hatchPtses = calcHatchPoints(self.polygons, ys)
            splitters = []
            init = np.zeros((1, len(turnPts)))
            up = np.zeros((1, len(turnPts)))
            up[0][-1] = 1
            inits = self.list_to_Str(init[0])
            ups = self.list_to_Str(up[0])
            flages = np.empty((pow(2, len(turnPts)), len(turnPts)))
            flages[0] = init[0]
            for i in range(1, pow(2, len(turnPts))):
                flages[i] = self.add(inits, ups)[1:]  # 选出list中的一部分
                inits = self.list_to_Str(self.add(inits, ups)[1:])
            for flags in flages:
                for i in range(len(turnPts)):
                    lPt, rPt = self.findLRPoints(turnPts[i], hatchPtses)
                    if lPt is not None and rPt is not None:
                        flag = flags[i]
                        if flag == 1:
                            splitter = self.createSplitter(turnPts[i], rPt)
                            splitters.append(splitter)
                        if flag == 0:
                            splitter = self.createSplitter(lPt, turnPts[i])
                            splitters.append(splitter)

                if len(splitters) != 0:
                    ##################################################
                    clipper, ca = pyclipper(), ClipperAdaptor()
                    clipper.AddPaths(ca.toPaths(self.polygons), pyclipper.PT_SUBJECT)  ##有改动
                    clipper.AddPaths(ca.toPaths(splitters), pyclipper.PT_CLIP)
                    sln = clipper.Execute(pyclipper.CT_DIFFERENCE)
                    testPolys = ca.toPolys(sln, turnPts[0].z)
                    splitters.clear()

                    testdis.append(self.checkminpoly(testPolys))
                    testPolyslist.append(testPolys)
                    #va = VtkAdaptor()
                    #for poly in testPolyslist[testdis.index(max(testdis))]:
                    #    va.drawPolyline(poly).GetProperty().SetColor(1, 0, 0)
                    #va.display()

            return testPolyslist[testdis.index(min(testdis))]

        return self.polygons

    def outputys(self):
        publiceys=[]
        turnPts = self.findTurnPoints()
        turnPts = self.selecttpt(turnPts)
        if len(turnPts) != 0:
            ys = []
            for pt in turnPts:
                ys.append(pt.y)
            ys.sort()
            hatchPtses = calcHatchPoints(self.polygons, ys)
            for turnPt in turnPts:
                lPt, rPt = self.findLRPoints(turnPt, hatchPtses)
                if lPt is not None and rPt is not None:
                    publiceys.append(lPt.y)
        publiceys.sort()
        return publiceys

    def findTurnPoints(self):
        vx = Vector3D(1, 0, 0)
        turnPts = []
        for poly in self.polygons:
            for i in range(poly.count()-1):
                pts = poly.points
                v1 = pts[-2 if (i == 0) else(i-1)].pointTo(pts[i])
                v2 = pts[i].pointTo(pts[i+1])
                if v1.crossProduct(vx).dz * v2.crossProduct(vx).dz <=0:
                    if v1.crossProduct(v2).dz <0:
                        turnPts.append(pts[i])
        return turnPts

    def findLRPoints(self, pt, ptses):
        for pts in ptses:
            if len(pts) >0 and pts[0].y == pt.y:
                for i in range(len(pts)-1):
                    if pt.x > pts[i].x and pt.x < pts[i+1].x:
                        return pts[i], pts[i+1]
        return None ,None
    def createSplitter(self,p1,p2,delta =1e-6):#
        vx, vy = Vector3D(1,0,0),Vector3D(0,1,0)
        splitter = Polyline()
        splitter.addPoint(p1 - vx.amplified(delta)-vy.amplified(delta))
        splitter.addPoint(p2 + vx.amplified(delta)- vy.amplified(delta))
        splitter.addPoint(p2+vx.amplified(delta)+vy.amplified(delta))
        splitter.addPoint(p1-vx.amplified(delta)+vy.amplified(delta))
        splitter.addPoint(splitter.startPoint())
        return splitter
def splitRegion(polygons,interval,adjustPolyDirs = False):
        return SplitRegion(polygons, interval,adjustPolyDirs).splitPolygons
