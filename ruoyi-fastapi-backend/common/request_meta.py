from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from fastapi import Request

from middlewares.trace_middleware import TraceCtx
from module_admin.entity.vo.user_vo import CurrentUserModel


@dataclass(slots=True)
class RequestMeta:
    """
    Normalized request metadata propagated across business/orchestrator/runtime layers.
    """

    authorization: str
    tenant_id: str
    user_id: str
    request_id: str
    trace_id: str

    def as_dict(self) -> dict[str, str]:
        return {
            'authorization': self.authorization,
            'tenantId': self.tenant_id,
            'userId': self.user_id,
            'requestId': self.request_id,
            'traceId': self.trace_id,
        }


def build_request_meta(request: Request, current_user: CurrentUserModel | None = None) -> RequestMeta:
    """
    Extract normalized metadata from incoming headers with safe defaults.
    """
    authorization = request.headers.get('Authorization', '')
    tenant_id = request.headers.get('X-Tenant-Id', '').strip() or 'default'

    header_user_id = request.headers.get('X-User-Id', '').strip()
    user_id = header_user_id
    if not user_id and current_user is not None:
        user_id = str(current_user.user.user_id)
    user_id = user_id or 'anonymous'

    request_id = request.headers.get('X-Request-Id', '').strip()
    if not request_id:
        request_id = TraceCtx.get_id().strip() or uuid4().hex

    trace_id = request.headers.get('X-Trace-Id', '').strip() or request_id

    return RequestMeta(
        authorization=authorization,
        tenant_id=tenant_id,
        user_id=user_id,
        request_id=request_id,
        trace_id=trace_id,
    )
