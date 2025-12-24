import os
import sqlite3
import secrets
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

# =========================
# 🔧 НАСТРОЙКИ
# =========================
ADMIN_USER = "admin"
ADMIN_PASS = "12345"
GEN_LIMIT = 30

DB_DIR = "data"
DB_PATH = f"{DB_DIR}/app.db"

os.makedirs(DB_DIR, exist_ok=True)

# =========================
# 🗄️ БАЗА ДАННЫХ
# =========================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS stats (
    id INTEGER PRIMARY KEY,
    generated INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS links (
    code TEXT PRIMARY KEY,
    url TEXT,
    opens INTEGER
)
""")

cursor.execute("SELECT COUNT(*) FROM stats")
if cursor.fetchone()[0] == 0:
    cursor.execute("INSERT INTO stats (generated) VALUES (0)")
    conn.commit()

# =========================
# 🚀 APP
# =========================
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="super-secret-key")
templates = Jinja2Templates(directory="templates")

# =========================
# 🔐 АВТОРИЗАЦИЯ
# =========================
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USER and password == ADMIN_PASS:
        request.session["auth"] = True
        return RedirectResponse("/", status_code=302)
    return HTMLResponse("❌ Неверные данные", status_code=401)

def require_login(request: Request):
    if not request.session.get("auth"):
        return RedirectResponse("/login", status_code=302)

# =========================
# 🏠 ГЛАВНАЯ
# =========================
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    auth = require_login(request)
    if auth:
        return auth

    cursor.execute("SELECT generated FROM stats")
    generated = cursor.fetchone()[0]

    return templates.TemplateResponse("index.html", {
        "request": request,
        "generated": generated,
        "limit": GEN_LIMIT,
        "remaining": GEN_LIMIT - generated,
        "link": None,
        "target_url": ""
    })

# =========================
# ➕ СОЗДАНИЕ ССЫЛКИ
# =========================
@app.post("/create", response_class=HTMLResponse)
def create(request: Request, target_url: str = Form(...)):
    auth = require_login(request)
    if auth:
        return auth

    cursor.execute("SELECT generated FROM stats")
    generated = cursor.fetchone()[0]

    if generated >= GEN_LIMIT:
        return HTMLResponse("❌ Лимит генераций исчерпан", status_code=403)

    code = secrets.token_urlsafe(3)
    cursor.execute(
        "INSERT INTO links (code, url, opens) VALUES (?, ?, 0)",
        (code, target_url)
    )
    cursor.execute(
        "UPDATE stats SET generated = generated + 1"
    )
    conn.commit()

    base = str(request.base_url).rstrip("/")
    link = f"{base}/{code}"

    return templates.TemplateResponse("index.html", {
        "request": request,
        "generated": generated + 1,
        "limit": GEN_LIMIT,
        "remaining": GEN_LIMIT - (generated + 1),
        "link": link,
        "target_url": target_url
    })

# =========================
# 🌍 ОДНОРАЗОВАЯ ССЫЛКА
# =========================
@app.get("/{code}")
def open_link(code: str):
    cursor.execute("SELECT url, opens FROM links WHERE code = ?", (code,))
    row = cursor.fetchone()

    if not row:
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    url, opens = row
    opens += 1

    if opens == 1:
        cursor.execute("UPDATE links SET opens = 1 WHERE code = ?", (code,))
        conn.commit()
        return HTMLResponse("⏳ Ссылка активирована. Откройте её ещё раз.")

    cursor.execute("DELETE FROM links WHERE code = ?", (code,))
    conn.commit()
    return RedirectResponse(url)


