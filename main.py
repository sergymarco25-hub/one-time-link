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
# DATA UTILS
# =====================
def load_data():
    if not DATA_FILE.exists():
        return {"links": {}, "last_link": "", "sessions": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# =====================
# AUTH
# =====================
def is_logged(request: Request, data):
    sid = request.cookies.get("sid")
    return sid in data["sessions"]

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    if username != ADMIN_USER or password != ADMIN_PASS:
        return HTMLResponse("Неверный логин или пароль", status_code=403)

    data = load_data()
    sid = secrets.token_urlsafe(16)
    data["sessions"][sid] = True
    save_data(data)

    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie("sid", sid, httponly=True, secure=True, samesite="None")
    return resp

# =====================
# HOME
# =====================
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    data = load_data()
    if not is_logged(request, data):
        return RedirectResponse("/login", status_code=302)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "link": data["last_link"],
            "links": data["links"]
        }
    )

# =====================
# CREATE LINK
# =====================
@app.post("/create")
def create(request: Request, target_url: str = Form(...)):
    data = load_data()
    if not is_logged(request, data):
        return RedirectResponse("/login", status_code=302)

    code = secrets.token_urlsafe(3)
    data["links"][code] = {
        "url": target_url,
        "state": "NEW"
    }

    base = str(request.base_url).rstrip("/")
    data["last_link"] = f"{base}/l/{code}"

    save_data(data)
    return RedirectResponse("/", status_code=302)

# =====================
# STATUS API
# =====================
@app.get("/status")
def status():
    data = load_data()
    return JSONResponse(data["links"])

# =====================
# LANDING
# =====================
@app.get("/l/{code}", response_class=HTMLResponse)
def landing(request: Request, code: str):
    data = load_data()
    link = data["links"].get(code)

    if not link:
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    if link["state"] == "USED":
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    if link["state"] == "OPENED":
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
    data = load_data()
    link = data["links"].get(code)

    if not link:
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    if link["state"] == "NEW":
        link["state"] = "OPENED"
        save_data(data)
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
    data = load_data()
    link = data["links"].get(code)

    if not link or link["state"] != "OPENED":
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    if password != REOPEN_PASSWORD:
        return templates.TemplateResponse(
            "password.html",
            {"request": request, "code": code, "error": True},
            status_code=403
        )

    link["state"] = "USED"
    save_data(data)
    return RedirectResponse(link["url"], status_code=302)












