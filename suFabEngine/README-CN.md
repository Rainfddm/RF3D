# suFabEngine

suFabEngine 是一个专为纤维增强打印设计的路径规划库。它提供从切片到G代码生成，用于优化 3D 打印过程中的纤维放置和路径生成。

## 特性

- 支持 STL 文件的加载和处理
- 模型切片功能
- 全局连续路径生成
- 支持多种填充路径类型，包括等距轮廓和费马螺旋
- G-code 生成功能
- 高效的数据处理和优化算法

## 安装

你可以使用 pip 来安装 suFabEngine：

```bash
pip install suFabEngine
```

## 快速开始

以下是一个简单的示例，展示了如何使用 suFabEngine 处理 STL 文件并生成填充路径：

```python
from suFabEngine import STLProcessor, Pipeline

# 初始化处理管线
pipeline = Pipeline()
pipeline.params['delta'] = 0.3  # 设置参数

# 加载 STL 文件
stl_processor = STLProcessor()
vtk_poly_data = stl_processor.read_stl("path/to/your/model.stl")

# 处理模型
pipeline.load(vtk_poly_data)
pipeline.slice()

# 生成填充路径（以等距轮廓为例）
contours = pipeline.fill_layer(4, pipeline.PATH_TYPE_ISO_CONTOUR)

# 可视化结果（需要额外的可视化模块）
# vtk_show_isocontours(contours)
```

## 详细用法

### 模型加载和预处理

```python
from suFabEngine import STLProcessor, DataProcessor

stl = STLProcessor()
vtk_poly_data = stl.read_stl("path/to/your/model.stl")
triangles = DataProcessor.convert_to_triangles(vtk_poly_data)
```

### 生成费马螺旋填充

```python
pipeline = Pipeline()
pipeline.load(vtk_poly_data)
pipeline.slice()
spiral = pipeline.fill_layer(4, pipeline.PATH_TYPE_FERMATS_SPIRAL)
```

### 全局路径生成

```python
global_path = pipeline.generate_global_path()
```

## 文档

详细的文档可以在 [链接到你的文档，如果有的话] 找到。

## 测试

suFabEngine 包含一套全面的单元测试。你可以通过以下方式运行测试：

```python
import unittest
from suFabEngine.tests import TestModelProcessing

if __name__ == '__main__':
    unittest.main()
```

## 贡献

我们欢迎贡献！请查看 [CONTRIBUTING.md](链接到 CONTRIBUTING.md) 了解如何开始。

## 许可证

本项目为专有软件（Proprietary），保留所有权利（All Rights Reserved）。未经授权，不得复制、修改、分发或用于商业用途。

## 联系

- 维护者：[你的名字]
- E-mail：[你的电子邮件]
- 项目链接：https://github.com/[你的用户名]/suFabEngine

## 致谢

- 感谢所有为本项目做出贡献的开发者和研究人员
- 特别感谢 VTK 库为本项目提供强大的 3D 数据处理能力