import copy
import math

import pyclipper

#import test_module
import numpy

#####
# 获取当前文件所在目录
from suFabEngine.PathOptimizer.Polyline import *
from suFabEngine.PathOptimizer.VtkAdaptor import *
from suFabEngine.PathOptimizer.argregin import *
from suFabEngine.PathOptimizer.Erroe import *
from suFabEngine.PathOptimizer.GeomAIgo import *
from suFabEngine.PathOptimizer.SplitRegion import *
from suFabEngine.PathOptimizer.Utility import *
from suFabEngine.PathOptimizer.build_connect_tree import *
#####
class GenDpPath:
    def __init__(self, polygons, interval, angle, O, no_split_region):#O means Original
        self.polygons, self.interval, self.angle = polygons, interval, angle
        self.splitPolys = []
        self.constinterval = interval
        self.ys1list=[]
        self.offsetflag = 0 #用来解决本来只有两个交点但是偏置后就有多个交点的问题
        self.startpoint = Point3D(float('-inf'), float('-inf'))
        self.endpoint = Point3D(float('-inf'), float('-inf'))
        self.O = O
        self.no_split = no_split_region

    def generate(self):
        rotPolys = GeomAIgo.rotatePolygons(self.polygons, -self.angle)
        self.splitPolys = splitRegion(rotPolys, self.interval)#有改动
        ys = self.genScanYs(rotPolys)
        paths = []
        a=-1
        for poly in self.splitPolys:
            a = a+1
            ys1 = self.genScanYs([poly]) #对于一个polyline不能构成一个list 加上[]
            if len(ys1)!= 0 and abs(ys1[0]-ys[0])<=1e-5:
                ys1.insert(0,ys1[0]-self.interval+1e-5)
            remainder = len(ys1) % 8
            splitymax = float('-inf')
            spacing_increment = 0.0
            for point in poly.points:
                splitymax = max(splitymax, point.y)
            if len(ys1)>=1 and (remainder==1 or remainder==3 or remainder==5 or remainder==7.):
                ys1.pop()

            #if(len(ys1) >= 2):
            #    spacing_increment = (splitymax - ys1[len(ys1) - 1]) / len(ys1)
            #    for i in range(len(ys1)):
            #        ys1[i] = ys1[i] + i * spacing_increment
            ysleft=[]
            ysright=[]
            n=int(len(ys1)/8)
            self.interval = self.interval + spacing_increment
            for i in range(0, n + 1):
                if 0 + 8 * i <= len(ys1) - 1:
                    ysleft.append(ys1[0 + 8 * i])
                if 3 + 8 * i <= len(ys1) - 1:
                    ysleft.append(ys1[3 + 8 * i])
                if 4 + 8 * i <= len(ys1) - 1:
                    ysleft.append(ys1[4 + 8 * i])
                if 7 + 8 * i <= len(ys1) - 1:
                    ysleft.append(ys1[7 + 8 * i])
                if 1 + 8 * i <= len(ys1) - 1:
                    ysright.append(ys1[1 + 8 * i])
                if 2 + 8 * i <= len(ys1) - 1:
                    ysright.append(ys1[2 + 8 * i])
                if 5 + 8 * i <= len(ys1) - 1:
                    ysright.append(ys1[5 + 8 * i])
                if 6 + 8 * i <= len(ys1) - 1:
                    ysright.append(ys1[6 + 8 * i])

            remainderL = (len(ysleft)) % 4
            remainderR = (len(ysright)) % 4

            if((remainderL==0 and remainderR==0) or (remainderL == 2 and remainderR == 2)): #第一种情况
                # reverse list
                segsL = genHatchesL0([poly], ysleft,self.interval,self.angle )
                segsR = genHatchesR0([poly], ysright,self.interval,self.angle)
                # segL = sorted(segsL, reverse=True) 重载<符号才能
               # segs = genHatches([poly], ys) 非连续路径
            #if((remainderL==1 and remainderR==0) or(remainderL==3 and remainderR==2)):
                #segsL = genHatchesL1([poly], ysleft,self.interval)
                #segsR = genHatchesR1([poly], ysright,self.interval)
            if ((remainderL == 1 and remainderR == 1) or (remainderL == 3 and remainderR == 3)):
                segsL = genHatchesL2([poly], ysleft,self.interval,self.angle)
                segsR = genHatchesR2([poly], ysright,self.interval,self.angle)
            #if ((remainderL == 1 and remainderR == 2) or (remainderL == 3 and remainderR == 0)):
               # segsL = genHatchesL3([poly], ysleft,self.interval)
                #segsR = genHatchesR3([poly], ysright,self.interval)

            #if (remainderL == 2 and remainderR == 2):
                #segsL = genHatchesL0([poly], ysleft,self.interval)
                #segsR = genHatchesR0([poly], ysright,self.interval)

            if len(segsL) > 0:
                pathL = self.linkLocalHatches(segsL,poly) #得到两条路径再合在一起！！！
                pathR = self.linkLocalHatches(segsR, poly)
                if (abs(pathL.points[len(pathL.points) - 1].x - segsL[len(segsL) - 1].B.x) <= 1e-12 and abs(
                        pathL.points[len(pathL.points) - 1].y - segsL[len(segsL) - 1].B.y) <= 1e-12):
                    PeekPoints = self.IsHavePeekR(pathR.points[len(pathR.points) - 1],pathL.points[len(pathL.points) - 1],poly)
                    if PeekPoints != None:
                        for i in range(len(PeekPoints)-1,-1,-1):
                            pathL.addPoint(PeekPoints[i])
                if (abs(pathL.points[len(pathL.points) - 1].x - segsL[len(segsL) - 1].A.x) <= 1e-12 and abs(
                        pathL.points[len(pathL.points) - 1].y - segsL[len(segsL) - 1].A.y) <= 1e-12):
                    PeekPoints = self.IsHavePeekL(pathL.points[len(pathL.points) - 1],pathR.points[len(pathR.points) - 1], poly)
                    if PeekPoints != None:
                        for PeekPoint in PeekPoints:
                            pathL.addPoint(PeekPoint)
                PeekPoints1 = self.IsHavePeekR(pathL.points[0], pathR.points[0],poly)
                path=Polyline()
                for i in range(pathL.count()):
                    path.points.append(pathL.points[i])
                for i in range(pathR.count()-1,-1,-1):
                    path.points.append(pathR.points[i])
                if PeekPoints1 != None:
                    for i in range(len(PeekPoints1) - 1, -1, -1):
                        path.addPoint(PeekPoints1[i])
                path.belongtowhichpoly = a
                #va = VtkAdaptor()
                #for curve in splitCurve:
                #va.drawPolyline(path).GetProperty().SetColor(1, 0, 0)
                paths.append(path)
            self.interval = self.interval - spacing_increment
        return GeomAIgo.rotatePolygons(paths, self.angle)

    #def get_clip_region(self, split_region):

    #    clipper, ca = Pyclipper(), ClipperAdaptor()
    #    clipper.AddPaths(ca.toPaths(self.total_offset), pyclipper.PT_SUBJECT)  ##有改动
    #    clipper.AddPaths(ca.toPaths(self.total_split), pyclipper.PT_CLIP)
    #    sln = clipper.Execute(pyclipper.CT_DIFFERENCE)
    #    testPolys = ca.toPolys(sln, split_region[0].points[0].z)
        #va = VtkAdaptor()

        #for o in testPolys:
        #    va.drawPolyline(o).GetProperty().SetColor(0, 0, 1)

        #for o in self.total_offset:
        #    va.drawPolyline(o).GetProperty().SetColor(0, 0.5, 0.5)
    #    for poly in testPolys:
    #        temp = test_module.Polyline_trans_tuple(split_region[0])
    #        if pyclipper.PointInPolygon((poly.centroid().x*10000, poly.centroid().y*10000, poly.centroid().z*10000), list(temp))==1:
                #va.drawPolyline(poly).GetProperty().SetColor(1, 0, 0)
                #va.drawPolyline(split_region[0]).GetProperty().SetColor(0, 0, 1)
                #va.display()
    #            return poly

                #va.drawPolyline(poly).GetProperty().SetColor(1, 0, 0)
                #va.display()

        #va.drawPolyline(split_region[0]).GetProperty().SetColor(1, 0, 0)

        #va.display()

        #va = VtkAdaptor()

