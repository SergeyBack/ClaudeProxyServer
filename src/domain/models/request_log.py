from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class RequestLog:
    user_id: UUID
    account_id: UUID | None
    request_id: str
    model: str
    status_code: int
    duration_ms: int
    is_streaming: bool
    id: UUID | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    prompt_content: dict | None = None
    response_content: dict | None = None
    error_type: str | None = None
    created_at: datetime | None = None
