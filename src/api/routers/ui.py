"""Server-rendered web panel (Jinja2 templates)."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/ui", tags=["ui"])
templates = Jinja2Templates(directory="templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    return templates.TemplateResponse(
        "admin/dashboard.html", {"request": request, "is_admin": True}
    )


@router.get("/admin/accounts", response_class=HTMLResponse)
async def admin_accounts(request: Request):
    return templates.TemplateResponse("admin/accounts.html", {"request": request, "is_admin": True})


@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request):
    return templates.TemplateResponse("admin/users.html", {"request": request, "is_admin": True})


@router.get("/user/usage", response_class=HTMLResponse)
async def user_usage(request: Request):
    return templates.TemplateResponse("user/usage.html", {"request": request})


@router.get("/", response_class=RedirectResponse)
async def root_redirect():
    return RedirectResponse("/ui/login")
