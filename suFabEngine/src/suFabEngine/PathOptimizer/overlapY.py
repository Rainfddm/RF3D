#####
# 获取当前文件所在目录
from suFabEngine.PathOptimizer.Polyline import *
from suFabEngine.PathOptimizer.arrviable import *
#####

class overlapY:
    def __init__(self):
        self.lh=[]
        self.ll=[]

    def findhly(self,countour1: Polyline, countour2: Polyline):
        listY1 = []
        listY2 = []
        higher = None
        for i in range(len(countour1.points) - 1):
            for j in range(len(countour2.points) - 1):
                a = arrviable.overlap(countour1.points[i], countour1.points[i + 1], countour2.points[j], countour2.points[j + 1])
                if (a == 1):
                    if (countour1.points[i].y == countour1.points[i + 1].y):
                        listY1.append(countour1.points[i].y)
                    if (countour2.points[j].y == countour2.points[j + 1].y):
                        listY2.append(countour2.points[j].y)
                    if (listY1[0] > listY2[0]):
                        self.lh.append(listY1[0])
                        self.ll.append(listY2[0])

                    else:
                        self.lh.append(listY2[0])
                        self.ll.append(listY1[0])
