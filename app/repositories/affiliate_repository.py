from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import settings
from app.core.logger import get_logger

from app.models.affiliate import Affiliate

logger = get_logger(__name__)



class AffiliateRepository:
    """Repositorio encargado de cargar y consultar los afiliados."""

    def __init__(self) -> None:
        self._dataframe: pd.DataFrame | None = None

    def load_data(self) -> None:
        """
        Carga en memoria la hoja del Excel que contiene los afiliados.
        """

        excel_path = Path(settings.data_path) / settings.excel_file

        logger.info(f"Cargando archivo: {excel_path}")

        excel = pd.ExcelFile(excel_path)

        for sheet in excel.sheet_names:

            df = pd.read_excel(excel_path, sheet_name=sheet)

            if "id_afiliado" in df.columns:

                self._dataframe = df.fillna("")

                logger.info(
                    f"Hoja '{sheet}' cargada correctamente "
                    f"con {len(df)} afiliados."
                )

                return

        raise ValueError(
            "No se encontró ninguna hoja con la columna 'id_afiliado'."
        )

    def get_by_id(self, affiliate_id: str) -> Affiliate | None:
        """
        Busca un afiliado por su identificador.

        Args:
            affiliate_id: Identificador único del afiliado.

        Returns:
            Un objeto Affiliate si existe, de lo contrario None.
        """

        if self._dataframe is None:
            raise RuntimeError(
                "Debe ejecutar load_data() antes de consultar afiliados."
            )

        result = self._dataframe.loc[
            self._dataframe["id_afiliado"] == affiliate_id
        ]

        if result.empty:
            logger.warning(f"Afiliado no encontrado: {affiliate_id}")
            return None

        affiliate_data = result.iloc[0].to_dict()

        affiliate_data["numero_documento"] = str(
            affiliate_data["numero_documento"]
        )

        affiliate_data["telefono_contacto"] = str(
            affiliate_data["telefono_contacto"]
        )

        # fillna("") convierte NaT/None en "" en campos opcionales.
        # Pydantic no puede parsear "" como date, así que lo revertimos a None.
        optional_str_fields = {
            "parentesco",
            "servicio_autorizado",
            "numero_autorizacion",
            "descripcion_preexistencia",
        }
        optional_date_fields = {
            "fecha_autorizacion",
            "vigencia_autorizacion",
        }

        for field in optional_str_fields | optional_date_fields:
            if affiliate_data.get(field) == "":
                affiliate_data[field] = None

        return Affiliate(**affiliate_data)