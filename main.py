import secrets
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

GEN_LIMIT = 30000

app = FastAPI()
templates = Jinja2Templates(directory="templates")

links = {}
stats = {"generated": 0}

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
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

@app.post("/create", response_class=HTMLResponse)
def create(request: Request, target_url: str = Form(...)):
    if stats["generated"] >= GEN_LIMIT:
        return HTMLResponse("Лимит исчерпан", status_code=403)

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

@app.api_route("/{code}", methods=["GET", "HEAD"])
def open_link(code: str):
    if code not in links:
        return HTMLResponse("Ссылка недействительна", status_code=410)

    links[code]["opens"] += 1
    if links[code]["opens"] == 1:
        return HTMLResponse("Активировано. Открой ещё раз.")

    url = links[code]["url"]
    del links[code]
    return RedirectResponse(url)
