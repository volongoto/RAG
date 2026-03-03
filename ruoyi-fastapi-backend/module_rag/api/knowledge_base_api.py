from datetime import datetime
from typing import Annotated

from fastapi import Depends, Path, Query, Request, Response
from pydantic_validation_decorator import ValidateFields
from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.log_annotation import Log
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import CurrentUserDependency, PreAuthDependency
from common.enums import BusinessType
from common.router import APIRouterPro
from common.vo import DataResponseModel, ResponseBaseModel
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_rag.entity.do.rag_do import RagKnowledgeBase
from module_rag.entity.vo.rag_vo import DeleteKnowledgeBaseModel, KnowledgeBaseModel, KnowledgeBaseQueryModel
from module_rag.service.knowledge_base_service import KnowledgeBaseDataScope, KnowledgeBaseService
from utils.log_util import logger
from utils.response_util import ResponseUtil

knowledge_base_controller = APIRouterPro(
    prefix='/rag/kb', order_num=20, tags=['RAG-知识库管理'], dependencies=[PreAuthDependency()]
)


@knowledge_base_controller.get(
    '/list',
    summary='获取知识库列表接口',
    description='用于获取知识库列表',
    response_model=DataResponseModel[list[KnowledgeBaseModel]],
    dependencies=[UserInterfaceAuthDependency('rag:kb:list')],
)
async def get_knowledge_base_list(
    request: Request,
    kb_query: Annotated[KnowledgeBaseQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    data_scope_sql: Annotated[ColumnElement, Depends(KnowledgeBaseDataScope(RagKnowledgeBase))],
) -> Response:
    kb_query_result = await KnowledgeBaseService.get_kb_list_services(query_db, kb_query, data_scope_sql)
    logger.info('获取成功')

    return ResponseUtil.success(data=kb_query_result)


@knowledge_base_controller.get(
    '/tree',
    summary='获取知识库树接口',
    description='用于获取知识库树（下拉选择）',
    response_model=DataResponseModel[list[dict]],
    dependencies=[UserInterfaceAuthDependency('rag:kb:list')],
)
async def get_knowledge_base_tree(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    data_scope_sql: Annotated[ColumnElement, Depends(KnowledgeBaseDataScope(RagKnowledgeBase))],
) -> Response:
    kb_tree_result = await KnowledgeBaseService.get_kb_tree_services(query_db, data_scope_sql)
    logger.info('获取成功')

    return ResponseUtil.success(data=kb_tree_result)


@knowledge_base_controller.get(
    '/{kb_id}',
    summary='获取知识库详情接口',
    description='用于获取指定知识库的详情信息',
    response_model=DataResponseModel[KnowledgeBaseModel],
    dependencies=[UserInterfaceAuthDependency('rag:kb:query')],
)
async def query_detail_knowledge_base(
    request: Request,
    kb_id: Annotated[int, Path(description='知识库ID')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    data_scope_sql: Annotated[ColumnElement, Depends(KnowledgeBaseDataScope(RagKnowledgeBase))],
) -> Response:
    if not current_user.user.admin:
        await KnowledgeBaseService.check_kb_data_scope_services(query_db, kb_id, data_scope_sql)
    detail_kb_result = await KnowledgeBaseService.get_kb_detail_services(query_db, kb_id)
    logger.info(f'获取kb_id为{kb_id}的信息成功')

    return ResponseUtil.success(data=detail_kb_result)


@knowledge_base_controller.post(
    '',
    summary='新增知识库接口',
    description='用于新增知识库',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('rag:kb:add')],
)
@ValidateFields(validate_model='add_kb')
@Log(title='知识库管理', business_type=BusinessType.INSERT)
async def add_knowledge_base(
    request: Request,
    add_kb: KnowledgeBaseModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    add_kb.create_by = current_user.user.user_name
    add_kb.create_time = datetime.now()
    add_kb.update_by = current_user.user.user_name
    add_kb.update_time = datetime.now()
    add_kb_result = await KnowledgeBaseService.add_kb_services(query_db, add_kb)
    logger.info(add_kb_result.message)

    return ResponseUtil.success(msg=add_kb_result.message)


@knowledge_base_controller.put(
    '',
    summary='编辑知识库接口',
    description='用于编辑知识库',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('rag:kb:edit')],
)
@ValidateFields(validate_model='edit_kb')
@Log(title='知识库管理', business_type=BusinessType.UPDATE)
async def edit_knowledge_base(
    request: Request,
    edit_kb: KnowledgeBaseModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    data_scope_sql: Annotated[ColumnElement, Depends(KnowledgeBaseDataScope(RagKnowledgeBase))],
) -> Response:
    if not current_user.user.admin:
        await KnowledgeBaseService.check_kb_data_scope_services(query_db, edit_kb.kb_id, data_scope_sql)
    edit_kb.update_by = current_user.user.user_name
    edit_kb.update_time = datetime.now()
    edit_kb_result = await KnowledgeBaseService.edit_kb_services(query_db, edit_kb)
    logger.info(edit_kb_result.message)

    return ResponseUtil.success(msg=edit_kb_result.message)


@knowledge_base_controller.delete(
    '/{kb_ids}',
    summary='删除知识库接口',
    description='用于删除知识库',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('rag:kb:remove')],
)
@Log(title='知识库管理', business_type=BusinessType.DELETE)
async def delete_knowledge_base(
    request: Request,
    kb_ids: Annotated[str, Path(description='需要删除的知识库ID')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    delete_kb = DeleteKnowledgeBaseModel(
        kbIds=kb_ids, updateBy=current_user.user.user_name, updateTime=datetime.now()
    )
    delete_kb_result = await KnowledgeBaseService.delete_kb_services(query_db, delete_kb)
    logger.info(delete_kb_result.message)

    return ResponseUtil.success(msg=delete_kb_result.message)
