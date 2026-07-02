"""
Configuración centralizada del sistema de logging.

Este módulo configura el logger de la aplicación para registrar eventos
tanto en consola como en un archivo de log.

Características:
- Salida en consola.
- Archivo logs/app.log.
- Nivel configurable desde .env.
- Formato uniforme.
- Soporte para loggers por módulo.
"""

import logging
from pathlib import Path

from app.core.config import settings

# =============================================================================
# RUTAS
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOG_FILE = LOGS_DIR / "app.log"

# =============================================================================
# CONFIGURACIÓN DEL LOGGER
# =============================================================================

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# Logger principal del proyecto
logger = logging.getLogger("agente_rag")



# FUNCIÓN AUXILIAR


def get_logger(name: str) -> logging.Logger:
    """
    Retorna un logger asociado al módulo que lo solicita.

    Parameters
    ----------
    name : str
        Nombre del módulo (__name__).

    Returns
    -------
    logging.Logger
        Instancia configurada del logger.
    """
    return logging.getLogger(name)