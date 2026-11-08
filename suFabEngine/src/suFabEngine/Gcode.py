#####

import os
# 获取当前文件所在目录
from suFabEngine import constants as c
#####
class Gcode:

    def __init__(self, param):
        '''
        start_code_path
        end_code_path
        print_speed
        
        '''
        self.pr = param
        #####
        # self.start_gcode_path = param.get('start_Gcode_FileName', '')
        # self.end_gcode_path = param.get('end_Gcode_FileName', '')
        self.print_speed = param.get('printSpeed', 200)
        #####
        
    def feedMove(self, endPoint, extrudeTo, printSpeed):
        extrudeString = ''
        if extrudeTo > 0:
            extrudeString = 'E{:.3f}'.format(extrudeTo)
        
        tempString = ('X{:.3f} Y{:.3f} {}'.format(endPoint[0],
                                                  endPoint[1], extrudeString))
        return 'G1 ' + tempString + ' F{:.0f}\n'.format(printSpeed)                    
    
    def feedMoveZ(self, z, printSpeed):
        tempString = ('Z{:.3f} F{:.0f}\n'.format(z, printSpeed))
        return 'G1 ' + tempString
                      
    def rapidMove(self, endPoint, atClearance=False):
        return ('G00 X{:.3f} Y{:.3f} Z{:.4f} F{:.0f}\n'.format(endPoint.x,
                                                               endPoint.y,
                                                                endPoint.z + atClearance*self.pr.ZHopHeight,
                                                                self.pr.RAPID))

    def retractLayer(self, currentE, currentPoint):
        tempString = 'G1 E{:.3f} F{:.0f}\n'.format(currentE-self.pr.retractDistance, self.pr.retractSpeed)
        tempString += 'G00 Z{:.3f} F{:.0f}\n'.format(currentPoint.z+self.pr.ZHopHeight, self.pr.RAPID)
        return tempString

    def approachLayer(self, lastE, startPoint):
        tempString = 'G1 Z{:.3f} F{:.0f} E{:.3f}\n'.format(startPoint.z+self.pr.ZHopHeight/2.0,
                                                           self.pr.RAPID, lastE-self.pr.retractDistance*0.75)
        tempString += 'G1 Z{:.3f} F{:.0f} E{:.3f}\n'.format(startPoint.z,
                                                            self.pr.APPROACH_FR, lastE)
        return tempString

    def firstApproach(self, lastE, startPoint):
        return 'G1 Z{:.3f} F{:.0f} E{:.3f}\n'.format(startPoint.z, self.pr.APPROACH_FR, lastE)

    def newPart(self):
        return 'G92 E0\n'

    def operatorMessage(self, *args, sep=' '):
        return 'M117 '+ sep.join(str(arg) for arg in args) + '.\n'

    def comment(self, comment):
        return self.pr.comment + ' ' + comment

    def startGcode(self, extruder_temp=210, bed_temp=50):
        with open(self.pr['start_Gcode_FileName']) as startFile:
            lines = startFile.readlines()   
            tempString = []
            for line in lines:
                line = str(line).replace(c.EXTRUDER_TEMP_FLAG, 'S'+str(extruder_temp))
                line = line.replace(c.BED_TEMP_FLAG, 'S'+str(bed_temp))
                tempString.append(line)
            return ''.join(tempString) + '\n\n'

    def endGcode(self):
        with open(self.pr['end_Gcode_FileName']) as endFile:
            return ''.join(endFile.readlines())
        
if __name__ == '__main__': 
    '''
    Test:
    convert path to GCode
    '''
    import numpy as np
    import json
    import os
    import math
    from pathlib import Path
    
    cwd = os.getcwd()
    parent_cwd = Path(cwd).parent
    
    start_code_path = os.path.join(str(parent_cwd), 'process/configs', 'start.gcode')
    end_code_path = os.path.join(str(parent_cwd), 'process/configs', 'end.gcode')
    pts = np.random.random([10,3])
    print(pts)
    param = {'startEndSubDirectory': 'configs/', 'start_Gcode_FileName': start_code_path,
             'end_Gcode_FileName': end_code_path, 'printSpeed': 200}
    
    def resample_by_curvature(pts):
        return pts
    
    gc = Gcode(param)
    
    str_gcode = ''
    str_gcode = str_gcode + gc.startGcode()
    
    cur_point = pts[0]
    cur_z = -1.0
    for pt in pts:          
        if not math.isclose(pt[2], cur_z):
            cur_z = pt[2]            
            str_gcode += gc.feedMoveZ(cur_z, 300)            
            
        str_gcode += gc.feedMove(pt, 0, param['printSpeed'])
        
        # z 
    str_gcode += gc.endGcode()  
    print(str_gcode)

