import secrets
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

# =====================
# НАСТРОЙКИ
# =====================

ADMINS = {
    "admin": "2345",
    "admin2": "2346",
}

REOPEN_PASSWORD = "7878"

DB_PATH = "data.db"

app = FastAPI()
templates = Jinja2Templates(directory="templates")
DB_PATH = "data.db"
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
        client TEXT,
        uid TEXT
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

def is_logged(request: Request) -> bool:
    sid = request.cookies.get("sid")
    if not sid:
        return False

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT 1 FROM sessions WHERE sid=?", (sid,))
    ok = cur.fetchone() is not None
    db.close()
    return ok


def get_uid(request: Request) -> str:
    uid = request.cookies.get("uid")
    if not uid:
        uid = secrets.token_urlsafe(12)
    return uid

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request}
    )
    
@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    if username not in ADMINS or ADMINS[username] != password:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": True},
            status_code=403
        )

    sid = secrets.token_urlsafe(16)
    uid = get_uid(request)

    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO sessions (sid) VALUES (?)",
        (sid,)
    )
    db.commit()
    db.close()

    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie("sid", sid, httponly=True, samesite="Lax")
    resp.set_cookie("uid", uid, max_age=60 * 60 * 24 * 365)
    return resp
# =====================
# HOME
# =====================
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    if not is_logged(request):
        return RedirectResponse("/login", status_code=302)

    uid = get_uid(request)

    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        SELECT code, url, state, created_at, opened_at, client
        FROM links
        WHERE uid=?
        ORDER BY created_at DESC
        """,
        (uid,)
    )
    rows = cur.fetchall()
    db.close()

    links = {
        code: {
            "url": url,
            "state": state,
            "created_at": created_at,
            "opened_at": opened_at,
            "client": client
        }
        for code, url, state, created_at, opened_at, client in rows
    }

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

    uid = get_uid(request)
    code = secrets.token_urlsafe(3)

    created_at = datetime.now(
        ZoneInfo("Europe/Moscow")
    ).strftime("%d.%m.%Y %H:%M:%S")

    db = get_db()
    db.execute(
        """
        INSERT INTO links (code, url, state, created_at, opened_at, client, uid)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            code,
            target_url,
            "NEW",
            created_at,
            None,
            client.strip(),
            uid
        )
    )
    db.commit()
    db.close()

    base = str(request.base_url).rstrip("/")
    one_time_link = f"{base}/l/{code}"

    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie("last_link", one_time_link, max_age=3600)
    resp.set_cookie("last_target", target_url, max_age=3600)
    resp.set_cookie("uid", uid, max_age=60 * 60 * 24 * 365)
    return resp
# =====================
# STATUS (для автообновления)
# =====================
@app.get("/status")
def status():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT code, state, created_at, opened_at, client
        FROM links
        ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    db.close()

    return JSONResponse({
        code: {
            "state": state,
            "created_at": created_at,
            "opened_at": opened_at,
            "client": client
        }
        for code, state, created_at, opened_at, client in rows
    })

# =====================
# LANDING
# =====================
@app.get("/l/{code}", response_class=HTMLResponse)
def landing(request: Request, code: str):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT state FROM links WHERE code=?", (code,))
    row = cur.fetchone()
    db.close()

    if not row:
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    state = row[0]

    if state == "OPENED":
        return templates.TemplateResponse(
            "password.html",
            {"request": request, "code": code}
        )

    if state == "USED":
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    return templates.TemplateResponse(
        "open.html",
        {"request": request, "code": code}
    )

# =====================
# FIRST OPEN
# =====================
@app.get("/open/{code}")
def open_link(code: str):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT url, state FROM links WHERE code=?", (code,))
    row = cur.fetchone()

    if not row:
        db.close()
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    url, state = row

    if state == "NEW":
        opened_at = datetime.now(
            ZoneInfo("Europe/Moscow")
        ).strftime("%d.%m.%Y %H:%M:%S")

        cur.execute(
            "UPDATE links SET state='OPENED', opened_at=? WHERE code=?",
            (opened_at, code)
        )
        db.commit()
        db.close()
        return RedirectResponse(url, status_code=302)

    db.close()
    return RedirectResponse(f"/l/{code}", status_code=302)

# =====================
# PASSWORD CHECK
# =====================
@app.post("/check-password")
def check_password(
    request: Request,
    code: str = Form(...),
    password: str = Form(...)
):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT url FROM links WHERE code=? AND state='OPENED'",
        (code,)
    )
    row = cur.fetchone()

    if not row:
        db.close()
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    if password != REOPEN_PASSWORD:
        db.close()
        return templates.TemplateResponse(
            "password.html",
            {"request": request, "code": code, "error": True},
            status_code=403
        )

    cur.execute(
        "UPDATE links SET state='USED' WHERE code=?",
        (code,)
    )
    db.commit()
    db.close()
    return RedirectResponse(row[0], status_code=302)
# stable version v1.0




