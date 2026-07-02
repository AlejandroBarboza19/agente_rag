from functools import lru_cache
from app.services.rag_service import RAGService
from app.services.llm_service import LLMService
from app.services.consultation_service import ConsultationService
from app.repositories.affiliate_repository import AffiliateRepository
from app.services.excel_service import ExcelService


@lru_cache
def get_affiliate_repository() -> AffiliateRepository:
    """
    Retorna una única instancia del repositorio de afiliados.
    """

    repository = AffiliateRepository()
    repository.load_data()

    return repository


@lru_cache
def get_excel_service() -> ExcelService:
    """
    Retorna una única instancia del servicio de afiliados.
    """

    return ExcelService(get_affiliate_repository())

@lru_cache
def get_consultation_service() -> ConsultationService:
    return ConsultationService(
        get_excel_service(),
        RAGService(),
        LLMService(),
    )