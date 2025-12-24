import secrets
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

# =====================
# НАСТРОЙКИ
# =====================
ADMIN_USER = "admin"
ADMIN_PASS = "12345"
GEN_LIMIT = 30
AUTH_COOKIE = "auth"

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# =====================
# ХРАНЕНИЕ В ПАМЯТИ
# =====================
links = {}
stats = {"generated": 0}

# =====================
# АВТОРИЗАЦИЯ
# =====================
def is_logged_in(request: Request) -> bool:
    return request.cookies.get(AUTH_COOKIE) == "ok"

def require_login(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

# =====================
# LOGIN
# =====================
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USER and password == ADMIN_PASS:
        response = RedirectResponse("/", status_code=302)
        response.set_cookie(AUTH_COOKIE, "ok", httponly=True)
        return response
    return HTMLResponse("❌ Неверный логин или пароль", status_code=401)

# =====================
# HOME
# =====================
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    auth = require_login(request)
    if auth:
        return auth

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "generated": stats["generated"],
            "limit": GEN_LIMIT,
            "remaining": GEN_LIMIT - stats["generated"],
            "link": None,
            "target_url": ""
        }
    )

# =====================
# CREATE LINK
# =====================
@app.post("/create", response_class=HTMLResponse)
def create(request: Request, target_url: str = Form(...)):
    auth = require_login(request)
    if auth:
        return auth

    if stats["generated"] >= GEN_LIMIT:
        return HTMLResponse("❌ Лимит генераций исчерпан", status_code=403)

    code = secrets.token_urlsafe(3)
    links[code] = {"url": target_url, "opens": 0}
    stats["generated"] += 1

    base = str(request.base_url).rstrip("/")
    link = f"{base}/{code}"

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "generated": stats["generated"],
            "limit": GEN_LIMIT,
            "remaining": GEN_LIMIT - stats["generated"],
            "link": link,
            "target_url": target_url
        }
    )

# =====================
# OPEN LINK
# =====================
@app.get("/{code}")
def open_link(code: str):
    if code not in links:
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    links[code]["opens"] += 1

    if links[code]["opens"] == 1:
        return HTMLResponse("⏳ Ссылка активирована. Откройте её ещё раз.")

    url = links[code]["url"]
    del links[code]
    return RedirectResponse(url)
