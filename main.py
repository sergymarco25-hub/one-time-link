import secrets
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates


# =====================
# НАСТРОЙКИ
# =====================
ADMIN_USER = "admin"
ADMIN_PASS = "12345"
REOPEN_PASSWORD = "1111"

DB_PATH = "data.db"

app = FastAPI()
templates = Jinja2Templates(directory="templates")


# =====================
# DATABASE
# =====================
def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    db = get_db()
    cur = db.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS links (
        code TEXT PRIMARY KEY,
        url TEXT,
        state TEXT,
        created_at TEXT,
        opened_at TEXT,
        client TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        sid TEXT PRIMARY KEY
    )
    """)

    db.commit()
    db.close()


init_db()


# =====================
# AUTH
# =====================
def is_logged(request: Request):
    sid = request.cookies.get("sid")
    if not sid:
        return False

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT 1 FROM sessions WHERE sid=?", (sid,))
    ok = cur.fetchone() is not None
    db.close()
    return ok


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username != ADMIN_USER or password != ADMIN_PASS:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": True},
            status_code=403
        )

    sid = secrets.token_urlsafe(16)
    db = get_db()
    db.execute("INSERT OR IGNORE INTO sessions VALUES (?)", (sid,))
    db.commit()
    db.close()

    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie("sid", sid, httponly=True, samesite="Lax")
    return resp


# =====================
# HOME (⬅️ ВАЖНАЯ ЧАСТЬ)
# =====================
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    if not is_logged(request):
        return RedirectResponse("/login", status_code=302)

    now = datetime.now(ZoneInfo("Europe/Moscow"))

    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT code, url, state, created_at, opened_at, client
        FROM links
    """)
    rows = cur.fetchall()
    db.close()

    links = {}

    for code, url, state, created_at, opened_at, client in rows:
        opened_recent = False

        if opened_at:
            opened_time = datetime.strptime(
                opened_at, "%d.%m.%Y %H:%M:%S"
            ).replace(tzinfo=ZoneInfo("Europe/Moscow"))

            if now - opened_time <= timedelta(hours=1):
                opened_recent = True

        links[code] = {
            "url": url,
            "state": state,
            "created_at": created_at,
            "opened_at": opened_at,
            "client": client,
            "opened_recent": opened_recent
        }

    # ⬆️ СОРТИРОВКА:
    # 1. те, кто открыл за последний час — вверх
    # 2. остальные — по дате создания
    links = dict(
        sorted(
            links.items(),
            key=lambda x: (
                not x[1]["opened_recent"],
                x[1]["created_at"]
            )
        )
    )

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "links": links,
            "link": request.cookies.get("last_link", ""),
            "target": request.cookies.get("last_target", "")
        }
    )


# =====================
# CREATE LINK
# =====================
@app.post("/create")
def create(
    request: Request,
    target_url: str = Form(...),
    client: str = Form("")
):
    if not is_logged(request):
        return RedirectResponse("/login", status_code=302)

    code = secrets.






