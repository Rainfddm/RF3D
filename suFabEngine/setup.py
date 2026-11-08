"""兼容入口：配置已迁移到 pyproject.toml（唯一真相源）。

保留此空壳以兼容旧版 editable install 工具链，
setuptools 会从 pyproject.toml 的 [project] 段读取元数据与依赖。
"""

from setuptools import setup

setup()
