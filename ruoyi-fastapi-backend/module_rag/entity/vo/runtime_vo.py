from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from module_rag.entity.vo.rag_vo import SourceChunkModel


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
    top_k: Optional[int] = Field(default=5, description='Top K')
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
