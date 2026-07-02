from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Modelo multilingüe liviano optimizado para CPU en Docker.
    paraphrase-multilingual-MiniLM-L12-v2: soporta 50+ idiomas incluyendo español,
    ~120MB vs ~570MB de bge-m3, significativamente más rápido en CPU sin GPU.
    Para entornos con GPU o Linux nativo, cambiar a BAAI/bge-m3 para mejor precisión.
    """
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )