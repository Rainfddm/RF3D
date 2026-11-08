3
# -*- coding: utf-8 -*-
###############################################################
"""
Development Tips
1) pip install pyqt5-tools
2) design UI generate .ui file by [pythonpath]\Lib\site-packages\pyqt5-tools\designer.exe
3) compile rc and ui
     pyrcc5 resource.qrc -o resource_rc.py
     pyuic5 ./**.ui -o **.py
     Instead of running above, we can run script update_ui.py in the directory scripts.
     Add self.setFixedSize(self.size())
     Add callback

4) add a capsulator
"""
###############################################################
import sys
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication

# local dependencies
from suFabUI.core.suView import Viewer

from suFabUI.core import global_settings as configs


class MainApp(QtWidgets.QMainWindow, Viewer):
    def __init__(self, parent=None):
        super(MainApp, self).__init__(parent)
        self.setupUi(self)
        # 用默认参数统一初始化 UI 控件（对齐 Web 端 default_params）
        self._apply_default_params_to_ui()


def main():
    configs.init()   # load global settings
    app = QApplication(sys.argv)
    form = MainApp()
    form.show()
    app.exec_()


if __name__ == '__main__':
    main()

