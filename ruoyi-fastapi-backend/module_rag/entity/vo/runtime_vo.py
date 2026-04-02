from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from module_rag.entity.vo.rag_vo import KnowledgeBaseModel, QueryRequestModel, SourceChunkModel


class RuntimeContextModel(BaseModel):
    """
    Shared context required by orchestrator/runtime contracts.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    session_id: str = Field(description='Session ID')
    scenario: str = Field(description='Scenario')
    locale: str = Field(description='Locale')


class RetrieveRequestModel(RuntimeContextModel):
    """
    Retrieve-only request model.
    """

    kb_ids: list[int] = Field(description='Knowledge base IDs')
    query_text: str = Field(description='User query')
    top_k: Optional[int] = Field(default=10, ge=1, le=50, description='Top K')
    retrieval_mode: Literal['vector', 'lexical', 'hybrid'] = Field(default='hybrid', description='Retrieval mode')


class RetrieveResponseModel(BaseModel):
    """
    Retrieve-only response model.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    chunks: list[SourceChunkModel] = Field(description='Retrieved chunks')
    response_time: int = Field(description='Latency in milliseconds')


class IndexJobCreateModel(RuntimeContextModel):
    """
    Index job create request model.
    """

    mode: Literal['reparse_docs', 'rebuild_kb'] = Field(default='reparse_docs', description='Job mode')
    doc_ids: list[int] = Field(default_factory=list, description='Document IDs')
    kb_ids: list[int] = Field(default_factory=list, description='Knowledge base IDs')


class IndexJobModel(BaseModel):
    """
    Index job status model.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    job_id: str = Field(description='Job ID')
    status: Literal['pending', 'running', 'success', 'failed'] = Field(description='Job status')
    mode: Literal['reparse_docs', 'rebuild_kb'] = Field(description='Job mode')
    total_docs: int = Field(default=0, description='Total docs')
    processed_docs: int = Field(default=0, description='Processed docs')
    failed_docs: int = Field(default=0, description='Failed docs')
    message: Optional[str] = Field(default=None, description='Status message')
    error: Optional[str] = Field(default=None, description='Error message')
    create_by: Optional[str] = Field(default=None, description='Created by')
    create_time: datetime = Field(description='Created time')
    update_time: datetime = Field(description='Updated time')


class ExternalPrincipalModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    source_system: str = Field(description='Source system code')
    external_user_id: Optional[str] = Field(default=None, description='External user ID')
    external_user_name: Optional[str] = Field(default=None, description='External user name')
    external_dept_id: Optional[str] = Field(default=None, description='External department ID')


class ResolvedPrincipalModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    source_system: str = Field(description='Source system code')
    external_user_id: Optional[str] = Field(default=None, description='External user ID')
    external_user_name: Optional[str] = Field(default=None, description='External user name')
    external_dept_id: Optional[str] = Field(default=None, description='External department ID')
    mapped_user_id: Optional[int] = Field(default=None, description='Mapped local user ID')
    mapped_user_name: Optional[str] = Field(default=None, description='Mapped local user name')
    mapped_dept_id: Optional[int] = Field(default=None, description='Mapped local department ID')
    mapped_dept_name: Optional[str] = Field(default=None, description='Mapped local department name')
    is_admin: bool = Field(default=False, description='Whether mapped local user is admin')
    resolution_mode: str = Field(default='unresolved', description='Resolution strategy')


class InternalVisibleKnowledgeBasesRequestModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    principal: ExternalPrincipalModel = Field(description='External principal payload')


class InternalVisibleKnowledgeBasesResponseModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    principal: ResolvedPrincipalModel = Field(description='Resolved local principal')
    kb_ids: list[int] = Field(default_factory=list, description='Visible knowledge base IDs')
    knowledge_bases: list[KnowledgeBaseModel] = Field(default_factory=list, description='Visible knowledge base list')


class InternalQueryRequestModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    principal: ExternalPrincipalModel = Field(description='External principal payload')
    query: QueryRequestModel = Field(description='RAG query payload')


class InternalUploadDocumentRequestModel(BaseModel):
    """内部文档上传请求模型（用于外部系统上传文档）"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    principal: ExternalPrincipalModel = Field(description='External principal payload')
    kb_id: int = Field(description='Target knowledge base ID')
    file_name: str = Field(description='Document file name')
    file_content_base64: str = Field(description='Base64 encoded file content')
    file_type: Optional[str] = Field(default=None, description='File type/extension (auto-detected if not provided)')


class InternalUploadDocumentResponseModel(BaseModel):
    """内部文档上传响应模型"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    doc_id: int = Field(description='Created document ID')
    file_name: str = Field(description='Stored file name')
    file_size: int = Field(description='File size in bytes')
    parse_status: str = Field(default='0', description='Parse status: 0=pending, 1=parsing, 2=completed, 3=failed')
    message: str = Field(description='Response message')
