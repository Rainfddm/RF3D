#!/usr/bin/env python3
"""
WSGI入口文件，用于部署到Web服务器
"""
import os
import sys
from werkzeug.middleware.dispatcher import DispatcherMiddleware

# 获取项目根目录
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# 导入Flask应用
from app import flask_app as application

# 如果需要与其他应用共享根域名，可以使用DispatcherMiddleware
# application = DispatcherMiddleware(
#     None,  # 主应用，这里设置为None
#     {
#         '/app/rf3d': application  # 我们的RF3D应用位于这个子路径
#     }
# )

if __name__ == "__main__":
    application.run()