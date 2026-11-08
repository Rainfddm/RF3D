import numpy
import pyclipper
import torch

import numpy as np

#####
# 获取当前文件所在目录
from suFabEngine.PathOptimizer.Bezier import *
from suFabEngine.PathOptimizer.Erroe import *
from suFabEngine.PathOptimizer.contourunion import *
from suFabEngine.PathOptimizer.GenDpPath5 import *
from suFabEngine.PathOptimizer.RNP import *
from suFabEngine.PathOptimizer.resample import *
from suFabEngine.PathOptimizer.Polyline import polyline_to_tuple
#####

class continuous_path:
    def __init__(self, higher):
        self.endpath = Polyline()
        self.popvalue=None
        self.count = -1
        self.insertPoint = {}
        self.higher = higher
    def RT(self, treenode, splitCurve, pathsop, interval, endpath):
       self.count = self.count+1
       self.endpath=endpath
       for child in treenode.children:
           fatherpath = using_contour_index_find_path(int(treenode.name), splitCurve, pathsop)
           #path_show([fatherpath])

           childpath = using_contour_index_find_path(int(child.name), splitCurve, pathsop)
           #path_show([childpath])
           high = self.higher[(int(treenode.name), int(child.name))][2]

           if high:
                #path_show([self.endpath, childpath])
                self.endpath.points = replaceL(findindex(self.insertPoint[self.count][1], self.endpath), self.endpath.points)

                childpath.points = replaceL(findindex(self.insertPoint[self.count][2],childpath), childpath.points)

                #temp2 = va.drawPolyline(pathsop[2])
                #temp2.GetProperty().SetColor(0, 0, 1)
                #temp2.GetProperty().SetLineWidth(4)
                #temp3 = va.drawPolyline(pathsop[3])
                #temp3.GetProperty().SetColor(0.9, 0.7, 0.2)
                #temp3.GetProperty().SetLineWidth(4)
                #va.drawPoint(self.endpath.points[0]).GetProperty().SetColor(1, 0, 0)
                #va.drawPoint(self.endpath.points[-1]).GetProperty().SetColor(1, 0, 0)
                #va.drawPoint(childpath.points[0]).GetProperty().SetColor(1, 0, 0)
                #va.drawPoint(childpath.points[-1]).GetProperty().SetColor(1, 0, 0)
                #va.display()

                #va = VtkAdaptor()
                #va.drawPolyline(self.endpath).GetProperty().SetColor(0, 0, 1)
                #va.drawPolyline(childpath).GetProperty().SetColor(0, 0, 1)
                #va.drawPoint(self.endpath.points[0]).GetProperty().SetColor(1, 0, 0)
                #va.drawPoint(self.endpath.points[-1]).GetProperty().SetColor(1, 0, 0)
                #va.drawPoint(childpath.points[0]).GetProperty().SetColor(1, 0, 0)
                #va.drawPoint(childpath.points[-1]).GetProperty().SetColor(1, 0, 0)
                #va.display()

                self.endpath = contourconnect(self.endpath, childpath)
           else:
                #path_show([self.endpath, childpath])
                #self.endpath.points.reverse()
                self.endpath.points = replaceL(findindex(self.insertPoint[self.count][0], self.endpath), self.endpath.points)
                #childpath.points.reverse()
                childpath.points = replaceL(findindex(self.insertPoint[self.count][3], childpath), childpath.points)
                #va = VtkAdaptor()
                #va.drawPolyline(self.endpath).GetProperty().SetColor(0, 0, 1)
                #va.drawPolyline(childpath).GetProperty().SetColor(0, 0, 1)
                #va.drawPoint(self.endpath.points[0]).GetProperty().SetColor(1, 0, 0)
                #va.drawPoint(self.endpath.points[-1])
                #va.drawPoint(childpath.points[0]).GetProperty().SetColor(1, 0, 0)
                #va.drawPoint(childpath.points[-1]).GetProperty().SetColor(1, 0, 0)
                #va.display()

                self.endpath = contourconnect(childpath, self.endpath)

           #print("{a}and{b}".format(a=treenode.name, b=child.name))
           self.popvalue=self.endpath.points.pop()
           self.RT(child, splitCurve, pathsop, interval, self.endpath)

    def currinsert(self, treenode, splitCurve, pathsop, interval,patho,ys1):
        #build_connect_tree.path_show(splitCurve)
        #build_connect_tree.path_show([pathsop[2]])
        self.count = self.count+1
        for child in treenode.children:
            fatherpatho = using_contour_index_find_path(int(treenode.name), splitCurve, patho)

            childpatho = using_contour_index_find_path(int(child.name), splitCurve, patho)
            #va = VtkAdaptor()
            #va.drawPolyline(splitCurve[int(treenode.name)]).GetProperty().SetColor(1, 0, 1)
            #va.drawPolyline(splitCurve[int(child.name)]).GetProperty().SetColor(0, 0, 0)
            #va.drawPolyline(fatherpatho).GetProperty().SetColor(1, 0, 0)
            #va.drawPolyline(childpatho).GetProperty().SetColor(1, 0, 0)

            #va.display()

            #listoverlapendpoint1, listoverlapendpoint2, higher = findoverlapY(splitCurve[int(treenode.name)], splitCurve[int(child.name)])
            #self.higher[(int(treenode.name), int(child.name))] = copy.deepcopy(higher)#找到合适连接的路径线
            listoverlapendpoint1, listoverlapendpoint2, higher = self.higher[(int(treenode.name), int(child.name))]
            #print("{},{} [{},{}]".format(listoverlapendpoint1[0], listoverlapendpoint2[0], int(treenode.name), int(child.name)))

            LF = []
            LC = []
            if higher:
                for i in range(len(fatherpatho.points)-1):
                    if (fatherpatho.points[i].y == fatherpatho.points[i+1].y) and fatherpatho.points[i].y > listoverlapendpoint1[0].y:
                        if not ((max(fatherpatho.points[i].x, fatherpatho.points[i + 1].x) <= min(
                                listoverlapendpoint1[0].x, listoverlapendpoint1[1].x)) or (
                                        min(fatherpatho.points[i].x, fatherpatho.points[i + 1].x) >= max(
                                    listoverlapendpoint1[0].x, listoverlapendpoint1[1].x))):
                            LF.append(fatherpatho.points[i].y)

                    if (fatherpatho.points[i] == listoverlapendpoint1[0] and fatherpatho.points[i + 1] ==
                        listoverlapendpoint1[1]) or (
                            fatherpatho.points[i + 1] == listoverlapendpoint1[0] and fatherpatho.points[i] ==
                            listoverlapendpoint1[1]):
                        LF.append(fatherpatho.points[i].y)

                for j in range(len(childpatho.points)-1):
                    if (childpatho.points[j].y == childpatho.points[j+1].y) and childpatho.points[j].y < listoverlapendpoint2[0].y:
                        if not ((max(childpatho.points[j].x, childpatho.points[j + 1].x) <= min(
                                listoverlapendpoint2[0].x, listoverlapendpoint2[1].x)) or (
                                        min(childpatho.points[j].x, childpatho.points[j + 1].x) >= max(
                                    listoverlapendpoint2[0].x, listoverlapendpoint2[1].x))):
                            LC.append(childpatho.points[j].y)
                    if (childpatho.points[j] == listoverlapendpoint2[0] and childpatho.points[j + 1] ==
                        listoverlapendpoint2[1]) or (
                            childpatho.points[j + 1] == listoverlapendpoint2[0] and childpatho.points[j] ==
                            listoverlapendpoint2[1]):
                        LC.append(childpatho.points[j].y)
            else:
                for i in range(len(fatherpatho.points)-1):
                    if (fatherpatho.points[i].y == fatherpatho.points[i+1].y) and fatherpatho.points[i].y < listoverlapendpoint1[0].y:
                        if not ((max(fatherpatho.points[i].x, fatherpatho.points[i + 1].x) <= min(
                                listoverlapendpoint1[0].x, listoverlapendpoint1[1].x)) or (
                                        min(fatherpatho.points[i].x, fatherpatho.points[i + 1].x) >= max(
                                    listoverlapendpoint1[0].x, listoverlapendpoint1[1].x))):
                            LF.append(fatherpatho.points[i].y)

                    if (fatherpatho.points[i] == listoverlapendpoint1[0] and fatherpatho.points[i + 1] ==
                        listoverlapendpoint1[1]) or (
                            fatherpatho.points[i + 1] == listoverlapendpoint1[0] and fatherpatho.points[i] ==
                            listoverlapendpoint1[1]):
                        LF.append(fatherpatho.points[i].y)

                for j in range(len(childpatho.points)-1):
                    if (childpatho.points[j].y == childpatho.points[j+1].y) and childpatho.points[j].y > listoverlapendpoint2[0].y:
                        if not ((max(childpatho.points[j].x, childpatho.points[j + 1].x) <= min(
                                listoverlapendpoint2[0].x, listoverlapendpoint2[1].x)) or (
                                        min(childpatho.points[j].x, childpatho.points[j + 1].x) >= max(
                                    listoverlapendpoint2[0].x, listoverlapendpoint2[1].x))):
                            LC.append(childpatho.points[j].y)
                    if (childpatho.points[j] == listoverlapendpoint2[0] and childpatho.points[j + 1] ==
                        listoverlapendpoint2[1]) or (
                            childpatho.points[j + 1] == listoverlapendpoint2[0] and childpatho.points[j] ==
                            listoverlapendpoint2[1]):
                        LC.append(childpatho.points[j].y)
            LF.sort(key=lambda x: abs(x-  listoverlapendpoint1[0].y))
            LC.sort(key=lambda x: abs(x - listoverlapendpoint2[0].y))
            #print("{},{} [{},{}]".format(LF[0], LC[0],int(treenode.name), int(child.name)))

            #path_show([fatherpatho])
            #path_show([childpatho])
            fatherpath = using_contour_index_find_path(int(treenode.name), splitCurve, pathsop)#都是在调用pathsop，所以father和child的改变直接影响了pathsop
            childpath = using_contour_index_find_path(int(child.name), splitCurve, pathsop)
            #path_show([fatherpath, childpath])
            freroute, creroute = getpoint(LF[0], LC[0], fatherpath, childpath, fatherpatho, childpatho,
                                          listoverlapendpoint1, listoverlapendpoint2)
            #va = VtkAdaptor()
            #va.drawPolyline(childpath).GetProperty().SetColor(1, 0, 0)
            #va.drawPolyline(fatherpath).GetProperty().SetColor(1, 0, 0)
            #va.drawPoint(fatherpath.points[freroute[1]]).GetProperty().SetColor(1, 0, 0)
            #va.drawPoint(fatherpath.points[freroute[0]]).GetProperty().SetColor(1, 0, 0)
            #va.drawPoint(childpath.points[creroute[1]]).GetProperty().SetColor(1, 0, 0)
            #va.drawPoint(childpath.points[creroute[0]]).GetProperty().SetColor(1, 0, 0)
            #va.display()
            if abs(LC[0] - LF[0]) < 0.2:
                fatherxL, fatherxR, childxL, childxR = fatherpath.points[freroute[1]], fatherpath.points[freroute[0]], \
                                                       childpath.points[creroute[1]], childpath.points[creroute[0]]
                self.insertPoint[self.count] = [fatherxL, fatherxR, childxL, childxR]
                self.currinsert(child, splitCurve, pathsop, interval, patho, ys1)

            else:
                fatherxL, fatherxR, childxL, childxR = insert(fatherpath, childpath, interval, freroute, creroute)
                self.insertPoint[self.count] = [fatherxL, fatherxR, childxL, childxR]
                self.currinsert(child, splitCurve, pathsop, interval, patho, ys1)

