import json

import httpx
import pytest

from common.request_meta import RequestMeta
from exceptions.exception import ServiceException
from module_orchestrator.service.rag_runtime_gateway import RagRuntimeGateway


class FakeAsyncClient:
    def __init__(self, *, timeout: float, response: httpx.Response | Exception, captured: dict):
        self.timeout = timeout
        self.response = response
        self.captured = captured

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, json: dict, headers: dict):
        self.captured['url'] = url
        self.captured['json'] = json
        self.captured['headers'] = headers
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def build_meta(**overrides) -> RequestMeta:
    payload = {
        'authorization': '',
        'tenant_id': 'default',
        'user_id': '1001',
        'request_id': 'req-1',
        'trace_id': 'trace-1',
    }
    payload.update(overrides)
    return RequestMeta(**payload)


def patch_async_client(monkeypatch: pytest.MonkeyPatch, response: httpx.Response | Exception, captured: dict):
    def factory(*, timeout: float):
        return FakeAsyncClient(timeout=timeout, response=response, captured=captured)

    monkeypatch.setattr(httpx, 'AsyncClient', factory)


def test_runtime_base_url_is_normalized(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('RAG_RUNTIME_BASE_URL', "'https://runtime.internal/api/'")

    gateway = RagRuntimeGateway()

    assert gateway.runtime_base_url == 'https://runtime.internal/api'


@pytest.mark.asyncio
async def test_post_json_filters_empty_headers_and_returns_data(monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}
    response = httpx.Response(
        status_code=200,
        content=json.dumps({'success': True, 'data': {'answerText': 'ok'}}).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    patch_async_client(monkeypatch, response, captured)

    monkeypatch.setenv('RAG_RUNTIME_BASE_URL', 'https://runtime.internal')
    gateway = RagRuntimeGateway()

    data = await gateway._post_json(
        path='/rag/query',
        payload={'queryText': 'hello'},
        meta=build_meta(authorization=''),
        timeout_seconds=5,
    )

    assert data == {'answerText': 'ok'}
    assert captured['url'] == 'https://runtime.internal/rag/query'
    assert 'Authorization' not in captured['headers']
    assert captured['headers']['X-User-Id'] == '1001'


@pytest.mark.asyncio
async def test_post_json_raises_clear_error_for_non_json_response(monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}
    response = httpx.Response(status_code=200, text='<html>bad gateway</html>')
    patch_async_client(monkeypatch, response, captured)

    monkeypatch.setenv('RAG_RUNTIME_BASE_URL', 'https://runtime.internal')
    gateway = RagRuntimeGateway()

    with pytest.raises(ServiceException) as exc_info:
        await gateway._post_json(
            path='/rag/query',
            payload={'queryText': 'hello'},
            meta=build_meta(),
            timeout_seconds=5,
        )

    assert 'Runtime returned non-JSON response' in exc_info.value.message
    assert '<html>bad gateway</html>' in exc_info.value.message


@pytest.mark.asyncio
async def test_post_json_includes_status_body_for_http_error(monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}
    response = httpx.Response(status_code=404, text='not found')
    patch_async_client(monkeypatch, response, captured)

    monkeypatch.setenv('RAG_RUNTIME_BASE_URL', 'https://runtime.internal')
    gateway = RagRuntimeGateway()

    with pytest.raises(ServiceException) as exc_info:
        await gateway._post_json(
            path='/rag/query',
            payload={'queryText': 'hello'},
            meta=build_meta(),
            timeout_seconds=5,
        )

    assert exc_info.value.message == 'Runtime request failed: HTTP 404, body=not found'
