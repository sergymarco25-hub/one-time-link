import secrets
import json
from pathlib import Path
from fastapi import (
    FastAPI,
    Request,
    Form,
    Depends,
    HTTPException
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# =========================
# 🔐 АВТОРИЗАЦИЯ
# =========================
security = HTTPBasic()

USERNAME = "admin"
PASSWORD = "12345"

def check_auth(credentials: HTTPBasicCredentials = Depends(security)):
    if not (
        secrets.compare_digest(credentials.username, USERNAME)
        and secrets.compare_digest(credentials.password, PASSWORD)
    ):
        raise HTTPException(
            status_code=401,
            headers={"WWW-Authenticate": "Basic"},
        )

# =========================
# ⚙️ НАСТРОЙКИ
# =========================
GENERATION_LIMIT = 30000
STATS_FILE = Path("stats.json")

# =========================
# 📊 ЗАГРУЗКА / СОХРАНЕНИЕ
# =========================
def load_stats():
    if not STATS_FILE.exists():
        return {"total_generated": 0}
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_stats(stats):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f)

stats = load_stats()

# =========================
# 🔗 ССЫЛКИ
# =========================
links = {}

def generate_code():
    return secrets.token_urlsafe(3)

# =========================
# 🏠 ГЛАВНАЯ
# =========================
@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    _: HTTPBasicCredentials = Depends(check_auth)
):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "target_url": "",
            "link": None,
            "total": stats["total_generated"],
            "limit": GENERATION_LIMIT,
            "remaining": GENERATION_LIMIT - stats["total_generated"]
        }
    )

# =========================
# ➕ СОЗДАНИЕ ССЫЛКИ
# =========================
@app.post("/create", response_class=HTMLResponse)
def create_link(
    request: Request,
    target_url: str = Form(...),
    _: HTTPBasicCredentials = Depends(check_auth)
):
    if stats["total_generated"] >= GENERATION_LIMIT:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "target_url": target_url,
                "error": "❌ Лимит генераций исчерпан",
                "total": stats["total_generated"],
                "limit": GENERATION_LIMIT,
                "remaining": 0
            }
        )

    code = generate_code()
    links[code] = {
        "url": target_url,
        "opens": 0
    }

    stats["total_generated"] += 1
    save_stats(stats)

    base_url = str(request.base_url).rstrip("/")
    full_link = f"{base_url}/{code}"

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "target_url": target_url,
            "link": full_link,
            "total": stats["total_generated"],
            "limit": GENERATION_LIMIT,
            "remaining": GENERATION_LIMIT - stats["total_generated"]
        }
    )

# =========================
# 🌍 ПУБЛИЧНАЯ ССЫЛКА
# =========================
@app.get("/{code}")
def open_link(code: str):
    if code not in links:
        return HTMLResponse("❌ Ссылка недействительна", status_code=410)

    data = links[code]
    data["opens"] += 1

    # 1-е открытие (предпросмотр)
    if data["opens"] == 1:
        return HTMLResponse("⏳ Ссылка активирована. Откройте её ещё раз.")

    # 2-е открытие
    if data["opens"] == 2:
        target = data["url"]
        links.pop(code)
        return RedirectResponse(target)

    return HTMLResponse("❌ Ссылка недействительна", status_code=410)
