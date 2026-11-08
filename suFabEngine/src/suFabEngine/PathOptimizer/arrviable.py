import numpy
import numpy as np
import random

#####
# 获取当前文件所在目录
from suFabEngine.PathOptimizer.GenDpPath5 import *
from suFabEngine.PathOptimizer.build_connect_tree import *
from suFabEngine.PathOptimizer.Utility import *
from suFabEngine.PathOptimizer.VtkAdaptor import *
from suFabEngine.PathOptimizer.resample import *
#####

class overlap:
    def Equal(f1, f2):
        return (abs(f1 - f2) < 1e-4)

    def PointEqual(p1, p2):
        return (Equal(p1.x, p2.x) and Equal(p1.y, p2.y))

    def PointC(p1, p2):
        return (p1.x > p2.x or (Equal(p1.x, p2.x) and p1.y > p2.y))

    def CrossP(p1, p2):
        return (p1.x * p2.y - p1.y * p2.x)

    def swap(t1, t2):
        return t2, t1

    def overlap(p1, p2, p3, p4):
        if (PointC(p1, p2)):
            p1, p2 = swap(p1, p2)
        if (PointC(p3, p4)):
            p3, p4 = swap(p3, p4)
        # if(PointEqual(p1,p3) and PointEqual(p2,p4)):
        # return 1
        vector1 = Point3D(p2.x - p1.x, p2.y - p1.y)
        vector2 = Point3D(p4.x - p3.x, p4.y - p3.y)
        Cross = CrossP(vector1, vector2)
        if (PointEqual(p1, p3)):
            if (abs(Cross - 0) <= 1e-14):
                return 1
            else:
                return 0
        if (PointEqual(p2, p4)):
            if (abs(Cross - 0) <= 1e-14):
                return 1
            else:
                return 0
        if (PointEqual(p1, p4)):
            return 0
        if (PointEqual(p2, p3)):
            return 0
        if (PointC(p1, p3)):
            p1, p3 = swap(p1, p3)
            p2, p4 = swap(p1, p3)
            vector1, vector2 = swap(vector1, vector2)
            Cross = CrossP(vector1, vector2)

        if (abs(Cross - 0) <= 1e-14):
            vs = Point3D(p3.x - p1.x, p3.y - p1.y)
            if (abs(CrossP(vector1, vs) - 0) <= 1e-14):
                if (PointC(p2, p3)):
                    return 1
            return 0
        return 0
def arrive(countour1:Polyline,countour2:Polyline):
    for i in range(len(countour1.points)-1):
        for j in range(len(countour2.points)-1):
            a = overlap(countour1.points[i], countour1.points[i+1], countour2.points[j], countour2.points[j+1])
            if a == 1:

                return 1
def crp(countour1:Polyline,countour2:Polyline,ys):
    maxy1 = countour1.maxy()
    miny1 = countour1.miny()
    maxy2 = countour2.maxy()
    miny2 = countour2.miny()
    for y in ys:
        if abs(miny1-y)<=2e-5 and abs(maxy2-y)<=2e-5:
            return 1
        if abs(maxy1 - y) <= 2e-5 and abs(miny2 - y) <= 2e-5:
            return 1
    return 0

def findoverlap(countour1:Polyline,countour2:Polyline):
    overlappoints1=[]
    for i in range(len(countour1.points) - 1):
        for j in range(len(countour2.points) - 1):
            a = overlap(countour1.points[i], countour1.points[i + 1], countour2.points[j], countour2.points[j + 1])
            if a==1:
                overlappoints1.append(countour1.points[i])
                overlappoints1.append(countour1.points[i + 1])

    return overlappoints1

