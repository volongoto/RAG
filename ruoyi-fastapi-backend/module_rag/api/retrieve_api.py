from typing import Annotated

from fastapi import Body, Depends, Request, Response
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
from module_rag.entity.vo.runtime_vo import RetrieveRequestModel, RetrieveResponseModel
from module_rag.service.knowledge_base_service import KnowledgeBaseDataScope, KnowledgeBaseService
from module_rag.service.query_service import QueryService
from utils.log_util import logger
from utils.response_util import ResponseUtil

retrieve_controller = APIRouterPro(
    prefix='/rag', order_num=23, tags=['RAG-Retrieve'], dependencies=[PreAuthDependency()]
)


@retrieve_controller.post(
    '/retrieve',
    summary='Retrieve evidence only',
    description='Retrieve chunks and scores without answer generation',
    response_model=DataResponseModel[RetrieveResponseModel],
    dependencies=[UserInterfaceAuthDependency('rag:query:execute')],
)
@Log(title='RAGRetrieve', business_type=BusinessType.OTHER)
async def retrieve_context(
    request: Request,
    retrieve_request: Annotated[RetrieveRequestModel, Body(description='Retrieve request payload')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    data_scope_sql: Annotated[ColumnElement, Depends(KnowledgeBaseDataScope(RagKnowledgeBase))],
) -> Response:
    if not current_user.user.admin:
        for kb_id in retrieve_request.kb_ids or []:
            await KnowledgeBaseService.check_kb_data_scope_services(query_db, kb_id, data_scope_sql)

    query_service = QueryService()
    retrieve_result = await query_service.retrieve_services(query_db, retrieve_request)
    logger.info('RAG retrieve finished')
    return ResponseUtil.success(data=retrieve_result)
