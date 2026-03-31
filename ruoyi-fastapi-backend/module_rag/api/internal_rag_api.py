from typing import Annotated

from fastapi import Body, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from common.aspect.db_seesion import DBSessionDependency
from common.aspect.internal_service_auth import InternalServiceAuthDependency
from common.router import APIRouterPro
from common.vo import DataResponseModel
from module_rag.entity.vo.rag_vo import QueryResponseModel
from module_rag.entity.vo.runtime_vo import (
    InternalQueryRequestModel,
    InternalVisibleKnowledgeBasesRequestModel,
    InternalVisibleKnowledgeBasesResponseModel,
)
from module_rag.service.internal_bridge_service import InternalRagBridgeService
from utils.log_util import logger
from utils.response_util import ResponseUtil

internal_rag_controller = APIRouterPro(
    prefix='/internal/rag',
    order_num=24,
    tags=['RAG-Internal'],
    dependencies=[InternalServiceAuthDependency()],
    include_in_schema=False,
)


@internal_rag_controller.post(
    '/kbs/visible',
    summary='Resolve visible knowledge bases for bridged principal',
    response_model=DataResponseModel[InternalVisibleKnowledgeBasesResponseModel],
)
async def get_visible_knowledge_bases(
    request: Request,
    payload: Annotated[InternalVisibleKnowledgeBasesRequestModel, Body()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await InternalRagBridgeService.get_visible_knowledge_bases(query_db, payload.principal)
    logger.info(
        f'Internal visible KB resolved source={payload.principal.source_system} '
        f'mapped_user={result.principal.mapped_user_id} count={len(result.kb_ids)}'
    )
    return ResponseUtil.success(data=result)


@internal_rag_controller.post(
    '/query',
    summary='Execute bridged RAG query',
    response_model=DataResponseModel[QueryResponseModel],
)
async def query_knowledge_bases(
    request: Request,
    payload: Annotated[InternalQueryRequestModel, Body()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await InternalRagBridgeService.query_knowledge_bases(query_db, payload.principal, payload.query)
    return ResponseUtil.success(data=result)
