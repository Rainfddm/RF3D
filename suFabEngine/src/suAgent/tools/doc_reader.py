# document_reader.py
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from abc import ABC, abstractmethod
import logging
import re
from dataclasses import dataclass


@dataclass
class DocumentInfo:
    """文档信息数据类"""
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    keywords: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    creation_date: Optional[str] = None
    modification_date: Optional[str] = None


@dataclass
class DocumentContent:
    """文档内容数据类"""
    text: str = ""
    has_toc: bool = False
    has_references: bool = False
    has_images: bool = False
    page_count: int = 0
    sections: List[str] = None

    def __post_init__(self):
        if self.sections is None:
            self.sections = []


class BaseDocumentReader(ABC):
    """文档读取器基类"""

    def __init__(self, file_path: Union[str, Path]):
        self.file_path = Path(file_path)
        self.doc_info = DocumentInfo()
        self.doc_content = DocumentContent()
        self._initialize()

    @abstractmethod
    def _initialize(self) -> None:
        """初始化文档，子类必须实现"""
        pass

    @abstractmethod
    def get_first_page_text(self) -> str:
        """获取第一页文本，子类必须实现"""
        pass

    @abstractmethod
    def get_document_info(self) -> DocumentInfo:
        """获取文档信息，子类必须实现"""
        pass

    @abstractmethod
    def get_full_text(self) -> str:
        """获取完整文本，子类必须实现"""
        pass

    @abstractmethod
    def analyze_structure(self) -> DocumentContent:
        """分析文档结构，子类必须实现"""
        pass

    def is_valid(self) -> bool:
        """检查文档是否有效"""
        return self.file_path.exists() and self.file_path.is_file()

    @staticmethod
    def clean_text(text: str) -> str:
        """清理文本内容"""
        if not text:
            return ""
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        # 处理特殊字符
        text = text.encode('utf-8', 'ignore').decode('utf-8')
        return text.strip()


class PdfDocumentReader(BaseDocumentReader):
    """PDF文档读取器"""

    def __init__(self, file_path: Union[str, Path]):
        super().__init__(file_path)

    def _initialize(self) -> None:
        try:
            from pypdf import PdfReader
            self._reader = PdfReader(str(self.file_path))
        except Exception as e:
            logging.error(f"Failed to initialize PDF reader: {e}")
            self._reader = None

    def get_first_page_text(self) -> str:
        """获取PDF第一页文本"""
        try:
            if not self._reader or len(self._reader.pages) == 0:
                return ""

            page = self._reader.pages[0]
            text = page.extract_text()
            return self.clean_text(text)
        except Exception as e:
            logging.error(f"Error extracting first page text: {e}")
            return ""

    def get_document_info(self) -> DocumentInfo:
        """获取PDF文档信息"""
        try:
            if not self._reader:
                return DocumentInfo()

            info = self._reader.metadata
            if info:
                return DocumentInfo(
                    title=info.title,
                    author=info.author,
                    subject=info.subject,
                    creator=info.creator,
                    producer=info.producer,
                    creation_date=str(info.creation_date) if info.creation_date else None,
                    modification_date=str(info.modification_date) if info.modification_date else None
                )
            return DocumentInfo()
        except Exception as e:
            logging.error(f"Error getting document info: {e}")
            return DocumentInfo()

    def get_full_text(self) -> str:
        """获取PDF完整文本"""
        try:
            if not self._reader:
                return ""

            text = []
            for page in self._reader.pages:
                text.append(page.extract_text())
            return self.clean_text(" ".join(text))
        except Exception as e:
            logging.error(f"Error extracting full text: {e}")
            return ""

    def analyze_structure(self) -> DocumentContent:
        """分析PDF文档结构"""
        try:
            if not self._reader:
                return DocumentContent()

            content = DocumentContent()
            content.page_count = len(self._reader.pages)

            # 获取第一页文本用于分析结构
            first_page = self.get_first_page_text().lower()

            # 检查目录
            content.has_toc = any(marker in first_page for marker in ['目录', 'contents', 'table of contents'])

            # 检查参考文献
            full_text = self.get_full_text().lower()
            content.text = full_text
            content.has_references = any(marker in full_text for marker in ['参考文献', 'references', 'bibliography'])

            # 检查图片
            content.has_images = self._has_images()

            # 提取章节
            content.sections = self._extract_sections()

            return content
        except Exception as e:
            logging.error(f"Error analyzing document structure: {e}")
            return DocumentContent()

    def _has_images(self) -> bool:
        """检查PDF是否包含图片"""
        try:
            if not self._reader:
                return False

            for page in self._reader.pages:
                if "/Resources" in page and "/XObject" in page["/Resources"]:
                    for obj in page["/Resources"]["/XObject"].values():
                        if obj["/Subtype"] == "/Image":
                            return True
            return False
        except Exception:
            return False

    def _extract_sections(self) -> List[str]:
        """提取PDF文档章节"""
        sections = []
        try:
            text = self.get_full_text()
            # 使用正则表达式匹配常见的章节标题模式
            patterns = [
                r'^第[一二三四五六七八九十\d]+章[\s\S]*?(?=第[一二三四五六七八九十\d]+章|$)',
                r'^\d+\.\s+.*?(?=\d+\.\s+|$)',
                r'^[一二三四五六七八九十]+、[\s\S]*?(?=[一二三四五六七八九十]+、|$)'
            ]
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.MULTILINE)
                sections.extend(match.group().strip() for match in matches)
        except Exception as e:
            logging.error(f"Error extracting sections: {e}")
        return sections


