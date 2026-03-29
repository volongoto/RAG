import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import fitz
from docx import Document
from loguru import logger

from exceptions.exception import ServiceException


class BaseParser(ABC):
    @abstractmethod
    async def parse(self, file_path: str) -> list[dict[str, Any]]:
        pass


class PDFParser(BaseParser):
    async def parse(self, file_path: str) -> list[dict[str, Any]]:
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
        except Exception as exc:
            logger.error(f'PDF parse failed: {file_path}, error: {exc}')
            raise exc
        return paragraphs

    def _split_into_paragraphs(self, text: str, page_num: int) -> list[dict[str, Any]]:
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
                        paragraphs.append(
                            {
                                'content': content,
                                'page_num': page_num,
                                'paragraph_index': para_index,
                            }
                        )
                        para_index += 1
                    current_para = []
            else:
                current_para.append(line)

        if current_para:
            content = ''.join(current_para).strip()
            if content:
                paragraphs.append(
                    {
                        'content': content,
                        'page_num': page_num,
                        'paragraph_index': para_index,
                    }
                )

        return paragraphs


class DocxParser(BaseParser):
    async def parse(self, file_path: str) -> list[dict[str, Any]]:
        paragraphs = []
        converted_file_path = ''
        converted_output_dir = ''
        try:
            detected_format = self._detect_word_file_format(file_path)
            logger.info(f'Word parser detected format: path={file_path}, detected_format={detected_format}')
            if detected_format == 'doc':
                converted_file_path = self._convert_doc_to_docx(file_path)
                converted_output_dir = os.path.dirname(converted_file_path)
                file_path = converted_file_path
                detected_format = 'docx'
            if detected_format in ('docm', 'dotm'):
                raise ServiceException(
                    message='当前不支持带宏的 Word 文档，请另存为标准 DOCX 后再上传'
                )
            if detected_format == 'unknown':
                raise ServiceException(
                    message='无法识别当前 Word 文档格式，请确认文件未损坏并重新保存为标准 DOCX'
                )

            doc = Document(file_path)
            para_index = 0

            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    continue
                paragraphs.append(
                    {
                        'content': text,
                        'page_num': None,
                        'paragraph_index': para_index,
                        'is_heading': self._is_heading(para),
                    }
                )
                para_index += 1
        except Exception as exc:
            logger.error(f'Word parse failed: {file_path}, error: {exc}')
            raise exc
        finally:
            if converted_file_path and os.path.exists(converted_file_path):
                try:
                    os.remove(converted_file_path)
                except OSError:
                    logger.warning(f'Failed to remove temporary converted docx: {converted_file_path}')
            if converted_output_dir and os.path.isdir(converted_output_dir):
                try:
                    shutil.rmtree(converted_output_dir, ignore_errors=True)
                except OSError:
                    logger.warning(f'Failed to remove temporary conversion directory: {converted_output_dir}')
        return paragraphs

    def _convert_doc_to_docx(self, file_path: str) -> str:
        office_binary = shutil.which('soffice') or shutil.which('libreoffice')
        if not office_binary:
            raise ServiceException(
                message='DOC 文档解析依赖 LibreOffice。当前环境未安装 soffice/libreoffice，无法自动转换 DOC。'
            )

        output_dir = tempfile.mkdtemp(prefix='rag_doc_convert_')
        command = [
            office_binary,
            '--headless',
            '--convert-to',
            'docx',
            '--outdir',
            output_dir,
            file_path,
        ]
        logger.info(f'Converting DOC to DOCX with LibreOffice: command={" ".join(command)}')
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=120)
        except subprocess.TimeoutExpired as exc:
            raise ServiceException(message='DOC 转换超时，请稍后重试或手动转换为 DOCX') from exc

        if result.returncode != 0:
            logger.error(
                'DOC to DOCX conversion failed: '
                f'returncode={result.returncode}, stdout={result.stdout}, stderr={result.stderr}'
            )
            raise ServiceException(message='DOC 转换失败，请检查文件是否损坏，或手动转换为 DOCX 后重试')

        converted_path = os.path.join(output_dir, f'{Path(file_path).stem}.docx')
        if not os.path.exists(converted_path):
            raise ServiceException(message='DOC 转换完成但未生成 DOCX 文件，请手动转换后重试')
        logger.info(f'DOC converted to DOCX successfully: source={file_path}, target={converted_path}')
        return converted_path

    def _detect_word_file_format(self, file_path: str) -> str:
        try:
            with open(file_path, 'rb') as file_obj:
                header = file_obj.read(8)
            if header.startswith(b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1'):
                return 'doc'
            if not header.startswith(b'PK'):
                return 'unknown'

            with zipfile.ZipFile(file_path) as archive:
                if '[Content_Types].xml' not in archive.namelist():
                    return 'unknown'
                content_types_xml = archive.read('[Content_Types].xml').decode('utf-8', errors='ignore').lower()

            if 'application/vnd.ms-word.document.macroenabled.main+xml' in content_types_xml:
                return 'docm'
            if 'application/vnd.ms-word.template.macroenabledtemplate.main+xml' in content_types_xml:
                return 'dotm'
            if 'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml' in content_types_xml:
                return 'docx'
            return 'unknown'
        except Exception as exc:
            logger.warning(f'Failed to detect word file format: path={file_path}, error={exc}')
            return 'unknown'

    def _is_heading(self, paragraph) -> bool:
        return paragraph.style.name.startswith('Heading')


class DocumentParserFactory:
    _parsers = {
        'pdf': PDFParser,
        'doc': DocxParser,
        'docx': DocxParser,
    }

    @classmethod
    def get_parser(cls, file_type: str) -> BaseParser:
        parser_class = cls._parsers.get(file_type.lower())
        if not parser_class:
            raise ValueError(f'Unsupported file type: {file_type}')
        return parser_class()

    @classmethod
    def get_supported_types(cls) -> list[str]:
        return list(cls._parsers.keys())
