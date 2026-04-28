import os
import shutil
import subprocess
import tempfile
import zipfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import fitz
from docx import Document
from docx.opc.exceptions import PackageNotFoundError
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
            raise
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
        source_file_path = file_path
        try:
            detected_format = self._detect_word_file_format(file_path)
            logger.info(f'Word parser detected format: path={file_path}, detected_format={detected_format}')
            if detected_format == 'doc':
                converted_file_path = self._convert_doc_to_docx(file_path)
                converted_output_dir = os.path.dirname(converted_file_path)
                file_path = converted_file_path
            elif detected_format in ('docm', 'dotm'):
                raise ServiceException(message='Macro-enabled Word documents are not supported. Please save as DOCX.')
            elif detected_format == 'unknown':
                converted_file_path = self._convert_office_file_to_docx(file_path)
                converted_output_dir = os.path.dirname(converted_file_path)
                file_path = converted_file_path

            doc, converted_file_path, converted_output_dir = self._open_docx_or_convert(
                source_file_path,
                file_path,
                converted_file_path,
                converted_output_dir,
            )
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
            raise
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

    def _open_docx_or_convert(
        self,
        source_file_path: str,
        file_path: str,
        converted_file_path: str,
        converted_output_dir: str,
    ):
        try:
            return Document(file_path), converted_file_path, converted_output_dir
        except (PackageNotFoundError, zipfile.BadZipFile, KeyError, ValueError) as exc:
            if converted_file_path:
                raise ServiceException(
                    message='Word document could not be opened after conversion. Please save it as DOCX and upload again.'
                ) from exc

            logger.warning(
                'DOCX open failed, trying LibreOffice conversion fallback: '
                f'source={source_file_path}, error={exc}'
            )
            fallback_file_path = self._convert_office_file_to_docx(source_file_path, source_label='WPS/Word')
            try:
                return Document(fallback_file_path), fallback_file_path, os.path.dirname(fallback_file_path)
            except (PackageNotFoundError, zipfile.BadZipFile, KeyError, ValueError) as fallback_exc:
                raise ServiceException(
                    message='Word document could not be opened after automatic conversion. Please save it as DOCX and upload again.'
                ) from fallback_exc

    def _convert_doc_to_docx(self, file_path: str) -> str:
        return self._convert_office_file_to_docx(file_path, source_label='DOC')

    def _convert_office_file_to_docx(self, file_path: str, source_label: str | None = None) -> str:
        office_binary = shutil.which('soffice') or shutil.which('libreoffice')
        if not office_binary:
            raise ServiceException(
                message=(
                    'This document is not a standard DOCX package. '
                    'Please install LibreOffice on the server, or save it as DOCX in WPS/Word and upload again.'
                )
            )

        readable_source_label = (source_label or Path(file_path).suffix.lstrip('.').upper() or 'OFFICE').strip()
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
        logger.info(
            f'Converting {readable_source_label} to DOCX with LibreOffice: command={" ".join(command)}'
        )
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=120)
        except subprocess.TimeoutExpired as exc:
            raise ServiceException(
                message=f'{readable_source_label} conversion timed out. Please try again or resave the file as DOCX.'
            ) from exc

        if result.returncode != 0:
            logger.error(
                f'{readable_source_label} to DOCX conversion failed: '
                f'returncode={result.returncode}, stdout={result.stdout}, stderr={result.stderr}'
            )
            raise ServiceException(
                message=f'{readable_source_label} conversion failed. Please save the file as DOCX in WPS/Word and upload again.'
            )

        converted_path = os.path.join(output_dir, f'{Path(file_path).stem}.docx')
        if not os.path.exists(converted_path):
            raise ServiceException(
                message=(
                    f'{readable_source_label} conversion finished but no DOCX file was generated. '
                    'Please save the file as DOCX in WPS/Word and upload again.'
                )
            )
        logger.info(
            f'{readable_source_label} converted to DOCX successfully: source={file_path}, target={converted_path}'
        )
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
        'wps': DocxParser,
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
