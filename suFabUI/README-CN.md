# suFabUI

suFabUI 是一个基于 PyQt5 的图形用户界面应用程序，为 suFabEngine 提供了直观的操作界面。它旨在简化纤维增强 3D 打印的路径规划过程。

## 特性

- 用户友好的界面，用于加载和处理 3D 模型文件（STL 格式）
- 集成 suFabEngine 的核心功能，包括模型切片和路径生成
- 可视化工具，用于预览切片结果和生成的打印路径
- 支持多种填充路径类型，如等距轮廓和费马螺旋
- G-code 生成和导出功能
- 参数调整界面，允许用户优化打印设置

## 安装

suFabUI 目前以独立的可执行文件形式发布，无需安装过程。你可以从我们的 [发布页面](链接到你的发布页面) 下载最新版本的 suFabUI。

## 使用说明

1. 启动 suFabUI 应用程序
2. 使用 "File" -> "Open" 菜单加载 STL 文件
3. 在参数面板中调整切片和路径生成参数
4. 点击 "Slice" 按钮进行模型切片
5. 选择填充路径类型并点击 "Generate Path" 生成打印路径
6. 使用可视化工具预览结果
7. 点击 "Export G-code" 导出可用于 3D 打印机的 G-code 文件

## 依赖

suFabUI 依赖于以下库：

- PyQt5
- VTK
- NumPy
- suFabEngine (内部库)

## 开发环境设置

如果你想参与 suFabUI 的开发，请按照以下步骤设置你的环境：

1. 克隆仓库：
   ```
   git clone https://github.com/[你的用户名]/suFabUI.git
   ```

2. 创建并激活虚拟环境：
   ```
   python -m venv venv
   source venv/bin/activate  # 在 Windows 上使用 venv\Scripts\activate
   ```

3. 安装依赖：
   ```
   pip install -r requirements.txt
   ```

4. 安装 suFabEngine（假设它作为一个单独的包）：
   ```
   pip install suFabEngine
   ```

## 生成发布包

要生成 suFabUI 的发布包，我们使用 PyInstaller。按照以下步骤操作：

1. 确保你已经安装了 PyInstaller：
   ```
   pip install pyinstaller
   ```

2. 导航到 suFabUI 项目的根目录。

3. 运行以下命令生成发布包：
   ```
   python build_suFabUI.py
   ```

   这个脚本会执行以下操作：
   - 生成必要的 spec 文件
   - 使用 PyInstaller 创建独立的可执行文件
   - 将结果放在 `dist/suFabUI` 目录中

4. 生成的发布包将包含 suFabUI 可执行文件及其所有依赖项。

注意：确保 `build_suFabUI.py` 脚本正确设置了所有必要的路径和依赖项。

## 贡献

我们欢迎贡献！如果你想为 suFabUI 做出贡献，请：

1. Fork 这个仓库
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启一个 Pull Request

## 许可证

本项目为专有软件（Proprietary），保留所有权利（All Rights Reserved）。未经授权，不得复制、修改、分发或用于商业用途。

## 联系

- 维护者：[你的名字]
- E-mail：[你的电子邮件]
- 项目链接：https://github.com/[你的用户名]/suFabUI