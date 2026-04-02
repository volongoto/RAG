"""
RAG 网关接口定义
用于解耦 OrchestratorService 和具体的 RAG 实现
"""

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.request_meta import RequestMeta
from module_rag.entity.vo.rag_vo import QueryRequestModel
from module_rag.entity.vo.runtime_vo import RetrieveRequestModel


class RagGatewayInterface(ABC):
    """
    RAG 网关接口
    定义 RAG 服务的标准接口，便于解耦和测试
    """

    @abstractmethod
    async def retrieve(
        self,
        query_db: AsyncSession,
        request_model: RetrieveRequestModel,
        meta: RequestMeta,
    ) -> Any:
        """
        执行知识检索

        Args:
            query_db: 数据库会话
            request_model: 检索请求模型
            meta: 请求元数据

        Returns:
            检索结果
        """
        pass

    @abstractmethod
    async def query(
        self,
        query_db: AsyncSession,
        request_model: QueryRequestModel,
        user_id: int,
        meta: RequestMeta,
    ) -> Any:
        """
        执行 RAG 查询（检索+生成）

        Args:
            query_db: 数据库会话
            request_model: 查询请求模型
            user_id: 用户 ID
            meta: 请求元数据

        Returns:
            查询结果
        """
        pass


class MockRagGateway(RagGatewayInterface):
    """
    Mock RAG 网关
    用于测试环境
    """

    async def retrieve(
        self,
        query_db: AsyncSession,
        request_model: RetrieveRequestModel,
        meta: RequestMeta,
    ) -> Any:
        """Mock 检索"""
        from module_rag.entity.vo.runtime_vo import RetrieveResponseModel

        return RetrieveResponseModel(
            chunks=[],
            response_time=0,
        )

    async def query(
        self,
        query_db: AsyncSession,
        request_model: QueryRequestModel,
        user_id: int,
        meta: RequestMeta,
    ) -> Any:
        """Mock 查询"""
        from module_rag.entity.vo.rag_vo import QueryResponseModel

        return QueryResponseModel(
            answer_text='Mock answer',
            source_chunks=[],
            response_time=0,
        )
