from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import get_user_service
from src.application.dto.user_dto import LoginRequest, TokenResponse
from src.application.services.user_service import UserService
from src.core.security import create_access_token
from src.domain.exceptions import InvalidCredentialsError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    user_service: UserService = Depends(get_user_service),
):
    try:
        user = await user_service.authenticate(req.username, req.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc))

    access_token = create_access_token(str(user.id))
    return TokenResponse(access_token=access_token)


@router.post("/logout")
async def logout():
    return {"message": "Logged out"}
