from app.core.logger import get_logger
from app.models.affiliate import Affiliate
from app.repositories.affiliate_repository import AffiliateRepository

logger = get_logger(__name__)


class ExcelService:
    """Servicio encargado de gestionar la información de los afiliados."""

    def __init__(self, repository: AffiliateRepository) -> None:
        self._repository = repository

    def get_affiliate(self, affiliate_id: str) -> Affiliate | None:
        """
        Obtiene un afiliado por su identificador.

        Returns:
            Objeto Affiliate o None si no existe.
        """

        affiliate = self._repository.get_by_id(affiliate_id)

        if affiliate is None:
            logger.warning(f"Afiliado no encontrado: {affiliate_id}")
            return None

        return affiliate