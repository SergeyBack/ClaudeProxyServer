"""
Mock Anthropic API server for local testing.

Simulates api.anthropic.com/v1/messages without real accounts.
Controlled via headers:
  X-Mock-Mode: normal      → 200 response (default)
  X-Mock-Mode: rate_limit  → 429 with retry-after
  X-Mock-Mode: banned      → 401
  X-Mock-Mode: slow        → 200 but delayed 2s
"""

import asyncio
import json
import os
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(title="Mock Anthropic API")

_REQUEST_COUNT = 0


@app.get("/health")
async def health():
    return {"status": "ok", "mock": True, "requests_served": _REQUEST_COUNT}


@app.post("/v1/messages")
async def messages(request: Request):
    global _REQUEST_COUNT
    _REQUEST_COUNT += 1

    body = await request.json()
    model = body.get("model", "claude-3-haiku-20240307")
    is_stream = body.get("stream", False)
    mode = request.headers.get("x-mock-mode", os.getenv("MOCK_MODE", "normal"))

    # Simulate various error modes
    if mode == "rate_limit":
        return JSONResponse(
            status_code=429,
            headers={
                "retry-after": "30",
                "anthropic-ratelimit-requests-remaining": "0",
                "anthropic-ratelimit-requests-reset": "2025-01-01T00:00:30Z",
            },
            content={
                "type": "error",
                "error": {"type": "rate_limit_error", "message": "Rate limit exceeded"},
            },
        )

    if mode == "banned":
        return JSONResponse(
            status_code=401,
            content={
                "type": "error",
                "error": {"type": "authentication_error", "message": "Invalid API Key"},
            },
        )

    if mode == "slow":
        await asyncio.sleep(2)

    # Extract prompt text for echo response
    messages_list = body.get("messages", [])
    last_content = ""
    if messages_list:
        last_msg = messages_list[-1]
        content = last_msg.get("content", "")
        if isinstance(content, str):
            last_content = content
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    last_content = block.get("text", "")
                    break

    response_text = (
        f"[MOCK] Echo: {last_content[:100]}"
        if last_content
        else "[MOCK] Hello from mock Anthropic!"
    )
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"
    input_tokens = max(10, len(last_content) // 4)
    output_tokens = len(response_text) // 4 + 1

    # Standard rate-limit headers (healthy state)
    rl_headers = {
        "anthropic-ratelimit-requests-limit": "2000",
        "anthropic-ratelimit-requests-remaining": "1999",
        "anthropic-ratelimit-tokens-limit": "200000",
        "anthropic-ratelimit-tokens-remaining": "190000",
    }

    if is_stream:
        return StreamingResponse(
            _sse_stream(msg_id, model, response_text, input_tokens, output_tokens),
            media_type="text/event-stream",
            headers=rl_headers,
        )

    response_body = {
        "id": msg_id,
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": response_text}],
        "model": model,
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
    }

    return JSONResponse(content=response_body, headers=rl_headers)


@app.post("/v1/messages/count_tokens")
async def count_tokens(request: Request):
    body = await request.json()
    messages_list = body.get("messages", [])
    total = sum(len(str(m)) // 4 for m in messages_list) + 10
    return JSONResponse(content={"input_tokens": total})


@app.get("/v1/models")
async def models():
    return {
        "object": "list",
        "data": [
            {"id": "claude-opus-4-6", "object": "model"},
            {"id": "claude-sonnet-4-6", "object": "model"},
            {"id": "claude-haiku-4-5-20251001", "object": "model"},
        ],
    }


async def _sse_stream(msg_id: str, model: str, text: str, input_tokens: int, output_tokens: int):
    events = [
        {
            "type": "message_start",
            "message": {
                "id": msg_id,
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [],
                "stop_reason": None,
                "usage": {"input_tokens": input_tokens, "output_tokens": 0},
            },
        },
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "ping"},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}},
        {"type": "content_block_stop", "index": 0},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": {"output_tokens": output_tokens},
        },
        {"type": "message_stop"},
    ]

    for event in events:
        yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
        await asyncio.sleep(0.01)

    yield "data: [DONE]\n\n"


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
