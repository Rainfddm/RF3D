# -*- coding: utf-8 -*-
"""View 层 — 主窗口控制器，负责界面交互与工艺流程调度"""

from typing import Dict, Any, Callable
import inspect
import logging
import time
import numpy as np
import traceback
import os

from suFabUI.core.ui_main_window import *
from suFabUI.core.VTKViewer import *
from suFabUI.core.dlg_printer_setting import *
from suFabUI.core.ui_about import *
from suFabUI.core.ui_printer_setting import *
from suFabUI.core.class_base import *
from suFabUI.core.controller import Controller
from suFabUI.core.common_funcs import *
from suFabUI.core.VTKSceneTreeWidget import *
from suFabUI.core.GcodeGenerator import *
from suFabEngine.Gcode import *
from suFabUI.core.GcodePaser import *
from suFabEngine.GCoder.suGCoder import *
from suFabEngine.PathOptimizer.PathOptimizer import *
from suFabUI.core.class_base import *

from PyQt5.QtWidgets import QWidget, QDialog, QFileDialog, QSplashScreen, QMainWindow, QSizePolicy, QPushButton
from PyQt5.QtGui import QFont, QIcon, QImage, QPixmap
from PyQt5.QtCore import QBasicTimer

from pathlib import Path
from os import path
import vtk

from suAgent.process_decision_engine import ProcessDecisionEngine

_PARAM_DEFAULTS = ProcessDecisionEngine().default_params

