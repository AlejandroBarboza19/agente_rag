from app.core.logger import get_logger
from app.models.affiliate import Affiliate
from app.services.excel_service import ExcelService
from app.services.rag_service import RAGService
from app.services.llm_service import LLMService

logger = get_logger(__name__)

# Valores exactos que usa el Excel (ajustar si el Excel usa otros literales)
_ESTADO_ACTIVO   = "Activo"
_PAGOS_AL_DIA    = "Al día"
_CARENCIA_MESES  = 6          # meses mínimos antes de cubrir procedimientos electivos


class ConsultationService:
    """Orquesta el flujo completo del asistente de cobertura médica."""

    def __init__(
        self,
        excel_service: ExcelService,
        rag_service: RAGService,
        llm_service: LLMService,
    ):
        self.excel_service = excel_service
        self.rag_service   = rag_service
        self.llm_service   = llm_service

    # ─────────────────────────────────────────────────────────────────────────
    # Reglas de elegibilidad deterministas (no dependen del LLM ni del RAG)
    # ─────────────────────────────────────────────────────────────────────────

    def _check_eligibility(self, affiliate: Affiliate) -> dict | None:
        """
        Aplica reglas de negocio duras antes de consultar al LLM.

        Retorna un dict de respuesta final si el afiliado NO es elegible,
        o None si pasa todos los filtros y debe continuar al LLM.
        """
        # 1. Afiliación inactiva
        if affiliate.estado_afiliacion != _ESTADO_ACTIVO:
            logger.info(f"Afiliado {affiliate.id_afiliado} inactivo: {affiliate.estado_afiliacion}")
            return {
                "estado":        "No cubierto",
                "explicacion":   (
                    f"La afiliación de {affiliate.nombre_completo} no está activa "
                    f"(estado: {affiliate.estado_afiliacion}). No hay cobertura hasta regularizar."
                ),
                "justificacion": "Regla de elegibilidad: afiliación inactiva (DOC2)",
                "condiciones":   None,
                "fuentes":       [],
            }

        # 2. Mora en pagos
        if affiliate.estado_pagos != _PAGOS_AL_DIA:
            logger.info(f"Afiliado {affiliate.id_afiliado} en mora: {affiliate.dias_mora} días")
            return {
                "estado":        "No cubierto",
                "explicacion":   (
                    f"{affiliate.nombre_completo} presenta mora en sus pagos "
                    f"({affiliate.dias_mora} días, valor pendiente: "
                    f"${affiliate.valor_pendiente_cop:,} COP). "
                    "La cobertura está suspendida hasta regularizar el estado de pagos."
                ),
                "justificacion": "Regla de elegibilidad: mora en pagos suspende cobertura (DOC2)",
                "condiciones":   "Regularizar pagos para restablecer cobertura.",
                "fuentes":       ["DOC2"],
            }

        return None  # elegible → continuar al LLM

    def _build_eligibility_notes(self, affiliate: Affiliate) -> str:
        """
        Genera notas de advertencia sobre condiciones del afiliado
        que el LLM debe considerar al evaluar cobertura.
        """
        notes = []

        if affiliate.antiguedad_meses < _CARENCIA_MESES:
            notes.append(
                f"⚠ CARENCIA ACTIVA: antigüedad {affiliate.antiguedad_meses} meses "
                f"(mínimo requerido: {_CARENCIA_MESES} meses para procedimientos electivos)."
            )

        if affiliate.preexistencia_declarada.lower() in ("sí", "si", "yes", "true", "1"):
            desc = f" ({affiliate.descripcion_preexistencia})" if affiliate.descripcion_preexistencia else ""
            notes.append(
                f"⚠ PREEXISTENCIA DECLARADA{desc}: evaluar si la consulta está relacionada."
            )

        if affiliate.tiene_autorizacion_previa.lower() in ("sí", "si", "yes", "true", "1"):
            notes.append(
                f"⚠ REQUIERE AUTORIZACIÓN PREVIA: N° {affiliate.numero_autorizacion or 'no indicado'}, "
                f"servicio: {affiliate.servicio_autorizado or 'no especificado'}."
            )

        return "\n".join(notes) if notes else "Sin restricciones adicionales detectadas."

    # ─────────────────────────────────────────────────────────────────────────
    # Pipeline principal
    # ─────────────────────────────────────────────────────────────────────────

    def process(self, affiliate_id: str, query: str) -> dict:
        """
        Ejecuta el pipeline completo:
        1. Recuperar datos del afiliado
        2. Aplicar reglas de elegibilidad deterministas
        3. Buscar contexto RAG
        4. Invocar LLM para evaluar cobertura del plan
        """
        logger.info(f"Iniciando consulta — afiliado: {affiliate_id}")

        # ── 1. Afiliado ───────────────────────────────────────────────────────
        affiliate = self.excel_service.get_affiliate(affiliate_id)

        if not affiliate:
            return {
                "estado":        "No encontrado",
                "explicacion":   f"El ID '{affiliate_id}' no existe en la base de datos.",
                "justificacion": "N/A",
                "condiciones":   None,
                "fuentes":       [],
            }

        # ── 2. Elegibilidad determinista (sin LLM) ────────────────────────────
        eligibility_block = self._check_eligibility(affiliate)
        if eligibility_block:
            return eligibility_block

        # ── 3. Contexto RAG ───────────────────────────────────────────────────
        context_docs = self.rag_service.search(query)

        context_text = "\n\n".join(
            f"[Fuente #{i + 1} — {doc['source']}]\n{doc['content']}"
            for i, doc in enumerate(context_docs)
        ) if context_docs else "No se encontraron documentos relevantes para esta consulta."

        # ── 4. Notas de elegibilidad condicional para el LLM ─────────────────
        eligibility_notes = self._build_eligibility_notes(affiliate)

        # ── 5. Variables auxiliares ───────────────────────────────────────────
        descripcion_preexistencia = (
            f" ({affiliate.descripcion_preexistencia})"
            if affiliate.descripcion_preexistencia else ""
        )

        if (affiliate.tiene_autorizacion_previa.lower() in ("sí", "si", "yes", "true", "1")
                and affiliate.numero_autorizacion):
            info_autorizacion = (
                f" — N° {affiliate.numero_autorizacion}"
                f", servicio: {affiliate.servicio_autorizado or 'no especificado'}"
                f", vigente hasta: {affiliate.vigencia_autorizacion or 'no indicado'}"
            )
        else:
            info_autorizacion = ""

        # ── 6. Dict de variables para el PromptTemplate ───────────────────────
        prompt_vars = {
            "id_afiliado":               affiliate.id_afiliado,
            "nombre_completo":           affiliate.nombre_completo,
            "plan":                      affiliate.plan,
            "tipo_afiliado":             affiliate.tipo_afiliado,
            "estado_afiliacion":         affiliate.estado_afiliacion,
            "estado_pagos":              affiliate.estado_pagos,
            "dias_mora":                 str(affiliate.dias_mora),
            "antiguedad_meses":          str(affiliate.antiguedad_meses),
            "preexistencia_declarada":   affiliate.preexistencia_declarada,
            "descripcion_preexistencia": descripcion_preexistencia,
            "tiene_autorizacion_previa": affiliate.tiene_autorizacion_previa,
            "info_autorizacion":         info_autorizacion,
            "eligibility_notes":         eligibility_notes,
            "query":                     query,
            "context_text":              context_text,
        }

        # ── 7. LLM ────────────────────────────────────────────────────────────
        response = self.llm_service.generate(prompt_vars)

        logger.info(f"Consulta completada — estado: {response.get('estado')}")

        return {
            "estado":        response.get("estado", "No determinado"),
            "explicacion":   response.get("explicacion", ""),
            "justificacion": response.get("justificacion", ""),
            "condiciones":   response.get("condiciones"),
            "fuentes":       [doc["source"] for doc in context_docs],
        }
