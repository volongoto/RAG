from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from common.request_meta import RequestMeta
from config.database import AsyncSessionLocal
from module_orchestrator.entity.vo.orchestrator_vo import (
    OrchestratorChatRequestModel,
    OrchestratorChatResponseModel,
    OrchestratorSessionMessageModel,
    OrchestratorSessionViewModel,
    OrchestratorTaskCreateModel,
    OrchestratorTaskModel,
    ToolCallTraceModel,
)
from module_orchestrator.service.rag_runtime_gateway import RagRuntimeGateway
from module_rag.entity.vo.rag_vo import QueryRequestModel
from module_rag.entity.vo.runtime_vo import RetrieveRequestModel


class OrchestratorService:
    """
    Agent orchestrator with in-memory session/task state.
    """

    RAG_RETRIEVE_TIMEOUT_SECONDS = 8
    RAG_QUERY_TIMEOUT_SECONDS = 20

    _session_store: dict[str, OrchestratorSessionViewModel] = {}
    _task_store: dict[str, OrchestratorTaskModel] = {}
    _lock = asyncio.Lock()

    def __init__(self):
        self.runtime_gateway = RagRuntimeGateway()

    async def chat(
        self,
        query_db: AsyncSession,
        current_user_id: int,
        meta: RequestMeta,
        payload: OrchestratorChatRequestModel,
    ) -> OrchestratorChatResponseModel:
        start_time = datetime.now()

        await self._append_session_message(payload.session_id, 'user', payload.message)

        tool_calls: list[ToolCallTraceModel] = []
        citations = []

        retrieve_start = datetime.now()
        retrieve_result = None
        try:
            retrieve_result = await asyncio.wait_for(
                self.runtime_gateway.retrieve(
                    query_db=query_db,
                    request_model=RetrieveRequestModel(
                        sessionId=payload.session_id,
                        scenario=payload.scenario,
                        locale=payload.locale,
                        kbIds=payload.kb_ids,
                        queryText=payload.message,
                        topK=payload.top_k,
                        retrievalMode=payload.retrieval_mode,
                    ),
                    meta=meta,
                ),
                timeout=self.RAG_RETRIEVE_TIMEOUT_SECONDS,
            )
            retrieve_latency = int((datetime.now() - retrieve_start).total_seconds() * 1000)
            citations = retrieve_result.chunks if payload.include_source else []
            tool_calls.append(
                ToolCallTraceModel(
                    tool='rag.retrieve',
                    status='success',
                    latencyMs=retrieve_latency,
                    summary=f'returned {len(retrieve_result.chunks)} chunks',
                )
            )
        except asyncio.TimeoutError:
            retrieve_latency = int((datetime.now() - retrieve_start).total_seconds() * 1000)
            tool_calls.append(
                ToolCallTraceModel(
                    tool='rag.retrieve',
                    status='failed',
                    latencyMs=retrieve_latency,
                    summary=f'timed out after {self.RAG_RETRIEVE_TIMEOUT_SECONDS}s',
                )
            )
        except Exception as e:
            retrieve_latency = int((datetime.now() - retrieve_start).total_seconds() * 1000)
            tool_calls.append(
                ToolCallTraceModel(
                    tool='rag.retrieve',
                    status='failed',
                    latencyMs=retrieve_latency,
                    summary=f'failed: {e}',
                )
            )

        query_start = datetime.now()
        answer_text = ''
        try:
            query_result = await asyncio.wait_for(
                self.runtime_gateway.query(
                    query_db=query_db,
                    request_model=QueryRequestModel(
                        sessionId=payload.session_id,
                        scenario=payload.scenario,
                        locale=payload.locale,
                        kbIds=payload.kb_ids,
                        queryText=payload.message,
                        topK=payload.top_k,
                        retrievalMode=payload.retrieval_mode,
                        includeSource=payload.include_source,
                    ),
                    user_id=current_user_id,
                    meta=meta,
                ),
                timeout=self.RAG_QUERY_TIMEOUT_SECONDS,
            )
            query_latency = int((datetime.now() - query_start).total_seconds() * 1000)
            answer_text = query_result.answer_text
            if payload.include_source and query_result.source_chunks:
                citations = query_result.source_chunks
            tool_calls.append(
                ToolCallTraceModel(
                    tool='rag.query',
                    status='success',
                    latencyMs=query_latency,
                    summary='answer generated',
                )
            )
        except asyncio.TimeoutError:
            query_latency = int((datetime.now() - query_start).total_seconds() * 1000)
            answer_text = self._build_degraded_answer(citations)
            tool_calls.append(
                ToolCallTraceModel(
                    tool='rag.query',
                    status='failed',
                    latencyMs=query_latency,
                    summary=f'timed out after {self.RAG_QUERY_TIMEOUT_SECONDS}s',
                )
            )
        except Exception as e:
            query_latency = int((datetime.now() - query_start).total_seconds() * 1000)
            answer_text = self._build_degraded_answer(citations)
            tool_calls.append(
                ToolCallTraceModel(
                    tool='rag.query',
                    status='failed',
                    latencyMs=query_latency,
                    summary=f'failed: {e}',
                )
            )

        await self._append_session_message(payload.session_id, 'assistant', answer_text)
        latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        return OrchestratorChatResponseModel(
            sessionId=payload.session_id,
            requestId=meta.request_id,
            finalAnswer=answer_text,
            citations=citations or [],
            toolCalls=tool_calls,
            latencyMs=latency_ms,
        )

    async def stream_chat(
        self,
        query_db: AsyncSession,
        current_user_id: int,
        meta: RequestMeta,
        payload: OrchestratorChatRequestModel,
    ) -> AsyncGenerator[str, None]:
        result = await self.chat(query_db, current_user_id, meta, payload)

        for tool in result.tool_calls:
            yield self._sse_line({'event': 'tool', 'data': tool.model_dump(by_alias=True)})

        answer = result.final_answer or ''
        for char in answer:
            yield self._sse_line({'event': 'token', 'data': char})
            await asyncio.sleep(0)

        yield self._sse_line({'event': 'done', 'data': result.model_dump(by_alias=True)})

    async def create_task(
        self,
        current_user_id: int,
        meta: RequestMeta,
        payload: OrchestratorTaskCreateModel,
    ) -> OrchestratorTaskModel:
        now = datetime.now()
        task = OrchestratorTaskModel(
            taskId=uuid4().hex,
            status='pending',
            taskType=payload.task_type,
            sessionId=payload.session_id,
            result=None,
            error=None,
            createTime=now,
            updateTime=now,
        )
        async with self._lock:
            self._task_store[task.task_id] = task
        asyncio.create_task(self._run_task(task.task_id, current_user_id, meta, payload))
        return task

    async def get_task(self, task_id: str) -> OrchestratorTaskModel | None:
        async with self._lock:
            return self._task_store.get(task_id)

    async def get_session(self, session_id: str) -> OrchestratorSessionViewModel:
        async with self._lock:
            session = self._session_store.get(session_id)
            if session:
                return session
            return OrchestratorSessionViewModel(
                sessionId=session_id,
                messages=[],
                updateTime=datetime.now(),
            )

    async def _run_task(
        self,
        task_id: str,
        current_user_id: int,
        meta: RequestMeta,
        payload: OrchestratorTaskCreateModel,
    ) -> None:
        try:
            await self._update_task(task_id, status='running')
            task_message = str(payload.payload.get('message') or '')
            kb_ids = payload.payload.get('kbIds') or payload.payload.get('kb_ids') or []
            if not task_message:
                raise ValueError('payload.message is required')
            if not kb_ids:
                raise ValueError('payload.kbIds is required')

            chat_payload = OrchestratorChatRequestModel(
                sessionId=payload.session_id,
                scenario=payload.scenario,
                locale=payload.locale,
                message=task_message,
                kbIds=kb_ids,
                stream=False,
                topK=int(payload.payload.get('topK') or 10),
                retrievalMode=payload.payload.get('retrievalMode')
                or payload.payload.get('retrieval_mode')
                or 'hybrid',
                includeSource=self._to_bool(payload.payload.get('includeSource', True)),
            )
            async with AsyncSessionLocal() as db:
                result = await self.chat(db, current_user_id, meta, chat_payload)
            await self._update_task(task_id, status='success', result=result, error=None)
        except Exception as e:
            await self._update_task(task_id, status='failed', error=str(e))

    async def _append_session_message(self, session_id: str, role: str, content: str) -> None:
        async with self._lock:
            session = self._session_store.get(session_id)
            now = datetime.now()
            if not session:
                session = OrchestratorSessionViewModel(sessionId=session_id, messages=[], updateTime=now)
            session.messages.append(
                OrchestratorSessionMessageModel(
                    role=role,
                    content=content,
                    time=now,
                )
            )
            session.update_time = now
            self._session_store[session_id] = session

    async def _update_task(
        self,
        task_id: str,
        *,
        status: str | None = None,
        result: OrchestratorChatResponseModel | None = None,
        error: str | None = None,
    ) -> None:
        async with self._lock:
            task = self._task_store.get(task_id)
            if not task:
                return
            data = task.model_dump()
            if status is not None:
                data['status'] = status
            if result is not None:
                data['result'] = result.model_dump(by_alias=True)
            if error is not None:
                data['error'] = error
            data['update_time'] = datetime.now()
            self._task_store[task_id] = OrchestratorTaskModel(**data)

    @staticmethod
    def _sse_line(payload: dict) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    @staticmethod
    def _to_bool(raw_value: object) -> bool:
        if isinstance(raw_value, bool):
            return raw_value
        if isinstance(raw_value, str):
            return raw_value.strip().lower() in {'1', 'true', 'yes', 'on'}
        return bool(raw_value)

    @staticmethod
    def _build_degraded_answer(citations: list) -> str:
        snippets: list[str] = []
        for item in citations[:3]:
            if hasattr(item, 'snippet'):
                snippet = str(item.snippet or '').strip()
            elif isinstance(item, dict):
                snippet = str(item.get('snippet') or '').strip()
            else:
                snippet = ''
            if snippet:
                snippets.append(snippet)

        if snippets:
            merged = ' '.join(snippets)
            if len(merged) > 240:
                merged = merged[:240].rstrip() + '...'
            return (
                'RAG runtime is temporarily unavailable for answer generation. '
                f'Best-effort evidence summary: {merged}'
            )
        return (
            'RAG runtime is temporarily unavailable and no evidence was returned. '
            'Please retry later.'
        )
