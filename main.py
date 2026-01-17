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

REOPEN_PASSWORD = os.getenv("REOPEN_PASSWORD", "CHANGE_ME")
GEN_LIMIT = 30000

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# =====================
# ХРАНЕНИЕ
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
def is_logged_in(request: Request):
    return request.cookies.get("session_id") in sessions

def has_seen_cookie(request: Request, code: str):
    return request.cookies.get(f"seen_{code}") == "1"

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
        resp = RedirectResponse("/", status_code=302)
        resp.set_cookie("session_id", sid, httponly=True, samesite="lax")
        return resp

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
        return HTMLResponse("❌ Лимит исчерпан", status_code=403)

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
# STEP 1 — ПОКАЗ КНОПКИ
# =====================
@app.get("/l/{code}", response_class=HTMLResponse)
def landing(request: Request, code: str):
    if code not in links:
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    if links[code]["state"] == "USED":
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    return templates.TemplateResponse(
        "open.html",
        {"request": request, "code": code}
    )

# =====================
# STEP 2 — ОСОЗНАННОЕ ОТКРЫТИЕ
# =====================
@app.post("/open")
def open_real(request: Request, code: str = Form(...)):
    if code not in links:
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    link = links[code]

    # первый реальный вход
    if link["state"] == "NEW":
        link["state"] = "OPENED"
        resp = RedirectResponse(link["url"])
        resp.set_cookie(f"seen_{code}", "1", max_age=3600, samesite="lax")
        return resp

    # повторный вход — пароль
    return templates.TemplateResponse(
        "password.html",
        {"request": request, "code": code}
    )

# =====================
# PASSWORD
# =====================
@app.post("/check-password")
def check_password(code: str = Form(...), password: str = Form(...)):
    if code not in links:
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    if password != REOPEN_PASSWORD:
        return templates.TemplateResponse(
    "password.html",
    {
        "request": request,
        "code": code,
        "error": True
    },
    status_code=403
)

    url = links[code]["url"]
    links[code]["state"] = "USED"
    del links[code]

    return RedirectResponse(url)




