"""AI终端模块 — 自然语言驱动的3D打印工艺流程控制"""

import json
import os
import time
import traceback
import logging

import openai
from PyQt5.QtWidgets import QTextEdit, QApplication, QFileDialog
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QTextCursor, QKeyEvent

def _load_dotenv():
    """从项目根目录 .env 文件加载环境变量（不依赖第三方库）"""
    _dotenv_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "../../../../", ".env"
    )
    if not os.path.exists(_dotenv_path):
        return
    with open(_dotenv_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip()
            if key and val and key not in os.environ:
                os.environ[key] = val

_load_dotenv()

from suFabUI.core.suView import *

from suFabEngine.pipeline_commands import PipelineDispatcher, STANDARD_PRECONDITIONS
from suFabEngine.ai_agent import PrintingControlAgent

# 模块所在目录（用于 commands.json 等资源文件的绝对路径解析）
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__)) 

class AITerminal(QTextEdit):
    # 定义信号
    command_executed = pyqtSignal(str, str)  # 命令执行信号(命令, 结果)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.prompt = "需求描述> "
        self.history = []
        self.history_index = 0
        self.current_command = ""
        self.commands = {}  # 命令映射字典
        self.chat_agent = PrintingControlAgent("fab_commander_agent", "fab_agent")
        self.chat_agent.use("kimi", "moonshot-v1-8k", 1000)
        self.viewer = None
        self.result_json = {}
        # 初始化界面
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #FFFFFF;
                font-family: Consolas, Monaco, monospace;
                font-size: 12pt;
                padding: 5px;
            }
        """)

        # 加载命令配置
        self.load_commands()

        # 显示欢迎信息
        self.append("欢迎使用AI终端! 输入'help'获取帮助。")
        self.append(self.prompt)

        # 保存提示符位置
        self.prompt_position = self.textCursor().position()

    def set_viewer(self, main_window_viewer):
        # 遍历父窗口直到找到指定类型
        self.viewer = main_window_viewer

    def _commands_path(self) -> str:
        """返回 commands.json 的绝对路径"""
        return os.path.join(_MODULE_DIR, "commands.json")

    def load_commands(self):
        """加载命令配置"""
        try:
            path = self._commands_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    self.commands = json.load(f)
        except Exception:
            self.commands = {"帮助": "help", "清屏": "clear", "退出": "exit"}

    def keyPressEvent(self, event: QKeyEvent):
        cursor = self.textCursor()

        if event.key() == Qt.Key_Return:
            current_line = self.toPlainText().split('\n')[-1]
            command = current_line[len(self.prompt):].strip()

            if command:
                self.history.append(command)
                self.history_index = len(self.history)
                self.execute_command(command)

            self.append(self.prompt)
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.setTextCursor(cursor)
            self.prompt_position = cursor.position()
            return

        elif event.key() == Qt.Key_Up:
            if self.history_index > 0:
                self.history_index -= 1
                self.show_history_command()
            return

        elif event.key() == Qt.Key_Down:
            if self.history_index < len(self.history):
                self.history_index += 1
                self.show_history_command()
            return

        elif event.key() == Qt.Key_Backspace:
            if cursor.position() <= self.prompt_position:
                return

        elif event.key() == Qt.Key_Left:
            if cursor.position() <= self.prompt_position:
                return

        elif cursor.position() < self.prompt_position:
            cursor.movePosition(QTextCursor.End)
            self.setTextCursor(cursor)

        super().keyPressEvent(event)

    def show_history_command(self):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.movePosition(QTextCursor.StartOfLine, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(self.prompt)

        if self.history_index < len(self.history):
            cursor.insertText(self.history[self.history_index])

    def execute_command(self, command):
        """执行命令"""
        cmd = command.lower()
        for key, value in self.commands.items():
            if key in command:
                cmd = value
                break

        result = ""
        if cmd == "help":
            result = self.show_help()
        elif cmd == "clear":
            self.clear()
            result = "屏幕已清空"
        elif cmd == "exit":
            QApplication.quit()
            result = "程序已退出"
        else:
            result_dict = self.chat_agent.run_cmd(query=cmd)
            if result_dict:
                self.result_json = result_dict
                self._auto_execute_pipeline()
            else:
                result = "AI指令解析失败"

        if result:
            self.append(result)

        self.command_executed.emit(command, result)

        # 兜底加载默认模型（AI 解析的 load_model 可能因缺少 file_path 被跳过）
        if self.viewer and not self.viewer.b_stl_loaded:
            default_model = self._find_default_model()
            if default_model and os.path.exists(default_model):
                self.viewer.execute_cmd("load_model", file_path=default_model)

    def _find_default_model(self):
        """在 uploads 目录中查找可用的 STL 模型（替代硬编码路径）"""
        import glob
        # 优先查 uploads 目录
        for search_dir in ('uploads', 'process', '.'):
            if os.path.isdir(search_dir):
                stl_files = glob.glob(os.path.join(search_dir, '*.stl'))
                if stl_files:
                    return os.path.abspath(stl_files[0])
        return None

    def _prompt_model_file(self):
        """弹出文件选择对话框，让用户选择要加载的 STL 模型。

        Returns:
            用户选中的文件路径（str），取消则返回 None。
        """
        fname = QFileDialog.getOpenFileName(
            self, '选择要加载的 STL 模型', '',
            "STL 模型 (*.stl);;所有文件 (*.*)"
        )
        return fname[0] if fname and fname[0] else None

    def _auto_execute_pipeline(self):
        """使用统一调度器执行 AI 解析的操作序列"""
        if not self.viewer:
            self.append("错误: Viewer 未初始化，无法执行管线操作。")
            return
        try:
            operations = self.result_json.get("operations", [])
            # 桌面端 Viewer 的方法是零参数方法（从 UI 控件回读参数），
            # 而 PipelineDispatcher.dispatch 会以 **params 调用 handler。
            # 因此用 lambda 吞掉参数，参数已通过 sync_params/_sync_ui_params 同步。
            handler_map = {
                "slice": lambda **p: self.viewer._run_slicing_workflow(),
                "generate_path": lambda **p: self.viewer._run_global_fill(),
                "generate_gcode": lambda **p: self.viewer._run_gcode_generation(),
            }

            for op in operations:
                command = op.get("command")
                parameters = op.get("parameters", {})
                description = op.get("description", "")

                # load_model / print 需要特殊参数处理，不进入调度器
                if command == "load_model":
                    file_path = parameters.get("file_path", "")
                    if not file_path:
                        # LLM 未指定路径 → 弹出文件选择对话框让用户挑选模型
                        file_path = self._prompt_model_file()
                    if file_path and os.path.exists(file_path):
                        self.append(f"加载模型: {description}")
                        self.viewer.execute_cmd("load_model", file_path=file_path)
                    else:
                        self.append("未选择模型文件，已取消加载")
                    continue
                if command == "print":
                    if "gcode_file" in parameters:
                        self.append(f"开始打印: {description}")
                    continue

                if command not in handler_map:
                    logging.warning("未知命令: %s，跳过", command)
                    continue

                # 同步 UI 参数（桌面端特有：_run_slicing_workflow 会从 UI 回读覆盖 params）
                PipelineDispatcher.sync_params(self.viewer, command, parameters)
                self._sync_ui_params(command, parameters)

                result = PipelineDispatcher.dispatch(
                    self.viewer, command, parameters, handler_map,
                    preconditions=STANDARD_PRECONDITIONS
                )
                self.append(f"执行{description}: {result if isinstance(result, str) else '完成'}")

        except Exception:
            logging.exception("流水线执行错误")
            self.append(f"执行错误: {traceback.format_exc()}")

    def _sync_ui_params(self, command, parameters):
        """同步参数到桌面端 UI 控件（AiTerminal 桌面模式特有）"""
        ui_map = {
            "layer_height": "lineEdit_delta",
            "first_layer_height": "lineEdit_first_delta",
            "offset": "lineEdit_offset",
            "reinforced_fiber_d": "lineEdit_reinforced_fiber_d",
            "base_fiber_d": "lineEdit_base_fiber_d",
            "nozzle_d": "lineEdit_nozzle_d",
            "filament_d": "lineEdit_filament_d",
        }
        for key, widget_name in ui_map.items():
            if key in parameters and hasattr(self.viewer, widget_name):
                getattr(self.viewer, widget_name).setText(str(parameters[key]))
            
    def show_help(self):
        """显示帮助信息"""
        help_text = "可用命令:\n"
        help_text += "- help: 显示帮助信息\n"
        help_text += "- clear: 清空屏幕\n"
        help_text += "- exit: 退出程序\n\n"

        help_text += "自然语言命令:\n"
        for key, value in self.commands.items():
            help_text += f"- {key}: {value}\n"

        return help_text

    def add_command(self, natural_command, system_command):
        """添加新的命令映射"""
        self.commands[natural_command] = system_command
        self.save_commands()

    def save_commands(self):
        """保存命令配置"""
        try:
            with open(self._commands_path(), "w", encoding="utf-8") as f:
                json.dump(self.commands, f, ensure_ascii=False, indent=4)
        except Exception:
            logging.exception("保存命令配置失败")