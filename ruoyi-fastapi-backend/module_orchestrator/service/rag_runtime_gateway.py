from __future__ import annotations

import json
import os
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from common.request_meta import RequestMeta
from config.env import normalize_env_string
from exceptions.exception import ServiceException
from module_orchestrator.service.rag_gateway_interface import RagGatewayInterface
from module_rag.entity.vo.rag_vo import QueryRequestModel, QueryResponseModel
from module_rag.entity.vo.runtime_vo import RetrieveRequestModel, RetrieveResponseModel
from module_rag.service.query_service import QueryService


class RagRuntimeGateway(RagGatewayInterface):
    """
    Runtime access gateway.
    Implements RagGatewayInterface for dependency injection.

    - If `RAG_RUNTIME_BASE_URL` is set, call runtime via HTTP/JSON.
    - Otherwise, fallback to in-process service calls.
    """

    def __init__(self, query_service: QueryService | None = None) -> None:
        runtime_base_url = normalize_env_string(os.getenv('RAG_RUNTIME_BASE_URL') or '')
        self.runtime_base_url = str(runtime_base_url or '').rstrip('/')
        self.query_service = query_service or QueryService()

    async def retrieve(
        self,
        *,
        query_db: AsyncSession,
        request_model: RetrieveRequestModel,
        meta: RequestMeta,
    ) -> RetrieveResponseModel:
        if self.runtime_base_url:
            data = await self._post_json(
                path='/rag/retrieve',
                payload=request_model.model_dump(by_alias=True),
                meta=meta,
                timeout_seconds=10,
            )
            return RetrieveResponseModel(**data)
        return await self.query_service.retrieve_services(query_db, request_model)

    async def query(
        self,
        *,
        query_db: AsyncSession,
        request_model: QueryRequestModel,
        user_id: int,
        meta: RequestMeta,
    ) -> QueryResponseModel:
        if self.runtime_base_url:
            data = await self._post_json(
                path='/rag/query',
                payload=request_model.model_dump(by_alias=True),
                meta=meta,
                timeout_seconds=25,
            )
            return QueryResponseModel(**data)
        return await self.query_service.query_services(query_db, request_model, user_id)

    async def _post_json(
        self,
        *,
        path: str,
        payload: dict[str, Any],
        meta: RequestMeta,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        url = f'{self.runtime_base_url}{path}'
        headers = {
            key: value
            for key, value in {
                'Authorization': meta.authorization,
                'X-Tenant-Id': meta.tenant_id,
                'X-User-Id': meta.user_id,
                'X-Request-Id': meta.request_id,
                'X-Trace-Id': meta.trace_id,
            }.items()
            if value
        }

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise ServiceException(message=f'Runtime call timed out: {exc}') from exc
        except httpx.HTTPError as exc:
            raise ServiceException(message=f'Runtime call failed: {exc}') from exc
        except Exception as exc:
            raise ServiceException(message=f'Runtime call failed: {exc}') from exc

        response_preview = self._response_preview(response)
        if response.status_code >= 500:
            raise ServiceException(
                message=f'Runtime service unavailable: HTTP {response.status_code}, body={response_preview}'
            )
        if response.status_code >= 400:
            raise ServiceException(
                message=f'Runtime request failed: HTTP {response.status_code}, body={response_preview}'
            )

        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            raise ServiceException(
                message=f'Runtime returned non-JSON response: HTTP {response.status_code}, body={response_preview}'
            ) from exc

        if not isinstance(body, dict):
            raise ServiceException(message=f'Runtime returned unexpected JSON payload: {type(body).__name__}')

        success = body.get('success', True)
        if not success:
            raise ServiceException(message=body.get('msg') or 'Runtime returned failure')

        data = body.get('data')
        if data is None:
            raise ServiceException(message='Runtime response missing data field')
        if not isinstance(data, dict):
            raise ServiceException(message=f'Runtime response data must be an object, got {type(data).__name__}')
        return data

    @staticmethod
    def _response_preview(response: httpx.Response, max_length: int = 300) -> str:
        try:
            text = (response.text or '').strip()
        except Exception:
            text = ''
        if not text:
            return '<empty>'
        if len(text) <= max_length:
            return text
        return f'{text[: max_length - 3]}...'
