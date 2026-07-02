import asyncio

from fastapi import APIRouter, Depends

from app.api.schemas import ConsultaRequest
from app.core.dependencies import get_consultation_service
from app.services.consultation_service import ConsultationService

router = APIRouter()


@router.post("/consulta")
async def consulta(
    request: ConsultaRequest,
    service: ConsultationService = Depends(get_consultation_service),
):
    result = await asyncio.to_thread(
        service.process,
        request.afiliado_id,
        request.consulta,
    )

    return {
        "estado":        result.get("estado", "No determinado"),
        "explicacion":   result.get("explicacion", ""),
        "justificacion": result.get("justificacion", ""),
        "condiciones":   result.get("condiciones"),
        "fuentes":       result.get("fuentes", []),
    }
