from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from pydantic_validation_decorator import NotBlank, Size


class KnowledgeBaseModel(BaseModel):
    """
    Knowledge base model.
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    kb_id: Optional[int] = Field(default=None, description='Knowledge base ID')
    kb_name: Optional[str] = Field(default=None, description='Knowledge base name')
    kb_type: Optional[Literal['dept', 'personal']] = Field(default=None, description='Knowledge base type')
    description: Optional[str] = Field(default=None, description='Description')
    dept_id: Optional[int] = Field(default=None, description='Department ID')
    user_id: Optional[int] = Field(default=None, description='Owner user ID')
    embedding_model: Optional[str] = Field(default='BAAI/bge-m3', description='Embedding model')
    status: Optional[Literal['0', '1']] = Field(default='0', description='Status: 0 enabled, 1 disabled')
    del_flag: Optional[Literal['0', '2']] = Field(default=None, description='Delete flag')
    create_by: Optional[str] = Field(default=None, description='Created by')
    create_time: Optional[datetime] = Field(default=None, description='Created time')
    update_by: Optional[str] = Field(default=None, description='Updated by')
    update_time: Optional[datetime] = Field(default=None, description='Updated time')
    remark: Optional[str] = Field(default=None, description='Remark')

    @NotBlank(field_name='kb_name', message='Knowledge base name cannot be empty')
    @Size(field_name='kb_name', min_length=0, max_length=200, message='Knowledge base name max length is 200')
    def get_kb_name(self):
        return self.kb_name

    @NotBlank(field_name='kb_type', message='Knowledge base type cannot be empty')
    def get_kb_type(self):
        return self.kb_type

    def validate_fields(self) -> None:
        self.get_kb_name()
        self.get_kb_type()


class KnowledgeBaseQueryModel(BaseModel):
    """
    Knowledge base query model.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    kb_id: Optional[int] = Field(default=None, description='Knowledge base ID')
    kb_name: Optional[str] = Field(default=None, description='Knowledge base name')
    kb_type: Optional[Literal['dept', 'personal']] = Field(default=None, description='Knowledge base type')
    dept_id: Optional[int] = Field(default=None, description='Department ID')
    user_id: Optional[int] = Field(default=None, description='Owner user ID')
    status: Optional[Literal['0', '1']] = Field(default=None, description='Status')
    page_num: Optional[int] = Field(default=1, description='Page number')
    page_size: Optional[int] = Field(default=10, description='Page size')


class DeleteKnowledgeBaseModel(BaseModel):
    """
    Delete knowledge base model.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    kb_ids: str = Field(default=None, description='Knowledge base IDs to delete')
    update_by: Optional[str] = Field(default=None, description='Updated by')
    update_time: Optional[datetime] = Field(default=None, description='Updated time')


class DocumentModel(BaseModel):
    """
    Document model.
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    doc_id: Optional[int] = Field(default=None, description='Document ID')
    kb_id: Optional[int] = Field(default=None, description='Knowledge base ID')
    file_name: Optional[str] = Field(default=None, description='File name')
    file_path: Optional[str] = Field(default=None, description='File path')
    file_size: Optional[int] = Field(default=None, description='File size in bytes')
    file_type: Optional[str] = Field(default=None, description='File type')
    chunk_count: Optional[int] = Field(default=0, description='Chunk count')
    parse_status: Optional[Literal['0', '1', '2', '3']] = Field(default='0', description='Parse status')
    parse_error: Optional[str] = Field(default=None, description='Parse error')
    del_flag: Optional[Literal['0', '2']] = Field(default=None, description='Delete flag')
    create_by: Optional[str] = Field(default=None, description='Created by')
    create_time: Optional[datetime] = Field(default=None, description='Created time')
    update_by: Optional[str] = Field(default=None, description='Updated by')
    update_time: Optional[datetime] = Field(default=None, description='Updated time')


class DocumentQueryModel(BaseModel):
    """
    Document query model.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    doc_id: Optional[int] = Field(default=None, description='Document ID')
    kb_id: Optional[int] = Field(default=None, description='Knowledge base ID')
    file_name: Optional[str] = Field(default=None, description='File name')
    file_type: Optional[str] = Field(default=None, description='File type')
    parse_status: Optional[Literal['0', '1', '2', '3']] = Field(default=None, description='Parse status')
    page_num: Optional[int] = Field(default=1, description='Page number')
    page_size: Optional[int] = Field(default=10, description='Page size')


class DeleteDocumentModel(BaseModel):
    """
    Delete document model.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    doc_ids: str = Field(default=None, description='Document IDs to delete')
    update_by: Optional[str] = Field(default=None, description='Updated by')
    update_time: Optional[datetime] = Field(default=None, description='Updated time')


