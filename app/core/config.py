"""
Configuración centralizada de la aplicación.

Este módulo carga todas las variables de entorno desde el archivo .env
y las expone mediante un único objeto 'settings' para que puedan ser
utilizadas en cualquier parte del proyecto.
"""

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings


# Cargar automáticamente el archivo .env


BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings(BaseSettings):
    """
    Configuración global de la aplicación.
    """

    # Información de la aplicación
    app_name: str = Field(alias="APP_NAME")
    app_version: str = Field(alias="APP_VERSION")
    debug: bool = Field(alias="DEBUG")

    # OpenRouter
    openrouter_api_key: str = Field(alias="OPENROUTER_API_KEY")
    model_name: str = Field(alias="MODEL_NAME")

    # Embeddings
    embedding_model: str = Field(alias="EMBEDDING_MODEL")

    # Rutas
    chroma_path: str = Field(alias="CHROMA_PATH")
    data_path: str = Field(alias="DATA_PATH")
    excel_file: str = Field(alias="EXCEL_FILE")

    # Logging
    log_level: str = Field(alias="LOG_LEVEL")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()