def judge_Xlap(x1left, x1right, x2left, x2right):
    if x1left>=x2right or x1right<=x2left:
        return False
    if ((x1left <= x2left) and (
            x1right <= x2right)):
        insertpointx = (x1right + x2left)
        return True
    elif(
            x1left >= x2left) and (
            x1right >= x2right):
        insertpointx = (x1left + x2right)
        return True
    elif ((x1right <= x2right) and (
            x1left >= x2left)):
        insertpointx = (x1left + x1right)
        return True

    elif ((x1right >= x2right) and (
                x1left <= x2left)):
        insertpointx = (x2right + x2left)
        return True
    else:
        return False

def Check_FC(fatherpath:Polyline, childpath:Polyline,freroute,creroute,higher):
    FE = 0 #表示f出错
    CE = 1 #表示c出错
    if higher == 1:#父路径在子路径上
        check_fy = fatherpath.points[freroute[0]].y
        for i in range(len(fatherpath.points)-1):
            if fatherpath.points[i].y == fatherpath.points[i+1].y:
                temp_y = fatherpath.points[i].y
                if temp_y < check_fy:
                    return FE
        return CE
    else:
        check_fy = fatherpath.points[freroute[0]].y
        for i in range(len(fatherpath.points) - 1):
            if fatherpath.points[i].y == fatherpath.points[i + 1].y:
                temp_y = fatherpath.points[i].y
                if temp_y > check_fy:
                    return FE
        return CE

def getoverlapY(treenode, splitCurve, Y):
    for child in treenode.children:
        Y.findhly(splitCurve[int(treenode.name)], splitCurve[int(child.name)])
        getoverlapY(child, splitCurve, Y)

def getpoint(fy, cy, fatherpath,childpath,fatherpatho,childpatho,listoverlapendpoint1, listoverlapendpoint2):
    a = []
    b = []
    freroute = []
    creroute = []
    if fy !=listoverlapendpoint1[0].y:
        for i in range(len(fatherpatho.points) - 1):
            if abs(fatherpatho.points[i].y - fy) <= 1e-14 and abs(fatherpatho.points[i + 1].y - fy) <= 1e-14:
                a.append(fatherpatho.points[i])
                a.append(fatherpatho.points[i + 1])
    else:
        for i in range(len(fatherpatho.points) - 1):
            if (fatherpatho.points[i] == listoverlapendpoint1[0] and fatherpatho.points[i + 1] ==
                listoverlapendpoint1[1]) or (
                    fatherpatho.points[i + 1] == listoverlapendpoint1[0] and fatherpatho.points[i] ==
                    listoverlapendpoint1[1]):
                a.append(fatherpatho.points[i])
                a.append(fatherpatho.points[i + 1])
                break
    if cy != listoverlapendpoint2[0].y:
        for i in range(len(childpatho.points) - 1):
            if abs(childpatho.points[i].y - cy) <= 1e-14 and abs(childpatho.points[i + 1].y - cy) <= 1e-14:
                b.append(childpatho.points[i])
                b.append(childpatho.points[i + 1])

    else:
        for i in range(len(childpatho.points) - 1):
            if (childpatho.points[i] == listoverlapendpoint2[0] and childpatho.points[i + 1] ==
                listoverlapendpoint2[1]) or (
                    childpatho.points[i + 1] == listoverlapendpoint2[0] and childpatho.points[i] ==
                    listoverlapendpoint2[1]):
                b.append(childpatho.points[i])
                b.append(childpatho.points[i + 1])
                break
    at = []
    bt = []
    for points in a:
        if points not in at:
            at.append(points)
    for points in b:
        if points not in bt:
            bt.append(points)
    at.sort(key=lambda point: point.x)
    bt.sort(key=lambda point: point.x)
    a1 = findindex(at[0], fatherpath)
    a2 = findindex(at[-1], fatherpath)
    b1 = findindex(bt[0], childpath)
    b2 = findindex(bt[-1], childpath)
    freroute = [a2, a1]
    creroute = [b2, b1]

    return freroute, creroute

def HD1(x,y):
    x = x.float()
    y = y.float()
    distance_matrix = torch.cdist(x, y, p=2)  # p=2 means Euclidean Distance

    value1 = distance_matrix.min(2)[0].min(1, keepdim=True)[0].item()
    xindex = distance_matrix.min(2)[0].min(1, keepdim=True)[1].item()
    # （2）对应在每一行中最小的那一列的indic，后一个min决定它在哪一行，前一个决定它在哪一列。 #因为tensor的形状要读取这个值需要如右边这样处理，min（2）【1】返回的是1,4tensor
    yindex = distance_matrix.min(2)[1][0][xindex].item()
    value2 = distance_matrix.min(1)[0].min(1, keepdim=True)[0].item()

    return min(value1, value2), xindex, yindex

def HD2team(x,y):
    x = x.float()
    y = y.float()
    distance_matrix = torch.cdist(x, y, p=2)
    teamxindex=[]
    teamyindex=[]# p=2 means Euclidean Distance
    sorted_logits, sorted_indices = torch.sort(distance_matrix.min(2)[0], descending=False, dim=-1)
    value1 = sorted_logits[0][2].item()
    #value1 = distance_matrix.min(2)[0].min(1, keepdim=True)[0].item()
    for i in range(distance_matrix.min(2)[0].size(1)):
        if distance_matrix.min(2)[0][0][i].item() < value1 + 0.1 and distance_matrix.min(2)[0][0][i].item() > value1:
            teamxindex.append(i)

    for i in range(len(teamxindex)):
        yindex = distance_matrix.min(2)[1][0][teamxindex[i]].item()
        teamyindex.append(yindex)

    return teamxindex, teamyindex

