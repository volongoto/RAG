from __future__ import annotations

import os
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from common.request_meta import RequestMeta
from exceptions.exception import ServiceException
from module_rag.entity.vo.rag_vo import QueryRequestModel, QueryResponseModel
from module_rag.entity.vo.runtime_vo import RetrieveRequestModel, RetrieveResponseModel
from module_rag.service.query_service import QueryService


class RagRuntimeGateway:
    """
    Runtime access gateway.

    - If `RAG_RUNTIME_BASE_URL` is set, call runtime via HTTP/JSON.
    - Otherwise, fallback to in-process service calls.
    """

    def __init__(self) -> None:
        self.runtime_base_url = (os.getenv('RAG_RUNTIME_BASE_URL') or '').strip().rstrip('/')
        self.query_service = QueryService()

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
            'Authorization': meta.authorization,
            'X-Tenant-Id': meta.tenant_id,
            'X-User-Id': meta.user_id,
            'X-Request-Id': meta.request_id,
            'X-Trace-Id': meta.trace_id,
        }
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(url, json=payload, headers=headers)
        except Exception as e:
            raise ServiceException(message=f'Runtime call failed: {e}')

        if response.status_code >= 500:
            raise ServiceException(message=f'Runtime service unavailable: HTTP {response.status_code}')
        if response.status_code >= 400:
            raise ServiceException(message=f'Runtime request failed: HTTP {response.status_code}')

        body = response.json()
        success = body.get('success', True)
        if not success:
            raise ServiceException(message=body.get('msg') or 'Runtime returned failure')

        data = body.get('data')
        if data is None:
            raise ServiceException(message='Runtime response missing data field')
        return data
