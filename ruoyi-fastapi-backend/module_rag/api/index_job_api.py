from typing import Annotated

from fastapi import Body, Depends, Header, Path, Request, Response
from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.log_annotation import Log
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import CurrentUserDependency, PreAuthDependency
from common.enums import BusinessType
from common.router import APIRouterPro
from common.vo import DataResponseModel
from exceptions.exception import ServiceException
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_rag.entity.do.rag_do import RagKnowledgeBase
from module_rag.entity.vo.runtime_vo import IndexJobCreateModel, IndexJobModel
from module_rag.service.index_job_service import IndexJobService
from module_rag.service.knowledge_base_service import KnowledgeBaseDataScope, KnowledgeBaseService
from module_rag.service.rag_service import DocumentService
from utils.idempotency_util import IdempotencyUtil
from utils.log_util import logger
from utils.response_util import ResponseUtil

index_job_controller = APIRouterPro(
    prefix='/rag/index', order_num=24, tags=['RAG-IndexJob'], dependencies=[PreAuthDependency()]
)


@index_job_controller.post(
    '/jobs',
    summary='Create index job',
    description='Create reparse/rebuild index job',
    response_model=DataResponseModel[IndexJobModel],
    dependencies=[UserInterfaceAuthDependency('rag:doc:edit')],
)
@Log(title='RAGIndexJob', business_type=BusinessType.INSERT)
async def create_index_job(
    request: Request,
    payload: Annotated[IndexJobCreateModel, Body(description='Index job request payload')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    data_scope_sql: Annotated[ColumnElement, Depends(KnowledgeBaseDataScope(RagKnowledgeBase))],
    idempotency_key: Annotated[str | None, Header(alias='Idempotency-Key')] = None,
) -> Response:
    await IdempotencyUtil.require_and_lock_key(
        request,
        scope='rag:index:jobs',
        key=idempotency_key,
        ttl_seconds=3600,
    )

    if not current_user.user.admin:
        for kb_id in payload.kb_ids or []:
            await KnowledgeBaseService.check_kb_data_scope_services(query_db, kb_id, data_scope_sql)

        for doc_id in payload.doc_ids or []:
            doc_detail = await DocumentService.get_doc_detail_services(query_db, int(doc_id))
            if not doc_detail or not doc_detail.kb_id:
                raise ServiceException(message=f'Document not found: {doc_id}')
            await KnowledgeBaseService.check_kb_data_scope_services(query_db, int(doc_detail.kb_id), data_scope_sql)

    job = await IndexJobService.create_job(payload, current_user.user.user_name)
    logger.info(f'RAG index job accepted: {job.job_id}')
    return ResponseUtil.success(data=job)


@index_job_controller.get(
    '/jobs/{job_id}',
    summary='Get index job',
    description='Get index job status by job ID',
    response_model=DataResponseModel[IndexJobModel],
    dependencies=[UserInterfaceAuthDependency('rag:doc:query')],
)
async def get_index_job(
    request: Request,
    job_id: Annotated[str, Path(description='Job ID')],
) -> Response:
    job = await IndexJobService.get_job(job_id)
    if not job:
        raise ServiceException(message='Index job not found')
    return ResponseUtil.success(data=job)