def polygons_show(polys , R,G,B, Linewidth):
    va = VtkAdaptor()
    for poly in polys:
        temp = va.drawPolyline(poly)
        temp.GetProperty().SetColor(R,G,B)
        temp.GetProperty().SetLineWidth(Linewidth)
    va.display()

def HD3team(x, y, interval):
    x = x.float()
    y = y.float()
    distance_matrix = torch.cdist(x, y, p=2)
    teamxindex=[]
    teamyindex=[]# p=2 means Euclidean Distance
    sorted_logits, sorted_indices=torch.sort(distance_matrix.min(2)[0], descending=False, dim=-1)
    value1 = sorted_logits[0][0].item()
    print("a")
    for i in range(distance_matrix.min(2)[0].size(1)):
        if distance_matrix.min(2)[0][0][i].item() < 1.5*interval and distance_matrix.min(2)[0][0][i].item()>= value1:
            teamxindex.append(i)

    for i in range(len(teamxindex)):
        yindex = distance_matrix.min(2)[1][0][teamxindex[i]].item()
        teamyindex.append(yindex)

    return teamxindex, teamyindex

def insertpathes(Curve: Polyline, interval):
    insertcurve = Polyline()
    endpoints = Curve.points
    insertcurve.points.append(Curve.points[0])
    for i in range(len(endpoints) - 1):
        temp = []
        dir = endpoints[i].pointTo(endpoints[i + 1]).normalized()

        if endpoints[i].distance(endpoints[i + 1]) > interval and endpoints[i].x != endpoints[i+1].x:
            totaldistace = endpoints[i].distance(endpoints[i + 1])
            N = int(totaldistace/interval)
            divdistance = totaldistace / N
            for j in range(1, N):
                temp.append(endpoints[i].translated(dir.amplified(divdistance * j)))
            temp.append(endpoints[i + 1])
            insertcurve.points.extend(temp)
        else:
            insertcurve.points.append(endpoints[i + 1])
    insertcurve.belongtowhichpoly = Curve.belongtowhichpoly
    return insertcurve

def initinsert(path1,path2,interval):
    fatherpath=path1
    childpath=path2
    childpatht = pathtotensor(childpath)
    fatherpatht = pathtotensor(fatherpath)
    minmun, fatherindex, childindex = HD1(fatherpatht, childpatht)
    freroute, creroute = findpoint(fatherindex, childindex, fatherpath, childpath)
    if abs(fatherpath.points[freroute[0]].x - fatherpath.points[freroute[1]].x) < abs(
            childpath.points[creroute[0]].x - childpath.points[creroute[1]].x):
        insertpointx = (fatherpath.points[freroute[0]].x + fatherpath.points[freroute[1]].x) * 0.5
    else:
        insertpointx = (childpath.points[creroute[0]].x + childpath.points[creroute[1]].x) * 0.5
    if (freroute[0] < freroute[1]):
        fatherpath.points.insert(freroute[1], Point3D(insertpointx-interval, fatherpath.points[freroute[0]].y))
        fatherpath.points.insert(freroute[1],
                                 Point3D(insertpointx, fatherpath.points[freroute[0]].y))
    else:
        fatherpath.points.insert(freroute[0], Point3D(insertpointx, fatherpath.points[freroute[0]].y))
        fatherpath.points.insert(freroute[0],
                                 Point3D(insertpointx-interval, fatherpath.points[freroute[0]].y) )
    if (creroute[0] < creroute[1]):

        childpath.points.insert(creroute[1], Point3D(insertpointx-interval, childpath.points[creroute[0]].y))
        childpath.points.insert(creroute[1], Point3D(insertpointx, childpath.points[creroute[0]].y))
    else:
        childpath.points.insert(creroute[0], Point3D(insertpointx, childpath.points[creroute[0]].y))
        childpath.points.insert(creroute[0], Point3D(insertpointx-interval, childpath.points[creroute[0]].y))

    return fatherpath,childpath

def insert(fatherpath,childpath,interval,freroute,creroute):
    """"0是x值大，1是x值小
    insertpoint有四种情况，完全包含两种，部分重合两种，总共四种if
    freroute和creroute都是len为2的包含了我们找到的那条路径的x的最小值和x的最大值的在path中的index"""

    #print(fatherpath.points[freroute[0]])
    #print(fatherpath.points[freroute[1]])
    #print(childpath.points[creroute[0]])
    #print(childpath.points[creroute[1]])
    #if 顺序不可以改变

    if ((fatherpath.points[freroute[1]].x <= childpath.points[creroute[1]].x) and (
            fatherpath.points[freroute[0]].x <= childpath.points[creroute[0]].x)):
        insertpointx = (fatherpath.points[freroute[0]].x + childpath.points[creroute[1]].x) * 0.5
    if(
            (fatherpath.points[freroute[1]].x >= childpath.points[creroute[1]].x) and (
            fatherpath.points[freroute[0]].x >= childpath.points[creroute[0]].x)):
        insertpointx = (fatherpath.points[freroute[1]].x + childpath.points[creroute[0]].x) * 0.5
    if ((fatherpath.points[freroute[0]].x <= childpath.points[creroute[0]].x) and (
            fatherpath.points[freroute[1]].x >= childpath.points[creroute[1]].x)):
        insertpointx = (fatherpath.points[freroute[0]].x + fatherpath.points[freroute[1]].x) * 0.5

    if ((fatherpath.points[freroute[0]].x >= childpath.points[creroute[0]].x) and (
                fatherpath.points[freroute[1]].x <= childpath.points[creroute[1]].x)):
        insertpointx = (childpath.points[creroute[0]].x + childpath.points[creroute[1]].x) * 0.5

    if (freroute[0] < freroute[1]):
        for i in range(freroute[0], freroute[1]+1):
            if (i != len(fatherpath.points) - 1):
                if insertpointx < fatherpath.points[i].x and insertpointx > fatherpath.points[i + 1].x:
                    fatherpath.points.insert(i + 1,
                                             Point3D(insertpointx - interval, fatherpath.points[i].y,fatherpath.points[freroute[0]].z))
                    fatherpath.points.insert(i + 1,
                                             Point3D(insertpointx, fatherpath.points[i].y,fatherpath.points[freroute[0]].z))
                    break
            else:
                if insertpointx < fatherpath.points[i].x and insertpointx > fatherpath.points[0].x:
                    fatherpath.points.insert(i + 1,
                                             Point3D(insertpointx - interval, fatherpath.points[i].y,fatherpath.points[freroute[0]].z))
                    fatherpath.points.insert(i + 1,
                                             Point3D(insertpointx, fatherpath.points[i].y,fatherpath.points[freroute[0]].z))
                    break

    else:
        for i in range(freroute[1], freroute[0]+1):
            if (i != len(fatherpath.points) - 1):
                if insertpointx > fatherpath.points[i].x and insertpointx < fatherpath.points[i + 1].x:
                    fatherpath.points.insert(i + 1,
                                             Point3D(insertpointx, fatherpath.points[i].y,fatherpath.points[freroute[0]].z))
                    fatherpath.points.insert(i + 1,
                                             Point3D(insertpointx - interval, fatherpath.points[i].y,fatherpath.points[freroute[0]].z))
                    break
            else:
                if insertpointx > fatherpath.points[i].x and insertpointx < fatherpath.points[0].x:
                    fatherpath.points.insert(i + 1,
                                             Point3D(insertpointx, fatherpath.points[i].y,fatherpath.points[freroute[0]].z))
                    fatherpath.points.insert(i + 1,
                                             Point3D(insertpointx - interval, fatherpath.points[i].y,fatherpath.points[freroute[0]].z))
                    break

    if (creroute[0] < creroute[1]):
        for i in range(creroute[0],creroute[1]+1):
            if (i != len(childpath.points) - 1):
                if insertpointx < childpath.points[i].x and insertpointx > childpath.points[i + 1].x:
                    childpath.points.insert(i + 1,
                                            Point3D(insertpointx - interval, childpath.points[i].y,fatherpath.points[freroute[0]].z))
                    childpath.points.insert(i + 1,
                                            Point3D(insertpointx, childpath.points[i].y,fatherpath.points[freroute[0]].z))
                    break
            else:
                if insertpointx < childpath.points[i].x and insertpointx > childpath.points[0].x:
                    childpath.points.insert(i + 1,
                                            Point3D(insertpointx - interval, childpath.points[i].y,fatherpath.points[freroute[0]].z))
                    childpath.points.insert(i + 1,
                                            Point3D(insertpointx, childpath.points[i].y,fatherpath.points[freroute[0]].z))
                    break

    else:
        for i in range(creroute[1], creroute[0]+1):
            if(i!=len(childpath.points)-1):
                if insertpointx > childpath.points[i].x and insertpointx < childpath.points[i + 1].x:

                    childpath.points.insert(i + 1,
                                            Point3D(insertpointx, childpath.points[i].y,fatherpath.points[freroute[0]].z))
                    childpath.points.insert(i + 1,
                                            Point3D(insertpointx - interval, childpath.points[i].y,fatherpath.points[freroute[0]].z))
                    break
            else:
                if insertpointx > childpath.points[i].x and insertpointx < childpath.points[0].x:
                    childpath.points.insert(i + 1,
                                            Point3D(insertpointx, childpath.points[i].y,fatherpath.points[freroute[0]].z))
                    childpath.points.insert(i + 1,
                                            Point3D(insertpointx - interval, childpath.points[i].y,fatherpath.points[freroute[0]].z))
                    break

    fatherxL = Point3D(insertpointx - interval, fatherpath.points[freroute[0]].y, fatherpath.points[freroute[0]].z)
    fatherxR = Point3D(insertpointx, fatherpath.points[freroute[0]].y,fatherpath.points[freroute[0]].z)
    childxL = Point3D(insertpointx-interval, childpath.points[creroute[0]].y, fatherpath.points[freroute[0]].z)
    childxR = Point3D(insertpointx, childpath.points[creroute[0]].y, fatherpath.points[freroute[0]].z)
    return fatherxL, fatherxR, childxL, childxR

