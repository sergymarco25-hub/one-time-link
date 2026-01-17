import os
import json
import secrets
from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates


# =====================
# НАСТРОЙКИ
# =====================
ADMIN_USER = "admin"
ADMIN_PASS = "12345"

REOPEN_PASSWORD = os.getenv("REOPEN_PASSWORD", "CHANGE_ME")
GEN_LIMIT = 30000

DATA_FILE = Path("data.json")

app = FastAPI()
templates = Jinja2Templates(directory="templates")


# =====================
# ХРАНИЛИЩЕ
# =====================
links = {}   # code -> {url, state}
stats = {"generated": 0}
sessions = set()

last_link = None
last_target = ""


# =====================
# JSON ХРАНИЛИЩЕ
# =====================
def load_data():
    global links, stats
    if not DATA_FILE.exists():
        return
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    links.clear()
    links.update(data.get("links", {}))
    stats.update(data.get("stats", {"generated": 0}))


def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"links": links, "stats": stats},
            f,
            ensure_ascii=False,
            indent=2
        )


load_data()


# =====================
# ВСПОМОГАТЕЛЬНОЕ
# =====================
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
            "generated": stats["generated"],
            "limit": GEN_LIMIT,
            "remaining": GEN_LIMIT - stats["generated"],
            "link": last_link,
            "target_url": last_target,
            "links": links
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
    save_data()

    base = str(request.base_url).rstrip("/")
    last_link = f"{base}/l/{code}"
    last_target = target_url

    return RedirectResponse("/", status_code=302)


# =====================
# LINK LANDING
# =====================
@app.get("/l/{code}", response_class=HTMLResponse)
def landing(request: Request, code: str):
    if code not in links:
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    link = links[code]

    if link["state"] == "OPENED":
        return templates.TemplateResponse(
            "password.html",
            {"request": request, "code": code}
        )

    if link["state"] == "USED":
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    return templates.TemplateResponse(
        "open.html",
        {"request": request, "code": code}
    )


# =====================
# FIRST REAL OPEN
# =====================
@app.post("/open")
def open_real(code: str = Form(...)):
    if code not in links:
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    link = links[code]

    if link["state"] == "NEW":
        link["state"] = "OPENED"
        save_data()
        return RedirectResponse(link["url"], status_code=302)

    return HTMLResponse("❌ Ссылка недействительна", status_code=410)


# =====================
# PASSWORD CHECK
# =====================
@app.post("/check-password")
def check_password(
    request: Request,
    code: str = Form(...),
    password: str = Form(...)
):
    if code not in links:
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    if password != REOPEN_PASSWORD:
        return templates.TemplateResponse(
            "password.html",
            {"request": request, "code": code, "error": True},
            status_code=403
        )

    url = links[code]["url"]
    links[code]["state"] = "USED"
    save_data()

    return RedirectResponse(url, status_code=302)


# =====================
# STATUS API (для автообновления)
# =====================
@app.get("/status")
def status_api():
    return JSONResponse(links)