class Viewer(Ui_suFab_MainWindow):
    def __init__(self):
        super(Ui_suFab_MainWindow, self).__init__()                      

        splash_pix = QPixmap(':/icons/splash.png')
        self.splash = QSplashScreen(splash_pix, QtCore.Qt.WindowStaysOnTopHint)
        self.splash.show()         
                
        self.controller = Controller(self)   
        self.progress = 0
        self.timer = QBasicTimer()

        # App status
        self.b_stl_loaded = False
        self.b_stl_sliced = False
        self.params = {}
        self.current_model_path = None  # 当前/最近加载的模型路径（供 AI 兜底加载）

        # App setting
        self.app_name = "suFab"
        self.com_name = "RMEC"

        # Add method mapping for AI invoking
        self.commands: Dict[str, Callable] = {}

        # register method when init
        self._register_methods()
        
    # 添加一个方法来安全地检查UI组件是否存在
    def _is_ui_ready(self):
        """检查UI是否已经准备好"""
        try:
            # 检查关键UI组件是否存在
            return (hasattr(self, 'MainWindow') and 
                   hasattr(self, 'lineEdit_delta') and
                   hasattr(self, 'lineEdit_nozzle_d') and
                   hasattr(self, 'lineEdit_filament_d'))
        except:
            return False

    # Register all method start with "_run_"
    def _register_methods(self):
        """自动注册所有以_run_开头的方法"""
        for name, method in inspect.getmembers(self, inspect.ismethod):
            if name.startswith('_run_'):
                command_name = name[5:]  # 移除'_run_'前缀
                self.commands[command_name] = method
                logging.info(f"Registered command: {command_name}")

    def execute_cmd(self, command_name: str, **params) -> Any:
        """执行指定的命令"""
        # 将命令名称转换为方法名称
        method_name = f"_run_{command_name}"

        if command_name not in self.commands:
            raise ValueError(f"Unknown command: {command_name}")

        try:
            logging.info(f"Executing command: {command_name}： {params}")
            return self.commands[command_name](**params)
        except Exception as e:
            logging.error(f"Error executing {command_name}: {str(e)}")
            raise RuntimeError(f"Error executing {command_name}: {str(e)}")

    def enable_all_push_buttons(self, status=True):
        """
        Disables all QPushButton objects in the given window.

        Args:
        window (QWidget): The window containing the QPushButtons to be disabled.
        """
        for widget in  self.MainWindow.findChildren(QPushButton):
            widget.setEnabled(status)

    def setupUi(self, MainWindow):
        self.MainWindow = MainWindow
        Ui_suFab_MainWindow.setupUi(self,MainWindow)                            
     
        self.load_config()    
        
        # set logger window
        self.logger = WinLoggerHandler(self.text_console)
        self.logger.register_logger()            
        self._connect_signals(MainWindow)
        #self.setFixedSize(self.size())
        # Restore window configs
        self.read_settings()      
        self.splash.close() 

        # set scene management window
        # replace old treeWidgetScene
        self.formFrame_tab_display.layout().removeWidget(self.treeWidgetScene)
        #self.treeWidgetScene.deleteLater()

        self.treeWidgetScene = VTKSceneTreeWidget(self.view3d)
        self.treeWidgetScene.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.formFrame_tab_display.layout().addRow(self.treeWidgetScene)

        # Test
        self.verticalSlider_layer_index.setMinimum(0)    # Set minimum value
        self.verticalSlider_layer_index.setMaximum(0)  # Set maximum value
        self.verticalSlider_layer_index.setSingleStep(1)  # Set step value for single steps
        self.verticalSlider_layer_index.setPageStep(5)  # Set step value for page steps

        self.enable_all_push_buttons(False)
        self.aiTerminal.set_viewer(self)

    def update_ui_parameters(self, params: dict):
        """更新UI控件参数"""
        if "nozzle_d" in params:
            self.lineEdit_nozzle_d.setText(str(params["nozzle_d"]))
        if "filament_d" in params:
            self.lineEdit_filament_d.setText(str(params["filament_d"]))
        if "layer_height" in params:
            self.lineEdit_delta.setText(str(params["layer_height"]))
    def _apply_default_params_to_ui(self):
        """用 ProcessDecisionEngine 默认参数统一初始化 UI 控件（对齐 Web 端 default_params）。

        消除桌面端 UI 默认值与 Web 端 default_params 的漂移
        （如 first_layer_height 0.3 vs 0.2、offset 0.6 vs 0.8）。
        需在 setupUi() 之后调用。
        """
        ui_map = {
            "layer_height": "lineEdit_delta",
            "first_layer_height": "lineEdit_first_delta",
            "offset": "lineEdit_offset",
            "nozzle_d": "lineEdit_nozzle_d",
            "filament_d": "lineEdit_filament_d",
        }
        for key, widget_name in ui_map.items():
            if key in _PARAM_DEFAULTS and hasattr(self, widget_name):
                getattr(self, widget_name).setText(str(_PARAM_DEFAULTS[key]))

    def _update_process_params(self):
        """从 UI 控件读取参数，仅在 UI 准备就绪时执行"""
        if not self._is_ui_ready():
            return
        self.params["layer_height"] = float(self.lineEdit_delta.text())
        self.params["first_layer_height"] = float(self.lineEdit_first_delta.text())
        self.params["offset"] = float(self.lineEdit_offset.text())
        self.params["reinforced_fiber_d"] = float(self.lineEdit_reinforced_fiber_d.text())
        self.params["base_fiber_d"] = float(self.lineEdit_base_fiber_d.text())
        self.params["nozzle_d"] = float(self.lineEdit_nozzle_d.text())
        self.params["filament_d"] = float(self.lineEdit_filament_d.text())
    
    def _update_scene(self):
        """更新场景树控件"""
        try:
            self.treeWidgetScene.init_tree()
        except Exception:
            logging.exception("更新场景树失败") 

    def _connect_signals(self, MainWindow):
        # menu action
        self.action_open.triggered.connect(self.load_file)
        self.action_export.triggered.connect(self.export_file)
        self.action_exit.triggered.connect(self.app_quit)
        self.action_about.triggered.connect(self.about)        
        self.action_printer_setting.triggered.connect(self.printer_setting)
        # widget action
        self.comb_disp_mode.currentIndexChanged.connect(self.on_combobox_disp_mode_changed)
        self.comb_disp_angle.currentIndexChanged.connect(self.on_combobox_angle_changed)
        self.slider_transparent.valueChanged.connect(self.on_slider_transparant_changed)
        # button action
        self.pushButtonRunWorkflow.clicked.connect(self.run_workflow)
        
    def on_combobox_disp_mode_changed(self):
        render_mode = self.comb_disp_mode.currentText()
        logging.info('DISP_MODE={}'.format(render_mode))
        self.view3d.set_display_mode(render_mode)

    def on_slider_transparant_changed(self):
        value = 1 - self.slider_transparent.value()/100
        logging.info('Transparancy={}'.format(value))
        self.view3d.set_transparancy(value)

    def on_combobox_angle_changed(self):
        value = self.comb_disp_angle.currentText()
        logging.info('ViewAngle={}'.format(value))
        if value == "Normal":
            self.view3d.setup_default_camera()
        elif value == "X":
            self.view3d.setup_default_camera(position=(300, 0, 0), view_up=(0, 0, 1))
        elif value == "Y":
            self.view3d.setup_default_camera(position=(0, 300, 0), view_up=(0, 0, 1))
        elif value == "Z":
            self.view3d.setup_default_camera(position=(0, 0, 300), view_up=(0, 1, 0))

    def closeEvent(self, event):
        # Save window configs
        self.write_settings()
        QMainWindow.closeEvent(self, event) 

    def write_settings(self):
        settings = QtCore.QSettings(self.com_name, self.app_name)
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())

    def read_settings(self):
        settings = QtCore.QSettings(self.com_name, self.app_name)
        geometry = settings.value("geometry", QtCore.QByteArray())
        if geometry:
            self.restoreGeometry(geometry)
        windowState = settings.value("windowState", QtCore.QByteArray())
        if windowState:
            self.restoreState(windowState)

    def run_workflow(self):
        """执行当前选中的工作流"""
        try:
            selected_item = self.comboWorkflow.currentText()
            logging.info("运行工作流: %s", selected_item)

            self._update_process_params()

            workflow_map = {
                "模型切片": self._run_slicing_workflow,
                "单层连续路径生成": self._run_one_layer_fill,
                "全局连续路径生成": self._run_global_fill,
                "单层连续路径优化": self._run_one_layer_optimize,
                "单层GCode生成": self._run_onelayer_gcode_generation,
                "全局GCode生成": self._run_gcode_generation
            }

            if selected_item in workflow_map:
                workflow_map[selected_item]()
            else:
                logging.error("未知工作流: %s", selected_item)

        except Exception:
            logging.exception("工作流执行异常")
        
    def _run_slicing_workflow(self):
        self._update_process_params()
        if not self.b_stl_loaded:
            return

        def call_back(value, algo_name="进度："):
            if self._is_ui_ready():
                self.label_progressbar.setText(algo_name)
                self.progressBar.setValue(int(round(value)))

        self.view3d.clear("process")
        self.view3d.clear("layer")

        polygons = self.view3d.get_data("model")
        poly_lines = self.controller.slicing(self.params, polygons, True, callback=call_back)
        if self._is_ui_ready():
            call_back(0, "Clearing..")
            self.view3d.clear("process")
            call_back(0, "进度")
        self.view3d.add_polylines(poly_lines)
        if self._is_ui_ready():
            call_back(100, "进度")

        _nLayer = len(self.controller.planes) - 1
        logging.info("切片完成，共 %d 层", _nLayer)
        if self._is_ui_ready():
            self.verticalSlider_layer_index.setMinimum(0)
            self.verticalSlider_layer_index.setMaximum(_nLayer)
            self.verticalSlider_layer_index.setValue(_nLayer)
            self.verticalSlider_layer_index.update()

        self._update_scene()
        if self._is_ui_ready():
            self.enable_all_push_buttons()

    def _run_one_layer_fill(self):
        # Define callback to show the progress, no thread here, so the UI is blocked!
        def call_back(value, algo_name="进度：", progressbar=self.progressBar, label=self.label_progressbar):
            label.setText(algo_name)
            progressbar.setValue(int(round(value)))   

        self._update_process_params()
        iLayer = int(self.label_layer_index.text())
        self.view3d.clear_layer(iLayer)
        # Clear original path
        cur_layer_polylines = self.controller.fill_layer(self.params, iLayer, call_back=call_back)
        actors = []
        for p in cur_layer_polylines:
            actor = self.view3d.add_polyline(p)
            actors.append(actor)
        # add actors to layer
        self.view3d.actors["layer"][str(iLayer)] = actors
        return
    def _run_global_fill(self):
        """全局连续路径生成"""
        self._update_process_params()
        try:
            # 获取总层数
            _nLayer = len(self.controller.planes) - 1
            if _nLayer <= 0:
                logging.error("未找到切片数据，请先执行模型切片")
                return

            # 定义进度回调
            def call_back(value, algo_name="进度：", progressbar=self.progressBar, label=self.label_progressbar):
                if self._is_ui_ready():
                    label.setText(f"{algo_name} ({int(value)}%)")
                    progressbar.setValue(int(value))

            # 清空现有路径
            self.view3d.clear("process")
            self.view3d.clear("layer")
            self._update_process_params()

            # 遍历所有层
            for iLayer in range(_nLayer):
                if self._is_ui_ready():
                    call_back((iLayer / _nLayer) * 100, "进度")
                
                # 生成单层路径
                cur_layer_polylines = self.controller.fill_layer(self.params, iLayer)
                
                # 添加路径到场景
                actors = []
                for p in cur_layer_polylines:
                    actor = self.view3d.add_polyline(p, color=(0, 1, 0))
                    actors.append(actor)
                
                # 按层存储actor
                self.view3d.actors["layer"][str(iLayer)] = actors

                if self._is_ui_ready():
                    QApplication.processEvents()  # 保持UI响应

            if self._is_ui_ready():
                call_back(100, "完成")
            self._update_scene()
            logging.info("全局路径生成完成")

        except Exception as e:
            logging.error(f"全局路径生成失败: {str(e)}")

    def _run_one_layer_optimize(self):
        """对当前层路径进行优化"""
        try:
            # 获取当前层索引，仅在UI准备就绪时执行
            if self._is_ui_ready():
                iLayer = int(self.label_layer_index.text())
            else:
                # 默认使用第0层
                iLayer = 0
            
            # 定义进度回调
            def call_back(value, algo_name="进度：", progressbar=self.progressBar, label=self.label_progressbar):
                if self._is_ui_ready():
                    label.setText(f"{algo_name} ({int(value)}%)")
                    progressbar.setValue(int(value))
            
            # 获取当前层路径数据
            cur_layer_polylines = self.controller.get_layer_path(iLayer)  # 假设存在获取路径的方法
            if not cur_layer_polylines:
                logging.warning(f"第{iLayer}层无路径数据，跳过优化")
                return

            # 转换为NumPy数组
            path_data = np.array([list(pt) for pt in cur_layer_polylines])
            
            # 调用优化器，仅在UI准备就绪时从lineEdit读取参数
            if self._is_ui_ready():
                interval = float(self.lineEdit_offset.text())  # 从UI获取间隔参数
            else:
                interval = self.params.get("offset", 0.0)  # 从params获取间隔参数
            
            optimized_path = self.controller.optimize_path(
                connective_path=path_data,
                interval=interval,
                iter_times=10,
                lamda=0.01
            )
            
            # 清除当前层旧路径
            self.view3d.clear_layer(iLayer)
            
            # 路径优化后的路径转换为VTK PolyLine并添加到场景
            actors = []
            for point in optimized_path:
                actor = self.view3d.add_polyline(point, color=(1, 0, 0))  # 红色表示优化路径
                actors.append(actor)
            
            # 更新场景中的路径数据
            self.view3d.actors["layer"][str(iLayer)] = actors
            if self._is_ui_ready():
                call_back(100, "优化完成")
            logging.info(f"第{iLayer}层路径优化完成")

        except Exception as e:
            logging.error(f"路径优化失败: {str(e)}\n{traceback.format_exc()}")
    
    def _run_onelayer_gcode_generation(self):
        """生成单层GCode（待实现）"""
        logging.warning("单层GCode生成功能尚未实现")

    def _run_gcode_generation(self):
        """生成全局 GCode 并保存至文件，同时返回GCode内容"""
        try:
            # 检查模型是否加载
            if not hasattr(self, 'point_set') or not self.point_set:
                # 在后端模式下，检查是否有其他方式确认模型已加载
                if not self.b_stl_loaded:
                    logging.error("未加载模型点集，请先加载模型。")
                    return None

            self._update_process_params()

            file_path = None
            if self._is_ui_ready():  # UI模式
                file_path, _ = QFileDialog.getSaveFileName(
                    self.MainWindow,
                    "保存 GCode 文件",
                    "",
                    "GCode 文件 (*.gcode)"
                )
                # 即使用户取消，在后端模式下我们仍然继续生成GCode内容
                if not file_path and self._is_ui_ready():
                    return None  # UI模式下用户取消操作

            # 确保 Pipeline 初始化
            if not self.controller.pipeline:
                logging.error("Pipeline 未初始化，请先执行切片。")
                return None

            # 传递参数给 Pipeline
            self.controller.pipeline.load_params(self.params)

            # 调用 Pipeline 生成路径
            raw_path = self.controller.pipeline.generate_global_path(
                collision_dist_xy=30,
                collision_dist_z=3000,
                offset=self.params.get("offset", 0.8)
            )

            # 复用 PipelineExecutor 的路径校验逻辑
            path = self.controller.executor._build_validated_path(raw_path)
            logging.info(f"路径数据验证通过，形状: {path.shape}")
            
            def call_back(value, total=100, algo_name="进度：", progressbar=self.progressBar, label=self.label_progressbar):
                percent = int(round((value / total) * 100))
                if self._is_ui_ready():
                    label.setText(f"{algo_name} {percent}%")
                    progressbar.setValue(percent)
                    QApplication.processEvents()

            # 同步参数到 executor 并复用其 GCode 生成逻辑
            self.controller.executor.params.update(self.params)
            gcode_generator = self.controller.executor.build_gcode(path, callback=call_back)
            
            # 保存到文件（仅在UI模式下）
            if file_path and self._is_ui_ready():
                gcode_generator.save(file_path)
            
            # 获取并返回GCode内容
            gcode_content = "".join(gcode_generator.output_lines)

            if file_path and self._is_ui_ready():
                logging.info(f"GCode 已成功生成并保存至：{file_path}")
            else:
                logging.info("GCode 已成功生成（未保存到文件）")
                
            return gcode_content

        except Exception:
            logging.exception("GCode 生成失败")
            return None

    def _run_load_model(self, file_path=None):
        """加载模型文件"""
        if not file_path:
            logging.warning("load_model 收到空文件路径，跳过加载")
            return
        ext_file = file_path.split('.')[-1].lower()
        if ext_file == 'stl':
            res = self.controller.load_stl(file_path)
            self.point_set = [
                res.GetPoints().GetPoint(i)
                for i in range(res.GetPoints().GetNumberOfPoints())
            ]
            self.b_stl_loaded = True
            self.current_model_path = file_path
            self._update_scene()
            self.enable_all_push_buttons()
   
 # Menu actions       
    def app_quit(self):
        self.MainWindow.close()
    
    def about(self):
        dialog = QDialog()
        dialog.ui = Ui_AboutDialog()
        dialog.ui.setupUi(dialog)
        dialog.setModal(True)
        dialog.show()
        dialog.exec_()
   
    def load_config(self):
        #self.controller.load_setting()            
        #self.refresh()
        return
    
    def update_progress(self, value):
        """
        Callback function to update the progress bar's value.
        """
        self.progressBar.setValue(value)
    
    def load_file(self):
        fname = QFileDialog.getOpenFileName(
            self, 'Open file', '',
            "stl model (*.stl);;G code (*.gcode);; path data (*.path);"
        )
        try:
            if not fname[0]:
                return
            ext_file = path.splitext(fname[0])[1].lower()
            if ext_file not in fname[1]:
                return

            logging.info("加载文件: %s", fname[0])
            if ext_file == '.path':
                self.controller.load_path(fname[0])
            elif ext_file == '.gcode':
                self.controller.load_gcode(fname[0])
            elif ext_file == '.stl':
                self.controller.load_stl(fname[0])
                self.b_stl_loaded = True
                self.current_model_path = fname[0]

            self._update_scene()
            self.enable_all_push_buttons()

        except Exception:
            logging.exception("加载文件失败")
       
    def export_file(self):
        fname = QFileDialog.getSaveFileName(self, 'Export file', '', "Path (*.txt);")
        if not fname[0]:
            return
        ext_file = path.splitext(fname[0])[1]
        if ext_file in fname[1]:
            logging.info("导出文件: %s", fname[0])
            if ext_file == '.txt':
                self.controller.export_path(fname[0])
        else:
            logging.warning("%s 不是合法的导出文件名", fname[0])
        
    def printer_setting(self):
        logging.info("需添加设置界面功能，同步设置到全局设置对象中。")
        dlg = DlgPrinterSetting()        
        dlg.show()               
        
    # trigger functions
    def gen_gcode(self):
        pass

    def gen_path(self):
        self.controller.gen_path()
        pass        

    def start_progress(self):
        if self.timer.isActive():
            self.timer.stop()
        self.timer.start(1, self)
        
    def pause_progress(self):
        if self.timer.isActive():
            self.timer.stop()        
            self.pb_start.setEnabled(True)
            self.pb_pause.setEnabled(False)
            self.pb_stop.setEnabled(True)               

    def stop_progress(self):
        if self.timer.isActive():
            self.timer.stop()
            self.progress = 0
        self.pb_start.setEnabled(True)
        self.pb_pause.setEnabled(False)
        self.pb_stop.setEnabled(False)        

    def timerEvent(self, event):
        if self.progress >= 100:
            self.timer.stop()
            self.pb_start.setEnabled(True)
            self.pb_pause.setEnabled(False)
            self.pb_stop.setEnabled(False)                 
            return
        # self.progress +=1
        self.controller.render_current_path()
        self.progressBar.setValue(self.progress)            
        self.repaint()
        return     
    
    def _reset_progressBar(self):
        self.progress = 0
        self.progressBar.setValue(self.progress)

