"""Flask 扩展实例（独立模块，避免循环导入）。"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()
