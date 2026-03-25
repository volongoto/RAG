import hashlib
import hmac
import json
from typing import Any


def canonical_json(payload: Any) -> str:
    return json.dumps(payload or {}, ensure_ascii=False, separators=(',', ':'), sort_keys=True)


def build_service_signature(*, method: str, path: str, source_system: str, timestamp: str, payload: Any, secret: str) -> str:
    canonical_payload = canonical_json(payload)
    canonical_message = '\n'.join(
        [
            (method or '').upper(),
            path or '',
            source_system or '',
            timestamp or '',
            canonical_payload,
        ]
    )
    return hmac.new(secret.encode('utf-8'), canonical_message.encode('utf-8'), hashlib.sha256).hexdigest()
