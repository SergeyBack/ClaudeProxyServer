from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.lifespan import lifespan
from src.api.middleware.request_id import RequestIDMiddleware
from src.api.middleware.timing import TimingMiddleware
from src.api.routers import health
from src.api.routers.admin.accounts import router as admin_accounts_router
from src.api.routers.admin.stats import router as admin_stats_router
from src.api.routers.admin.users import router as admin_users_router
from src.api.routers.auth import router as auth_router
from src.api.routers.proxy import router as proxy_router
from src.api.routers.user.profile import router as user_profile_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Claude Code Corporate Proxy",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Middleware (order matters — last added = outermost)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(health.router)
    app.include_router(auth_router)
    app.include_router(proxy_router)
    app.include_router(admin_accounts_router)
    app.include_router(admin_users_router)
    app.include_router(admin_stats_router)
    app.include_router(user_profile_router)

    # Web UI routes
    from src.api.routers import ui

    app.include_router(ui.router)

    # Static files
    try:
        app.mount("/static", StaticFiles(directory="static"), name="static")
    except Exception:
        pass

    return app


app = create_app()
