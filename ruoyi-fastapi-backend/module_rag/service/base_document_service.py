"""
文档服务基础类
提取 LegacyDocumentService 和 DocumentService 的公共逻辑
"""

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, ClassVar

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from module_rag.entity.vo.rag_vo import DocumentModel
from utils.log_util import logger


class BaseDocumentService(ABC):
    """
    文档服务抽象基类
    定义文档服务的公共接口和通用逻辑
    """

    # 类级别的任务跟踪
    _parse_tasks: ClassVar[dict[int, asyncio.Task]] = {}
    _progress_key_prefix: ClassVar[str] = 'rag:doc:parse_progress'
    _progress_ttl_seconds: ClassVar[int] = 24 * 60 * 60  # 24 小时

    @classmethod
    def _progress_key(cls, doc_id: int) -> str:
        """生成进度缓存键"""
        return f'{cls._progress_key_prefix}:{doc_id}'

    @classmethod
    def _default_progress(cls, doc: dict[str, Any]) -> tuple[int, str]:
        """
        根据文档状态获取默认进度信息

        Returns:
            (进度百分比, 状态消息)
        """
        status = doc.get('parseStatus') or doc.get('parse_status')
        if status == '2':
            return 100, '解析完成'
        if status == '3':
            return 0, doc.get('parseError') or doc.get('parse_error') or '解析失败'
        if status == '1':
            return 1, '解析中'
        return 0, '等待解析'

    @classmethod
    async def _set_progress(
        cls, redis: Redis | None, doc_id: int, progress: int, message: str
    ) -> None:
        """
        设置文档解析进度

        Args:
            redis: Redis 客户端
            doc_id: 文档 ID
            progress: 进度百分比 (0-100)
            message: 进度消息
        """
        if redis is None:
            return

        payload = json.dumps(
            {
                'parseProgress': max(0, min(100, int(progress))),
                'parseMessage': message,
            },
            ensure_ascii=False,
        )
        await redis.set(cls._progress_key(doc_id), payload, ex=cls._progress_ttl_seconds)

    @classmethod
    async def _get_progress(cls, redis: Redis | None, doc_id: int) -> dict[str, Any]:
        """
        获取文档解析进度

        Args:
            redis: Redis 客户端
            doc_id: 文档 ID

        Returns:
            进度信息字典
        """
        if redis is None:
            return {}

        raw_value = await redis.get(cls._progress_key(doc_id))
        if not raw_value:
            return {}

        try:
            progress_data = json.loads(raw_value)
            return progress_data if isinstance(progress_data, dict) else {}
        except json.JSONDecodeError:
            return {}

    @classmethod
    async def _decorate_docs_with_progress(
        cls, redis: Redis | None, docs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        为文档列表添加进度信息

        Args:
            redis: Redis 客户端
            docs: 文档列表

        Returns:
            添加了进度信息的文档列表
        """
        for doc in docs:
            doc_id = doc.get('docId') or doc.get('doc_id')
            default_progress, default_message = cls._default_progress(doc)
            progress_data = await cls._get_progress(redis, int(doc_id)) if doc_id else {}
            doc['parseProgress'] = int(progress_data.get('parseProgress', default_progress))
            doc['parseMessage'] = progress_data.get('parseMessage') or default_message
        return docs

    @classmethod
    def _start_parse_task(cls, doc_id: int, redis: Redis | None) -> None:
        """
        启动文档解析任务

        Args:
            doc_id: 文档 ID
            redis: Redis 客户端
        """
        existing_task = cls._parse_tasks.get(doc_id)
        if existing_task and not existing_task.done():
            logger.warning(f'Parse task for doc_id={doc_id} already exists, skipping')
            return

        cls._parse_tasks[doc_id] = asyncio.create_task(
            cls._parse_document_async(doc_id, redis),
            name=f'parse_doc_{doc_id}'
        )
        logger.info(f'Started parse task for doc_id={doc_id}')

    @classmethod
    async def _cancel_parse_task(cls, doc_id: int) -> None:
        """
        取消文档解析任务

        Args:
            doc_id: 文档 ID
        """
        task = cls._parse_tasks.get(doc_id)
        if task and not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
            logger.info(f'Cancelled parse task for doc_id={doc_id}')

    @classmethod
    @abstractmethod
    async def _parse_document_async(cls, doc_id: int, redis: Redis | None) -> None:
        """
        异步解析文档（子类必须实现）

        Args:
            doc_id: 文档 ID
            redis: Redis 客户端
        """
        pass

    @classmethod
    @abstractmethod
    async def get_doc_list_services(
        cls,
        query_db: AsyncSession,
        page_object: DocumentModel,
        data_scope_sql=None,
        redis: Redis | None = None,
    ) -> list[dict[str, Any]]:
        """获取文档列表（子类必须实现）"""
        pass

    @classmethod
    @abstractmethod
    async def get_doc_detail_services(
        cls, query_db: AsyncSession, doc_id: int, redis: Redis | None = None
    ) -> DocumentModel:
        """获取文档详情（子类必须实现）"""
        pass

    @classmethod
    @abstractmethod
    async def upload_document_services(
        cls,
        query_db: AsyncSession,
        redis: Redis | None,
        kb_id: int,
        file_name: str,
        file_path: str,
        file_size: int,
        file_type: str,
        create_by: str,
    ) -> Any:
        """上传文档（子类必须实现）"""
        pass

    @classmethod
    @abstractmethod
    async def delete_document_services(
        cls, query_db: AsyncSession, redis: Redis | None, doc_ids: str, update_by: str
    ) -> Any:
        """删除文档（子类必须实现）"""
        pass

    @classmethod
    @abstractmethod
    async def reparse_document_services(
        cls, query_db: AsyncSession, redis: Redis | None, doc_id: int
    ) -> Any:
        """重新解析文档（子类必须实现）"""
        pass
