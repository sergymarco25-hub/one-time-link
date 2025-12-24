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

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# =====================
# ХРАНЕНИЕ В ПАМЯТИ
# =====================
links = {}
stats = {"generated": 0}
sessions = set()  # активные сессии

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
            "session_id",
            sid,
            httponly=True,
            samesite="lax"
        )
        return response

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Неверный логин или пароль"}
    )

# =====================
# HOME
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
            "link": None,
            "target_url": ""
        }
    )

# =====================
# CREATE LINK
# =====================
@app.post("/create", response_class=HTMLResponse)
def create(request: Request, target_url: str = Form(...)):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

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
@app.api_route("/{code}", methods=["GET", "HEAD"])
def open_link(code: str):
    if code not in links:
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    links[code]["opens"] += 1

    # защита от предпросмотра
    if links[code]["opens"] == 1:
        return HTMLResponse("⏳ Ссылка активирована. Откройте её ещё раз.")

    url = links[code]["url"]
    del links[code]
    return RedirectResponse(url)
