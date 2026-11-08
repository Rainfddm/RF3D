import os

#####
import os
# 获取当前文件所在目录

from suAgent.tools.base import Tool
from suAgent.tools.doc_reader import create_document_reader
#####

#pdf reader
def get_content_from_pdf(pdf_path: str) -> str:
    reader = create_document_reader(pdf_path)
    content = reader.get_full_text()
    return content

def get_n_parent_directory(directory: str, file_name: str, n=0):
    """
    获取指定层级的父目录，并与给定的目录和文件名拼接成完整路径。

    此函数首先获取当前文件所在目录，然后向上遍历指定层数的父目录，
    最后将目标目录和文件名拼接到该路径后面。

    Args:
        directory (str): 要添加到父目录后的目录名
        file_name (str): 要查找的文件名
        n (int, optional): 要向上遍历的父目录层数。默认为0
            注意：即使提供了默认值，函数内部仍然硬编码将n设为2

    Returns:
        str: 完整的文件路径
            例如：如果当前文件在 /a/b/c/d.py，n=2，directory='test'，file_name='data.txt'
            则返回 /a/b/test/data.txt

    Examples:
        >>> get_n_parent_directory('config', 'settings.json', 2)
        '/path/to/parent/config/settings.json'

    Notes:
        - 函数使用 Path(__file__) 获取当前文件的路径
        - parents 索引从0开始计数
    """
    from pathlib import Path
    current_dir = Path(__file__).resolve().parent
    parent_dir = current_dir.parents[n - 1]  # n-1 是因为 parents 是从 0 开始的索引

    file_path = os.path.join(parent_dir, directory, file_name)
    return file_path

# 创建工具实例
pdf_reader_tool = Tool(
    name="read_pdf",
    description="读取pdf文件并提取标题",
    function=get_content_from_pdf,
    required_args=["pdf_path"]
)

get_file_relative_path_tool = Tool(
    name="get_file_relative_path",
    description="根据相对路径关系返回文件路径",
    function=get_n_parent_directory,
    required_args=["directory", "file_name", "n"]
)