def initjudgeattached(Curve,ys):
    distancematrix = np.ndarray((len(Curve), len(Curve)))
    for i in range(len(Curve)):
        for j in range(len(Curve)):
            if i != j:
                distancematrix[i][j] = crp(Curve[i], Curve[j], ys)
            else:
                distancematrix[i][j] = 0
    return distancematrix

def judgeattached(Curve):
    distancematrix = np.ndarray((len(Curve), len(Curve)))
    for i in range(len(Curve)):
        for j in range(len(Curve)):
            if i != j:
                distancematrix[i][j] = arrive(Curve[i], Curve[j])
            else:
                distancematrix[i][j] = 0
    return distancematrix

def contouropti(Curve1,dislist,layercontours:list,finishedcontourorder:list):
    for j in range(len(dislist[0])):
        Curve2=layercontours[j]
        if dislist[0][j] == 1 and j not in finishedcontourorder:
            if direnction(Curve1) == 1:
                Curve1.points.reverse()
            if direnction(layercontours[j]) == 1:
                layercontours[j].points.reverse()

            overlappoints1 = findoverlap(Curve1, layercontours[j])
            overlappoints = []
            for point in overlappoints1:
                if point not in overlappoints:
                    overlappoints.append(point)
            overlappoint_r = copy.deepcopy(overlappoints)
            overlappoint_r.reverse()
            adjuststart(Curve1,overlappoints)
            #path_show([layercontours[j],Curve1])
            adjuststart(layercontours[j],overlappoint_r)
            index1 = findindex(overlappoints[0], Curve1)
            index2 = findindex(overlappoint_r[0], layercontours[j])
            tempCurvefront = Curve1.points[:index1]
            tempCurvehind = Curve1.points[index1 + len(overlappoints)-1:-1]
            tempCurvefrontr = layercontours[j].points[:index2]
            tempCurvehindr = layercontours[j].points[index2 + len(overlappoints)-1:-1]
            temp1=Polyline()
            temp2=Polyline()
            temp1.points=tempCurvefrontr
            temp2.points=tempCurvehindr
            tempCurvein = []
            tempCurveinr = []
            listpoint = []
            curve_list = []
            for point in overlappoints:
                listpoint.append(point.x)
                listpoint.append(point.y)
                curve_list.append(listpoint)
                listpoint = []
            t_points = np.arange(0, 1,
                                 0.5)
            points1 = np.array(curve_list)
            curve_list.reverse()
            points2=np.array(curve_list)
            curve1 = Bezier.Curve(t_points, points1)
            curve2 = Bezier.Curve(t_points, points2)

            for list in curve1:
                tempCurvein.append(Point3D(list[0], list[1]))
            T=Polyline()
            T.points=tempCurvein
            #if direnction(T)==1:
             #   tempCurvein.reverse()

            for list in curve2:
                tempCurveinr.append(Point3D(list[0], list[1]))
            #T1 = Polyline()
            #T1.points = tempCurveinr
            #if direnction(T1) == 1:
                #tempCurveinr.reverse()
            Curve1.points.clear()
            layercontours[j].points.clear()
            Curve1.points.extend(tempCurvefront)
            Curve1.points.extend(tempCurvein)
            Curve1.points.extend(tempCurvehind)
            layercontours[j].points.extend(tempCurvefrontr)
            layercontours[j].points.extend(tempCurveinr)
            layercontours[j].points.extend(tempCurvehindr)
            if Curve1.points[-1]!=Curve1.points[0]:
                Curve1.points.append(Curve1.points[0])
            if layercontours[j].points[-1]!=layercontours[j].points[0]:
                layercontours[j].points.append(layercontours[j].points[0])
            temppoints=[]
            for points in layercontours[j].points:
                if points not in temppoints:
                    temppoints.append(points)
            copyp=copy.deepcopy(temppoints)
            layercontours[j].points=copyp
            layercontours[j].points.append(layercontours[j].points[0])
            temppoints = []
            for points in Curve1.points:
                if points not in temppoints:
                    temppoints.append(points)
            copyp = copy.deepcopy(temppoints)
            Curve1.points = copyp
            Curve1.points.append(Curve1.points[0])

            #v=Polyline()
            #v.points.append(layercontours[j].points[0])
            #for i in range(1,len(layercontours[j].points)):
                #v.points.append(layercontours[j].points[i])
                #path_show([v])

            #path_show([layercontours[j], Curve1])

def adjuststart(curve:Polyline,overlappoints):
    while (curve.points[0] in overlappoints  ):
        curve.points = replaceL(1,curve.points)

def direnction(contour:Polyline):
    points = contour.points
    d = 0
    for i in range(len(points)-1):
        d += -0.5*(points[i+1].y+points[i].y)*(points[i+1].x-points[i].x)#离散求曲面积分判断轮廓顺逆，>0逆时针，<0,顺时针
    if d > 0:
        return 0
    else:
        return 1

def initTree(distancematrix, root):
    T = MultiTree("{}".format(root))

    var1 = TreeNode('{parentnode}'.format(parentnode=root))
    for j in range(len(distancematrix[root])):
        if distancematrix[root][j] == 1:
            var2 = TreeNode('{childnode}'.format(childnode=j))
            T.add(var2, var1)
    return T

def BT(T, treenode, distancematrix):
    for child in treenode.children:
        ADDT(distancematrix, child, T)
        BT(T, child, distancematrix)
    return T

def ADDT(distancematrix, child, T):
    i = int(child.name)
    dislist = distancematrix[i:i + 1].tolist()
    var1 = TreeNode('{parentnode}'.format(parentnode=i))
    for j in range(len(dislist[0])):
        if dislist[0][j] == 1:
            var2 = TreeNode('{childnode}'.format(childnode=j))
            T.add(var2, var1)

def pathtotensor(path: Polyline):
    Tensor = torch.Tensor(1, len(path.points), 2)
    for i in range(len(path.points)):
        v = torch.Tensor(1, 2)
        v[0][0] = path.points[i].x
        v[0][1] = path.points[i].y
        Tensor[0][i] = v
    return Tensor

def CheckError(splitCurve, pathes: list):
    indexpath = []
    for path in pathes:
        indexpath.append(path.belongtowhichpoly)
    indexcontour = range(len(splitCurve))
    errorcontour = []
    for i in indexcontour:
        if i in indexpath:
            pass
        else:
            errorcontour.append(i)
    return errorcontour

def ModifyError(errorcontour, T: MultiTree):
    for countour in errorcontour:
        var = TreeNode("{s}".format(s=countour))
        T.if_node_exist = False
        T.if_node_exist_recursion(T.tree, var, search=True, if_del=False)
        T.search_result_parent
        if (len(T.search_result_children) == 0):
            T.delete(var)
        if (len(T.search_result_children) == 1):
            T.modify(var, T.search_result_children[0])
        # #if(len(T.search_result_children)>=2):

def watch_UNITION(unitarea: Polyline):
    va = VtkAdaptor()
    va.drawPolyline(unitarea).GetProperty().SetColor(0, 0, 0)
    va.display()

def splitCurve_show(splitCurve):
    va = VtkAdaptor()
    for i in range(len(splitCurve)):
        va.drawPolyline(splitCurve[i]).GetProperty().SetColor(0, 0, 0)
    va.display()

def path_show(paths):
    if len(paths)==0:
        return
    va = VtkAdaptor()
    for i in range(len(paths)):
        va.drawPolyline(paths[i]).GetProperty().SetColor(0, 0, 1)
    va.display()

