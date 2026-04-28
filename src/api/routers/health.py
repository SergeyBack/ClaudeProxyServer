from fastapi import APIRouter
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import text

from src.core.database import AsyncSessionLocal

router = APIRouter(tags=["system"])


@router.get("/")
async def root():
    return RedirectResponse(url="/ui/login")


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/ready")
async def ready():
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "detail": str(exc)},
        )
