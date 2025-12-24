import secrets
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

# =====================
# НАСТРОЙКИ
# =====================
ADMIN_USER = "admin"
ADMIN_PASS = "12345"
GEN_LIMIT = 30

security = HTTPBasic()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# =====================
# ХРАНЕНИЕ В ПАМЯТИ
# =====================
links = {}
stats = {"generated": 0}

# =====================
# AUTH CHECK
# =====================
def check_auth(credentials: HTTPBasicCredentials = Depends(security)):
    correct_user = secrets.compare_digest(credentials.username, ADMIN_USER)
    correct_pass = secrets.compare_digest(credentials.password, ADMIN_PASS)

    if not (correct_user and correct_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )

# =====================
# HOME
# =====================
@app.get("/", response_class=HTMLResponse)
def home(request: Request, auth=Depends(check_auth)):
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
def create(
    request: Request,
    target_url: str = Form(...),
    auth=Depends(check_auth)
):
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

    # первый заход — защита от предпросмотра
    if links[code]["opens"] == 1:
        return HTMLResponse("⏳ Ссылка активирована. Откройте её ещё раз.")

    url = links[code]["url"]
    del links[code]
    return RedirectResponse(url)
