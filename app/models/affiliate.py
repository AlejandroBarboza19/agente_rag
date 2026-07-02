from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict


class Affiliate(BaseModel):
    """Representa un afiliado del sistema de cobertura médica."""

    model_config = ConfigDict(from_attributes=True)

    id_afiliado: str
    tipo_documento: str
    numero_documento: str

    primer_nombre: str
    primer_apellido: str
    segundo_apellido: str

    sexo: str

    fecha_nacimiento: date
    edad: int

    ciudad: str
    departamento: str

    tipo_afiliado: str
    parentesco: Optional[str] = None

    plan: str

    fecha_afiliacion: date
    antiguedad_meses: int

    estado_afiliacion: str
    estado_pagos: str

    dias_mora: int
    valor_pendiente_cop: int

    tiene_autorizacion_previa: str
    servicio_autorizado: Optional[str] = None
    numero_autorizacion: Optional[str] = None
    fecha_autorizacion: Optional[date] = None
    vigencia_autorizacion: Optional[date] = None

    preexistencia_declarada: str
    descripcion_preexistencia: Optional[str] = None

    correo_contacto: str
    telefono_contacto: str

    @property
    def nombre_completo(self) -> str:
        """Retorna el nombre completo del afiliado."""

        return " ".join(
            filtro
            for filtro in [
                self.primer_nombre,
                self.primer_apellido,
                self.segundo_apellido,
            ]
            if filtro
        )