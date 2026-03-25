import os
import sys
import time

from loguru import logger as _logger
from loguru._logger import Logger

from middlewares.trace_middleware import TraceCtx


class LoggerInitializer:
    def __init__(self) -> None:
        self.log_path = os.path.join(os.getcwd(), 'logs')
        self.__ensure_log_directory_exists()
        self.log_path_error = os.path.join(self.log_path, f'{time.strftime("%Y-%m-%d")}_error.log')

    def __ensure_log_directory_exists(self) -> None:
        if not os.path.exists(self.log_path):
            os.mkdir(self.log_path)

    @staticmethod
    def __filter(log: dict) -> dict:
        log['trace_id'] = TraceCtx.get_id()
        return log

    def __configure_sinks(self, format_str: str, *, enqueue: bool) -> None:
        _logger.add(sys.stderr, filter=self.__filter, format=format_str, enqueue=enqueue)
        _logger.add(
            self.log_path_error,
            filter=self.__filter,
            format=format_str,
            rotation='50MB',
            encoding='utf-8',
            enqueue=enqueue,
            compression='zip',
        )

    def init_log(self) -> Logger:
        format_str = (
            '<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | '
            '<cyan>{trace_id}</cyan> | '
            '<level>{level: <8}</level> | '
            '<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - '
            '<level>{message}</level>'
        )
        _logger.remove()
        try:
            self.__configure_sinks(format_str, enqueue=True)
        except Exception:
            _logger.remove()
            self.__configure_sinks(format_str, enqueue=False)
            _logger.warning('Log queue initialization failed, fallback to synchronous logging')

        return _logger


log_initializer = LoggerInitializer()
logger = log_initializer.init_log()