def parentnode(index, T: MultiTree):
    var = TreeNode("{s}".format(s=index))
    T.if_node_exist = False
    T.if_node_exist_recursion(T.tree, var, search=True, if_del=False)
    return T.search_result_parent

def childnode(index, T: MultiTree):
    var = TreeNode("{s}".format(s=index))
    T.if_node_exist = False
    T.if_node_exist_recursion(T.tree, var, search=True, if_del=False)
    childindex = []
    if var.name == T.tree.name:
        for child in T.tree.children:
            childindex.append(int(child.name))

    else:
        for i in T.search_result_children:
            childindex.append(int(i))

    return childindex

def printable(polygon,interval):
    g1=GenDpPath(polygon,interval,0)
    ys = g1.genScanYs([polygon])
    ipses=calcHatchPoints([polygon], ys)
    for ips in ipses:
        if len(ips)!=2:
            return 0
    return 1

def unionnewsc(splitCurve,B1,index,j,interval):
    s1 = splitCurve[index]
    s2 = splitCurve[j]
    splitCurve.remove(s1)
    splitCurve.remove(s2)
    splitCurve.append(B1)
    distancematrix = judgeattached(splitCurve)
    T = initTree(distancematrix)
    T = BT(T, T.tree, distancematrix)
    # T.show_tree()
    # (lianggejiaodian)
    pathsop, ys1= genDpPath1(splitCurve, interval, 0)
    a = CheckError(splitCurve, pathsop)
    print(a)
    return splitCurve, T, pathsop,a

def abnewsc(splitCurve,index,interval):
    splitCurve.remove(splitCurve[index])
    distancematrix = judgeattached(splitCurve)
    T = initTree(distancematrix, 6)
    T = BT(T, T.tree, distancematrix)
    # T.show_tree()

    pathsop, ys1 = genDpPath1(splitCurve, interval, 0)
    # path_show(pathsop)
    a = CheckError(splitCurve, pathsop)
    print(a)
    return splitCurve, T, pathsop,a

def opticontour(a, splitCurve, interval, Original, ys):
    if(len(a)==0):
        pathsop, ys1, startpoint, endpoint = genDpPath2(splitCurve, interval, 0, Original, ys)
        return splitCurve, pathsop, ys1, startpoint, endpoint, Original

def dic_slice(_dic, start, end):
        keys = list(_dic.keys())
        _dic_slice = {}
        for key in keys[keys.index(start): keys.index(end)]:  # 通过index方法，让列表自己找到索引值并返回
            _dic_slice[key] = _dic[key]
        _dic_slice[end] = _dic[end]  # 这里我是想取包括这两个键之间的所有元素，所以将end对应键的值也传入了新字典
        return _dic_slice

def using_contour_index_find_path(index, splitCurve, pathsop):
    contourindexdir = {}
    for path in pathsop:
        contourindexdir[path.belongtowhichpoly] = path
    return contourindexdir[index]

def get_curvature(inner_poly, index):
    #if index!=
    vp = inner_poly.points[index - 1].pointTo(inner_poly.points[index])
    vn = inner_poly.points[index].pointTo(inner_poly.points[index + 1])
    dp = inner_poly.points[index - 1].distance(inner_poly.points[index])
    dn = inner_poly.points[index].distance(inner_poly.points[index + 1])
    total = dp + dn
    aj = build_connect_tree.get_angle(vp, vn)  # 0 到pi
    if math.isnan(aj) == True:
        print("A")
    kj = 2 * aj / total

    return kj

def chose_reroute_points(out_contour, inner_contour, out_contour_tensor, inner_contour_tensor, interval, index):
    "index depends the level of punishment with the large figure"
    data = {}
    temp_list = []
    #va = VtkAdaptor()
    #va.drawPolyline(out_contour).GetProperty().SetColor(0, 0, 1)
    #va.drawPolyline(inner_contour).GetProperty().SetColor(1, 0, 0)
    #va.display()
    index1, index2 = HD3team(out_contour_tensor,
                                                inner_contour_tensor, interval)

    b = float("inf")
    v = float("inf")
    for j in range(len(index1)):
        out_contour.points = build_connect_tree.replaceL(index1[j], out_contour.points)
        inner_contour.points = build_connect_tree.replaceL(index2[j], inner_contour.points)
        #va = VtkAdaptor()
        #va.drawPolyline(out_contour).GetProperty().SetColor(0, 0, 1)
        #va.drawPolyline(inner_contour).GetProperty().SetColor(1, 0, 0)
        #va.drawPoint(out_contour.points[-1]).GetProperty().SetColor(1, 0, 0)
        #va.drawPoint(out_contour.points[0]).GetProperty().SetColor(0, 0, 1)
        #va.drawPoint(inner_contour.points[-1]).GetProperty().SetColor(1, 0, 0)
        #va.drawPoint(inner_contour.points[0]).GetProperty().SetColor(0, 0, 1)
        #va.display()

        connect_interval_outcontour = out_contour.points[0].distance(out_contour.points[-1])
        connect_inerval_inner_poly = inner_contour.points[0].distance(inner_contour.points[-1])

        connect_direction_O_i = out_contour.points[0].pointTo(inner_contour.points[0]).normalized()
        connect_direction_i_O = inner_contour.points[-1].pointTo(out_contour.points[-1]).normalized()

        result1 = SelfIntersections(inner_contour, out_contour.points[-1], inner_contour.points[-1],
                                        inner_contour.points[0], out_contour.points[0])
        result2 = SelfIntersections(out_contour, out_contour.points[-1], inner_contour.points[-1],
                                        inner_contour.points[0], out_contour.points[0])

        #seg1 = Segment(out_contour.points[-1], inner_contour.points[-1])
        #seg2 = Segment(inner_contour.points[0], out_contour.points[0])

        if len(result1) != 0 or len(result2) != 0:
            #va = VtkAdaptor()
            #va.drawPolyline(inner_contour).GetProperty().SetColor(1, 0, 0)
            #va.drawPolyline(out_contour).GetProperty().SetColor(0, 0, 1)
            #va.drawSegment(seg1).GetProperty().SetColor(1, 0, 0)
            #va.drawSegment(seg2).GetProperty().SetColor(1, 0, 0)

            #for point in result:
            #    va.drawPoint(Point3D(point[0], point[1], inner_contour.points[0].z)).GetProperty().SetColor(0, 0, 1)
            #va.display()
            #print("{};{}".format(result1,result2))
            out_contour.points = build_connect_tree.replaceL(-index1[j], out_contour.points)
            inner_contour.points = build_connect_tree.replaceL(-index2[j], inner_contour.points)
            continue
        out_point0 = build_connect_tree.get_curvature(out_contour, 0)
        out_point1 = build_connect_tree.get_curvature(out_contour, -1)
        inner_point0 =build_connect_tree.get_curvature(inner_contour, 0)
        if math.isnan(inner_point0) == True:
            print("A")

        inner_point1 = build_connect_tree.get_curvature(inner_contour, -1)
        if math.isnan(inner_point1) == True:
            print("A")

        if connect_interval_outcontour >= interval*0.5 and connect_inerval_inner_poly >= interval*0.5:
            # not in temppath.points:
            #va = VtkAdaptor()

            #va.drawPolyline(out_contour).GetProperty().SetColor(0, 0, 1)
            #va.drawPolyline(inner_contour).GetProperty().SetColor(1, 0, 0)

            # va.drawPolyline(outcontour).GetProperty().SetColor(0, 0, 1)
            # va.drawPolyline(childpath).GetProperty().SetColor(0, 0, 1)
            #va.drawPoint(out_contour.points[0]).GetProperty().SetColor(1, 0, 0)
            #va.drawPoint(out_contour.points[-1]).GetProperty().SetColor(1, 0, 0)
            #va.drawPoint(inner_contour.points[0]).GetProperty().SetColor(1, 0, 0)
            #va.drawPoint(inner_contour.points[-1]).GetProperty().SetColor(1, 0, 0)

            #va.display()
            b1 = inner_contour.points[-1].distance(out_contour.points[0])
            b2 = out_contour.points[-1].distance(inner_contour.points[0])
            sub = abs(b1 - b2)
            tempangle = build_connect_tree.get_angle(connect_direction_i_O, connect_direction_O_i)
            data[copy.deepcopy(j)] = numpy.array(
                [(tempangle + 1), out_point0, out_point1, inner_point0, inner_point1, sub])
            temp_list.append([tempangle + 1, out_point0, out_point1, inner_point0, inner_point1, sub])
        out_contour.points = build_connect_tree.replaceL(-index1[j], out_contour.points)
        inner_contour.points = build_connect_tree.replaceL(-index2[j], inner_contour.points)
    if len(temp_list) != 0 and len(temp_list) != 1:
        total = numpy.array(temp_list)
        #print(total.shape)

        min = numpy.min(total, axis=0)
        max = numpy.max(total, axis=0)
        section = max - min
        total = total - min

        zero = np.where(section == 0)# the result means the feature 3 do not need to be considered
        if len(zero) == 0:

            section = np.diag(section)
            # section = copy.deepcopy(section)

            total = np.dot(total, np.linalg.inv(section))
        else:
            for i in zero:
                i = i.tolist()
                for j in i:
                    section[j]=1
            section = np.diag(section)
            # section = copy.deepcopy(section)

            total = np.dot(total, np.linalg.inv(section))
        cofficient_matrix = np.diag([1, 0, 0, 0, 0, 1])
        total = np.dot(total, cofficient_matrix)
        #total = total ** index

        add = np.sum(total, axis=1)

        result = add.argmin(axis=0)
        #print("{}and {}".format(result, add[result]))
        #print("aa")
        temp = list(data.keys())

        return out_contour, inner_contour, index1[temp[result]], index2[temp[result]]
    elif len(temp_list) == 1:
        return out_contour, inner_contour, index1[list(data.keys())[0]], index2[list(data.keys())[0]]
    elif len(temp_list) == 0:
        raise interval_error("没找到连接点，需要扩大范围")