#####
    def get_ui_parameter(self, param_name):
        """获取UI参数值，UI未就绪时返回默认值"""
        if not self._is_ui_ready():
            return _PARAM_DEFAULTS.get(param_name, 0.0)

        param_map: Dict[str, Callable[[], float]] = {
            "layer_height":       lambda: float(self.lineEdit_delta.text()),
            "first_layer_height": lambda: float(self.lineEdit_first_delta.text()),
            "offset":             lambda: float(self.lineEdit_offset.text()),
            "nozzle_d":           lambda: float(self.lineEdit_nozzle_d.text()),
            "filament_d":         lambda: float(self.lineEdit_filament_d.text()),
        }

        if param_name in param_map:
            try:
                return param_map[param_name]()
            except (ValueError, AttributeError):
                return _PARAM_DEFAULTS.get(param_name, 0.0)
        return None
    def set_ui_parameter(self, param_name, value):
        """设置UI参数值"""
        param_map = {
            "layer_height": self.lineEdit_delta,
            "first_layer_height": self.lineEdit_first_delta,
            "offset": self.lineEdit_offset,
            "nozzle_d": self.lineEdit_nozzle_d,
            "filament_d": self.lineEdit_filament_d,
            "reinforced_fiber_d": self.lineEdit_reinforced_fiber_d,
            "base_fiber_d": self.lineEdit_base_fiber_d,
        }

        if param_name in param_map and self._is_ui_ready():
            param_map[param_name].setText(str(value))