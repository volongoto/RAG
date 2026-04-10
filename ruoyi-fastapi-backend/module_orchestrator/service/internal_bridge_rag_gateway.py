from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from common.request_meta import RequestMeta
from module_orchestrator.service.rag_gateway_interface import RagGatewayInterface
from module_rag.entity.vo.rag_vo import QueryRequestModel, QueryResponseModel
from module_rag.entity.vo.runtime_vo import ExternalPrincipalModel, RetrieveRequestModel, RetrieveResponseModel
from module_rag.service.internal_bridge_service import InternalRagBridgeService


class InternalBridgeRagGateway(RagGatewayInterface):
    """
    Route orchestrator RAG calls through the internal principal bridge.
    """

    def __init__(self, principal: ExternalPrincipalModel):
        self.principal = principal

    async def retrieve(
        self,
        query_db: AsyncSession,
        request_model: RetrieveRequestModel,
        meta: RequestMeta,
    ) -> RetrieveResponseModel:
        return await InternalRagBridgeService.retrieve_knowledge_bases(query_db, self.principal, request_model)

    async def query(
        self,
        query_db: AsyncSession,
        request_model: QueryRequestModel,
        user_id: int,
        meta: RequestMeta,
    ) -> QueryResponseModel:
        return await InternalRagBridgeService.query_knowledge_bases(query_db, self.principal, request_model)
