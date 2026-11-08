#####
# 获取当前文件所在目录
from suFabEngine.PathOptimizer.GeomBase import *
#####

class Ray:
    def __init__(self, P, V):
        self.P = P.clone()
        self.V = V.clone()

    def __str__(self):
        return  "Ray \nP%s\nV%s\n" %(str(self.P), str(self.V))
