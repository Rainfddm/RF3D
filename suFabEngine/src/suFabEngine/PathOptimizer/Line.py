#####
# 获取当前文件所在目录
from suFabEngine.PathOptimizer.GeomBase import *
#####

class Line:
    def __init__(self, P, V):
        self.P = P.clone()
        self.V = V.clone().normalized()

    def __str__(self):
        return "Line \nP%s\nV%s\n"%(str(self.P), str(self.V))
