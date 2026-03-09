from typing import Annotated

from fastapi import Body, Header, Path, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.log_annotation import Log
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import CurrentUserDependency, PreAuthDependency
from common.enums import BusinessType
from common.request_meta import build_request_meta
from common.router import APIRouterPro
from common.vo import DataResponseModel
from exceptions.exception import ServiceException
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_orchestrator.entity.vo.orchestrator_vo import (
    OrchestratorChatRequestModel,
    OrchestratorChatResponseModel,
    OrchestratorSessionViewModel,
    OrchestratorTaskCreateModel,
    OrchestratorTaskModel,
)
from module_orchestrator.service.orchestrator_service import OrchestratorService
from utils.idempotency_util import IdempotencyUtil
from utils.log_util import logger
from utils.response_util import ResponseUtil

orchestrator_controller = APIRouterPro(
    prefix='/orchestrator', order_num=30, tags=['Agent-Orchestrator'], dependencies=[PreAuthDependency()]
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
    service = OrchestratorService()
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
        scope='orchestrator:tasks',
        key=idempotency_key,
        ttl_seconds=3600,
    )
    service = OrchestratorService()
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
) -> Response:
    service = OrchestratorService()
    task = await service.get_task(task_id)
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
) -> Response:
    service = OrchestratorService()
    session = await service.get_session(session_id)
    return ResponseUtil.success(data=session)
