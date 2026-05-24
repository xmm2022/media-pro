import hmac

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, Response


ADMIN_SESSION_COOKIE = "gateway_admin_session"

router = APIRouter(tags=["admin-auth"])


LOGIN_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>media-pro admin login</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: #f6f7f9;
      color: #18202a;
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    main {
      width: min(360px, calc(100vw - 28px));
      padding: 22px;
      border: 1px solid #d9dee7;
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 1px 2px rgba(15, 23, 42, .08);
    }
    h1 { margin: 0 0 16px; font-size: 18px; letter-spacing: 0; }
    label { display: grid; gap: 6px; color: #687384; font-size: 12px; }
    input {
      width: 100%;
      min-height: 38px;
      padding: 8px 9px;
      border: 1px solid #d9dee7;
      border-radius: 6px;
      font: inherit;
    }
    button {
      width: 100%;
      min-height: 38px;
      margin-top: 14px;
      border: 1px solid #0f766e;
      border-radius: 6px;
      background: #0f766e;
      color: #fff;
      font: inherit;
      cursor: pointer;
    }
    p { min-height: 20px; margin: 12px 0 0; color: #b42318; }
  </style>
</head>
<body>
  <main>
    <h1>media-pro admin</h1>
    <form id="login-form">
      <label>管理员密码 <input name="password" type="password" autocomplete="current-password" autofocus required></label>
      <button type="submit">登录</button>
      <p id="error"></p>
    </form>
  </main>
  <script>
    document.querySelector('#login-form').addEventListener('submit', async (event) => {
      event.preventDefault();
      const password = new FormData(event.currentTarget).get('password');
      const response = await fetch('/api/admin/login', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ password }),
      });
      if (response.ok) {
        window.location.href = '/admin';
        return;
      }
      document.querySelector('#error').textContent = '密码不正确';
    });
  </script>
</body>
</html>
"""


@router.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request) -> Response:
    if not getattr(request.app.state, "admin_password", ""):
        return HTMLResponse(LOGIN_HTML)
    token = request.cookies.get(ADMIN_SESSION_COOKIE)
    if token and admin_session_is_valid(request, token):
        response = Response(status_code=status.HTTP_303_SEE_OTHER)
        response.headers["location"] = "/admin"
        return response
    return HTMLResponse(LOGIN_HTML)


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
    return JSONResponse({"auth_enabled": bool(getattr(request.app.state, "admin_password", ""))})


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
