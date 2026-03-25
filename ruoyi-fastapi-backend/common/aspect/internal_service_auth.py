import hmac
import json
import time
from typing import Any

from fastapi import Depends, Request, params

from config.env import AppConfig, InternalRagBridgeConfig
from exceptions.exception import AuthException
from utils.service_signature import build_service_signature


class InternalServiceAuth:
    async def __call__(self, request: Request) -> dict[str, Any]:
        shared_secret = (InternalRagBridgeConfig.rag_internal_shared_secret or '').strip()
        if not shared_secret:
            raise AuthException(message='内部服务签名鉴权未配置')

        source_system = (request.headers.get('X-Service-Source-System') or '').strip()
        timestamp = (request.headers.get('X-Service-Timestamp') or '').strip()
        signature = (request.headers.get('X-Service-Signature') or '').strip()
        canonical_path = (request.headers.get('X-Service-Path') or '').strip()
        request_id = (request.headers.get('X-Service-Request-Id') or '').strip()

        if not source_system or not timestamp or not signature or not canonical_path:
            raise AuthException(message='内部服务签名头缺失')

        allowed_sources = {
            item.strip()
            for item in str(InternalRagBridgeConfig.rag_internal_allowed_source_systems or '').split(',')
            if item.strip()
        }
        if allowed_sources and source_system not in allowed_sources:
            raise AuthException(message='内部服务来源不在允许列表内')

        try:
            timestamp_value = int(timestamp)
        except ValueError as exc:
            raise AuthException(message='内部服务签名时间戳非法') from exc

        if abs(int(time.time()) - timestamp_value) > int(InternalRagBridgeConfig.rag_internal_signature_ttl_seconds):
            raise AuthException(message='内部服务签名已过期')

        normalized_path = request.url.path
        if AppConfig.app_root_path and normalized_path.startswith(AppConfig.app_root_path):
            normalized_path = normalized_path[len(AppConfig.app_root_path) :]
        if canonical_path != normalized_path:
            raise AuthException(message='内部服务签名路径不匹配')

        body_bytes = await request.body()
        try:
            payload = json.loads(body_bytes.decode('utf-8')) if body_bytes else {}
        except json.JSONDecodeError as exc:
            raise AuthException(message='内部服务请求体不是合法 JSON') from exc

        expected_signature = build_service_signature(
            method=request.method,
            path=canonical_path,
            source_system=source_system,
            timestamp=timestamp,
            payload=payload,
            secret=shared_secret,
        )
        if not hmac.compare_digest(signature, expected_signature):
            raise AuthException(message='内部服务签名校验失败')

        auth_context = {
            'source_system': source_system,
            'request_id': request_id,
            'timestamp': timestamp_value,
        }
        request.state.internal_service_auth = auth_context
        return auth_context


def InternalServiceAuthDependency() -> params.Depends:  # noqa: N802
    return Depends(InternalServiceAuth())
