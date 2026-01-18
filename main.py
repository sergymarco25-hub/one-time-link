import json
import secrets
from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

ADMIN_USER = "admin"
ADMIN_PASS = "12345"
GEN_LIMIT = 30000

DATA_FILE = Path("data.json")

app = FastAPI()
templates = Jinja2Templates(directory="templates")

links = {}
stats = {"generated": 0}
sessions = set()


def load_data():
    if DATA_FILE.exists():
        data = json.load(open(DATA_FILE, "r", encoding="utf-8"))
        links.update(data.get("links", {}))
        stats.update(data.get("stats", {"generated": 0}))


def save_data():
    json.dump(
        {"links": links, "stats": stats},
        open(DATA_FILE, "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=2
    )


load_data()


def is_logged_in(request: Request):
    return request.cookies.get("session_id") in sessions


# -------- LOGIN --------

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login_action(username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USER and password == ADMIN_PASS:
        sid = secrets.token_urlsafe(16)
        sessions.add(sid)
        resp = RedirectResponse("/", status_code=302)
        resp.set_cookie("session_id", sid, httponly=True, samesite="lax")
        return resp
    return HTMLResponse("Неверный логин или пароль", status_code=403)


# -------- HOME --------

@app.get("/", response_class=HTMLResponse)
def home(request: Request, link: str = ""):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "link": link,
            "generated": stats["generated"],
            "remaining": GEN_LIMIT - stats["generated"],
            "links": links
        }
    )


# -------- CREATE --------

@app.post("/create")
def create(request: Request, target_url: str = Form(...)):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    if stats["generated"] >= GEN_LIMIT:
        return HTMLResponse("Лимит исчерпан", status_code=403)

    code = secrets.token_urlsafe(3)
    links[code] = {"url": target_url, "state": "NEW"}
    stats["generated"] += 1
    save_data()

    base = str(request.base_url).rstrip("/")
    return RedirectResponse(f"/?link={base}/l/{code}", status_code=302)


# -------- LANDING --------

@app.get("/l/{code}", response_class=HTMLResponse)
def landing(request: Request, code: str):
    if code not in links:
        return HTMLResponse("Ссылка недействительна", status_code=410)

    return templates.TemplateResponse("open.html", {"request": request, "code": code})


# -------- OPEN (HTTP REDIRECT) --------

@app.get("/open/{code}")
def open_direct(code: str):
    if code not in links:
        return HTMLResponse("Ссылка недействительна", status_code=410)

    link = links[code]

    if link["state"] == "NEW":
        link["state"] = "OPENED"
        save_data()
        return RedirectResponse(link["url"], status_code=302)

    if link["state"] == "OPENED":
        return RedirectResponse(link["url"], status_code=302)

    return HTMLResponse("Ссылка недействительна", status_code=410)


# -------- STATUS --------

@app.get("/status")
def status():
    return JSONResponse(links)






