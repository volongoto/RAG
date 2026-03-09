from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from module_rag.entity.vo.rag_vo import SourceChunkModel


class OrchestratorContextModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    session_id: str = Field(description='Session ID')
    scenario: str = Field(description='Scenario')
    locale: str = Field(description='Locale')


class OrchestratorChatRequestModel(OrchestratorContextModel):
    message: str = Field(description='User message')
    kb_ids: list[int] = Field(description='Knowledge base IDs')
    stream: bool = Field(default=False, description='Whether to stream response')
    top_k: int = Field(default=5, description='Top K retrieval')
    retrieval_mode: Literal['vector', 'lexical', 'hybrid'] = Field(default='hybrid', description='Retrieval mode')
    include_source: bool = Field(default=True, description='Include source chunks')


class ToolCallTraceModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    tool: str = Field(description='Tool name')
    status: Literal['success', 'failed'] = Field(description='Execution status')
    latency_ms: int = Field(description='Tool latency in milliseconds')
    summary: Optional[str] = Field(default=None, description='Execution summary')


class OrchestratorChatResponseModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    session_id: str = Field(description='Session ID')
    request_id: str = Field(description='Request ID')
    final_answer: str = Field(description='Final answer')
    citations: list[SourceChunkModel] = Field(default_factory=list, description='Cited chunks')
    tool_calls: list[ToolCallTraceModel] = Field(default_factory=list, description='Tool traces')
    latency_ms: int = Field(description='Total latency in milliseconds')


class OrchestratorTaskCreateModel(OrchestratorContextModel):
    task_type: str = Field(description='Task type')
    payload: dict[str, Any] = Field(default_factory=dict, description='Task payload')


class OrchestratorTaskModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    task_id: str = Field(description='Task ID')
    status: Literal['pending', 'running', 'success', 'failed'] = Field(description='Task status')
    task_type: str = Field(description='Task type')
    session_id: str = Field(description='Session ID')
    result: Optional[OrchestratorChatResponseModel] = Field(default=None, description='Task result')
    error: Optional[str] = Field(default=None, description='Error message')
    create_time: datetime = Field(description='Created time')
    update_time: datetime = Field(description='Updated time')


class OrchestratorSessionMessageModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    role: Literal['user', 'assistant'] = Field(description='Message role')
    content: str = Field(description='Message content')
    time: datetime = Field(description='Message time')


class OrchestratorSessionViewModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    session_id: str = Field(description='Session ID')
    messages: list[OrchestratorSessionMessageModel] = Field(default_factory=list, description='Session messages')
    update_time: datetime = Field(description='Updated time')
