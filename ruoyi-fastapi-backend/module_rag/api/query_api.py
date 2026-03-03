from typing import Annotated

from fastapi import Body, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.log_annotation import Log
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import CurrentUserDependency, PreAuthDependency
from common.enums import BusinessType
from common.router import APIRouterPro
from common.vo import DataResponseModel, ResponseBaseModel
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_rag.entity.vo.rag_vo import QueryLogQueryModel, QueryRequestModel, QueryResponseModel
from module_rag.service.query_service import QueryService
from utils.log_util import logger
from utils.response_util import ResponseUtil

query_controller = APIRouterPro(
    prefix='/rag/query', order_num=22, tags=['RAG-知识查询'], dependencies=[PreAuthDependency()]
)


@query_controller.post(
    '',
    summary='知识查询接口',
    description='用于执行知识查询',
    response_model=DataResponseModel[QueryResponseModel],
    dependencies=[UserInterfaceAuthDependency('rag:query:execute')],
)
@Log(title='知识查询', business_type=BusinessType.OTHER)
async def execute_query(
    request: Request,
    query_request: Annotated[QueryRequestModel, Body(description='查询请求')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    query_service = QueryService()
    query_result = await query_service.query_services(
        query_db, query_request, current_user.user.user_id
    )
    logger.info('查询完成')

    return ResponseUtil.success(data=query_result)


@query_controller.get(
    '/logs',
    summary='获取查询记录接口',
    description='用于获取查询记录列表',
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
    logger.info('获取成功')

    return ResponseUtil.success(data=logs_result)
