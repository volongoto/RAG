import base64
from typing import Annotated

from fastapi import Body, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from common.aspect.db_seesion import DBSessionDependency
from common.aspect.internal_service_auth import InternalServiceAuthDependency
from common.router import APIRouterPro
from common.vo import DataResponseModel, ResponseBaseModel
from module_rag.entity.vo.rag_vo import DocumentModel, QueryResponseModel
from module_rag.entity.vo.runtime_vo import (
    InternalQueryRequestModel,
    InternalUploadDocumentRequestModel,
    InternalUploadDocumentResponseModel,
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


@internal_rag_controller.get(
    '/documents',
    summary='List documents for bridged principal',
    response_model=DataResponseModel[dict],
)
async def list_documents(
    request: Request,
    principal: Annotated[InternalVisibleKnowledgeBasesRequestModel, Body()],
    kb_id: Annotated[int | None, Query(description='Knowledge base ID filter')] = None,
    page_num: Annotated[int, Query(ge=1, description='Page number')] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description='Page size')] = 10,
    query_db: Annotated[AsyncSession, DBSessionDependency()] = None,
) -> Response:
    """获取文档列表（支持外部系统调用）"""
    result = await InternalRagBridgeService.get_document_list(
        query_db,
        principal.principal,
        kb_id=kb_id,
        page_num=page_num,
        page_size=page_size,
        redis=request.app.state.redis,
    )
    logger.info(
        f'Internal document list fetched: source={principal.principal.source_system} '
        f'kb_id={kb_id} page={page_num}/{page_size}'
    )
    return ResponseUtil.success(data=result)


@internal_rag_controller.post(
    '/documents/upload',
    summary='Upload document for bridged principal',
    response_model=DataResponseModel[InternalUploadDocumentResponseModel],
)
async def upload_document(
    request: Request,
    payload: Annotated[InternalUploadDocumentRequestModel, Body()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    """上传文档（支持外部系统调用，文件内容使用 Base64 编码）"""
    try:
        # 解码 Base64 文件内容
        file_content = base64.b64decode(payload.file_content_base64)
    except Exception as e:
        logger.error(f'Base64 decode failed: {e}')
        return ResponseUtil.failure(msg='文件内容 Base64 解码失败')

    result = await InternalRagBridgeService.upload_document(
        query_db,
        payload.principal,
        kb_id=payload.kb_id,
        file_name=payload.file_name,
        file_content=file_content,
        file_type=payload.file_type,
        redis=request.app.state.redis,
    )

    logger.info(
        f'Internal document uploaded: source={payload.principal.source_system} '
        f'kb_id={payload.kb_id} filename={payload.file_name} size={result["file_size"]}'
    )

    return ResponseUtil.success(
        data=InternalUploadDocumentResponseModel(
            doc_id=result['doc_id'],
            file_name=result['file_name'],
            file_size=result['file_size'],
            parse_status=result['parse_status'],
            message=result['message'],
        )
    )


@internal_rag_controller.delete(
    '/documents/{doc_id}',
    summary='Delete document for bridged principal',
    response_model=ResponseBaseModel,
)
async def delete_document(
    request: Request,
    doc_id: Annotated[int, ...],
    principal: Annotated[InternalVisibleKnowledgeBasesRequestModel, Body()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    """删除文档（支持外部系统调用）"""
    result = await InternalRagBridgeService.delete_document(
        query_db,
        principal.principal,
        doc_id=doc_id,
        redis=request.app.state.redis,
    )

    logger.info(
        f'Internal document deleted: source={principal.principal.source_system} doc_id={doc_id}'
    )

    return ResponseUtil.success(msg=result['message'])
