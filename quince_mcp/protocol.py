from __future__ import annotations

from typing import Any


def response(*, request_id: str, message_type: str, **data: Any) -> dict[str, Any]:
    return {
        "id": request_id,
        "type": message_type,
        **data,
    }
