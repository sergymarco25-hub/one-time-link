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
active_tokens = set()

# =====================
# ПРОВЕРКА АВТОРИЗАЦИИ
# =====================
def is_logged_in(request: Request) -> bool:
    token = request.query_params.get("auth")
    return token in active_tokens

# =====================
# LOGIN
# =====================
@app.api_route("/login", methods=["GET", "POST"], response_class=HTMLResponse)
def login(
    request: Request,
    username: str = Form(None),
    password: str = Form(None),
):
    if request.method == "POST":
        if username == ADMIN_USER and password == ADMIN_PASS:
            token = secrets.token_urlsafe(16)
            active_tokens.add(token)
            return RedirectResponse(f"/?auth={token}", status_code=302)

        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Неверный логин или пароль"}
        )

    return templates.TemplateResponse("login.html", {"request": request})

# =====================
# HOME
# =====================
@app.api_route("/", methods=["GET", "POST"], response_class=HTMLResponse)
def home(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    auth = request.query_params.get("auth")

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "generated": stats["generated"],
            "limit": GEN_LIMIT,
            "remaining": GEN_LIMIT - stats["generated"],
            "link": None,
            "target_url": "",
            "auth": auth
        }
    )

# =====================
# CREATE LINK
# =====================
@app.post("/create", response_class=HTMLResponse)
def create(
    request: Request,
    target_url: str = Form(...),
    auth: str = Form(...)
):
    if auth not in active_tokens:
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
            "target_url": target_url,
            "auth": auth
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

    if links[code]["opens"] == 1:
        return HTMLResponse("⏳ Ссылка активирована. Откройте её ещё раз.")

    url = links[code]["url"]
    del links[code]
    return RedirectResponse(url)
