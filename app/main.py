from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import router
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación."""
    logger.info("Iniciando aplicación...")
    logger.info(f"Aplicación: {settings.app_name}")
    logger.info(f"Versión: {settings.app_version}")

    yield

    logger.info("Cerrando aplicación...")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Asistente Inteligente de Cobertura Médica basado en RAG.",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

app.include_router(router, prefix="/api")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