def resmaple_about_interval(interval, polyline, isOpen):
    length = resample.pl_arcLength(polyline.points, isOpen)
    if length < interval:
        raise lengtherror("too short can not resample")

    N = int(length / interval)

    pathrp = resample.ResampleCurve(polyline, N)
    return pathrp

def pathhigher(fatherpath: Polyline, childpath: Polyline):
    fmin, fmax = MIN_MAX(fatherpath)
    cmin, cmax = MIN_MAX(childpath)
    if fmax < cmin:
        return 0
    if fmin > cmax:
        return 1
def realpathhigher(countour1:Polyline,countour2:Polyline):#在有内控的情况下这么写会有bug，错误的判断了上下关系导致连接错误
    listY1 = []
    listY2 = []
    higher = None
    for i in range(len(countour1.points) - 1):
        for j in range(len(countour2.points) - 1):
            a = overlap(countour1.points[i], countour1.points[i + 1], countour2.points[j], countour2.points[j + 1])
            if (a == 1):
                if (countour1.points[i].y == countour1.points[i + 1].y):
                    listY1.append(countour1.points[i].y)
                else:
                    break
                if (countour2.points[j].y == countour2.points[j + 1].y):
                    listY2.append(countour2.points[j].y)
                else:
                    break
                if (listY1[0] > listY2[0]):
                    higher = 1
                else:
                    higher = 0
                return  higher

def MIN_MAX(path: Polyline):
    yMin, yMax = float('inf'), float('-inf')
    for pt in path.points:
        yMin, yMax = min(yMin, pt.y), max(yMax, pt.y)
    return yMin, yMax

def contourconnect(pathhigher: Polyline, path: Polyline):
    pathhighervar=Polyline()
    pathhighervar.points=copy.deepcopy(pathhigher.points)
    pathhighervar.points.extend(path.points)
    pathhighervar.points.append(pathhighervar.points[0])
    return pathhighervar
def out_to_in_connect(out:Polyline,incontour:Polyline, flag=0):#两个轮廓都是逆时针
    outvar=Polyline()
    re=Polyline()
    outvar.points=copy.deepcopy(out.points)
    re.points=copy.deepcopy(incontour.points)
    if flag==0:
        re.points.reverse()
        outvar.points.extend(re.points)
        return outvar

    #outvar.points.append(outvar.points[0])

def get_angle( vector1: Vector3D, vector2: Vector3D):
    dot = vector1.dotProduct(vector2)
    v1l = vector1.length()
    v2l = vector2.length()
    temp = dot / (v1l * v2l)
    if temp < -1:
        temp = -1
    if temp > 1:
        temp = 1
    #if math.isnan(temp) == True:
    #    print("A")
    angle = temp  # angle is arc
    return angle

def findpoint(findex, cindex, fatherpath: Polyline, childpath: Polyline):
    freroute = []
    creroute = []
    freroute.clear()
    creroute.clear()
    freroute.append(findex)
    creroute.append(cindex)
    freroute=findbeside(findex, fatherpath, freroute)
    creroute=findbeside(cindex, childpath, creroute)
    return freroute, creroute

def findbeside(findex, fatherpath: Polyline, freroute: list):
    if findex == len(fatherpath.points)-1:
        if (fatherpath.points[0].x < fatherpath.points[findex].x and fatherpath.points[0].y ==
                fatherpath.points[findex].y):
            freroute.append(0)
        if (fatherpath.points[findex - 1].x < fatherpath.points[findex].x and fatherpath.points[findex - 1].y ==
                fatherpath.points[findex].y):
            freroute.append(findex - 1)
    else:
        if (fatherpath.points[findex + 1].x < fatherpath.points[findex].x and fatherpath.points[findex + 1].y ==
                fatherpath.points[findex].y):
            freroute.append(findex + 1)
        if (fatherpath.points[findex - 1].x < fatherpath.points[findex].x and fatherpath.points[findex - 1].y ==
                fatherpath.points[findex].y):
            freroute.append(findex - 1)
    if(len(freroute)<=1):
        #if (fatherpath.points[findex + 1].y ==
             #   fatherpath.points[findex].y==fatherpath.points[findex + 2].y):
            #freroute[0] = findex + 2
            #freroute.append(findex+1)
        #if (fatherpath.points[findex - 1].y ==
             #   fatherpath.points[findex].y == fatherpath.points[findex - 2].y):
            #freroute[0] = findex - 2
            #freroute.append(findex - 1)
            if (fatherpath.points[findex + 1].y ==
                    fatherpath.points[findex].y):
                freroute[0] = findex + 1
                freroute.append(findex)
            else:
                freroute[0] = findex - 1
                freroute.append(findex)

    return freroute

def swaporder(fatherpath: Polyline, childpath: Polyline):
    if pathhigher(fatherpath, childpath) == 1:
        contourconnect(childpath, fatherpath)
    else:
        contourconnect(fatherpath, childpath)

def replaceR(index, A):
    for i in range(index):  ###右移
        A.insert(0, A.pop())
    return A

def replaceL(index, A):

    return A[index:] + A[:index]

def outcontourconnect_not_use_tree(R_contour1, R_contour2):
    outcontourt1 = pathtotensor(R_contour1)
    outcontourt2 = pathtotensor(R_contour2)
    index1, index2 = HD3team(outcontourt1, outcontourt2,0) #返回一系列符合距离的点的index
    outcontour1original = copy.deepcopy(R_contour1)
    outcontour2ccoriginal = copy.deepcopy(R_contour2)

    for i in range(len(index1)):
        R_contour1.points = replaceL(index1[i], R_contour1.points)
        R_contour2.points = replaceL(index2[i], R_contour2.points)
        outcontour2cc = Polyline()
        outcontour2cc.points = copy.deepcopy(R_contour2.points)
        a = outcontour2cc.points[0].distance(outcontour2cc.points[-1])
        b = R_contour1.points[0].distance(R_contour1.points[-1])
        v1 = outcontour2cc.points[-1].pointTo(R_contour1.points[0]).normalized()  # 用来给b验证方向的
        v2 = R_contour1.points[-1].pointTo(outcontour2cc.points[0]).normalized()
        if (v1.crossProduct(v2).lengthSquare() - 0) < 1e-3:
            R_contour1.points.extend(outcontour2cc.points)
            break
        else:
            R_contour1 = copy.deepcopy(outcontour1original)
            R_contour2 = copy.deepcopy(outcontour2ccoriginal)
    return R_contour1

def path_clean(path,cofficent = 1e5):

    c_path = Polyline()
    result = Polyline()
    for point in path.points:
        c_path.points.append(Point3D((round(point.x*cofficent))/cofficent, (round(point.y*cofficent))/cofficent, point.z))
    for point in c_path.points:
        if point not in result.points:
            result.points.append(point)

    return result

