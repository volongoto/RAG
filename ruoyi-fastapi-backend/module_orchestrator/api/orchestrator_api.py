from typing import Annotated
from uuid import uuid4

from fastapi import Body, Header, Path, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.log_annotation import Log
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.internal_service_auth import InternalServiceAuthDependency
from common.aspect.pre_auth import CurrentUserDependency, PreAuthDependency
from common.enums import BusinessType
from common.request_meta import RequestMeta, build_request_meta
from common.router import APIRouterPro
from common.vo import DataResponseModel
from exceptions.exception import ServiceException
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_orchestrator.entity.vo.orchestrator_vo import (
    InternalOrchestratorChatRequestModel,
    OrchestratorChatRequestModel,
    OrchestratorChatResponseModel,
    OrchestratorSessionViewModel,
    OrchestratorTaskCreateModel,
    OrchestratorTaskModel,
)
from module_orchestrator.service.internal_bridge_rag_gateway import InternalBridgeRagGateway
from module_orchestrator.service.orchestrator_service import OrchestratorService
from module_rag.entity.vo.runtime_vo import ResolvedPrincipalModel
from module_rag.service.internal_bridge_service import InternalRagBridgeService
from utils.idempotency_util import IdempotencyUtil
from utils.log_util import logger
from utils.response_util import ResponseUtil

orchestrator_controller = APIRouterPro(
    prefix='/orchestrator', order_num=30, tags=['Agent-Orchestrator'], dependencies=[PreAuthDependency()]
)
internal_orchestrator_controller = APIRouterPro(
    prefix='/internal/orchestrator',
    order_num=31,
    tags=['Agent-Orchestrator-Internal'],
    dependencies=[InternalServiceAuthDependency()],
    include_in_schema=False,
)


def _build_internal_request_meta(
    request: Request,
    payload: InternalOrchestratorChatRequestModel,
    resolved_principal: ResolvedPrincipalModel,
) -> RequestMeta:
    auth_context = getattr(request.state, 'internal_service_auth', {}) or {}
    request_id = str(auth_context.get('request_id') or '').strip() or uuid4().hex
    tenant_id = request.headers.get('X-Tenant-Id', '').strip() or 'default'
    if resolved_principal.mapped_user_id is not None:
        user_id = str(resolved_principal.mapped_user_id)
    else:
        external_identity = (
            (payload.principal.external_user_id or '').strip()
            or (payload.principal.external_user_name or '').strip()
            or (payload.principal.external_dept_id or '').strip()
            or 'anonymous'
        )
        user_id = f'bridge:{payload.principal.source_system}:{external_identity}'
    return RequestMeta(
        authorization='',
        tenant_id=tenant_id,
        user_id=user_id,
        request_id=request_id,
        trace_id=request_id,
    )


@orchestrator_controller.post(
    '/chat',
    summary='Agent chat',
    description='Single/multi-turn chat entry, supports SSE streaming',
    response_model=DataResponseModel[OrchestratorChatResponseModel],
    dependencies=[UserInterfaceAuthDependency('rag:query:execute')],
)
@Log(title='AgentChat', business_type=BusinessType.OTHER)
async def orchestrator_chat(
    request: Request,
    payload: Annotated[OrchestratorChatRequestModel, Body(description='Chat payload')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    service = OrchestratorService(getattr(request.app.state, 'redis', None))
    meta = build_request_meta(request, current_user)

    if payload.stream:
        stream = service.stream_chat(query_db, current_user.user.user_id, meta, payload)
        return ResponseUtil.streaming(
            data=stream,
            media_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
            },
        )

    result = await service.chat(query_db, current_user.user.user_id, meta, payload)
    logger.info('Orchestrator chat finished')
    return ResponseUtil.success(data=result)


@internal_orchestrator_controller.post(
    '/chat',
    summary='Execute bridged orchestrator chat',
    description='Bridge external principal into orchestrator chat, supports SSE streaming',
    response_model=DataResponseModel[OrchestratorChatResponseModel],
)
async def internal_orchestrator_chat(
    request: Request,
    payload: Annotated[InternalOrchestratorChatRequestModel, Body(description='Bridged chat payload')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    resolved_principal = await InternalRagBridgeService.resolve_principal(query_db, payload.principal)
    meta = _build_internal_request_meta(request, payload, resolved_principal)
    service = OrchestratorService(
        getattr(request.app.state, 'redis', None),
        runtime_gateway=InternalBridgeRagGateway(payload.principal),
    )
    mapped_user_id = resolved_principal.mapped_user_id or 0

    if payload.chat.stream:
        stream = service.stream_chat(query_db, mapped_user_id, meta, payload.chat)
        return ResponseUtil.streaming(
            data=stream,
            media_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
            },
        )

    result = await service.chat(query_db, mapped_user_id, meta, payload.chat)
    logger.info(
        'Internal orchestrator chat finished '
        f'source={payload.principal.source_system} mapped_user={resolved_principal.mapped_user_id}'
    )
    return ResponseUtil.success(data=result)


@orchestrator_controller.post(
    '/tasks',
    summary='Create orchestrator task',
    description='Create long-running agent task',
    response_model=DataResponseModel[OrchestratorTaskModel],
    dependencies=[UserInterfaceAuthDependency('rag:query:execute')],
)
@Log(title='AgentTask', business_type=BusinessType.INSERT)
async def create_orchestrator_task(
    request: Request,
    payload: Annotated[OrchestratorTaskCreateModel, Body(description='Task payload')],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    idempotency_key: Annotated[str | None, Header(alias='Idempotency-Key')] = None,
) -> Response:
    await IdempotencyUtil.require_and_lock_key(
        request,
        scope=f'orchestrator:tasks:{current_user.user.user_id}',
        key=idempotency_key,
        ttl_seconds=3600,
    )
    service = OrchestratorService(getattr(request.app.state, 'redis', None))
    meta = build_request_meta(request, current_user)
    task = await service.create_task(current_user.user.user_id, meta, payload)
    logger.info(f'Orchestrator task created: {task.task_id}')
    return ResponseUtil.success(data=task)


@orchestrator_controller.get(
    '/tasks/{task_id}',
    summary='Get orchestrator task',
    description='Get long-running task status/result',
    response_model=DataResponseModel[OrchestratorTaskModel],
    dependencies=[UserInterfaceAuthDependency('rag:query:execute')],
)
async def get_orchestrator_task(
    request: Request,
    task_id: Annotated[str, Path(description='Task ID')],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    service = OrchestratorService(getattr(request.app.state, 'redis', None))
    meta = build_request_meta(request, current_user)
    task = await service.get_task(task_id, current_user.user.user_id, meta.tenant_id, current_user.user.admin)
    if not task:
        raise ServiceException(message='Task not found')
    return ResponseUtil.success(data=task)


@orchestrator_controller.get(
    '/sessions/{session_id}',
    summary='Get orchestrator session',
    description='Get session history view',
    response_model=DataResponseModel[OrchestratorSessionViewModel],
    dependencies=[UserInterfaceAuthDependency('rag:query:execute')],
)
async def get_orchestrator_session(
    request: Request,
    session_id: Annotated[str, Path(description='Session ID')],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    service = OrchestratorService(getattr(request.app.state, 'redis', None))
    meta = build_request_meta(request, current_user)
    session = await service.get_session(
        session_id,
        current_user.user.user_id,
        meta.tenant_id,
        current_user.user.admin,
    )
    return ResponseUtil.success(data=session)