#        #for o in testPolys:
         #   va.drawPolyline(o).GetProperty().SetColor(0, 0, 1)
#        for o in self.total_offset:
#            va.drawPolyline(o).GetProperty().SetColor(0, 0.5, 0.5)

#        va.drawPolyline(split_region[0]).GetProperty().SetColor(1, 0, 0)

        #clipper, ca = Pyclipper(), ClipperAdaptor()
        #clipper.AddPaths(ca.toPaths(self.total_offset), pyclipper.PT_SUBJECT)  ##有改动
        #clipper.AddPaths(ca.toPaths(testPolys), pyclipper.PT_CLIP)
        #sln = clipper.Execute(pyclipper.CT_DIFFERENCE)
        #result_testPolys = ca.toPolys(sln, split_region[0].points[0].z)
        #i= 0
        #for i in range(len(result_testPolys)):
        #i = i+0.1

        #va.display()

        #result_testPolys.sort(key=lambda poly: pyclipper.Area(test_module.Polyline_trans_tuple(poly)))######记住这种写法
        #c = va.drawPolyline(result_testPolys[-1])
        #c.GetProperty().SetColor(1 - i, 1 - i, 1 - i)
        #c.GetProperty().SetLineWidth(5)
        #va.display()

    def generate1(self):
        #rotPolys = GeomAIgo.rotatePolygons(self.polygons, -self.angle)#有改动
        ys = self.genScanYs(self.polygons)
        paths = []
        a=-1
        for poly in self.polygons:
            a=a+1
            ys1 = self.genScanYs([poly]) #对于一个polyline不能构成一个list 加上[]
            if len(ys1)!=0 and abs(ys1[0]-ys[0])<=1e-5:
                ys1.insert(0, ys1[0]-self.interval+1e-5)
            remainder = len(ys1) % 8
            splitymax = float('-inf')
            spacing_increment = 0.0
            for point in poly.points:
                splitymax = max(splitymax, point.y)
            if len(ys1) >= 1 and (remainder == 1 or remainder == 3 or remainder == 5 or remainder == 7):
                ys1.pop()
            #if(len(ys1) >= 2):

            #    spacing_increment = (splitymax - ys1[len(ys1) - 1]) / len(ys1)

            #    for i in range(len(ys1)):

            #        ys1[i] = ys1[i] + i * spacing_increment
            ysleft=[]
            ysright=[]
            n = int(len(ys1)/8)
            self.interval = self.interval + spacing_increment
            for i in range(0, n + 1):
                if 0 + 8 * i <= len(ys1) - 1:
                    ysleft.append(ys1[0 + 8 * i])
                if 3 + 8 * i <= len(ys1) - 1:
                    ysleft.append(ys1[3 + 8 * i])
                if 4 + 8 * i <= len(ys1) - 1:
                    ysleft.append(ys1[4 + 8 * i])
                if 7 + 8 * i <= len(ys1) - 1:
                    ysleft.append(ys1[7 + 8 * i])
                if 1 + 8 * i <= len(ys1) - 1:
                    ysright.append(ys1[1 + 8 * i])
                if 2 + 8 * i <= len(ys1) - 1:
                    ysright.append(ys1[2 + 8 * i])
                if 5 + 8 * i <= len(ys1) - 1:
                    ysright.append(ys1[5 + 8 * i])
                if 6 + 8 * i <= len(ys1) - 1:
                    ysright.append(ys1[6 + 8 * i])

            remainderL = (len(ysleft)) % 4
            remainderR = (len(ysright)) % 4

            if((remainderL==0 and remainderR==0) or (remainderL == 2 and remainderR == 2)): #第一种情况
                # reverse list
                segsL = genHatchesL0([poly], ysleft,self.interval,self.angle )
                segsR = genHatchesR0([poly], ysright,self.interval,self.angle)
                # segL = sorted(segsL, reverse=True) 重载<符号才能
               # segs = genHatches([poly], ys) 非连续路径
            #if((remainderL==1 and remainderR==0) or(remainderL==3 and remainderR==2)):
                #segsL = genHatchesL1([poly], ysleft,self.interval)
                #segsR = genHatchesR1([poly], ysright,self.interval)
            if ((remainderL == 1 and remainderR == 1) or (remainderL == 3 and remainderR == 3)):
                segsL = genHatchesL2([poly], ysleft,self.interval,self.angle)
                segsR = genHatchesR2([poly], ysright,self.interval,self.angle)
            #if ((remainderL == 1 and remainderR == 2) or (remainderL == 3 and remainderR == 0)):
               # segsL = genHatchesL3([poly], ysleft,self.interval)
                #segsR = genHatchesR3([poly], ysright,self.interval)

            #if (remainderL == 2 and remainderR == 2):
                #segsL = genHatchesL0([poly], ysleft,self.interval)
                #segsR = genHatchesR0([poly], ysright,self.interval)

            if len(segsL) > 0:
                pathL = self.linkLocalHatches(segsL, poly)  #得到两条路径再合在一起！！！

                pathR = self.linkLocalHatches(segsR, poly)

                if (abs(pathL.points[len(pathL.points) - 1].x - segsL[len(segsL) - 1].B.x) <= 1e-12 and abs(
                        pathL.points[len(pathL.points) - 1].y - segsL[len(segsL) - 1].B.y) <= 1e-12):
                    PeekPoints = self.IsHavePeekR(pathR.points[len(pathR.points) - 1], pathL.points[len(pathL.points) - 1], poly)
                    if PeekPoints != None:
                        for i in range(len(PeekPoints)-1,-1,-1):
                            pathL.addPoint(PeekPoints[i])
                if (abs(pathL.points[len(pathL.points) - 1].x - segsL[len(segsL) - 1].A.x) <= 1e-12 and abs(
                        pathL.points[len(pathL.points) - 1].y - segsL[len(segsL) - 1].A.y) <= 1e-12):
                    PeekPoints = self.IsHavePeekL(pathL.points[len(pathL.points) - 1], pathR.points[len(pathR.points) - 1],  poly)
                    if PeekPoints != None:
                        for PeekPoint in PeekPoints:
                            pathL.addPoint(PeekPoint)
                PeekPoints1 = self.IsHavePeekR(pathL.points[0], pathR.points[0],poly)
                path=Polyline()
                for i in range(pathL.count()):
                    path.points.append(pathL.points[i])

                for i in range(pathR.count()-1,-1,-1):
                    path.points.append(pathR.points[i])

                if PeekPoints1 != None:
                    for i in range(len(PeekPoints1) - 1, -1, -1):
                        path.addPoint(PeekPoints1[i])
                #va = VtkAdaptor()
                #va.drawPolyline(path).GetProperty().SetColor(1, 0, 0)
                #va.display()
                path.belongtowhichpoly = a
                path.points.reverse()

                paths.append(path)
                self.ys1list.extend(ys1)
            self.interval = self.interval - spacing_increment
        return GeomAIgo.rotatePolygons(paths, self.angle), self.ys1list

    def generate2(self):
        # rotPolys = GeomAIgo.rotatePolygons(self.polygons, -self.angle)#有改动
        q = argregin.ArgRegion(self.no_split, self.constinterval, 1e-6)
        ys = q.ys
        paths = []
        a = -1
        for i in range(len(self.polygons)):
            temp123 = copy.deepcopy(i)
            y = i
            #if i == 20:
            #    print("assaasr")
            poly = self.polygons[i]
            for i in range(len(self.O)):
                if self.O[i] == poly:
                    a = i

            if poly.error_poly == 1:
                path = copy.deepcopy(poly)
                path.belongtowhichpoly = a
                path.points.pop()
                # path.points.reverse()
                paths.append(path)
                continue

            #try:
                #if len(self.total_split)!=0:
                    #offset_poly = self.get_clip_region([poly])
            #    offset_poly = self.contouroffset(poly)
                #else:
                #    offset_poly = self.total_offset[0]

            #except Small as s:
            #    s.msg  = "子区域太小了，无法生成连续zigzag，原因是无法偏置一次"
            #    print(s)
            #    path = copy.deepcopy(poly)
            #    path.belongtowhichpoly = a
                #path.points.reverse()

            #except Pocket as p:
            #    print(p)

            # 对于一个polyline不能构成一个list 加上[]
            #poly = self.Re_big(offset_poly, self.constinterval-0.05)
            #ip_Sweep = q.calcHatchPoints([poly], q.ys)

            #if len(ip_Sweep)<=1:
            #    path = copy.deepcopy(poly)
            #    path.belongtowhichpoly = a
            #    path.points.pop()
                # path.points.reverse()
            #    paths.append(path)
            #    continue

            ys1 = q.get_ys(poly)
            ys1.sort()
            self.get_y_min_and_y_max(poly)
            L = self.get_left_right_offset_segments(poly, 0)
            R = self.get_left_right_offset_segments(poly, 1)
            L = self.line_offset(L)
            R = self.line_offset(R)
            L = self.reduce_repeated_points(L)
            R = self.reduce_repeated_points(R)
            #L.points.pop()
            #R.points.pop()
            #if temp123 == 20:
            #    va = VtkAdaptor()
            #    for y in ys1:
            #        seg = Segment(Point3D(-10+90, y, poly.points[0].z), Point3D(10+120, y, poly.points[0].z))
            #        va.drawSegment(seg).GetProperty().SetColor(1, 0, 0)
            #    va.drawPolyline(poly).GetProperty().SetColor(1, 0, 0)
            #    va.drawPolyline(L).GetProperty().SetColor(0, 0, 1)
            #    va.drawPolyline(R).GetProperty().SetColor(0, 1, 0)
            #    va.display()

            #build_connect_tree.path_show([poly])
            #if len(ys1) != 0 and abs(ys1[0] - ys[0]) <= 1e-5:
            #    ys1.insert(0, ys1[0] - self.interval + 1e-5)
            remainder = len(ys1) % 8
            splitymax = float('-inf')
            spacing_increment = 0.0
            for point in poly.points:
                splitymax = max(splitymax, point.y)
            if len(ys1) >= 1 and (remainder == 1 or remainder == 3 or remainder == 5 or remainder == 7.):
                X_distance = {}
                for i in (0, -1):
                    ipses = calcHatchPoints([poly], [ys1[i]])
                    X_distance[i] = abs(ipses[0][1].x - ipses[0][0].x)
                X_distance = sorted(X_distance.items(), key=lambda x : x[1])
                ys1.pop(X_distance[0][0])
            #if (len(ys1) >= 2):

            #    spacing_increment = (splitymax - ys1[len(ys1) - 1]) / len(ys1)

            #    for i in range(len(ys1)):
            #        ys1[i] = ys1[i] + i * spacing_increment
            ysleft = []
            ysright = []
            n = int(len(ys1) / 8)
            self.interval = self.interval + spacing_increment
            for i in range(0, n + 1):
                if 0 + 8 * i <= len(ys1) - 1:
                    ysleft.append(ys1[0 + 8 * i])
                if 3 + 8 * i <= len(ys1) - 1:
                    ysleft.append(ys1[3 + 8 * i])
                if 4 + 8 * i <= len(ys1) - 1:
                    ysleft.append(ys1[4 + 8 * i])
                if 7 + 8 * i <= len(ys1) - 1:
                    ysleft.append(ys1[7 + 8 * i])
                if 1 + 8 * i <= len(ys1) - 1:
                    ysright.append(ys1[1 + 8 * i])
                if 2 + 8 * i <= len(ys1) - 1:
                    ysright.append(ys1[2 + 8 * i])
                if 5 + 8 * i <= len(ys1) - 1:
                    ysright.append(ys1[5 + 8 * i])
                if 6 + 8 * i <= len(ys1) - 1:
                    ysright.append(ys1[6 + 8 * i])

            remainderL = (len(ysleft)) % 4
            remainderR = (len(ysright)) % 4

            if ((remainderL == 0 and remainderR == 0) or (remainderL == 2 and remainderR == 2)):  # 第一种情况
                # reverse list
                segsL = genHatchesL0([poly], ysleft, self.interval, self.angle)
                segsR = genHatchesR0([poly], ysright, self.interval, self.angle)
                # segL = sorted(segsL, reverse=True) 重载<符号才能
            # segs = genHatches([poly], ys) 非连续路径
            # if((remainderL==1 and remainderR==0) or(remainderL==3 and remainderR==2)):
            # segsL = genHatchesL1([poly], ysleft,self.interval)
            # segsR = genHatchesR1([poly], ysright,self.interval)
            if ((remainderL == 1 and remainderR == 1) or (remainderL == 3 and remainderR == 3)):
                segsL = genHatchesL2([poly], ysleft, self.interval, self.angle)
                segsR = genHatchesR2([poly], ysright, self.interval, self.angle)
            # if ((remainderL == 1 and remainderR == 2) or (remainderL == 3 and remainderR == 0)):
            # segsL = genHatchesL3([poly], ysleft,self.interval)
            # segsR = genHatchesR3([poly], ysright,self.interval)

            # if (remainderL == 2 and remainderR == 2):
            # segsL = genHatchesL0([poly], ysleft,self.interval)
            # segsR = genHatchesR0([poly], ysright,self.interval)

            if len(segsL) > 0:
                #va = VtkAdaptor()
                #for seg in segsL:
                #    va.drawSegment(seg).GetProperty().SetColor(0, 0, 1)
                #for seg2 in segsR:
                #    va.drawSegment(seg2).GetProperty().SetColor(1, 0, 0)
                #va.drawPolyline(poly).GetProperty().SetColor(0, 0,0)
                #va.display()
                pathL = self.linkLocalHatches(segsL, poly, L, R, ys1)# 得到两条路径再合在一起！！！
                #va = VtkAdaptor()
                #va.drawPolyline(poly).GetProperty().SetColor(1, 0, 1)
                #va.display()
                pathR = self.linkLocalHatches(segsR, poly, L, R, ys1)
                #va1 = VtkAdaptor()
                # va1.drawPolyline(pathL).GetProperty().SetColor(0, 0, 1)
                #va1.drawPolyline(pathR).GetProperty().SetColor(1, 0, 0)
                # va1.drawPolyline(offset_poly).GetProperty().SetColor(0, 0, 1)
                # va1.drawPolyline(poly).GetProperty().SetColor(1, 0.5, 1)
                #va1.display()

                if (abs(pathL.points[len(pathL.points) - 1].x - segsL[len(segsL) - 1].B.x) <= 1e-12 and abs(
                        pathL.points[len(pathL.points) - 1].y - segsL[len(segsL) - 1].B.y) <= 1e-12):
                    PeekPoints = self.IsHavePeekR(pathR.points[len(pathR.points) - 1],
                                                  pathL.points[len(pathL.points) - 1], poly)
                    if PeekPoints != None:
                        for i in range(len(PeekPoints) - 1, -1, -1):
                            pathL.addPoint(PeekPoints[i])
                if (abs(pathL.points[len(pathL.points) - 1].x - segsL[len(segsL) - 1].A.x) <= 1e-12 and abs(
                        pathL.points[len(pathL.points) - 1].y - segsL[len(segsL) - 1].A.y) <= 1e-12):
                    PeekPoints = self.IsHavePeekL(pathL.points[len(pathL.points) - 1],
                                                  pathR.points[len(pathR.points) - 1], poly)
                    if PeekPoints != None:
                        for PeekPoint in PeekPoints:
                            pathL.addPoint(PeekPoint)
                PeekPoints1 = self.IsHavePeekR(pathL.points[0], pathR.points[0], poly)
                path = Polyline()

                for i in range(pathL.count()):
                    path.points.append(pathL.points[i])
                for i in range(pathR.count() - 1, -1, -1):
                    path.points.append(pathR.points[i])
                if PeekPoints1 != None:
                    for i in range(len(PeekPoints1) - 1, -1, -1):
                        path.addPoint(PeekPoints1[i])
                # va = VtkAdaptor()
                # va.drawPolyline(path).GetProperty().SetColor(1, 0, 0)
                # va.display()
                if (self.startpoint.y < pathL.points[-1].y):
                    self.startpoint = pathL.points[-1]
                    self.endpoint = pathR.points[-1]
                else:
                   pass

                path.belongtowhichpoly = a
                path.points.reverse()
                paths.append(path)
                for y in ys1:
                    if y not in self.ys1list:
                        self.ys1list.append(y)
                self.ys1list.sort()

            self.interval = self.interval - spacing_increment
        return GeomAIgo.rotatePolygons(paths, self.angle), self.ys1list, self.startpoint, self.endpoint

    def reduce_repeated_points(self,polygon):
        "这个函数改变了输入"
        temp = []
        for point in polygon.points:
            if point not in temp:
                temp.append(point)
        polygon.points = temp
        polygon.points.append(polygon.points[0])
        return polygon

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

    def get_y_min_and_y_max(self, poly):
        poly.y_min = float("inf")
        poly.y_max = float("-inf")
        for point in poly.points:
            if point.y <= poly.y_min:
                poly.y_min = point.y
            if point.y >= poly.y_max:
                poly.y_max = point.y

    def get_left_right_offset_segments(self, poly,L_R_flag = 0):
        y_min = []
        y_max = []
        for point in poly.points:
            if point.y == poly.y_min:
                y_min.append(point)
            if point.y == poly.y_max:
                y_max.append(point)
        y_min.sort(key=lambda x: x.x)
        y_max.sort(key=lambda x: x.x)
        temp = Polyline()
        original = copy.deepcopy(poly)
        if L_R_flag == 0:
            original.points.pop()
            original.points = build_connect_tree.replaceL(build_connect_tree.findindex(y_max[0], original), original.points)
            for i in range(len(original.points)):
                if original.points[i] != y_min[0]:
                    temp.points.append(original.points[i])
                else:
                    temp.points.append(original.points[i])
                    break
        else:
            original.points.pop()
            original.points = build_connect_tree.replaceL(build_connect_tree.findindex(y_min[-1], original), original.points)
            for i in range(len(original.points)):
                if original.points[i] != y_max[-1]:
                    temp.points.append(original.points[i])
                else:
                    temp.points.append(original.points[i])
                    break

        return temp

    def caculatetheta(self,P2:Point3D,P1:Point3D):#P2 默认在P1上面
        if(abs(P2.x - P1.x) >= 1e-6):
            theta = math.atan((P2.y - P1.y) / (P2.x - P1.x))
        else:
            theta=math.pi * 0.5

        return theta
    def peekpointsoffsetR(self,PeekPoint,theta1,theta2):
        deg1 = radToDeg(theta1)
        deg2 = radToDeg(theta2)
        if(theta1<0 and theta2>0):
            theta1=abs(theta1)

        elif(theta1<0 and theta2<0):
            theta1=theta1+math.pi
            theta2=abs(theta2)
            deg1=radToDeg(theta1)
            deg2=radToDeg(theta2)
        elif(theta1>0 and theta2>0):
            theta1=math.pi-theta1
            deg1 = radToDeg(theta1)
            deg2 = radToDeg(theta2)
        elif(theta1>0 and theta2<0):
            theta2=abs(theta2)
            deg1 = radToDeg(theta1)
            deg2 = radToDeg(theta2)

        degtotal=radToDeg((theta1 + theta2) * 0.5)
        PeekPoint.x = PeekPoint.x - (
                self.interval / abs(math.sin((theta1 + theta2) * 0.5)))

        return PeekPoint.x
    def peekpointsoffsetL(self,PeekPoint,theta1,theta2):
        deg1 = radToDeg(theta1)
        deg2 = radToDeg(theta2)
        if(theta1<0 and theta2>0):
            theta1=abs(theta1)

        elif(theta1<0 and theta2<0):
            theta1=theta1+math.pi
            theta2=abs(theta2)
            deg1=radToDeg(theta1)
            deg2=radToDeg(theta2)
        elif(theta1>0 and theta2>0):
            theta1=math.pi-theta1
            deg1 = radToDeg(theta1)
            deg2 = radToDeg(theta2)
        elif(theta1>0 and theta2<0):
            theta2=abs(theta2)
            deg1 = radToDeg(theta1)
            deg2 = radToDeg(theta2)

        degtotal = radToDeg((theta1 + theta2) * 0.5)
        PeekPoint.x = PeekPoint.x + (
                self.interval / abs(math.sin((theta1 + theta2) * 0.5)))

        return PeekPoint.x

    def linternaloffset(self, theta1, P1):
        if (theta1 != math.pi * 0.5):
            P1.x = P1.x + (self.interval / abs(math.sin(theta1)))
        else:
            P1.x = P1.x + self.interval
        return P1.x
    def rinternaloffset(self,theta1,P1):
        if (theta1 != math.pi * 0.5):
            P1.x = P1.x - (self.interval / abs(math.sin(theta1)))
        else:
            P1.x = P1.x - self.interval
        return P1.x
    def peektheta(self,PeekPoints2):
        thetai2 = []
        if (len(PeekPoints2) == 1):
            return thetai2
        else:
            for i in range(len(PeekPoints2)):
                if (i != len(PeekPoints2) - 1):
                    thetai = self.caculatetheta(PeekPoints2[i + 1], PeekPoints2[i])
                    thetai2.append(thetai)
            return thetai2

    def linkLocalHatches(self, segs, polys, L,R,ys1): ###判断最后一条线是左线还是右线
        poly = Polyline()

        for i, seg in enumerate(segs):
            poly.addPoint(seg.B if (i % 2 == 0)else seg.A)
            poly.addPoint(seg.A if(i % 2 == 0)else seg.B)#LINK LOCAK
            #if len(polys.points) == 115:
            #   va = VtkAdaptor()
            #    c = va.drawPolyline(polys)
            #    c1 = va.drawPolyline(poly)
                #c2 = va.drawPolyline(offset_poly)
            #    c.GetProperty().SetColor(0, 0, 1)
                # c.GetProperty().SetLineWidth(2)
            #    c1.GetProperty().SetColor(1, 0, 0)
                # c1.GetProperty().SetLineWidth(2)
                #c2.GetProperty().SetColor(1, 0.5, 0)
                # c2.GetProperty().SetLineWidth(2)

            #    va.display()

            if (i != len(segs) - 1):
                if (i % 2 == 0):
                    if (abs(segs[i + 1].A.y - poly.points[poly.count() - 1].y - self.interval) >= 1e-5):
                        PeekPoints = self.IsHavePeekL(poly.points[poly.count() - 1], segs[i + 1].A, polys)
                    else:
                        segs[i + 1].A.x = segs[i + 1].A.x
                        poly.points[poly.count() - 1].x = poly.points[poly.count() - 1].x
                        #PeekPoints_1 = self.IsHavePeekL(poly.points[poly.count() - 1], segs[i + 1].A, polys, 1)
                        #PeekPoints_1.reverse()
                        #poly_l = Polyline()
                        #poly_l.points.append(L.points[0])
                        #for j in range(1, len(L.points)):
                        #    poly_l.points.append(L.points[j])
                        #    if abs(poly_l.points[-1].y - poly_l.points[-2].y) < 1e-7 and (
                        #            poly_l.points[-1] not in PeekPoints_1 and poly_l.points[-2] not in PeekPoints_1):
                        #        if PeekPoints_1[0] in poly_l.points and PeekPoints_1[-1] in poly_l.points:
                        #            break
                        #        poly_l.points.clear()
                        #        poly_l.points.append(L.points[j])

                        #p_L = self.line_offset(poly_l)
                        #va = VtkAdaptor()
                        #for y in ys1:
                        #    seg = Segment(Point3D(-10 + 90, y, poly.points[0].z),
                        #                  Point3D(10 + 120, y, poly.points[0].z))
                        #    va.drawSegment(seg).GetProperty().SetColor(0, 0, 0)
                        #va.drawPolyline(polys).GetProperty().SetColor(1, 0, 0)
                        #va.drawPolyline(p_L).GetProperty().SetColor(0, 0, 1)
                        #va.drawPolyline(R).GetProperty().SetColor(0, 1, 0)
                       # va.display()

                        #real_p = []
                        #for point in PeekPoints:
                        #    if poly.points[poly.count() - 1].y <= point.y <= segs[i + 1].A.y:
                        #        real_p.append(point)
                        #PeekPoints = real_p

                        #这一步是用来处理最上层和最下层如果没有

                        #if len(polys2) == 0:
                         #   errorpoly = Polyline()
                          #  return errorpoly
                        #else:

                        #if len(polys.points)==18:
                            #A=Polyline()
                            #A.points.extend([Point3D(-5,poly.points[poly.count() - 1].y),Point3D(40,poly.points[poly.count() - 1].y)])

                         #   va = VtkAdaptor()
                          #  va.drawPolyline(A).GetProperty().SetColor(0, 0, 0)
                           # va.drawPolyline(polys1).GetProperty().SetColor(1, 0, 1)
                           # va.drawPolyline(polys).GetProperty().SetColor(1, 0, 0)
                           # va.display()

                        ips1 = calcHatchPoints([L], [poly.points[poly.count() - 1].y])
                        ips2 = calcHatchPoints([L], [segs[i+1].A.y])
                        ips2[0].sort(key=lambda x: x.x)
                        ips1[0].sort(key=lambda x: x.x)
                        segs[i + 1].A.x = ips2[0][-1].x
                        segs[i + 1].A.y = ips2[0][-1].y
                        poly.points[poly.count() - 1].x = ips1[0][-1].x
                        poly.points[poly.count() - 1].y = ips1[0][-1].y
                        PeekPoints = self.IsHavePeekR(poly.points[poly.count() - 1], segs[i + 1].A, L)

                else:
                    if (abs(segs[i + 1].B.y - poly.points[poly.count() - 1].y - self.interval) >= 1e-5):
                        PeekPoints = self.IsHavePeekR(poly.points[poly.count() - 1], segs[i + 1].B, polys)
                    else:
                        segs[i + 1].B.x = segs[i + 1].B.x
                        poly.points[poly.count() - 1].x = poly.points[poly.count() - 1].x
                        #PeekPoints_1 = self.IsHavePeekR(poly.points[poly.count() - 1], segs[i + 1].B, polys, 1)

                        #poly_r = Polyline()
                        #poly_r.points.append(R.points[0])
                        #for j in range(1, len(R.points)):
                        #    poly_r.points.append(R.points[j])
                        #    if abs(poly_r.points[-1].y - poly_r.points[-2].y) < 1e-7 and (poly_r.points[-1] not in PeekPoints_1 and poly_r.points[-2] not in PeekPoints_1):
                        #        if PeekPoints_1[0] in poly_r.points and PeekPoints_1[-1] in poly_r.points:
                        #            break
                        #        poly_r.points.clear()
                        #        poly_r.points.append(R.points[j])

                        #p_R = self.line_offset(poly_r)

                        #real_p = []
                        #for point in PeekPoints:
                        #    if poly.points[poly.count() - 1].y <= point.y <= segs[i + 1].B.y:
                        #        real_p.append(point)
                        #PeekPoints = real_p

                        #if len(polys4) == 0:
                         #   errorpoly = Polyline()
                          #  return errorpoly
                        #else:
                        #if len(polys.points)==82:
                        #    A = Polyline()
                        #    A.points.extend([Point3D(-40, poly.points[poly.count() - 1].y),
                                             #Point3D(20, poly.points[poly.count() - 1].y)])
                        #    B = Polyline()
                        #    B.points.extend([Point3D(-40, segs[i + 1].A.y),
                                             #Point3D(20, segs[i + 1].A.y)])

                        #    va = VtkAdaptor()
                        #    va.drawPolyline(A).GetProperty().SetColor(0, 0, 0)
                        #    va.drawPolyline(B).GetProperty().SetColor(0, 0, 0)

                        #    va.drawPolyline(polys3).GetProperty().SetColor(1, 0, 1)
                        #    va.drawPolyline(polys).GetProperty().SetColor(1, 0, 1)
                        #    va.display()

                        ips3 = calcHatchPoints([R], [poly.points[poly.count() - 1].y])
                        ips4 = calcHatchPoints([R], [segs[i + 1].B.y])
                        ips4[0].sort(key=lambda x: x.x)
                        ips3[0].sort(key=lambda x: x.x)
                        segs[i + 1].B.x = ips4[0][0].x
                        segs[i + 1].B.y = ips4[0][0].y
                        poly.points[poly.count() - 1].x = ips3[0][0].x
                        poly.points[poly.count() - 1].y = ips3[0][0].y
                        PeekPoints = self.IsHavePeekL(poly.points[poly.count() - 1], segs[i + 1].B, R)

                if PeekPoints != None and len(PeekPoints)!=0:
                    for PeekPoint in PeekPoints:
                        poly.addPoint(PeekPoint)
                    #if len(polys.points)==115:
                        #va = VtkAdaptor()
                        #c = va.drawPolyline(polys)
                        #c1 = va.drawPolyline(poly)
                        #c2 = va.drawPolyline(offset_poly)
                        #c.GetProperty().SetColor(0, 0, 1)
                        #c.GetProperty().SetLineWidth(2)
                        #c1.GetProperty().SetColor(1, 0, 0)
                        #c1.GetProperty().SetLineWidth(2)
                        #c2.GetProperty().SetColor(1, 0.5, 0)
                        # c2.GetProperty().SetLineWidth(2)
                        #va.display()

                    #print("2")
        return poly

    def check_remove(self, poly_list:list):
        pass

    def line_offset(self, lines, dig=7):
        cofficient = math.pow(10, dig)
        contourtuple = []
        for point in lines.points:
            var_tuple = (round(point.x * cofficient), round(point.y * cofficient))
            contourtuple.append(var_tuple)
        contourtuple = tuple(contourtuple)
        pco = pyclipper.PyclipperOffset()
        pco.AddPath(contourtuple, pyclipper.JT_SQUARE, pyclipper.ET_OPENBUTT)
        solution = pco.Execute(self.constinterval * cofficient)
        # if len(solution)==0:
        #   return solution
        polys1 = Polyline()
        for i in range(len(solution)):
            solution[i] = numpy.array(solution[i]) / cofficient
            solution[i] = solution[i].tolist()

        if len(solution) == 0:

            raise Small("the lines errot")
        for j in range(len(solution[0])):
            point = Point3D(solution[0][j][0], solution[0][j][1], lines.points[0].z)
            polys1.points.append(point)
        polys1.points.append(polys1.points[0])

        return polys1

    def Re_big(self, poly, interval, dig = 7):
        cofficient = math.pow(10, 7)
        contourtuple = []
        for point in poly.points:
            var_tuple = (round(point.x * cofficient), round(point.y * cofficient))
            contourtuple.append(var_tuple)
        contourtuple = tuple(contourtuple)
        pco = pyclipper.PyclipperOffset()
        pco.AddPath(contourtuple, pyclipper.JT_SQUARE, pyclipper.ET_CLOSEDPOLYGON)
        solution = pco.Execute(interval * cofficient)
        polys1 = Polyline()
        for i in range(len(solution)):
            solution[i] = numpy.array(solution[i]) / cofficient
            solution[i] = solution[i].tolist()
        if len(solution) == 0:
            raise Small("big wrong")
        for j in range(len(solution[0])):
            point = Point3D(solution[0][j][0], solution[0][j][1], poly.points[0].z)
            polys1.points.append(point)
        polys1.points.append(polys1.points[0])

        return polys1

    def contouroffset(self, splitpoly:Polyline):
        #build_connect_tree.path_show([splitpoly])
        #self.offsetflag = 0
        cofficient = 10000
        contourtuple = []
        for point in splitpoly.points:
            var_tuple = (round(point.x * cofficient), round(point.y * cofficient))
            contourtuple.append(var_tuple)
        contourtuple = tuple(contourtuple)
        pco = pyclipper.PyclipperOffset()
        pco.AddPath(contourtuple, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
        solution = pco.Execute(-self.constinterval * cofficient)
        #if len(solution)==0:
        #   return solution
        polys1 = Polyline()
        #solution = numpy.array(solution)/cofficient
        #solution = solution.tolist()
        polylist = []
        #else:
        #############################################下面代码为改进代码的一部分
        for i in range(len(solution)):
            solution[i] = numpy.array(solution[i])/cofficient
            solution[i] = solution[i].tolist()
        ##############################################bug会在这里出现
        if len(solution) == 0:
            #print("a")
            raise Small("the single poly too narrow can not offset one time")
        #if len(solution) > 1:
        #    raise Pocket("the poly have the pocket and after offsetting,the poly divide into two polys")
        for i in range(len(solution)):
            polys1 = Polyline()
            for j in range(len(solution[i])):
                point = Point3D(solution[i][j][0], solution[i][j][1],  splitpoly.points[0].z)
                polys1.points.append(point)
            polys1.points.append(polys1.points[0])
            polylist.append(polys1)
        disdir = {}
        if len(solution)>1:

                #va = VtkAdaptor()
                for poly in polylist:
                    disdir[poly.centroid().distance(splitpoly.centroid())] = poly
                #for a in disdir.items():#可以取出，但是不能迭代。
                #    i =a#items可以用list（）转换成list items(),keys(),values()都一样
                tmp = sorted(disdir.items(), key=lambda item: item[0])#DIC的item返回的是一个list包含着键值对组成的tuple
                disdir = dict(tmp)

                #va.drawPolyline(disdir[list(disdir.keys())[0]]).GetProperty().SetColor(0, 0, 1)

                #va.drawPolyline(splitpoly).GetProperty().SetColor(1, 0, 0)
                #va.display()
                return disdir[list(disdir.keys())[0]]
                #build_connect_tree.path_show(polylist)

        return polys1

    def IsHavePeekL(self, prep, nextp, polys: Polyline,flag = 0):

        #if (abs(prep.x - (0.4004001))<1e-8) and (abs(prep.y - (10.800399489622))<1e-6) :#此方法不考虑prep 和 nextp 刚好在轮廓顶点的情况
        #    print("woc")
        temp_poly = copy.deepcopy(polys)
        peekpointL = []
        temp_poly.points.reverse()
        x3 = prep.x
        y3 = prep.y
        x4 = nextp.x
        y4 = nextp.y
        min_sp = float("inf")
        min_sn = float("inf")
        start_index = None
        end_index = None
        start_point = Point3D(float("inf"), float("inf"))
        end_point = None
        #计算左边的点的话，将轮廓暂时调整为顺时针
        for i in range(len(temp_poly.points)-1):
            x1 = temp_poly.points[i].x
            y1 = temp_poly.points[i].y
            x2 = temp_poly.points[i + 1].x
            y2 = temp_poly.points[i + 1].y
            if (x1 == x3 and y1 == y3) or (x2 == x3 and y2 == y3):
                print("error pre")
            if (x1 == x4 and y1 == y4) or (x2 == x4 and y2 == y4):
                print("error nex")
            sprep = 0.5 * (x1 * y2 + x2 * y3 + x3 * y1 - x1 * y3 - x2 * y1 - x3 * y2)
            snextp = 0.5 * (x1 * y2 + x2 * y4 + x4 * y1 - x1 * y4 - x2 * y1 - x4 * y2)

            if abs(sprep) <= 1e-3:
                "這個的0.004001和0.004001的誤差來源於交點的計算，沒辦法"
                if ((min(x1, x2) < x3 or abs(min(x1, x2) - x3) <= 1e-6) and (
                        max(x1, x2) > x3 or abs(max(x1, x2) - x3) <= 1e-6)) and (
                        (min(y1, y2) < y3 or abs(min(y1, y2) - y3) <= 1e-6) and (
                        max(y1, y2) > y3 or abs(max(y1, y2) - y3) <= 1e-6)):
                    if min_sp > abs(sprep):
                        min_sp = abs(sprep)
                        start_point = temp_poly.points[i] if temp_poly.points[i].y < temp_poly.points[i + 1].y else \
                            temp_poly.points[i + 1]

            if abs(snextp) <= 1e-3:
                if ((min(x1, x2) < x4 or abs(min(x1, x2) - x4) <= 1e-6) and (
                        max(x1, x2) > x4 or abs(max(x1, x2) - x4) <= 1e-6)) and (
                        (min(y1, y2) < y4 or abs(min(y1, y2) - y4) <= 1e-6) and (
                        max(y1, y2) > y4 or abs(max(y1, y2) - y4) <= 1e-6)):
                    if min_sn > abs(snextp):
                        min_sn = abs(snextp)
                        end_point = temp_poly.points[i] if temp_poly.points[i].y > temp_poly.points[i + 1].y else \
                        temp_poly.points[i + 1]

        temp_poly.points.pop()
        if start_point.x == float("inf"):
            print("dfsdf")
        if end_point is None:
            print("a")

        temp_poly.points = build_connect_tree.replaceL(build_connect_tree.findindex(start_point, temp_poly), temp_poly.points)
        end_index = build_connect_tree.findindex(end_point, temp_poly)
        if flag==0:
            for i in range(1, end_index):
                peekpointL.append(temp_poly.points[i])

        else:
            for i in range(0, end_index+1):
                peekpointL.append(temp_poly.points[i])

        return peekpointL

    def IsHavePeekR(self, prep, nextp, polys, flag=0):
        temp_poly = copy.deepcopy(polys)
        peekpointR = []
        x3 = prep.x
        y3 = prep.y
        x4 = nextp.x
        y4 = nextp.y
        min_sp = float("inf")
        min_sn = float("inf")
        start_index = None
        end_index = None
        start_point = None
        end_point = None
        # 计算左边的点的话，将轮廓暂时调整为顺时针
        for i in range(len(temp_poly.points) - 1):
            x1 = temp_poly.points[i].x
            y1 = temp_poly.points[i].y
            x2 = temp_poly.points[i + 1].x
            y2 = temp_poly.points[i + 1].y
            if (x1 == x3 and y1 == y3) or (x2 == x3 and y2 == y3):
                print("error pre")
            if (x1 == x4 and y1 == y4) or (x2 == x4 and y2 == y4):
                print("error nex")
            sprep = 0.5 * (x1 * y2 + x2 * y3 + x3 * y1 - x1 * y3 - x2 * y1 - x3 * y2)
            snextp = 0.5 * (x1 * y2 + x2 * y4 + x4 * y1 - x1 * y4 - x2 * y1 - x4 * y2)

            if abs(sprep) <= 1e-3:
                if ((min(x1, x2) < x3 or abs(min(x1, x2) - x3) <= 1e-6) and (
                        max(x1, x2) > x3 or abs(max(x1, x2) - x3) <= 1e-6)) and (
                        (min(y1, y2) < y3 or abs(min(y1, y2) - y3) <= 1e-6) and (
                        max(y1, y2) > y3 or abs(max(y1, y2) - y3) <= 1e-6)):
                    if min_sp > abs(sprep):
                        min_sp = abs(sprep)
                        start_point = temp_poly.points[i] if temp_poly.points[i].y < temp_poly.points[i + 1].y else \
                            temp_poly.points[i + 1]
                #if len(temp_poly.points)==69:
                #    va = VtkAdaptor()
                #    va.drawPolyline(polys).GetProperty().SetColor(0, 0, 1)
                #    va.drawPoint(temp_poly.points[i]).GetProperty().SetColor(1, 0, 0)
                #    va.drawPoint(temp_poly.points[i + 1]).GetProperty().SetColor(1, 0, 0)
                #    va.display()

            if abs(snextp) <= 1e-3:
                if ((min(x1, x2) < x4 or abs(min(x1, x2) - x4) <= 1e-6) and (
                        max(x1, x2) > x4 or abs(max(x1, x2) - x4) <= 1e-6)) and (
                        (min(y1, y2) < y4 or abs(min(y1, y2) - y4) <= 1e-6) and (
                        max(y1, y2) > y4 or abs(max(y1, y2) - y4) <= 1e-6)):
                    if min_sn > abs(snextp):
                        min_sn = abs(snextp)
                        end_point = temp_poly.points[i] if temp_poly.points[i].y > temp_poly.points[i + 1].y else \
                        temp_poly.points[i + 1]
        temp_poly.points.pop()
        if start_point is None:
            print("dfsdf")

            #build_connect_tree.path_show([polys])
        temp_poly.points = build_connect_tree.replaceL(build_connect_tree.findindex(start_point, temp_poly),
                                                       temp_poly.points)
        end_index = build_connect_tree.findindex(end_point, temp_poly) #在bunny 0.1 27.504中有bug
        if flag==0:
            for i in range(1, end_index):
                peekpointR.append(temp_poly.points[i])
        else:
            for i in range(0, end_index+1):
                peekpointR.append(temp_poly.points[i])

        return peekpointR

def caculate_offset_point_l(point, PeekPoints, interval, flag):
    if flag==1:#第一个点：
        vector_f = PeekPoints[0].pointTo(PeekPoints[1])
    else:
        vector_f = PeekPoints[-2].pointTo(PeekPoints[-1])

    normal_v = Vector3D(vector_f.dy, -vector_f.dx)
    if vector_f.crossProduct(normal_v).normalized().dz > 0:
        normal_v = Vector3D(-vector_f.dy, vector_f.dx)
    theta = vector_f.getAngle2D()
    offset = 1 / (math.sin(theta) / interval)
    if normal_v.dotProduct(Vector3D(1,0,0))>0:
        point.x = point.x + offset
    else:
        point.x = point.x - offset

def caculate_offset_peek(PeekPoints, interval):
    offset_peek = []
    for i in range(len(PeekPoints)-2):
        pre = PeekPoints[i].pointTo(PeekPoints[i+1])
        next = PeekPoints[i+1].pointTo(PeekPoints[i+2])
        angle = pre.getAngle(next)
        angle = math.pi - angle
        length = 1/(math.sin((angle/2))/interval)
        vector1 = PeekPoints[i].pointTo(PeekPoints[i+1]).normalized()
        vector2 = PeekPoints[i+2].pointTo(PeekPoints[i+1]).normalized()
        direction = vector1 + vector2
        direction = direction.normalized()
        offset_peek.append(PeekPoints[i+1] + direction.amplified(length))
    return offset_peek

def caculate_offset_point_r(point, PeekPoints, interval, flag):
    if flag==1:#第一个点：
        vector_f = PeekPoints[0].pointTo(PeekPoints[1])
    else:
        vector_f = PeekPoints[-2].pointTo(PeekPoints[-1])
    normal_v = Vector3D(vector_f.dy, -vector_f.dx)
    if vector_f.crossProduct(normal_v).normalized().dz < 0:
        normal_v = Vector3D(-vector_f.dy, vector_f.dx)
    theta = vector_f.getAngle2D()
    offset = 1 / (math.sin(theta) / interval)
    if normal_v.dotProduct(Vector3D(1, 0, 0)) > 0:
        point.x = point.x + offset
    else:
        point.x = point.x - offset

def genDpPath(polygons, interval, angle):
    return GenDpPath(polygons, interval, angle).generate()
def genDpPath1(polygons, interval, angle):
    return GenDpPath(polygons, interval, angle).generate1()

def genDpPath2(polygons, interval, angle, Original,ys):

    return GenDpPath(polygons, interval, angle, Original, ys).generate2()