def outcontourconnect(treenode, splitCurve:list,endpath):
    for child in treenode.children:
        outcontour1 = splitCurve[int(treenode.name)]
        outcontour2 = splitCurve[int(child.name)]
        outcontour2c = copy.deepcopy(outcontour2)
        outcontour2c.points.reverse()
        outcontourt1 = pathtotensor(outcontour1)
        outcontourt2 = pathtotensor(outcontour2c)
        index1, index2 = HD2team(outcontourt1, outcontourt2)
        outcontour1original=copy.deepcopy(outcontour1)
        outcontour2ccoriginal=copy.deepcopy(outcontour2c)

        for i in range(len(index1)):
            endpath.points = replaceL(findindex(outcontour1.points[index1[i]], endpath), endpath.points)
            outcontour2c.points = replaceL(findindex(outcontour2c.points[index2[i]], outcontour2c), outcontour2c.points)
            outcontour2cc = Polyline()
            outcontour2cc.points = copy.deepcopy(outcontour2c.points)
            outcontour2cc.points.reverse()
            #path_show([outcontour2cc, endpath])
            a = outcontour2cc.points[0].distance(outcontour2cc.points[-1])
            b = endpath.points[0].distance(endpath.points[-1])
            v1 = outcontour2cc.points[-1].pointTo(endpath.points[0]).normalized()  # 用来给b验证方向的
            v2 = endpath.points[-1].pointTo(outcontour2cc.points[0]).normalized()
            if (v1.crossProduct(v2).lengthSquare()-0) < 1e-3:
                endpath.points.extend(outcontour2cc.points)
                break
            else:
                outcontour1 = copy.deepcopy(outcontour1original)
                outcontour2c = copy.deepcopy(outcontour2ccoriginal)

        # 用来给a验证方向的
            #dirb1 = endpath.points[0].pointTo(endpath.points[1])
            #dirb2 = endpath.points[-1].pointTo(endpath.points[-2])
            #dira1 = outcontour2cc.points[-1].pointTo(outcontour2cc.points[-2])
            #dira2 = outcontour2cc.points[0].pointTo(outcontour2cc.points[1])
            #delta = 0.05
            #while b < interval - 0.01:
             #   if dirb1.crossProduct(av).lengthSquare() - 0 <= dirb2.crossProduct(av).lengthSquare() - 0:
              #      endpath.points[0].translate(dirb1.amplified(delta))
               #     b = endpath.points[0].distance(endpath.points[-1])  # Nonetype 很有可能是没有返回值的类方式直接改变了对象的类成员的值
                    # path_show([outcontour2cc, endpath])
                #else:
                 #   endpath.points[-1].translate(dirb2.amplified(delta))
                  #  b = endpath.points[0].distance(endpath.points[-1])  # Nonetype 很有可能是没有返回值的类方式直接改变了对象的类成员的值
                    # path_show([outcontour2cc, endpath])

            #while a < interval - 0.01:
             #   if dira1.crossProduct(bv).lengthSquare() - 0 <= dira2.crossProduct(bv).lengthSquare() - 0:
              #      outcontour2cc.points[-1].translate(dira1.amplified(delta))
               #     a = outcontour2cc.points[0].distance(
                #        outcontour2cc.points[-1])  # Nonetype 很有可能是没有返回值的类方式直接改变了对象的类成员的值
                    # path_show([outcontour2cc, endpath])
                #else:
                 #   outcontour2cc.points[0].translate(dira2.amplified(delta))
                  #  a = outcontour2cc.points[0].distance(outcontour2cc.points[-1])
                    # path_show([outcontour2cc, endpath])# Nonetype 很有可能是没有返回值的类方式直接改变了对象的类成员的值

        outcontourconnect(child, splitCurve, endpath)

def connectpoint(endpath,outcontour2):
    value1=endpath.points[0].distance(outcontour2[0])
    value2=endpath.points[0].distance(outcontour2[-1])
    minnum=min(value1, value2)

def findindex(point: Point3D, endpath: Polyline):
    for i in range(len(endpath.points)):
        if abs(endpath.points[i].x - point.x) <= 1e-8 and abs(endpath.points[i].y - point.y) <= 1e-8:
            break
    return i

def modify_region(splitCurve:Polyline, interval):
    contour = splitCurve
    original = copy.deepcopy(contour)
    contour.points.pop()
    rnp = RNP.DNP(contour, interval, 10)
    contour = rnp.dnp()
    contour = build_connect_tree.insertpathes(contour, interval)
    contour_tensor = build_connect_tree.pathtotensor(contour)
    # build_connect_tree.path_show([self.splitCurve[int(tree.name)]])
    temp = GenDpPath5.GenDpPath([splitCurve], interval, 0)
    try:
        contours_offset = temp.contouroffset(splitCurve)
    except Small as s:
        s.msg = "modify contour too small can not offset one time"
        print(s.msg)
        outcontour = copy.deepcopy(original)
        return outcontour

    else:
        contours_offset.points.pop()
        rnp = RNP.DNP(contours_offset, interval, 10)
        contours_offset = rnp.dnp()
        contours_offset = build_connect_tree.insertpathes(contours_offset, interval)
        contours_offset_tensor = build_connect_tree.pathtotensor(contours_offset)
        min_value, index1, index2 = build_connect_tree.HD1(contour_tensor, contours_offset_tensor)
        contour.points = build_connect_tree.replaceL(index1, contour.points)
        contours_offset.points = build_connect_tree.replaceL(index2, contours_offset.points)
        outcontour = build_connect_tree.out_to_in_connect(contour, contours_offset)

def check_self_intersect(path):
    def abc(x1, y1, x2, y2, x, y):
        return (y2 - y1) * x - (x2 - x1) * y + y1 * (x2 - x1) - x1 * (y2 - y1)

    for i in range(len(path.points) - 2):
        for j in range(i + 1, len(path.points) - 1):
            x1, y1, x2, y2 = path.points[i].x, path.points[i].y, path.points[i + 1].x, path.points[i + 1].y
            x3, y3, x4, y4 = path.points[j].x, path.points[j].y, path.points[j + 1].x, path.points[j + 1].y
            # p1,p2在p3p4两边，p3,p4在p1p2两边
            if abc(x1, y1, x2, y2, x3, y3) * abc(x1, y1, x2, y2, x4, y4) < 0 and abc(x3, y3, x4, y4, x1, y1) * abc(x3,
                                                                                                                   y3,
                                                                                                                   x4,
                                                                                                                   y4,
                                                                                                                   x2,
                                                                                                                   y2) < 0:
                return True
    return False

def SelfIntersections(path, a, b, c, d):
        epsilon = 1e-20

        def LineIntersects(p1, p2, q1, q2):  # check if intersection present for segment

            def Clockwise(p0, p1, p2):  # check for intersection of all point combinations
                dx1 = p1.x - p0.x
                dy1 = p1.y - p0.y
                dx2 = p2.x - p0.x
                dy2 = p2.y - p0.y
                d = dx1 * dy2 - dy1 * dx2  # distance
                if d > epsilon: return 1
                if d < epsilon: return -1
                if dx1 * dx2 < -epsilon or dy1 * dy2 < -epsilon: return -1
                if dx1 * dx1 + dy1 * dy1 < (dx2 * dx2 + dy2 * dy2) + epsilon: return 1
                return 0

            return (Clockwise(p1, p2, q1) * Clockwise(p1, p2, q2) <= 0) and (
                    0 >= Clockwise(q1, q2, p1) * Clockwise(q1, q2, p2))

        def line(p1, p2):  # find A,B,C coefficients for line
            A = (p1.y - p2.y)
            B = (p2.x - p1.x)
            C = (p1.x * p2.y - p2.x * p1.y)
            return A, B, -C

        def IntersectionPoint(L1, L2):  # find intersection point for two lines
            D = L1[0] * L2[1] - L1[1] * L2[0]
            Dx = L1[2] * L2[1] - L1[1] * L2[2]
            Dy = L1[0] * L2[2] - L1[2] * L2[0]
            if D != 0:
                x = Dx / D
                y = Dy / D
                return x, y
            else:
                return False

        segments = path.Segments()
        end_segments = [(a, b), (c, d)]
        segments.extend(end_segments)
        present = []
        for seg1 in segments:  # for all combinations of segments
            for seg2 in end_segments:
                if (seg1[0] != seg2[1] and seg1[1] != seg2[0]) and \
                        (seg1[1] != seg2[1] and seg1[0] != seg2[0]):  # exclude points of segments connection
                    if LineIntersects(seg1[0], seg1[1], seg2[0], seg2[1]) == True:  # check if current segment intersect
                        L1 = line(seg1[0], seg1[1])  # find line coefficients (A, B, C) for segment parts
                        L2 = line(seg2[0], seg2[1])
                        P = IntersectionPoint(L1, L2)  # get point coordinate of intersection
                        present.append(P)  # add points to list
        answer = sorted(set(present))  # clean list from duplicate points
        return answer  # return list of points

