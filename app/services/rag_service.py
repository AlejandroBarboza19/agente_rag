from app.core.logger import get_logger
from app.rag.vector_store import get_vector_store

logger = get_logger(__name__)


class RAGService:
    """Servicio encargado de recuperar contexto desde ChromaDB."""

    def __init__(self):
        self._vector_store = get_vector_store()

    def search(self, query: str, k: int = 5) -> list[dict]:
        """
        Recupera los chunks mas relevantes para la query.

        Usa source_short (DOC1/DOC2/DOC3) si esta disponible en metadata,
        para que el LLM pueda citarlo correctamente en justificacion.

        Args:
            query: Consulta del usuario.
            k: Numero maximo de chunks distintos a retornar.

        Returns:
            Lista de dicts con 'content' y 'source'.
        """
        logger.info(f"Buscando contexto en RAG: {query}")

        # Recuperar el doble para poder deduplicar por fuente
        results = self._vector_store.similarity_search(
            query=query,
            k=k * 3,
        )

        seen_sources = set()
        context = []

        for r in results:
            # Preferir source_short si existe, sino usar source completo
            source = (
                r.metadata.get("source_short")
                or r.metadata.get("source", "desconocido")
            )

            # Deduplicar por fuente para dar variedad de documentos
            if source in seen_sources:
                continue

            seen_sources.add(source)
            context.append({
                "content": r.page_content,
                "source":  source,
            })

            if len(context) >= k:
                break

        logger.info(f"Fuentes recuperadas: {[c['source'] for c in context]}")
        return context
