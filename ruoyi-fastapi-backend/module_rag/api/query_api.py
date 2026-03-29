from typing import Annotated

from fastapi import Body, Depends, Query, Request, Response
from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.log_annotation import Log
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import CurrentUserDependency, PreAuthDependency
from common.enums import BusinessType
from common.router import APIRouterPro
from common.vo import DataResponseModel
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_rag.entity.do.rag_do import RagKnowledgeBase
from module_rag.entity.vo.rag_vo import QueryLogQueryModel, QueryRequestModel, QueryResponseModel
from module_rag.service.knowledge_base_service import KnowledgeBaseDataScope, KnowledgeBaseService
from module_rag.service.query_service import QueryService
from utils.log_util import logger
from utils.response_util import ResponseUtil

query_controller = APIRouterPro(
    prefix='/rag/query', order_num=22, tags=['RAG-Query'], dependencies=[PreAuthDependency()]
)


@query_controller.post(
    '',
    summary='Query knowledge',
    description='Run retrieval + generation in RAG runtime',
    response_model=DataResponseModel[QueryResponseModel],
    dependencies=[UserInterfaceAuthDependency('rag:query:execute')],
)
@Log(title='RAGQuery', business_type=BusinessType.OTHER)
async def execute_query(
    request: Request,
    query_request: Annotated[QueryRequestModel, Body(description='Query request payload')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    data_scope_sql: Annotated[ColumnElement, Depends(KnowledgeBaseDataScope(RagKnowledgeBase))],
) -> Response:
    logger.info(
        'RAG query request received: '
        f'path={request.url.path}, '
        f'root_path={request.scope.get("root_path", "")}, '
        f'user_id={current_user.user.user_id}, '
        f'kb_ids={query_request.kb_ids}, '
        f'top_k={query_request.top_k}, '
        f'retrieval_mode={query_request.retrieval_mode}, '
        f'answer_mode={query_request.answer_mode}, '
        f'query_length={len((query_request.query_text or "").strip())}'
    )

    if not current_user.user.admin:
        for kb_id in query_request.kb_ids or []:
            await KnowledgeBaseService.check_kb_data_scope_services(query_db, kb_id, data_scope_sql)

    query_service = QueryService()
    query_result = await query_service.query_services(query_db, query_request, current_user.user.user_id)
    logger.info(
        'RAG query finished: '
        f'user_id={current_user.user.user_id}, '
        f'kb_ids={query_request.kb_ids}, '
        f'response_time={query_result.response_time}, '
        f'source_chunk_count={len(query_result.source_chunks or [])}'
    )
    return ResponseUtil.success(data=query_result)


@query_controller.get(
    '/logs',
    summary='Get query logs',
    description='List RAG query logs',
    response_model=DataResponseModel[list],
    dependencies=[UserInterfaceAuthDependency('rag:query:logs')],
)
async def get_query_logs(
    request: Request,
    log_query: Annotated[QueryLogQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    query_service = QueryService()
    user_id = None if current_user.user.admin else current_user.user.user_id
    logs_result = await query_service.get_query_logs_services(query_db, log_query, user_id)
    logger.info('Query logs fetched')
    return ResponseUtil.success(data=logs_result)
