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
REOPEN_PASSWORD = "1111"

DATA_FILE = Path("data.json")

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# =====================
# ХРАНЕНИЕ
# =====================
links = {}                 # code -> {url, state}
sessions = set()
last_generated_link = ""   # сохраняем последнюю ссылку на сервере

# =====================
# DATA
# =====================
def load_data():
    global last_generated_link
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            links.update(data.get("links", {}))
            last_generated_link = data.get("last_link", "")

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "links": links,
                "last_link": last_generated_link
            },
            f,
            ensure_ascii=False,
            indent=2
        )

load_data()

# =====================
# AUTH
# =====================
def is_logged(request: Request):
    return request.cookies.get("sid") in sessions

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USER and password == ADMIN_PASS:
        sid = secrets.token_urlsafe(16)
        sessions.add(sid)
        r = RedirectResponse("/", status_code=302)
        r.set_cookie("sid", sid, httponly=True, secure=True, samesite="None")
        return r
    return HTMLResponse("Неверный логин или пароль", status_code=403)

# =====================
# HOME
# =====================
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    if not is_logged(request):
        return RedirectResponse("/login", status_code=302)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "link": last_generated_link,
            "links": links
        }
    )

# =====================
# CREATE
# =====================
@app.post("/create")
def create(request: Request, target_url: str = Form(...)):
    global last_generated_link

    if not is_logged(request):
        return RedirectResponse("/login", status_code=302)

    code = secrets.token_urlsafe(3)
    links[code] = {
        "url": target_url,
        "state": "NEW"
    }

    base = str(request.base_url).rstrip("/")
    last_generated_link = f"{base}/l/{code}"

    save_data()

    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie(
        "last_link",
        last_generated_link,
        max_age=600,
        secure=True,
        samesite="None"
    )
    return resp

# =====================
# STATUS API (ДЛЯ АВТООБНОВЛЕНИЯ)
# =====================
@app.get("/status")
def status():
    """
    Возвращает статусы всех ссылок:
    NEW / OPENED / USED
    """
    return JSONResponse(links)

# =====================
# LANDING
# =====================
@app.get("/l/{code}", response_class=HTMLResponse)
def landing(request: Request, code: str):
    if code not in links:
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    state = links[code]["state"]

    if state == "USED":
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    if state == "OPENED":
        return templates.TemplateResponse(
            "password.html",
            {"request": request, "code": code}
        )

    return templates.TemplateResponse(
        "open.html",
        {"request": request, "code": code}
    )

# =====================
# AUTO OPEN
# =====================
@app.get("/open/{code}")
def open_link(code: str):
    if code not in links:
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    link = links[code]

    if link["state"] == "NEW":
        link["state"] = "OPENED"
        save_data()
        return RedirectResponse(link["url"], status_code=302)

    if link["state"] == "OPENED":
        return RedirectResponse(f"/l/{code}", status_code=302)

    return HTMLResponse("❌ Ссылка недействительна", status_code=410)

# =====================
# PASSWORD
# =====================
@app.post("/check-password")
def check_password(
    request: Request,
    code: str = Form(...),
    password: str = Form(...)
):
    if code not in links or links[code]["state"] != "OPENED":
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










