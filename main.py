import json
import secrets
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

ADMIN_USER = "admin"
ADMIN_PASS = "12345"
REOPEN_PASSWORD = "1111"

DATA_FILE = Path("data.json")

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# ---------- DATA ----------
def load_data():
    if not DATA_FILE.exists():
        return {"links": {}, "sessions": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------- AUTH ----------
def is_logged(request: Request, data):
    return request.cookies.get("sid") in data["sessions"]

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    if username != ADMIN_USER or password != ADMIN_PASS:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": True},
            status_code=403
        )

    data = load_data()
    sid = secrets.token_urlsafe(16)
    data["sessions"][sid] = True
    save_data(data)

    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie("sid", sid, httponly=True, samesite="Lax")
    return resp

# ---------- HOME ----------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    data = load_data()
    if not is_logged(request, data):
        return RedirectResponse("/login", status_code=302)

    links_sorted = dict(
        sorted(
            data["links"].items(),
            key=lambda x: x[1]["created_at"],
            reverse=True
        )
    )

    last_link = request.cookies.get("last_link", "")
    last_target = request.cookies.get("last_target", "")

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "link": last_link,
            "target": last_target,
            "links": links_sorted
        }
    )

# ---------- CREATE ----------
@app.post("/create")
def create(request: Request, target_url: str = Form(...)):
    data = load_data()
    if not is_logged(request, data):
        return RedirectResponse("/login", status_code=302)

    code = secrets.token_urlsafe(3)
    moscow_time = datetime.now(ZoneInfo("Europe/Moscow"))

    data["links"][code] = {
        "url": target_url,
        "state": "NEW",
        "created_at": moscow_time.strftime("%d.%m.%Y %H:%M:%S")
    }
    save_data(data)

    base = str(request.base_url).rstrip("/")
    one_time_link = f"{base}/l/{code}"

    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie("last_link", one_time_link, max_age=3600, samesite="Lax")
    resp.set_cookie("last_target", target_url, max_age=3600, samesite="Lax")
    return resp

# ---------- STATUS ----------
@app.get("/status")
def status():
    data = load_data()
    return JSONResponse(data["links"])

# ---------- LANDING ----------
@app.get("/l/{code}", response_class=HTMLResponse)
def landing(request: Request, code: str):
    data = load_data()
    link = data["links"].get(code)

    if not link or link["state"] == "USED":
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

# ---------- AUTO OPEN ----------
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

    return RedirectResponse(f"/l/{code}", status_code=302)

# ---------- PASSWORD ----------
@app.post("/check-password")
def check_password(code: str = Form(...), password: str = Form(...)):
    data = load_data()
    link = data["links"].get(code)

    if not link or link["state"] != "OPENED":
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    if password != REOPEN_PASSWORD:
        return templates.TemplateResponse(
            "password.html",
            {"request": {}, "code": code, "error": True},
            status_code=403
        )

    link["state"] = "USED"
    save_data(data)
    return RedirectResponse(link["url"], status_code=302)
