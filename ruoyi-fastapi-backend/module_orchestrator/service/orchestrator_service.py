from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Awaitable, Callable
from uuid import uuid4

from redis import asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from common.request_meta import RequestMeta
from config.database import AsyncSessionLocal
from exceptions.exception import PermissionException
from module_orchestrator.entity.vo.orchestrator_vo import (
    OrchestratorChatRequestModel,
    OrchestratorChatResponseModel,
    OrchestratorSessionMessageModel,
    OrchestratorSessionViewModel,
    OrchestratorTaskCreateModel,
    OrchestratorTaskModel,
    ToolCallTraceModel,
    TraceEventModel,
)
from module_orchestrator.service.rag_gateway_interface import RagGatewayInterface
from module_orchestrator.service.rag_runtime_gateway import RagRuntimeGateway
from module_rag.entity.vo.rag_vo import QueryRequestModel
from module_rag.entity.vo.runtime_vo import RetrieveRequestModel
from utils.log_util import logger

TraceCallback = Callable[[TraceEventModel], Awaitable[None]]


class OrchestratorService:
    """
    Agent orchestrator with Redis-backed state and in-memory fallback.
    Uses dependency injection for RAG gateway to enable testing and flexibility.
    """

    RAG_RETRIEVE_TIMEOUT_SECONDS = 8
    RAG_QUERY_TIMEOUT_SECONDS = 20
    STORE_TTL_SECONDS = 24 * 3600
    TASK_STALE_SECONDS = 120
    TASK_STALE_ERROR = 'worker interrupted or state expired'

    STEP_LABELS = {
        'request.accepted': '接收请求',
        'rag.retrieve': '知识检索',
        'rag.query': '答案生成',
        'response.finalized': '整理结果',
    }
    STEP_PROGRESS = {
        ('request.accepted', 'started'): 10,
        ('request.accepted', 'success'): 25,
        ('request.accepted', 'failed'): 25,
        ('rag.retrieve', 'started'): 35,
        ('rag.retrieve', 'success'): 50,
        ('rag.retrieve', 'failed'): 50,
        ('rag.query', 'started'): 60,
        ('rag.query', 'success'): 75,
        ('rag.query', 'failed'): 75,
        ('response.finalized', 'started'): 90,
        ('response.finalized', 'success'): 100,
        ('response.finalized', 'failed'): 100,
    }

    _session_store: dict[str, OrchestratorSessionViewModel] = {}
    _task_store: dict[str, OrchestratorTaskModel] = {}
    _trace_store: dict[str, list[TraceEventModel]] = {}
    _lock = asyncio.Lock()

    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        runtime_gateway: RagGatewayInterface | None = None,
    ):
        self.redis_client = redis_client
        # 支持依赖注入，便于测试和替换实现
        self.runtime_gateway = runtime_gateway or RagRuntimeGateway()

    async def chat(
        self,
        query_db: AsyncSession,
        current_user_id: int,
        meta: RequestMeta,
        payload: OrchestratorChatRequestModel,
    ) -> OrchestratorChatResponseModel:
        return await self._execute_chat(query_db, current_user_id, meta, payload)

    async def stream_chat(
        self,
        query_db: AsyncSession,
        current_user_id: int,
        meta: RequestMeta,
        payload: OrchestratorChatRequestModel,
    ) -> AsyncGenerator[str, None]:
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def on_step(event: TraceEventModel) -> None:
            await queue.put(self._sse_line({'event': 'step', 'data': event.model_dump(by_alias=True, mode='json')}))

        async def runner() -> None:
            try:
                result = await self._execute_chat(
                    query_db,
                    current_user_id,
                    meta,
                    payload,
                    step_callback=on_step,
                )
                await queue.put(
                    self._sse_line(
                        {
                            'event': 'answer',
                            'data': {
                                'finalAnswer': result.final_answer,
                                'citations': [item.model_dump(by_alias=True, mode='json') for item in result.citations],
                            },
                        }
                    )
                )
                await queue.put(self._sse_line({'event': 'done', 'data': result.model_dump(by_alias=True, mode='json')}))
            except Exception as e:
                logger.exception('Orchestrator stream failed')
                await queue.put(
                    self._sse_line(
                        {
                            'event': 'error',
                            'data': {
                                'requestId': meta.request_id,
                                'traceId': meta.trace_id,
                                'message': str(e),
                            },
                        }
                    )
                )
            finally:
                await queue.put(None)

        runner_task = asyncio.create_task(runner())
        try:
            while True:
                line = await queue.get()
                if line is None:
                    break
                yield line
        finally:
            if not runner_task.done():
                runner_task.cancel()
            with suppress(asyncio.CancelledError):
                await runner_task

    async def create_task(
        self,
        current_user_id: int,
        meta: RequestMeta,
        payload: OrchestratorTaskCreateModel,
    ) -> OrchestratorTaskModel:
        now = datetime.now()
        task = OrchestratorTaskModel(
            taskId=uuid4().hex,
            ownerUserId=meta.user_id,
            ownerTenantId=meta.tenant_id,
            status='pending',
            taskType=payload.task_type,
            sessionId=payload.session_id,
            requestId=meta.request_id,
            traceId=meta.trace_id,
            currentStep='等待执行',
            progressPercent=0,
            traceEvents=[],
            result=None,
            error=None,
            createTime=now,
            updateTime=now,
        )
        await self._save_task(task)
        asyncio.create_task(self._run_task(task.task_id, current_user_id, meta, payload))
        return task

    async def get_task(
        self,
        task_id: str,
        requester_user_id: int | str,
        requester_tenant_id: str,
        is_admin: bool = False,
    ) -> OrchestratorTaskModel | None:
        task = await self._load_task(task_id)
        if not task:
            return None
        task = await self._ensure_task_access(task, str(requester_user_id), requester_tenant_id, is_admin)

        if task.status == 'running' and task.update_time <= datetime.now() - timedelta(seconds=self.TASK_STALE_SECONDS):
            await self._update_task(
                task_id,
                status='failed',
                error=self.TASK_STALE_ERROR,
                current_step='执行失败',
                progress_percent=max(task.progress_percent, 75),
            )
            return await self._load_task(task_id)
        return task

    async def get_session(
        self,
        session_id: str,
        requester_user_id: int | str,
        requester_tenant_id: str,
        is_admin: bool = False,
    ) -> OrchestratorSessionViewModel:
        session = await self._load_session(session_id)
        if session:
            return await self._ensure_session_access(session, str(requester_user_id), requester_tenant_id, is_admin)
        return OrchestratorSessionViewModel(
            sessionId=session_id,
            ownerUserId=str(requester_user_id),
            ownerTenantId=requester_tenant_id,
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
            await self._update_task(
                task_id,
                status='running',
                current_step='开始执行',
                progress_percent=10,
                request_id=meta.request_id,
                trace_id=meta.trace_id,
                error=None,
            )
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
                result = await self._execute_chat(db, current_user_id, meta, chat_payload, task_id=task_id)
            await self._update_task(
                task_id,
                status='success',
                result=result,
                error=None,
                current_step='已完成',
                progress_percent=100,
                request_id=meta.request_id,
                trace_id=meta.trace_id,
                trace_events=result.trace_events,
            )
        except Exception as e:
            logger.exception('Orchestrator task failed')
            await self._update_task(
                task_id,
                status='failed',
                error=str(e),
                current_step='执行失败',
                progress_percent=100,
                request_id=meta.request_id,
                trace_id=meta.trace_id,
            )

    async def _execute_chat(
        self,
        query_db: AsyncSession,
        current_user_id: int,
        meta: RequestMeta,
        payload: OrchestratorChatRequestModel,
        *,
        task_id: str | None = None,
        step_callback: TraceCallback | None = None,
    ) -> OrchestratorChatResponseModel:
        start_time = datetime.now()
        trace_events: list[TraceEventModel] = []
        trace_store_key = self._build_trace_key(meta.request_id, task_id)

        await self._append_session_message(payload.session_id, 'user', payload.message, meta.user_id, meta.tenant_id)

        accepted_at = datetime.now()
        await self._emit_trace_event(
            trace_events=trace_events,
            trace_store_key=trace_store_key,
            meta=meta,
            session_id=payload.session_id,
            task_id=task_id,
            step_key='request.accepted',
            status='started',
            start_time=accepted_at,
            summary='request accepted',
            event_meta={
                'stream': payload.stream,
                'topK': payload.top_k,
                'retrievalMode': payload.retrieval_mode,
            },
            step_callback=step_callback,
        )
        await self._emit_trace_event(
            trace_events=trace_events,
            trace_store_key=trace_store_key,
            meta=meta,
            session_id=payload.session_id,
            task_id=task_id,
            step_key='request.accepted',
            status='success',
            start_time=accepted_at,
            end_time=datetime.now(),
            latency_ms=0,
            summary='request accepted',
            event_meta={
                'stream': payload.stream,
                'topK': payload.top_k,
                'retrievalMode': payload.retrieval_mode,
            },
            step_callback=step_callback,
        )

        tool_calls: list[ToolCallTraceModel] = []
        citations = []

        retrieve_start = datetime.now()
        await self._emit_trace_event(
            trace_events=trace_events,
            trace_store_key=trace_store_key,
            meta=meta,
            session_id=payload.session_id,
            task_id=task_id,
            step_key='rag.retrieve',
            status='started',
            start_time=retrieve_start,
            summary='retrieval started',
            event_meta={'includeSource': payload.include_source},
            step_callback=step_callback,
        )
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
            retrieve_summary = f'returned {len(retrieve_result.chunks)} chunks'
            tool_calls.append(
                ToolCallTraceModel(
                    tool='rag.retrieve',
                    status='success',
                    latencyMs=retrieve_latency,
                    summary=retrieve_summary,
                )
            )
            await self._emit_trace_event(
                trace_events=trace_events,
                trace_store_key=trace_store_key,
                meta=meta,
                session_id=payload.session_id,
                task_id=task_id,
                step_key='rag.retrieve',
                status='success',
                start_time=retrieve_start,
                end_time=datetime.now(),
                latency_ms=retrieve_latency,
                summary=retrieve_summary,
                event_meta={
                    'chunkCount': len(retrieve_result.chunks),
                    'responseTime': retrieve_result.response_time,
                },
                step_callback=step_callback,
            )
        except asyncio.TimeoutError:
            retrieve_latency = int((datetime.now() - retrieve_start).total_seconds() * 1000)
            retrieve_summary = f'timed out after {self.RAG_RETRIEVE_TIMEOUT_SECONDS}s'
            tool_calls.append(
                ToolCallTraceModel(
                    tool='rag.retrieve',
                    status='failed',
                    latencyMs=retrieve_latency,
                    summary=retrieve_summary,
                )
            )
            await self._emit_trace_event(
                trace_events=trace_events,
                trace_store_key=trace_store_key,
                meta=meta,
                session_id=payload.session_id,
                task_id=task_id,
                step_key='rag.retrieve',
                status='failed',
                start_time=retrieve_start,
                end_time=datetime.now(),
                latency_ms=retrieve_latency,
                summary=retrieve_summary,
                event_meta={'timeoutSeconds': self.RAG_RETRIEVE_TIMEOUT_SECONDS},
                step_callback=step_callback,
            )
        except Exception as e:
            retrieve_latency = int((datetime.now() - retrieve_start).total_seconds() * 1000)
            retrieve_summary = f'failed: {e}'
            tool_calls.append(
                ToolCallTraceModel(
                    tool='rag.retrieve',
                    status='failed',
                    latencyMs=retrieve_latency,
                    summary=retrieve_summary,
                )
            )
            await self._emit_trace_event(
                trace_events=trace_events,
                trace_store_key=trace_store_key,
                meta=meta,
                session_id=payload.session_id,
                task_id=task_id,
                step_key='rag.retrieve',
                status='failed',
                start_time=retrieve_start,
                end_time=datetime.now(),
                latency_ms=retrieve_latency,
                summary=retrieve_summary,
                event_meta={'errorType': type(e).__name__},
                step_callback=step_callback,
            )

        query_start = datetime.now()
        await self._emit_trace_event(
            trace_events=trace_events,
            trace_store_key=trace_store_key,
            meta=meta,
            session_id=payload.session_id,
            task_id=task_id,
            step_key='rag.query',
            status='started',
            start_time=query_start,
            summary='answer generation started',
            event_meta={},
            step_callback=step_callback,
        )
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
            query_summary = 'answer generated'
            tool_calls.append(
                ToolCallTraceModel(
                    tool='rag.query',
                    status='success',
                    latencyMs=query_latency,
                    summary=query_summary,
                )
            )
            await self._emit_trace_event(
                trace_events=trace_events,
                trace_store_key=trace_store_key,
                meta=meta,
                session_id=payload.session_id,
                task_id=task_id,
                step_key='rag.query',
                status='success',
                start_time=query_start,
                end_time=datetime.now(),
                latency_ms=query_latency,
                summary=query_summary,
                event_meta={
                    'responseTime': query_result.response_time,
                    'citationCount': len(query_result.source_chunks or []),
                },
                step_callback=step_callback,
            )
        except asyncio.TimeoutError:
            query_latency = int((datetime.now() - query_start).total_seconds() * 1000)
            answer_text = self._build_degraded_answer(citations)
            query_summary = f'timed out after {self.RAG_QUERY_TIMEOUT_SECONDS}s'
            tool_calls.append(
                ToolCallTraceModel(
                    tool='rag.query',
                    status='failed',
                    latencyMs=query_latency,
                    summary=query_summary,
                )
            )
            await self._emit_trace_event(
                trace_events=trace_events,
                trace_store_key=trace_store_key,
                meta=meta,
                session_id=payload.session_id,
                task_id=task_id,
                step_key='rag.query',
                status='failed',
                start_time=query_start,
                end_time=datetime.now(),
                latency_ms=query_latency,
                summary=query_summary,
                event_meta={
                    'timeoutSeconds': self.RAG_QUERY_TIMEOUT_SECONDS,
                    'degraded': True,
                },
                step_callback=step_callback,
            )
        except Exception as e:
            query_latency = int((datetime.now() - query_start).total_seconds() * 1000)
            answer_text = self._build_degraded_answer(citations)
            query_summary = f'failed: {e}'
            tool_calls.append(
                ToolCallTraceModel(
                    tool='rag.query',
                    status='failed',
                    latencyMs=query_latency,
                    summary=query_summary,
                )
            )
            await self._emit_trace_event(
                trace_events=trace_events,
                trace_store_key=trace_store_key,
                meta=meta,
                session_id=payload.session_id,
                task_id=task_id,
                step_key='rag.query',
                status='failed',
                start_time=query_start,
                end_time=datetime.now(),
                latency_ms=query_latency,
                summary=query_summary,
                event_meta={
                    'errorType': type(e).__name__,
                    'degraded': True,
                },
                step_callback=step_callback,
            )

        await self._append_session_message(payload.session_id, 'assistant', answer_text, meta.user_id, meta.tenant_id)

        finalized_start = datetime.now()
        await self._emit_trace_event(
            trace_events=trace_events,
            trace_store_key=trace_store_key,
            meta=meta,
            session_id=payload.session_id,
            task_id=task_id,
            step_key='response.finalized',
            status='started',
            start_time=finalized_start,
            summary='assembling response',
            event_meta={'citationCount': len(citations or [])},
            step_callback=step_callback,
        )

        latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        await self._emit_trace_event(
            trace_events=trace_events,
            trace_store_key=trace_store_key,
            meta=meta,
            session_id=payload.session_id,
            task_id=task_id,
            step_key='response.finalized',
            status='success',
            start_time=finalized_start,
            end_time=datetime.now(),
            latency_ms=0,
            summary='response ready',
            event_meta={'totalLatencyMs': latency_ms},
            step_callback=step_callback,
        )

        result = OrchestratorChatResponseModel(
            sessionId=payload.session_id,
            requestId=meta.request_id,
            traceId=meta.trace_id,
            finalAnswer=answer_text,
            citations=citations or [],
            toolCalls=tool_calls,
            traceEvents=trace_events,
            latencyMs=latency_ms,
        )

        if task_id:
            await self._update_task(
                task_id,
                status='running',
                result=result,
                current_step='整理结果',
                progress_percent=100,
                request_id=meta.request_id,
                trace_id=meta.trace_id,
                trace_events=trace_events,
                error=None,
            )
        return result

    async def _append_session_message(
        self,
        session_id: str,
        role: str,
        content: str,
        owner_user_id: str,
        owner_tenant_id: str,
    ) -> None:
        async with self._lock:
            session = self._session_store.get(session_id)
            now = datetime.now()
            if not session:
                session = OrchestratorSessionViewModel(
                    sessionId=session_id,
                    ownerUserId=owner_user_id,
                    ownerTenantId=owner_tenant_id,
                    messages=[],
                    updateTime=now,
                )
            elif not self._is_owner_match(session.owner_user_id, session.owner_tenant_id, owner_user_id, owner_tenant_id):
                raise PermissionException(message='Session access denied')
            session.messages.append(
                OrchestratorSessionMessageModel(
                    role=role,
                    content=content,
                    time=now,
                )
            )
            session.update_time = now
            self._session_store[session_id] = session

        await self._save_json(
            self._session_key(session_id),
            session.model_dump(by_alias=True, mode='json'),
        )

    async def _emit_trace_event(
        self,
        *,
        trace_events: list[TraceEventModel],
        trace_store_key: str,
        meta: RequestMeta,
        session_id: str,
        task_id: str | None,
        step_key: str,
        status: str,
        start_time: datetime,
        end_time: datetime | None = None,
        latency_ms: int | None = None,
        summary: str | None = None,
        event_meta: dict[str, Any] | None = None,
        step_callback: TraceCallback | None = None,
    ) -> None:
        event = TraceEventModel(
            eventId=uuid4().hex,
            requestId=meta.request_id,
            traceId=meta.trace_id,
            sessionId=session_id,
            taskId=task_id,
            stepKey=step_key,
            stepLabel=self.STEP_LABELS.get(step_key, step_key),
            status=status,
            startTime=start_time,
            endTime=end_time,
            latencyMs=latency_ms,
            summary=summary,
            meta=event_meta or {},
        )
        trace_events.append(event)
        await self._save_trace_events(trace_store_key, trace_events)

        if task_id:
            await self._update_task(
                task_id,
                trace_events=trace_events,
                current_step=self.STEP_LABELS.get(step_key, step_key),
                progress_percent=self.STEP_PROGRESS.get((step_key, status), 0),
                request_id=meta.request_id,
                trace_id=meta.trace_id,
            )

        if step_callback is not None:
            await step_callback(event)

    async def _update_task(
        self,
        task_id: str,
        *,
        status: str | None = None,
        result: OrchestratorChatResponseModel | None = None,
        error: str | None = None,
        current_step: str | None = None,
        progress_percent: int | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
        trace_events: list[TraceEventModel] | None = None,
    ) -> None:
        task = await self._load_task(task_id)
        if not task:
            return

        data = task.model_dump()
        if status is not None:
            data['status'] = status
        if result is not None:
            data['result'] = result.model_dump(by_alias=True)
        if error is not None:
            data['error'] = error
        if current_step is not None:
            data['current_step'] = current_step
        if progress_percent is not None:
            data['progress_percent'] = max(0, min(progress_percent, 100))
        if request_id is not None:
            data['request_id'] = request_id
        if trace_id is not None:
            data['trace_id'] = trace_id
        if trace_events is not None:
            data['trace_events'] = [item.model_dump(by_alias=True) for item in trace_events]
        data['update_time'] = datetime.now()

        updated = OrchestratorTaskModel(**data)
        await self._save_task(updated)

        if trace_events is not None:
            await self._save_trace_events(self._build_trace_key(updated.request_id or task_id, task_id), trace_events)

    async def _save_task(self, task: OrchestratorTaskModel) -> None:
        async with self._lock:
            self._task_store[task.task_id] = task
        await self._save_json(self._task_key(task.task_id), task.model_dump(by_alias=True, mode='json'))

    async def _load_task(self, task_id: str) -> OrchestratorTaskModel | None:
        task_data = await self._load_json(self._task_key(task_id))
        if task_data is not None:
            task = OrchestratorTaskModel(**task_data)
            async with self._lock:
                self._task_store[task_id] = task
            return task

        async with self._lock:
            return self._task_store.get(task_id)

    async def _load_session(self, session_id: str) -> OrchestratorSessionViewModel | None:
        session_data = await self._load_json(self._session_key(session_id))
        if session_data is not None:
            session = OrchestratorSessionViewModel(**session_data)
            async with self._lock:
                self._session_store[session_id] = session
            return session

        async with self._lock:
            return self._session_store.get(session_id)

    async def _ensure_task_access(
        self,
        task: OrchestratorTaskModel,
        requester_user_id: str,
        requester_tenant_id: str,
        is_admin: bool,
    ) -> OrchestratorTaskModel:
        if is_admin:
            return task
        if not task.owner_user_id:
            task.owner_user_id = requester_user_id
            task.owner_tenant_id = requester_tenant_id
            await self._save_task(task)
            return task
        if not self._is_owner_match(task.owner_user_id, task.owner_tenant_id, requester_user_id, requester_tenant_id):
            raise PermissionException(message='Task access denied')
        return task

    async def _ensure_session_access(
        self,
        session: OrchestratorSessionViewModel,
        requester_user_id: str,
        requester_tenant_id: str,
        is_admin: bool,
    ) -> OrchestratorSessionViewModel:
        if is_admin:
            return session
        if not session.owner_user_id:
            session.owner_user_id = requester_user_id
            session.owner_tenant_id = requester_tenant_id
            await self._save_json(
                self._session_key(session.session_id),
                session.model_dump(by_alias=True, mode='json'),
            )
            return session
        if not self._is_owner_match(session.owner_user_id, session.owner_tenant_id, requester_user_id, requester_tenant_id):
            raise PermissionException(message='Session access denied')
        return session

    async def _save_trace_events(self, trace_store_key: str, trace_events: list[TraceEventModel]) -> None:
        async with self._lock:
            self._trace_store[trace_store_key] = list(trace_events)
        await self._save_json(
            self._trace_key(trace_store_key),
            [item.model_dump(by_alias=True, mode='json') for item in trace_events],
        )

    async def _save_json(self, key: str, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
        if self.redis_client is None:
            return
        try:
            await self.redis_client.set(key, json.dumps(payload, ensure_ascii=False), ex=self.STORE_TTL_SECONDS)
        except Exception as e:
            logger.warning(f'Failed to write orchestrator state to redis: {e}')

    async def _load_json(self, key: str) -> dict[str, Any] | list[dict[str, Any]] | None:
        if self.redis_client is None:
            return None
        try:
            raw = await self.redis_client.get(key)
        except Exception as e:
            logger.warning(f'Failed to read orchestrator state from redis: {e}')
            return None
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f'Invalid orchestrator state payload: {key}')
            return None

    @classmethod
    def _session_key(cls, session_id: str) -> str:
        return f'orchestrator:session:{session_id}'

    @classmethod
    def _task_key(cls, task_id: str) -> str:
        return f'orchestrator:task:{task_id}'

    @classmethod
    def _trace_key(cls, trace_store_key: str) -> str:
        return f'orchestrator:trace:{trace_store_key}'

    @staticmethod
    def _build_trace_key(request_id: str, task_id: str | None = None) -> str:
        return task_id or request_id

    @staticmethod
    def _is_owner_match(
        owner_user_id: str | None,
        owner_tenant_id: str | None,
        requester_user_id: str,
        requester_tenant_id: str,
    ) -> bool:
        if not owner_user_id:
            return False
        if owner_user_id != requester_user_id:
            return False
        if owner_tenant_id and owner_tenant_id != requester_tenant_id:
            return False
        return True

    @staticmethod
    def _sse_line(payload: dict[str, Any]) -> str:
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
