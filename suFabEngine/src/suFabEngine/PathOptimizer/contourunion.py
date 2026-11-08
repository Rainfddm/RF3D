import pyclipper
import numpy as np

#####
# 获取当前文件所在目录
from suFabEngine.PathOptimizer.Tree import *
from suFabEngine.PathOptimizer.arrviable import *
from suFabEngine.PathOptimizer.VtkAdaptor import *
from suFabEngine.PathOptimizer.GenDpPath5 import *
from suFabEngine.PathOptimizer.overlapY import *
from suFabEngine.PathOptimizer.Utility import *
#####

def contourunion(contour1:Polyline,contour2:Polyline):
    cofficient = 10000
    contourtuple1 = []
    contourtuple2=[]
    poly0 = Polyline()
    poly1=Polyline()
    for i in range(len(contour1.points)-1):
                var_tuple = (round(contour1.points[i].x * cofficient), round(contour1.points[i].y * cofficient) )
                contourtuple1.append(var_tuple)

    contourtuple1 = tuple(contourtuple1)
    for j in range(len(contour2.points) - 1):
            var_tuple = (round(contour2.points[j].x * cofficient), round(contour2.points[j].y * cofficient))
            contourtuple2.append(var_tuple)

    contourtuple2 = tuple(contourtuple2)
    countourlist1=[]
    countourlist2=[]
    countourlist1.append(contourtuple1)
    countourlist2.append(contourtuple2)
    pco = pyclipper.Pyclipper()
    pco.AddPaths(countourlist1, pyclipper.PT_SUBJECT,True)
    pco.AddPaths(countourlist2, pyclipper.PT_SUBJECT, True)

    solution = pco.Execute(pyclipper.CT_UNION,pyclipper.PFT_NONZERO,pyclipper.PFT_NONZERO)
    for sl1 in solution:
        for i in range(len(sl1)):
            point = Point3D(sl1[i][0] / cofficient, sl1[i][1] / cofficient)
            poly0.points.append(point)
        poly0.points.append(Point3D(sl1[0][0] / cofficient, sl1[0][1] / cofficient))
    for sl2 in solution:
        for i in  range(len(sl2)):
            point = Point3D(sl2[i][0] / cofficient, sl2[i][1] / cofficient)
            poly1.points.append(point)
        poly1.points.append(Point3D(sl2[0][0] / cofficient, sl2[0][1] / cofficient))
    #va1=VtkAdaptor()
    #va2=VtkAdaptor()
    #va1.drawPolyline(poly0).GetProperty().SetColor(1,0,1)
    #va2.drawPolyline(contour1).GetProperty().SetColor(1,0,0)
    #va2.drawPolyline(contour2).GetProperty().SetColor(1, 0, 1)

    #va2.display()
    #va1.drawPolyline(poly1).GetProperty().SetColor(1,0,0)
    #va1.display()

    solution = numpy.array(solution) / cofficient
    solution = solution.tolist()
    polys3 = Polyline()
    polys4 = solution
    for K in range(len(polys4[0])):
        point = Point3D(polys4[0][K][0], polys4[0][K][1])
        polys3.points.append(point)
    polys3.points.append(polys3.points[0])
    polys3=contouroffset(polys3)
    #for i in range(len(polys3)):

    return polys3
def contouroffset(splitpoly:Polyline):
        cofficient=100000
        contourtuple=[]
        poly0=Polyline()
        for point in splitpoly.points:
            var_tuple=(round(point.x * cofficient), round(point.y* cofficient))
            contourtuple.append(var_tuple)
        contourtuple=tuple(contourtuple)
        pco = pyclipper.PyclipperOffset()
        pco.AddPath(contourtuple, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
        solution = pco.Execute(-5)
        #for sl1 in solution:
           # for i in range(len(sl1)):
             #   point=Point3D(sl1[i][0]/cofficient,sl1[i][1]/cofficient)
              #  poly0.points.append(point)
            #poly0.points.append(Point3D(sl1[0][0]/cofficient,sl1[0][1]/cofficient))
        #va = VtkAdaptor()
        #va1=VtkAdaptor()
        #va1.drawPolyline(splitpoly).GetProperty().SetColor(0, 0, 0)
        #va1.display()
        #va.drawPolyline(poly0).GetProperty().SetColor(0, 0, 0)
        #va.display()
        solution = numpy.array(solution) / cofficient
        solution=solution.tolist()
        polys3 = Polyline()
        polys4 = solution
        for K in range(len(polys4[0])):
            point = Point3D(polys4[0][K][0], polys4[0][K][1])
            polys3.points.append(point)
        polys3.points.append(polys3.points[0])
        # for i in range(len(polys3)):
        return polys3
