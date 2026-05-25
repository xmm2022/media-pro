import hmac

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse


ADMIN_SESSION_COOKIE = "gateway_admin_session"

router = APIRouter(tags=["admin-auth"])


@router.post("/api/admin/login")
async def admin_login(request: Request) -> JSONResponse:
    configured_password = getattr(request.app.state, "admin_password", "")
    if not configured_password:
        return JSONResponse({"ok": True, "auth_enabled": False})

    try:
        payload = await request.json()
    except ValueError:
        payload = {}
    supplied_password = payload.get("password") if isinstance(payload, dict) else None
    if not isinstance(supplied_password, str) or not hmac.compare_digest(
        supplied_password,
        configured_password,
    ):
        return JSONResponse(
            {"detail": "invalid admin password"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    token = request.app.state.admin_session_cipher.issue()
    response = JSONResponse({"ok": True, "auth_enabled": True})
    response.set_cookie(
        ADMIN_SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=request.app.state.admin_session_ttl_seconds,
        path="/",
    )
    return response


@router.get("/api/admin/session")
def admin_session(request: Request) -> JSONResponse:
    auth_enabled = bool(getattr(request.app.state, "admin_password", ""))
    if not auth_enabled:
        authenticated = False
    else:
        token = request.cookies.get(ADMIN_SESSION_COOKIE)
        authenticated = bool(token) and admin_session_is_valid(request, token)
    return JSONResponse({"auth_enabled": auth_enabled, "authenticated": authenticated})


@router.post("/api/admin/logout")
def admin_logout() -> JSONResponse:
    response = JSONResponse({"ok": True})
    response.delete_cookie(ADMIN_SESSION_COOKIE, path="/")
    return response


def admin_session_is_valid(request: Request, token: str) -> bool:
    try:
        request.app.state.admin_session_cipher.verify(
            token,
            ttl_seconds=request.app.state.admin_session_ttl_seconds,
        )
    except ValueError:
        return False
    return True
