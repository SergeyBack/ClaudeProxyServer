from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response

from src.api.dependencies import get_current_user_from_api_key, get_proxy_service
from src.application.services.proxy_service import ProxyService
from src.domain.exceptions import NoAvailableAccountError
from src.domain.models.user import User

router = APIRouter(tags=["proxy"])

_ANTHROPIC_MODELS = [
    {"id": "claude-opus-4-6", "object": "model"},
    {"id": "claude-sonnet-4-6", "object": "model"},
    {"id": "claude-haiku-4-5-20251001", "object": "model"},
    {"id": "claude-3-5-sonnet-20241022", "object": "model"},
    {"id": "claude-3-5-haiku-20241022", "object": "model"},
    {"id": "claude-3-opus-20240229", "object": "model"},
]


@router.post("/v1/messages")
async def proxy_messages(
    request: Request,
    current_user: User = Depends(get_current_user_from_api_key),
    proxy_service: ProxyService = Depends(get_proxy_service),
) -> Response:
    try:
        return await proxy_service.proxy_request(current_user, request)
    except NoAvailableAccountError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )


@router.post("/v1/messages/count_tokens")
async def proxy_count_tokens(
    request: Request,
    current_user: User = Depends(get_current_user_from_api_key),
    proxy_service: ProxyService = Depends(get_proxy_service),
) -> Response:
    try:
        return await proxy_service.proxy_request(current_user, request)
    except NoAvailableAccountError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )


@router.get("/v1/models")
async def list_models(
    current_user: User = Depends(get_current_user_from_api_key),
):
    return {"object": "list", "data": _ANTHROPIC_MODELS}
