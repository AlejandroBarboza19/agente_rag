from functools import lru_cache

from langchain_chroma import Chroma

from app.rag.embeddings import get_embeddings


@lru_cache(maxsize=1)
def get_vector_store(persist_directory: str = "chroma") -> Chroma:
    """
    Inicializa el vector store de ChromaDB una sola vez.
    """
    return Chroma(
        persist_directory=persist_directory,
        embedding_function=get_embeddings()
    )