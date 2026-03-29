from datetime import datetime
from typing import Annotated

from fastapi import Depends, File, HTTPException, Path, Query, Request, Response, UploadFile
from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.log_annotation import Log
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import CurrentUserDependency, PreAuthDependency
from common.enums import BusinessType
from common.router import APIRouterPro
from common.vo import DataResponseModel, ResponseBaseModel
from config.env import RAGConfig
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_rag.entity.do.rag_do import RagKnowledgeBase
from module_rag.entity.vo.rag_vo import (
    DeleteDocumentModel,
    DocumentModel,
    DocumentQueryModel,
    DocumentUploadPolicyModel,
)
from module_rag.service.document_storage_service import DocumentStorageService
from module_rag.service.knowledge_base_service import KnowledgeBaseDataScope, KnowledgeBaseService
from module_rag.service.rag_service import DocumentService
from utils.log_util import logger
from utils.response_util import ResponseUtil

ALLOWED_DOCUMENT_EXTENSIONS = ['pdf', 'doc', 'docx']
BYTES_PER_MB = 1024 * 1024

document_controller = APIRouterPro(
    prefix='/rag/doc', order_num=21, tags=['RAG-Document'], dependencies=[PreAuthDependency()]
)


@document_controller.get(
    '/list',
    summary='Get document list',
    description='List documents in a knowledge base',
    response_model=DataResponseModel[list[DocumentModel]],
    dependencies=[UserInterfaceAuthDependency('rag:doc:list')],
)
async def get_document_list(
    request: Request,
    doc_query: Annotated[DocumentQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    doc_query_result = await DocumentService.get_doc_list_services(
        query_db, doc_query, redis=request.app.state.redis
    )
    logger.info('Document list fetched')
    return ResponseUtil.success(data=doc_query_result)


def _normalize_non_negative_int(value: int | None, default: int = 0) -> int:
    if value is None:
        return default
    return max(default, int(value))


def _build_upload_policy() -> DocumentUploadPolicyModel:
    return DocumentUploadPolicyModel(
        allowed_extensions=ALLOWED_DOCUMENT_EXTENSIONS,
        submit_concurrency=max(1, int(getattr(RAGConfig, 'rag_upload_submit_concurrency', 2))),
        queue_size=_normalize_non_negative_int(getattr(RAGConfig, 'rag_upload_queue_size', 0)),
        max_total_size_bytes=_normalize_non_negative_int(getattr(RAGConfig, 'rag_upload_max_total_size_mb', 0))
        * BYTES_PER_MB,
        max_single_file_size_bytes=_normalize_non_negative_int(
            getattr(RAGConfig, 'rag_upload_max_single_file_size_mb', 200)
        )
        * BYTES_PER_MB,
    )


@document_controller.get(
    '/upload-policy',
    summary='Get upload policy',
    description='Return upload constraints for the frontend uploader',
    response_model=DataResponseModel[DocumentUploadPolicyModel],
    dependencies=[UserInterfaceAuthDependency('rag:doc:add')],
)
async def get_document_upload_policy() -> Response:
    return ResponseUtil.success(data=_build_upload_policy())


@document_controller.get(
    '/{doc_id}',
    summary='Get document detail',
    description='Get detail for a single document',
    response_model=DataResponseModel[DocumentModel],
    dependencies=[UserInterfaceAuthDependency('rag:doc:query')],
)
async def query_detail_document(
    request: Request,
    doc_id: Annotated[int, Path(description='Document ID')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    detail_doc_result = await DocumentService.get_doc_detail_services(
        query_db, doc_id, redis=request.app.state.redis
    )
    logger.info(f'Document detail fetched: doc_id={doc_id}')
    return ResponseUtil.success(data=detail_doc_result)


def _resolve_upload_kb_id(
    kb_id: Annotated[int | None, Query(alias='kbId', description='Knowledge base ID')] = None,
    kb_id_legacy: Annotated[int | None, Query(alias='kb_id', include_in_schema=False)] = None,
) -> int:
    resolved_kb_id = kb_id if kb_id is not None else kb_id_legacy
    if resolved_kb_id is None:
        raise HTTPException(
            status_code=422,
            detail=[{'type': 'missing', 'loc': ['query', 'kbId'], 'msg': 'Field required', 'input': None}],
        )
    return resolved_kb_id


@document_controller.post(
    '/upload',
    summary='Upload document',
    description='Upload a document into a knowledge base',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('rag:doc:add')],
)
@Log(title='DocumentManage', business_type=BusinessType.INSERT)
async def upload_document(
    request: Request,
    kb_id: Annotated[int, Depends(_resolve_upload_kb_id)],
    file: Annotated[UploadFile, File(description='Uploaded file')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    data_scope_sql: Annotated[ColumnElement, Depends(KnowledgeBaseDataScope(RagKnowledgeBase))],
) -> Response:
    logger.info(
        'Document upload request received: '
        f'path={request.url.path}, '
        f'root_path={request.scope.get("root_path", "")}, '
        f'user_id={current_user.user.user_id}, '
        f'kb_id={kb_id}, '
        f'filename={file.filename}, '
        f'content_type={file.content_type}'
    )

    if not current_user.user.admin:
        await KnowledgeBaseService.check_kb_data_scope_services(query_db, kb_id, data_scope_sql)

    if not file.filename:
        return ResponseUtil.failure(msg='文件名不能为空')

    file_ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if file_ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        logger.warning(
            'Document upload rejected due to unsupported extension: '
            f'kb_id={kb_id}, filename={file.filename}, extension={file_ext}, content_type={file.content_type}'
        )
        return ResponseUtil.failure(msg='仅支持 PDF、DOC 和 DOCX 文档')

    normalized_file_name = DocumentStorageService.normalize_db_file_name(file.filename)
    if normalized_file_name != file.filename:
        logger.warning(
            'Document file name truncated to fit storage constraints: '
            f'original_filename={file.filename}, normalized_filename={normalized_file_name}'
        )

    upload_policy = _build_upload_policy()
    file_content = await file.read()
    file_size = len(file_content)
    logger.info(
        'Document upload payload loaded: '
        f'kb_id={kb_id}, filename={file.filename}, extension={file_ext}, '
        f'content_type={file.content_type}, size_bytes={file_size}'
    )

    if upload_policy.max_single_file_size_bytes > 0 and file_size > upload_policy.max_single_file_size_bytes:
        max_size_mb = upload_policy.max_single_file_size_bytes // BYTES_PER_MB
        logger.warning(
            'Document upload rejected due to size limit: '
            f'kb_id={kb_id}, filename={file.filename}, size_bytes={file_size}, '
            f'max_size_bytes={upload_policy.max_single_file_size_bytes}'
        )
        return ResponseUtil.failure(msg=f'单个文件大小不能超过 {max_size_mb} MB')

    file_path = await DocumentStorageService.store_uploaded_file(kb_id, normalized_file_name, file_content)
    logger.info(
        'Document stored successfully: '
        f'kb_id={kb_id}, filename={normalized_file_name}, stored_path={file_path}, '
        f'storage_mode={DocumentStorageService.storage_mode()}'
    )

    upload_result = await DocumentService.upload_document_services(
        query_db,
        request.app.state.redis,
        kb_id=kb_id,
        file_name=normalized_file_name,
        file_path=file_path,
        file_size=file_size,
        file_type=file_ext,
        create_by=current_user.user.user_name,
    )
    logger.info(upload_result.message)
    return ResponseUtil.success(msg=upload_result.message)


@document_controller.delete(
    '/{doc_ids}',
    summary='Delete document',
    description='Delete one or more documents',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('rag:doc:remove')],
)
@Log(title='DocumentManage', business_type=BusinessType.DELETE)
async def delete_document(
    request: Request,
    doc_ids: Annotated[str, Path(description='Document IDs')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    delete_doc = DeleteDocumentModel(
        docIds=doc_ids, updateBy=current_user.user.user_name, updateTime=datetime.now()
    )
    delete_doc_result = await DocumentService.delete_document_services(
        query_db, request.app.state.redis, delete_doc.doc_ids, delete_doc.update_by
    )
    logger.info(delete_doc_result.message)
    return ResponseUtil.success(msg=delete_doc_result.message)


@document_controller.post(
    '/reparse/{doc_id}',
    summary='Reparse document',
    description='Submit a document for reparsing',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('rag:doc:edit')],
)
@Log(title='DocumentManage', business_type=BusinessType.UPDATE)
async def reparse_document(
    request: Request,
    doc_id: Annotated[int, Path(description='Document ID')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    reparse_result = await DocumentService.reparse_document_services(
        query_db, request.app.state.redis, doc_id
    )
    logger.info(reparse_result.message)
    return ResponseUtil.success(msg=reparse_result.message)