class DocxDocumentReader(BaseDocumentReader):
    """Word文档读取器"""

    def __init__(self, file_path: Union[str, Path]):
        super().__init__(file_path)

    def _initialize(self) -> None:
        try:
            import docx
            self._doc = docx.Document(self.file_path)
        except Exception as e:
            logging.error(f"Failed to initialize DOCX reader: {e}")
            self._doc = None

    def get_first_page_text(self) -> str:
        """获取Word文档第一页文本（前5段）"""
        try:
            if not self._doc:
                return ""

            text_parts = []
            count = 0
            for p in self._doc.paragraphs:
                text = p.text.strip()
                if text:
                    text_parts.append(text)
                    count += 1
                    if count >= 5:
                        break
            return self.clean_text('\n'.join(text_parts))
        except Exception as e:
            logging.error(f"Error extracting first page text: {e}")
            return ""

    def get_document_info(self) -> DocumentInfo:
        """获取Word文档信息"""
        try:
            if not self._doc:
                return DocumentInfo()

            core_props = self._doc.core_properties
            return DocumentInfo(
                title=core_props.title,
                author=core_props.author,
                subject=core_props.subject,
                keywords=core_props.keywords,
                creation_date=str(core_props.created) if core_props.created else None,
                modification_date=str(core_props.modified) if core_props.modified else None
            )
        except Exception as e:
            logging.error(f"Error getting document info: {e}")
            return DocumentInfo()

    def get_full_text(self) -> str:
        """获取Word文档完整文本"""
        try:
            if not self._doc:
                return ""

            text = [p.text for p in self._doc.paragraphs if p.text.strip()]
            return self.clean_text('\n'.join(text))
        except Exception as e:
            logging.error(f"Error extracting full text: {e}")
            return ""

    def analyze_structure(self) -> DocumentContent:
        """分析Word文档结构"""
        try:
            if not self._doc:
                return DocumentContent()

            content = DocumentContent()

            # 统计段落数量作为页数估算（假设每页约15段）
            para_count = len([p for p in self._doc.paragraphs if p.text.strip()])
            content.page_count = (para_count + 14) // 15

            first_page = self.get_first_page_text().lower()
            content.has_toc = any(marker in first_page for marker in ['目录', 'contents', 'table of contents'])

            full_text = self.get_full_text().lower()
            content.text = full_text
            content.has_references = any(marker in full_text for marker in ['参考文献', 'references', 'bibliography'])

            # 检查图片
            content.has_images = bool(len(self._doc.inline_shapes))

            # 提取章节
            content.sections = self._extract_sections()

            return content
        except Exception as e:
            logging.error(f"Error analyzing document structure: {e}")
            return DocumentContent()

    def _extract_sections(self) -> List[str]:
        """提取Word文档章节"""
        sections = []
        try:
            for para in self._doc.paragraphs:
                # 检查段落样式是否为标题样式
                if para.style.name.startswith('Heading'):
                    sections.append(para.text.strip())
                # 同时也用正则表达式匹配常见的章节标题模式
                elif re.match(r'^第[一二三四五六七八九十\d]+章|^\d+\.\s+|^[一二三四五六七八九十]+、', para.text.strip()):
                    sections.append(para.text.strip())
        except Exception as e:
            logging.error(f"Error extracting sections: {e}")
        return sections


def create_document_reader(file_path: Union[str, Path]) -> Optional[BaseDocumentReader]:
    """工厂函数：根据文件类型创建相应的文档读取器"""
    file_path = Path(file_path)
    ext = file_path.suffix.lower()

    if ext == '.pdf':
        return PdfDocumentReader(file_path)
    elif ext == '.docx':
        return DocxDocumentReader(file_path)
    else:
        logging.error(f"Unsupported file type: {ext}")
        return None


if __name__ == '__main__':
    import logging
    import sys

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

    pdf_path = Path("../extracted_pdfs/24721742-黄梓恒/24721742-黄梓恒-K-Means算法技术报告.pdf")


    def print_document_analysis(reader, file_type: str):
        """打印文档分析结果"""
        print(f"\n{'=' * 50}")
        print(f"{file_type} 文档分析结果")
        print(f"{'=' * 50}")

        # 打印文档信息
        print("\n--- 文档基本信息 ---")
        info = reader.get_document_info()
        print(f"标题: {info.title}")
        print(f"作者: {info.author}")
        print(f"主题: {info.subject}")
        print(f"关键词: {info.keywords}")
        print(f"创建者: {info.creator}")
        print(f"创建时间: {info.creation_date}")
        print(f"修改时间: {info.modification_date}")

        # 打印第一页文本
        print("\n--- 第一页文本内容 ---")
        first_page = reader.get_first_page_text()
        print(first_page)

        # 打印文档结构分析
        print("\n--- 文档结构分析 ---")
        content = reader.analyze_structure()
        print(f"总页数: {content.page_count}")
        print(f"是否包含目录: {content.has_toc}")
        print(f"是否包含参考文献: {content.has_references}")
        print(f"是否包含图片: {content.has_images}")

        # 打印章节信息
        if content.sections:
            print("\n--- 检测到的章节 ---")
            for i, section in enumerate(content.sections, 1):
                print(f"{i}. {section}")

        # 简单统计
        full_text = reader.get_full_text()
        print("\n--- 文本统计 ---")
        print(f"总字符数: {len(full_text)}")
        print(f"总行数: {len(full_text.splitlines())}")
        print(f"{'=' * 50}\n")
        # print(full_text)


    def test_pdf_reader(pdf_path):
        print("start test_pdf_reader")
        """测试PDF读取器"""
        reader = create_document_reader(pdf_path)

        if reader and reader.is_valid():
            print_document_analysis(reader, "PDF")

            reader.get_document_info()
            reader.analyze_structure()
            reader.get_first_page_text()

            # 内容测试
            content = reader.get_first_page_text()
            print(content)

            content = reader.get_full_text()
            print(content)


    test_pdf_reader(pdf_path)