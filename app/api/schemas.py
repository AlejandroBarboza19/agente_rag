from typing import List
from pydantic import BaseModel


class ConsultaRequest(BaseModel):
    afiliado_id: str
    consulta: str


class ConsultaResponse(BaseModel):
    estado: str
    explicacion: str
    fuentes: List[str]