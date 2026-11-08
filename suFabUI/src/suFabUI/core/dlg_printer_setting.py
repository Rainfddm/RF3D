# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QFrame, QWidget, QAction, QTableWidget, QTableWidgetItem, QHeaderView, QDialog

#####
# 获取当前文件所在目录
from suFabUI.core.ui_printer_setting import *
#####

import numpy as np
class DlgPrinterSetting(QDialog):
    def __init__(self):
        super().__init__()
        self.ui = Ui_PrinterSettingDialog()
        self.ui.setupUi(self)
        self.setModal(True)     
        
        # message connection       
        self.ui.pb_connect_test.clicked.connect(self.connect_test)
        
        self.ui.pb_OK.clicked.connect(self.OK)
        self.ui.pb_Cancel.clicked.connect(self.Cancel)
           
    def show(self):
        super(DlgPrinterSetting, self).show()
        self.exec_()
    
    def OK(self):
        self.close()
    
    def Cancel(self):
        self.close()

    def message(self, msg):
        win = self.ui.planText_message
        win.appendPlainText(msg)
        
    def connect_test(self):
        self.message("测试打印机连接")
        
