from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from module_rag.entity.vo.rag_vo import SourceChunkModel
from module_rag.entity.vo.runtime_vo import ExternalPrincipalModel


class OrchestratorContextModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    session_id: str = Field(description='Session ID')
    scenario: str = Field(description='Scenario')
    locale: str = Field(description='Locale')


class OrchestratorChatRequestModel(OrchestratorContextModel):
    message: str = Field(description='User message')
    kb_ids: list[int] = Field(description='Knowledge base IDs')
    stream: bool = Field(default=False, description='Whether to stream response')
    top_k: int = Field(default=10, ge=1, le=50, description='Top K retrieval')
    retrieval_mode: Literal['vector', 'lexical', 'hybrid'] = Field(default='hybrid', description='Retrieval mode')
    include_source: bool = Field(default=True, description='Include source chunks')


class InternalOrchestratorChatRequestModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    principal: ExternalPrincipalModel = Field(description='External principal payload')
    chat: OrchestratorChatRequestModel = Field(description='Orchestrator chat payload')


class TraceEventModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    event_id: str = Field(description='Event ID')
    request_id: str = Field(description='Request ID')
    trace_id: str = Field(description='Trace ID')
    session_id: str = Field(description='Session ID')
    task_id: Optional[str] = Field(default=None, description='Task ID')
    step_key: str = Field(description='Step key')
    step_label: str = Field(description='Step label')
    status: Literal['started', 'success', 'failed'] = Field(description='Execution status')
    start_time: datetime = Field(description='Step start time')
    end_time: Optional[datetime] = Field(default=None, description='Step end time')
    latency_ms: Optional[int] = Field(default=None, description='Step latency in milliseconds')
    summary: Optional[str] = Field(default=None, description='Execution summary')
    meta: dict[str, Any] = Field(default_factory=dict, description='Step metadata')


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
    trace_id: str = Field(description='Trace ID')
    final_answer: str = Field(description='Final answer')
    citations: list[SourceChunkModel] = Field(default_factory=list, description='Cited chunks')
    tool_calls: list[ToolCallTraceModel] = Field(default_factory=list, description='Tool traces')
    trace_events: list[TraceEventModel] = Field(default_factory=list, description='Structured trace events')
    latency_ms: int = Field(description='Total latency in milliseconds')


class OrchestratorTaskCreateModel(OrchestratorContextModel):
    task_type: str = Field(description='Task type')
    payload: dict[str, Any] = Field(default_factory=dict, description='Task payload')


class OrchestratorTaskModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    task_id: str = Field(description='Task ID')
    owner_user_id: Optional[str] = Field(default=None, description='Owner user ID', exclude=True)
    owner_tenant_id: Optional[str] = Field(default=None, description='Owner tenant ID', exclude=True)
    status: Literal['pending', 'running', 'success', 'failed'] = Field(description='Task status')
    task_type: str = Field(description='Task type')
    session_id: str = Field(description='Session ID')
    request_id: Optional[str] = Field(default=None, description='Request ID')
    trace_id: Optional[str] = Field(default=None, description='Trace ID')
    current_step: Optional[str] = Field(default=None, description='Current step label')
    progress_percent: int = Field(default=0, ge=0, le=100, description='Task progress percent')
    trace_events: list[TraceEventModel] = Field(default_factory=list, description='Structured trace events')
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
    owner_user_id: Optional[str] = Field(default=None, description='Owner user ID', exclude=True)
    owner_tenant_id: Optional[str] = Field(default=None, description='Owner tenant ID', exclude=True)
    messages: list[OrchestratorSessionMessageModel] = Field(default_factory=list, description='Session messages')
    update_time: datetime = Field(description='Updated time')
