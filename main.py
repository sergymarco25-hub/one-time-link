import os
import json
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo

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

DATA_FILE = "data.json"
TZ = ZoneInfo("Europe/Moscow")

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# =====================
# ХРАНЕНИЕ
# =====================
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"links": [], "generated": 0}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()
sessions = set()

# =====================
# ВСПОМОГАТЕЛЬНОЕ
# =====================
def now_msk():
    return datetime.now(TZ).strftime("%d.%m.%Y %H:%M:%S")

def is_logged_in(request: Request):
    return request.cookies.get("session_id") in sessions

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
            "links": list(data["links"].values())[::-1],
            "generated": data["generated"],
            "limit": GEN_LIMIT,
            "remaining": GEN_LIMIT - data["generated"],
        }
    )

# =====================
# CREATE LINK
# =====================
@app.post("/create")
def create(
    request: Request,
    target_url: str = Form(...),
    label: str = Form("")
):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    if data["generated"] >= GEN_LIMIT:
        return HTMLResponse("Лимит исчерпан", status_code=403)

    code = secrets.token_urlsafe(3)
    base = str(request.base_url).rstrip("/")
    link_url = f"{base}/l/{code}"

    data["links"].append({
        "code": code,
        "short": link_url,
        "target": target_url,
        "label": label,
        "status": "new",
        "created_at": now_msk(),
        "opened_at": None
    })

    data["generated"] += 1
    save_data(data)

    return RedirectResponse("/", status_code=302)

# =====================
# OPEN LINK
# =====================
@app.get("/l/{code}", response_class=HTMLResponse)
def open_link(request: Request, code: str):
    link = next((l for l in data["links"] if l["code"] == code), None)
    if not link or link["status"] == "used":
        return HTMLResponse("Ссылка недействительна", status_code=410)

    if link["status"] == "new":
        link["status"] = "opened"
        link["opened_at"] = now_msk()
        save_data(data)
        return RedirectResponse(link["target"])

    return templates.TemplateResponse(
        "password.html",
        {"request": request, "code": code}
    )

# =====================
# PASSWORD CHECK
# =====================
@app.post("/check-password")
def check_password(
    request: Request,
    code: str = Form(...),
    password: str = Form(...)
):
    link = next((l for l in data["links"] if l["code"] == code), None)
    if not link:
        return HTMLResponse("Ссылка недействительна", status_code=410)

    if password != REOPEN_PASSWORD:
        return templates.TemplateResponse(
            "password.html",
            {"request": request, "code": code, "error": True},
            status_code=403
        )

    link["status"] = "used"
    save_data(data)
    return RedirectResponse(link["target"])




