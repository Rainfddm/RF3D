import logging
class WinLoggerHandler(logging.Handler):
    def __init__(self, widget):
        super().__init__()
        self.widget = widget
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    def emit(self, record):
        if self.widget is None:
            return
            
        try:
            # 检查widget是否仍然有效
            text = self.widget.toPlainText()
        except RuntimeError:
            # Widget已被删除，停止记录
            self.widget = None
            return
            
        msg = self.format(record)
        # 使用线程安全的方式更新UI
        if hasattr(self.widget, 'append'):
            self.widget.append(msg)

    def register_logger(self):
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(self)
        # You can control the logging level
        logging.getLogger().setLevel(logging.INFO)  

    # def emit(self, record):
    #     msg = self.format(record)
    #     text = self.widget.toPlainText()
    #     if len(text) > 5120:
    #         self.widget.setPlainText('Clear\n')
    #     self.widget.appendPlainText(msg)

    def disable_console(self):
        logging.basicConfig(level=logging.DEBUG, format=' %(asctime)s - %(name)s - %(levelname)s - %(message)s')