def findoverlapY(countour1:Polyline,countour2:Polyline):#现在只招一个满足条件的两条线段
    listoverlapendpoint1=[]
    listoverlapendpoint2=[]
    higher = None
    for i in range(len(countour1.points) - 1):
        for j in range(len(countour2.points) - 1):
                if(countour1.points[i].y == countour1.points[i + 1].y) and (countour2.points[j].y == countour2.points[j + 1].y):
                    if abs(countour1.points[i].y-countour2.points[j].y) <= 4e-5:
                        if build_connect_tree.judge_Xlap(min(countour1.points[i].x, countour1.points[i + 1].x),
                                                         max(countour1.points[i].x, countour1.points[i + 1].x),
                                                         min(countour2.points[j].x, countour2.points[j + 1].x),
                                                         max(countour2.points[j].x, countour2.points[j + 1].x)) == True:
                            #va = VtkAdaptor()
                            #va.drawPolyline(countour1).GetProperty().SetColor(1, 0, 0)
                            #va.drawPolyline(countour2).GetProperty().SetColor(0, 0, 1)
                            #va.drawPoint(countour1.points[i]).GetProperty().SetColor(1, 0, 0)
                            #va.drawPoint(countour1.points[i + 1]).GetProperty().SetColor(1, 0, 0)
                            #va.drawPoint(countour2.points[j]).GetProperty().SetColor(0, 0, 1)
                            #va.drawPoint(countour2.points[j+1]).GetProperty().SetColor(0, 0, 1)
                            #va.display()
                            temp1 = []
                            temp2 = []
                            temp1.append(countour1.points[i])
                            temp1.append(countour1.points[i + 1])
                            temp2.append(countour2.points[j])
                            temp2.append(countour2.points[j + 1])
                            temp1.sort(key=lambda point: point.x)
                            temp2.sort(key=lambda point: point.x)
                            listoverlapendpoint1.append(tuple(temp1))
                            listoverlapendpoint2.append(tuple(temp2))

    #index = random.randint(0, len(listoverlapendpoint1)-1)
    #index = -1

    #print("a")
    "默认列向量"
    y1 = numpy.array([temp[0].y for temp in listoverlapendpoint1])
    y2 = numpy.array([temp[0].y for temp in listoverlapendpoint2])

    difference = numpy.abs(y1-y2)
    #print(y1.shape)
    #print(y2.shape)
    #print(difference.shape)
    index = numpy.argmin(difference, axis=0)

    if listoverlapendpoint1[index][0].y > listoverlapendpoint2[index][0].y:
        higher = 1
    if listoverlapendpoint1[index][0].y < listoverlapendpoint2[index][0].y:
        higher = 0
    return listoverlapendpoint1[index], listoverlapendpoint2[index], higher

#def overlapop():

def Equal(f1, f2):
    return (abs(f1 - f2) < 1e-4)
def PointEqual(p1,p2):
    return (Equal(p1.x, p2.x) and Equal(p1.y, p2.y))
def PointC(p1,p2):
    return (p1.x > p2.x or (Equal(p1.x, p2.x) and p1.y > p2.y))
def CrossP(p1,p2):
    return (p1.x * p2.y - p1.y * p2.x)
def swap(t1, t2):
    return t2, t1
def overlap(p1,p2,p3,p4):
    if(PointC(p1,p2)):
        p1, p2=swap(p1,p2)
    if (PointC(p3, p4)):
        p3,p4=swap(p3, p4)
    #if(PointEqual(p1,p3) and PointEqual(p2,p4)):
        #return 1
    vector1 = Point3D(p2.x-p1.x, p2.y-p1.y)
    vector2 = Point3D(p4.x - p3.x, p4.y - p3.y)
    Cross = CrossP(vector1, vector2)
    if(PointEqual(p1,p3)):
        if(abs(Cross- 0)<=1e-14):
            return 1
        else:
            return 0
    if (PointEqual(p2, p4)):
        if (abs(Cross-0)<=1e-14):
            return 1
        else:
            return 0
    if(PointEqual(p1,p4)):
        return 0
    if (PointEqual(p2, p3)):
        return 0
    if(PointC(p1,p3)):
        p1, p3 = swap(p1, p3)
        p2, p4 = swap(p1, p3)
        vector1, vector2 = swap(vector1,vector2)
        Cross = CrossP(vector1, vector2)

    if(abs(Cross-0)<=1e-14):
        vs = Point3D(p3.x - p1.x, p3.y - p1.y)
        if (abs(CrossP(vector1, vs)- 0)<=1e-14):
            if (PointC(p2, p3)):

                return 1
        return 0
    return 0