def contouroffset(polygons:list, interval, flag = 0, union_flag=0):#self.offsetflag = 0、
    "将输入的polygons偏置，返回一个layer，layer有多个或者一个polygons，polygons代表一个连通区域"
    length_inner = 0
    length_out  = 0
    for poly in polygons:
        if direnction(poly) == 1:
            length_inner = length_inner + 1
        else:
            length_out = length_out + 1
    """可能有bug这里，要注意！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！"""
    if length_out == 0:
        length_out = length_inner
        length_inner = 0
    """可能有bug，注意！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！"""

    cofficient = 10000
    pco = pyclipper.PyclipperOffset()
    for poly in polygons:
        contourtuple = []
        for point in poly.points:
            var_tuple = (round(point.x * cofficient), round(point.y * cofficient))
            contourtuple.append(var_tuple)
        contourtuple = tuple(contourtuple)
        pco.AddPath(contourtuple, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
    solution = pco.Execute(-interval * cofficient)

    # if len(self.polygons) == 1 and len(self.polygons[0].points) == 121:
    #    print("check")
    # va = VtkAdaptor()
    # va.drawPolyline(splitpoly).GetProperty().SetColor(1, 0, 0)
    # va.drawPolyline(poly0).GetProperty().SetColor(0, 0, 0)
    # va.display()

    # if len(solution)==0:
    #   return solution
    # solution = numpy.array(solution)/cofficient
    # solution = solution.tolist()
    poly_out_list = []
    poly_inner_list = []
    total_polygons = []

    for i in range(len(solution)):
        solution[i] = numpy.array(solution[i]) / cofficient
        solution[i] = solution[i].tolist()
    if len(solution) == 0:
        raise Small("total area too small")
    # if len(solution) > 1:
    #    raise Pocket("the poly have the pocket and after offsetting,the poly divide into two polys")
    if flag == 0:
        for i in range(len(solution)):
            polys1 = Polyline()
            for j in range(len(solution[i])):
                point = Point3D(solution[i][j][0], solution[i][j][1], polygons[0].points[0].z)
                polys1.points.append(point)
            polys1.points.append(polys1.points[0])
            #path_show([polys1, polygons[0]])
            if direnction(polys1) == 1:
                poly_inner_list.append(polys1)
            else:
                poly_out_list.append(polys1)

        if length_inner != len(poly_inner_list) or len(
                poly_out_list) != length_out:  ###目前的一种可能轮廓孔洞离轮廓边缘太近了，一次偏置就改变了原本的拓扑，对于没分区的整体R2判定条件是，对于分区的图形就是会产生pocket
            for out_poly in poly_out_list:
                polygons = []
                polygons.append(out_poly)
                for inner_poly in poly_inner_list:
                    tuple_Point = (
                        round(inner_poly.points[0].x * cofficient), round(inner_poly.points[0].y * cofficient),
                        round(inner_poly.points[0].z * cofficient))
                    tuple_Poly = polyline_to_tuple(out_poly)
                    if pyclipper.PointInPolygon(tuple_Point, tuple_Poly) == 1:
                        polygons.append(inner_poly)
                total_polygons.append(polygons)
            raise topology(msg = "topology will be change after one time offset", polygons=total_polygons, len_inner=len(poly_inner_list))
            """
            if union_flag!=1:
                raise topology("topology will be change after one time offset", total_polygons)
            else:
                un = pyclipper.Pyclipper()
                for i in range(len(solution)):
                    solution[i] = numpy.array(solution[i])*cofficient
                    solution[i] = solution[i].tolist()
                un.AddPaths(solution, PT_SUBJECT)
                solution = un.Execute(pyclipper.CT_UNION)
                for i in range(len(solution)):
                    solution[i] = numpy.array(solution[i]) /cofficient
                    solution[i] = solution[i].tolist()

                for i in range(len(solution)):
                    polys1 = Polyline()
                    for j in range(len(solution[i])):
                        point = Point3D(solution[i][j][0], solution[i][j][1], polygons[0].points[0].z)
                        polys1.points.append(point)
                    polys1.points.append(polys1.points[0])

                return polys1
                """
        else:
            poly_out_list.extend(poly_inner_list)
            total_polygons.append(poly_out_list)
            return total_polygons
    else:
        return None

def contouroffset_SQUARE(polygons:list, interval, flag = 0, union_flag=0):#self.offsetflag = 0、
    "将输入的polygons偏置，返回一个layer，layer有多个或者一个polygons，polygons代表一个连通区域"
    length_inner = 0
    length_out  = 0
    for poly in polygons:
        if direnction(poly) == 1:
            length_inner = length_inner + 1
        else:
            length_out = length_out + 1
    """可能有bug这里，要注意！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！"""
    if length_out == 0:
        length_out = length_inner
        length_inner = 0
    """可能有bug，注意！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！"""

    cofficient = 10000
    pco = pyclipper.PyclipperOffset()
    for poly in polygons:
        contourtuple = []
        for point in poly.points:
            var_tuple = (round(point.x * cofficient), round(point.y * cofficient))
            contourtuple.append(var_tuple)
        contourtuple = tuple(contourtuple)
        pco.AddPath(contourtuple, pyclipper.JT_SQUARE, pyclipper.ET_CLOSEDPOLYGON)
    solution = pco.Execute(-interval * cofficient)

    # if len(self.polygons) == 1 and len(self.polygons[0].points) == 121:
    #    print("check")
    # va = VtkAdaptor()
    # va.drawPolyline(splitpoly).GetProperty().SetColor(1, 0, 0)
    # va.drawPolyline(poly0).GetProperty().SetColor(0, 0, 0)
    # va.display()

    # if len(solution)==0:
    #   return solution
    # solution = numpy.array(solution)/cofficient
    # solution = solution.tolist()
    poly_out_list = []
    poly_inner_list = []
    total_polygons = []

    for i in range(len(solution)):
        solution[i] = numpy.array(solution[i]) / cofficient
        solution[i] = solution[i].tolist()
    if len(solution) == 0:
        raise Small("total area too small")
    # if len(solution) > 1:
    #    raise Pocket("the poly have the pocket and after offsetting,the poly divide into two polys")
    if flag == 0:
        for i in range(len(solution)):
            polys1 = Polyline()
            for j in range(len(solution[i])):
                point = Point3D(solution[i][j][0], solution[i][j][1], polygons[0].points[0].z)
                polys1.points.append(point)
            polys1.points.append(polys1.points[0])
            #path_show([polys1, polygons[0]])
            if direnction(polys1) == 1:
                poly_inner_list.append(polys1)
            else:
                poly_out_list.append(polys1)

        if length_inner != len(poly_inner_list) or len(
                poly_out_list) != length_out:  ###目前的一种可能轮廓孔洞离轮廓边缘太近了，一次偏置就改变了原本的拓扑，对于没分区的整体R2判定条件是，对于分区的图形就是会产生pocket
            for out_poly in poly_out_list:
                polygons = []
                polygons.append(out_poly)
                for inner_poly in poly_inner_list:
                    tuple_Point = (
                        round(inner_poly.points[0].x * cofficient), round(inner_poly.points[0].y * cofficient),
                        round(inner_poly.points[0].z * cofficient))
                    tuple_Poly = polyline_to_tuple(out_poly)
                    if pyclipper.PointInPolygon(tuple_Point, tuple_Poly) == 1:
                        polygons.append(inner_poly)
                total_polygons.append(polygons)
            raise topology(msg = "topology will be change after one time offset", polygons=total_polygons, len_inner=len(poly_inner_list))
            """
            if union_flag!=1:
                raise topology("topology will be change after one time offset", total_polygons)
            else:
                un = pyclipper.Pyclipper()
                for i in range(len(solution)):
                    solution[i] = numpy.array(solution[i])*cofficient
                    solution[i] = solution[i].tolist()
                un.AddPaths(solution, PT_SUBJECT)
                solution = un.Execute(pyclipper.CT_UNION)
                for i in range(len(solution)):
                    solution[i] = numpy.array(solution[i]) /cofficient
                    solution[i] = solution[i].tolist()

                for i in range(len(solution)):
                    polys1 = Polyline()
                    for j in range(len(solution[i])):
                        point = Point3D(solution[i][j][0], solution[i][j][1], polygons[0].points[0].z)
                        polys1.points.append(point)
                    polys1.points.append(polys1.points[0])

                return polys1
                """
        else:
            poly_out_list.extend(poly_inner_list)
            total_polygons.append(poly_out_list)
            return total_polygons
    else:
        return None

def line_offset(lines,interval, dig=7 ):
        cofficient = math.pow(10, dig)
        contourtuple = []
        for point in lines.points:
            var_tuple = (round(point.x * cofficient), round(point.y * cofficient))
            contourtuple.append(var_tuple)
        contourtuple = tuple(contourtuple)
        pco = pyclipper.PyclipperOffset()
        pco.AddPath(contourtuple, pyclipper.JT_SQUARE, pyclipper.ET_OPENBUTT)
        solution = pco.Execute(interval * cofficient)
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