class ChunkModel(BaseModel):
    """
    Chunk model.
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    chunk_id: Optional[int] = Field(default=None, description='Chunk ID')
    doc_id: Optional[int] = Field(default=None, description='Document ID')
    kb_id: Optional[int] = Field(default=None, description='Knowledge base ID')
    chunk_index: Optional[int] = Field(default=None, description='Chunk index')
    content: Optional[str] = Field(default=None, description='Chunk content')
    metadata: Optional[dict[str, Any]] = Field(default=None, description='Chunk metadata')
    create_time: Optional[datetime] = Field(default=None, description='Created time')


class QueryRequestModel(BaseModel):
    """
    Query request model.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    kb_ids: list[int] = Field(default=None, description='Knowledge base ID list')
    query_text: str = Field(default=None, description='Query text')
    top_k: Optional[int] = Field(default=10, ge=1, le=50, description='Top K results')
    include_source: Optional[bool] = Field(default=True, description='Include source chunks')
    session_id: str = Field(description='Session ID')
    scenario: str = Field(description='Scenario')
    locale: str = Field(description='Locale')
    retrieval_mode: Literal['vector', 'lexical', 'hybrid'] = Field(default='hybrid', description='Retrieval mode')
    answer_mode: Literal['concise', 'detailed'] = Field(default='detailed', description='Answer mode')


class SourceChunkModel(BaseModel):
    """
    Source evidence model.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    kb_id: Optional[int] = Field(default=None, description='Knowledge base ID')
    chunk_id: int = Field(description='Chunk ID')
    doc_id: int = Field(description='Document ID')
    file_name: Optional[str] = Field(default=None, description='Document file name')
    file_path: Optional[str] = Field(default=None, description='Document file path')
    section: Optional[str] = Field(default=None, description='Section title')
    page: Optional[int] = Field(default=None, description='Page number')
    paragraph: Optional[int] = Field(default=None, description='Paragraph index')
    snippet: str = Field(description='Matched snippet')
    retrieval_score: Optional[float] = Field(default=None, description='Retrieval score')
    rerank_score: Optional[float] = Field(default=None, description='Rerank score')
    retrieval_channel: Optional[str] = Field(default=None, description='Retrieval channel')
    # backward-compatible fields
    doc_name: Optional[str] = Field(default=None, description='Legacy document name')
    content: Optional[str] = Field(default=None, description='Legacy content')
    page_num: Optional[int] = Field(default=None, description='Legacy page')
    paragraph_index: Optional[int] = Field(default=None, description='Legacy paragraph')
    similarity: Optional[float] = Field(default=None, description='Legacy similarity score')


class QueryResponseModel(BaseModel):
    """
    Query response model.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    answer_text: str = Field(description='Answer text')
    source_chunks: Optional[list[SourceChunkModel]] = Field(default=None, description='Source chunks')
    response_time: Optional[int] = Field(default=None, description='Response latency in milliseconds')


class QueryLogModel(BaseModel):
    """
    Query log model.
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    log_id: Optional[int] = Field(default=None, description='Log ID')
    kb_ids: Optional[str] = Field(default=None, description='Queried knowledge base IDs')
    query_text: Optional[str] = Field(default=None, description='Query text')
    answer_text: Optional[str] = Field(default=None, description='Answer text')
    source_chunks: Optional[dict[str, Any]] = Field(default=None, description='Source chunks')
    query_time: Optional[datetime] = Field(default=None, description='Query time')
    user_id: Optional[int] = Field(default=None, description='User ID')
    response_time: Optional[int] = Field(default=None, description='Response time in milliseconds')


class QueryLogQueryModel(BaseModel):
    """
    Query log query model.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    log_id: Optional[int] = Field(default=None, description='Log ID')
    user_id: Optional[int] = Field(default=None, description='User ID')
    query_text: Optional[str] = Field(default=None, description='Query text')
    begin_time: Optional[str] = Field(default=None, description='Begin time')
    end_time: Optional[str] = Field(default=None, description='End time')
    page_num: Optional[int] = Field(default=1, description='Page number')
    page_size: Optional[int] = Field(default=10, description='Page size')
