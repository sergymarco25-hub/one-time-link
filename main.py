import json
import secrets
from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

ADMIN_USER = "admin"
ADMIN_PASS = "12345"
REOPEN_PASSWORD = "1111"  # пароль на второй вход

DATA_FILE = Path("data.json")

app = FastAPI()
templates = Jinja2Templates(directory="templates")

links = {}
sessions = set()


# ---------- DATA ----------
def load_data():
    if DATA_FILE.exists():
        data = json.load(open(DATA_FILE, "r", encoding="utf-8"))
        links.update(data.get("links", {}))


def save_data():
    json.dump(
        {"links": links},
        open(DATA_FILE, "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=2
    )


load_data()


# ---------- AUTH ----------
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
        r.set_cookie("sid", sid)
        return r
    return HTMLResponse("Неверный логин или пароль", status_code=403)


# ---------- HOME ----------
@app.get("/", response_class=HTMLResponse)
def home(request: Request, link: str = ""):
    if not is_logged(request):
        return RedirectResponse("/login", status_code=302)

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "link": link}
    )


# ---------- CREATE ----------
@app.post("/create")
def create(request: Request, target_url: str = Form(...)):
    if not is_logged(request):
        return RedirectResponse("/login", status_code=302)

    code = secrets.token_urlsafe(3)
    links[code] = {"url": target_url, "state": "NEW"}
    save_data()

    base = str(request.base_url).rstrip("/")
    return RedirectResponse(f"/?link={base}/l/{code}", status_code=302)


# ---------- LANDING ----------
@app.get("/l/{code}", response_class=HTMLResponse)
def landing(request: Request, code: str):
    if code not in links:
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    state = links[code]["state"]

    if state == "USED":
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    if state == "OPENED":
        return templates.TemplateResponse("password.html", {"request": request, "code": code})

    return templates.TemplateResponse("open.html", {"request": request, "code": code})


# ---------- AUTO OPEN ----------
@app.get("/open/{code}")
def open_link(code: str):
    if code not in links:
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    link = links[code]

    if link["state"] == "NEW":
        link["state"] = "OPENED"
        save_data()
        return RedirectResponse(link["url"], status_code=302)

    return RedirectResponse(f"/l/{code}", status_code=302)


# ---------- PASSWORD ----------
@app.post("/check-password")
def check_password(request: Request, code: str = Form(...), password: str = Form(...)):
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







