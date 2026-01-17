import os
import secrets
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

# =====================
# НАСТРОЙКИ
# =====================
ADMIN_USER = "admin"
ADMIN_PASS = "12345"

# 🔐 ГЛОБАЛЬНЫЙ ПАРОЛЬ ДЛЯ ПОВТОРНОГО ДОСТУПА
# МЕНЯЕТСЯ В НАСТРОЙКАХ RENDER (Environment Variables)
REOPEN_PASSWORD = os.getenv("REOPEN_PASSWORD", "CHANGE_ME")

GEN_LIMIT = 30000

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# =====================
# ХРАНЕНИЕ В ПАМЯТИ
# =====================
# code -> {"url": str, "state": "NEW" | "OPENED" | "USED"}
links = {}

stats = {"generated": 0}
sessions = set()

last_link = None
last_target = ""

# =====================
# ВСПОМОГАТЕЛЬНОЕ
# =====================
def get_session_id(request: Request):
    return request.cookies.get("session_id")

def is_logged_in(request: Request):
    sid = get_session_id(request)
    return sid in sessions

# =====================
# LOGIN
# =====================
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login_action(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    if username == ADMIN_USER and password == ADMIN_PASS:
        sid = secrets.token_urlsafe(16)
        sessions.add(sid)

        response = RedirectResponse("/", status_code=302)
        response.set_cookie(
            key="session_id",
            value=sid,
            httponly=True,
            samesite="lax"
        )
        return response

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Неверный логин или пароль"}
    )

# =====================
# HOME
# =====================
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "generated": stats["generated"],
            "limit": GEN_LIMIT,
            "remaining": GEN_LIMIT - stats["generated"],
            "link": last_link,
            "target_url": last_target
        }
    )

# =====================
# CREATE LINK
# =====================
@app.post("/create")
def create(request: Request, target_url: str = Form(...)):
    global last_link, last_target

    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    if stats["generated"] >= GEN_LIMIT:
        return HTMLResponse("❌ Лимит генераций исчерпан", status_code=403)

    code = secrets.token_urlsafe(3)

    links[code] = {
        "url": target_url,
        "state": "NEW"
    }

    stats["generated"] += 1

    base = str(request.base_url).rstrip("/")
    last_link = f"{base}/l/{code}"
    last_target = target_url

    return RedirectResponse("/", status_code=302)

# =====================
# OPEN LINK
# =====================
@app.api_route("/l/{code}", methods=["GET", "HEAD"])
def open_link(request: Request, code: str):
    if code not in links:
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    link = links[code]

    # 1️⃣ ПЕРВЫЙ ВХОД — БЕЗ ПАРОЛЯ
    if link["state"] == "NEW":
        link["state"] = "OPENED"
        return RedirectResponse(f"/go/{code}")

    # 2️⃣ ВТОРОЙ ВХОД — ТРЕБУЕТ ПАРОЛЬ
    if link["state"] == "OPENED":
        return templates.TemplateResponse(
            "password.html",
            {"request": request, "code": code}
        )

    # 3️⃣ ИСПОЛЬЗОВАНА
    return HTMLResponse("❌ Ссылка недействительна", status_code=410)

# =====================
# ПРОВЕРКА ПАРОЛЯ
# =====================
@app.post("/check-password")
def check_password(code: str = Form(...), password: str = Form(...)):
    if code not in links:
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    if password != REOPEN_PASSWORD:
return HTMLResponse("❌ Неверный пароль", status_code=403)

    url = links[code]["url"]
    links[code]["state"] = "USED"
    del links[code]

    return RedirectResponse(url)

# =====================
# ПРОМЕЖУТОЧНАЯ СТРАНИЦА (АВТО-ПЕРЕХОД)
# =====================
@app.get("/go/{code}", response_class=HTMLResponse)
def go_page(code: str):
    return HTMLResponse(f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Переход…</title>
    <script>
        setTimeout(function () {{
            window.location.href = "/l/{code}";
        }}, 300);
    </script>
</head>
<body>
    <p>Переход к ссылке…</p>
</body>
</html>
""")
