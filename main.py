import secrets
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

# =====================
# НАСТРОЙКИ
# =====================
ADMIN_USER = "admin"
ADMIN_PASS = "12345"
GEN_LIMIT = 30000

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# =====================
# ХРАНЕНИЕ В ПАМЯТИ
# =====================
links = {}                   # одноразовые ссылки
stats = {"generated": 0}     # счётчик генераций
sessions = set()             # активные сессии

# данные для отображения после редиректа
last_link = None
last_target = ""

# =====================
# УТИЛИТЫ
# =====================
def get_session_id(request: Request):
    return request.cookies.get("session_id")

def is_logged_in(request: Request):
    sid = get_session_id(request)
    return sid in sessions

# =====================
# LOGIN
# =====================
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
def login_action(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    if username == ADMIN_USER and password == ADMIN_PASS:
        sid = secrets.token_urlsafe(16)
        sessions.add(sid)

        response = RedirectResponse("/", status_code=302)
        response.set_cookie(
            key="session_id",
            value=sid,
            httponly=True,
            samesite="lax"
        )
        return response

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Неверный логин или пароль"}
    )

# =====================
# HOME (GET)
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
            "target_url": last_target
        }
    )

# =====================
# CREATE LINK (POST → REDIRECT)
# =====================
@app.post("/create")
def create(request: Request, target_url: str = Form(...)):
    global last_link, last_target

    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    if stats["generated"] >= GEN_LIMIT:
        return HTMLResponse("❌ Лимит генераций исчерпан", status_code=403)

    code = secrets.token_urlsafe(3)
    links[code] = target_url
    stats["generated"] += 1

    base = str(request.base_url).rstrip("/")
    last_link = f"{base}/l/{code}"
    last_target = target_url

    # 🔑 ВАЖНО: редирект, а не HTML
    return RedirectResponse("/", status_code=302)

# =====================
# OPEN ONE-TIME LINK
# =====================
@app.api_route("/l/{code}", methods=["GET", "HEAD"])
def open_link(code: str):
    if code not in links:
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    url = links[code]
    del links[code]

    return RedirectResponse(url)
