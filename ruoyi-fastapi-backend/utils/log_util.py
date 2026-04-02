import json
import os
import sys
import time
from typing import Any

from loguru import logger as _logger
from loguru._logger import Logger

from middlewares.trace_middleware import TraceCtx


class StructuredLogFormatter:
    """
    结构化日志格式化器
    支持 JSON 格式输出，便于日志收集和分析
    """

    @staticmethod
    def format_json(record: dict) -> str:
        """将日志记录格式化为 JSON"""
        log_data = {
            'timestamp': record['time'].isoformat(),
            'level': record['level'].name,
            'message': record['message'],
            'trace_id': record.get('trace_id', ''),
            'logger': record['name'],
            'function': record['function'],
            'line': record['line'],
            'file': record['file'].name,
        }

        # 添加额外的上下文信息
        if 'extra' in record and record['extra']:
            log_data['extra'] = dict(record['extra'])

        # 添加异常信息
        if record['exception']:
            log_data['exception'] = record['exception']

        return json.dumps(log_data, ensure_ascii=False, default=str)


class LoggerInitializer:
    """日志初始化器"""

    def __init__(self) -> None:
        self.log_path = os.path.join(os.getcwd(), 'logs')
        self.__ensure_log_directory_exists()
        self.log_path_error = os.path.join(self.log_path, f'{time.strftime("%Y-%m-%d")}_error.log')
        self.log_path_json = os.path.join(self.log_path, f'{time.strftime("%Y-%m-%d")}.jsonl')

    def __ensure_log_directory_exists(self) -> None:
        if not os.path.exists(self.log_path):
            os.mkdir(self.log_path)

    @staticmethod
    def __filter(log: dict) -> dict:
        log['trace_id'] = TraceCtx.get_id()
        return log

    def __configure_sinks(self, format_str: str, *, enqueue: bool, json_format: bool = False) -> None:
        # 控制台输出（人类可读格式）
        _logger.add(sys.stderr, filter=self.__filter, format=format_str, enqueue=enqueue)

        # 错误日志文件（人类可读格式）
        _logger.add(
            self.log_path_error,
            filter=self.__filter,
            format=format_str,
            rotation='50MB',
            encoding='utf-8',
            enqueue=enqueue,
            compression='zip',
            level='ERROR',
        )

        # JSON 格式日志（便于日志收集系统处理）
        if json_format:
            _logger.add(
                self.log_path_json,
                filter=self.__filter,
                format='{message}',
                rotation='100MB',
                encoding='utf-8',
                enqueue=enqueue,
                compression='zip',
                serialize=True,  # 启用结构化日志
            )

    def init_log(self, *, json_format: bool = True) -> Logger:
        """
        初始化日志

        Args:
            json_format: 是否启用 JSON 格式日志文件

        Returns:
            Logger 实例
        """
        format_str = (
            '<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | '
            '<cyan>{trace_id}</cyan> | '
            '<level>{level: <8}</level> | '
            '<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - '
            '<level>{message}</level>'
        )
        _logger.remove()
        try:
            self.__configure_sinks(format_str, enqueue=True, json_format=json_format)
        except Exception:
            _logger.remove()
            self.__configure_sinks(format_str, enqueue=False, json_format=False)
            _logger.warning('Log queue initialization failed, fallback to synchronous logging')

        return _logger


def log_structured(
    level: str,
    message: str,
    *,
    extra: dict[str, Any] | None = None,
    **kwargs,
) -> None:
    """
    记录结构化日志

    Args:
        level: 日志级别 (debug, info, warning, error, critical)
        message: 日志消息
        extra: 额外的结构化数据
        **kwargs: 其他关键字参数
    """
    log_func = getattr(logger, level.lower(), logger.info)

    # 构建结构化数据
    context = {
        'event': message,
        **(extra or {}),
        **kwargs,
    }

    # 使用 bind 添加上下文
    bound_logger = logger.bind(**context)
    log_func(message)


def log_rag_query(
    query: str,
    kb_ids: list[int],
    response_time_ms: int,
    chunk_count: int,
    *,
    success: bool = True,
    error: str | None = None,
) -> None:
    """
    记录 RAG 查询日志

    Args:
        query: 查询文本
        kb_ids: 知识库 ID 列表
        response_time_ms: 响应时间（毫秒）
        chunk_count: 检索到的片段数量
        success: 是否成功
        error: 错误信息（如果失败）
    """
    log_data = {
        'event': 'rag_query',
        'query_length': len(query),
        'kb_ids': kb_ids,
        'response_time_ms': response_time_ms,
        'chunk_count': chunk_count,
        'success': success,
    }

    if error:
        log_data['error'] = error
        logger.error(f'RAG query failed: {error}', extra=log_data)
    else:
        logger.info(f'RAG query completed', extra=log_data)


def log_document_parse(
    doc_id: int,
    file_name: str,
    duration_ms: int,
    chunk_count: int,
    *,
    success: bool = True,
    error: str | None = None,
) -> None:
    """
    记录文档解析日志

    Args:
        doc_id: 文档 ID
        file_name: 文件名
        duration_ms: 解析耗时（毫秒）
        chunk_count: 生成的片段数量
        success: 是否成功
        error: 错误信息（如果失败）
    """
    log_data = {
        'event': 'document_parse',
        'doc_id': doc_id,
        'file_name': file_name,
        'duration_ms': duration_ms,
        'chunk_count': chunk_count,
        'success': success,
    }

    if error:
        log_data['error'] = error
        logger.error(f'Document parse failed: doc_id={doc_id}', extra=log_data)
    else:
        logger.info(f'Document parse completed: doc_id={doc_id}', extra=log_data)


# 初始化日志
log_initializer = LoggerInitializer()
logger = log_initializer.init_log()

# 导出便捷函数
__all__ = [
    'logger',
    'log_structured',
    'log_rag_query',
    'log_document_parse',
    'StructuredLogFormatter',
]
