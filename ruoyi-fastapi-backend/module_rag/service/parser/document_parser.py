import json
import re
from abc import ABC, abstractmethod
from typing import Any

import fitz
from docx import Document
from loguru import logger


class BaseParser(ABC):
    """
    文档解析器基类
    """

    @abstractmethod
    async def parse(self, file_path: str) -> list[dict[str, Any]]:
        """
        解析文档，返回段落列表
        每个段落包含：content, page_num, paragraph_index
        """
        pass


class PDFParser(BaseParser):
    """
    PDF文档解析器
    """

    async def parse(self, file_path: str) -> list[dict[str, Any]]:
        """
        解析PDF文档
        """
        paragraphs = []
        try:
            doc = fitz.open(file_path)
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text()
                if not text.strip():
                    continue
                
                page_paragraphs = self._split_into_paragraphs(text, page_num)
                paragraphs.extend(page_paragraphs)
            doc.close()
        except Exception as e:
            logger.error(f'PDF解析失败: {file_path}, 错误: {str(e)}')
            raise e
        return paragraphs

    def _split_into_paragraphs(self, text: str, page_num: int) -> list[dict[str, Any]]:
        """
        将页面文本分割成段落
        """
        paragraphs = []
        lines = text.split('\n')
        current_para = []
        para_index = 0

        for line in lines:
            line = line.strip()
            if not line:
                if current_para:
                    content = ''.join(current_para).strip()
                    if content:
                        paragraphs.append({
                            'content': content,
                            'page_num': page_num,
                            'paragraph_index': para_index,
                        })
                        para_index += 1
                    current_para = []
            else:
                current_para.append(line)

        if current_para:
            content = ''.join(current_para).strip()
            if content:
                paragraphs.append({
                    'content': content,
                    'page_num': page_num,
                    'paragraph_index': para_index,
                })

        return paragraphs


class DocxParser(BaseParser):
    """
    Word文档解析器
    """

    async def parse(self, file_path: str) -> list[dict[str, Any]]:
        """
        解析Word文档
        """
        paragraphs = []
        try:
            doc = Document(file_path)
            para_index = 0
            
            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    continue
                
                if self._is_heading(para):
                    paragraphs.append({
                        'content': text,
                        'page_num': None,
                        'paragraph_index': para_index,
                        'is_heading': True,
                    })
                else:
                    paragraphs.append({
                        'content': text,
                        'page_num': None,
                        'paragraph_index': para_index,
                        'is_heading': False,
                    })
                para_index += 1

        except Exception as e:
            logger.error(f'Word解析失败: {file_path}, 错误: {str(e)}')
            raise e
        return paragraphs

    def _is_heading(self, paragraph) -> bool:
        """
        判断段落是否为标题
        """
        if paragraph.style.name.startswith('Heading'):
            return True
        return False


class DocumentParserFactory:
    """
    文档解析器工厂
    """

    _parsers = {
        'pdf': PDFParser,
        'docx': DocxParser,
    }

    @classmethod
    def get_parser(cls, file_type: str) -> BaseParser:
        """
        获取文档解析器
        """
        parser_class = cls._parsers.get(file_type.lower())
        if not parser_class:
            raise ValueError(f'不支持的文件类型: {file_type}')
        return parser_class()

    @classmethod
    def get_supported_types(cls) -> list[str]:
        """
        获取支持的文件类型
        """
        return list(cls._parsers.keys())
