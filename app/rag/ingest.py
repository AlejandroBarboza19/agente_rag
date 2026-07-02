"""
ingest.py
=========
Pipeline de ingesta de documentos hacia ChromaDB.

Mejoras respecto a la versión original:
- chunk_size reducido a 500 (granularidad mayor, mejor recall en RAG)
- chunk_overlap 80 para preservar contexto entre chunks
- Metadata enriquecida: source_short (DOC1/DOC2/DOC3) para que el LLM
  pueda citarla con el nombre corto que usa en la justificacion
- Limpieza de la coleccion antes de reingestar para evitar duplicados
- Soporte DOCX y PDF mediante loaders independientes
"""

import re
from pathlib import Path

from docx import Document as DocxDocument
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader

from app.rag.vector_store import get_vector_store

DATA_PATH = Path("data")

# Mapeo nombre_archivo → nombre_corto que usa el LLM en justificacion
SOURCE_ALIAS = {
    "DOC1_Manual_de_Beneficios.docx":           "DOC1",
    "DOC2_Terminos_y_Condiciones.docx":          "DOC2",
    "DOC3_Criterios_de_Necesidad_Medica.docx":   "DOC3",
    "DOC1_Manual_de_Beneficios.pdf":             "DOC1",
    "DOC2_Terminos_y_Condiciones.pdf":           "DOC2",
    "DOC3_Criterios_de_Necesidad_Medica.pdf":    "DOC3",
}

# Archivos a ingestar (DOCX tiene prioridad sobre PDF si ambos existen)
DOCUMENT_FILES = [
    "DOC1_Manual_de_Beneficios.docx",
    "DOC2_Terminos_y_Condiciones.docx",
    "DOC3_Criterios_de_Necesidad_Medica.docx",
]


# ─────────────────────────────────────────────────────────────────────────────
# Loaders
# ─────────────────────────────────────────────────────────────────────────────

def _read_docx(file_path: Path) -> str:
    """Lee un DOCX preservando encabezados y párrafos."""
    doc = DocxDocument(file_path)
    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        # Marcar encabezados con ## para que el splitter los respete como límites
        if para.style and para.style.name and para.style.name.startswith("Heading"):
            text = f"\n## {text}\n"
        paragraphs.append(text)
    return "\n".join(paragraphs)


def _read_pdf(file_path: Path) -> str:
    """Lee un PDF usando PyPDFLoader."""
    loader = PyPDFLoader(str(file_path))
    pages  = loader.load()
    return "\n".join(p.page_content for p in pages)


def _load_document(filename: str) -> dict | None:
    """Carga un documento y retorna {text, source, source_short}."""
    path = DATA_PATH / filename
    if not path.exists():
        print(f"  [SKIP] No encontrado: {path}")
        return None

    ext = path.suffix.lower()
    if ext == ".docx":
        text = _read_docx(path)
    elif ext == ".pdf":
        text = _read_pdf(path)
    else:
        print(f"  [SKIP] Formato no soportado: {filename}")
        return None

    source_short = SOURCE_ALIAS.get(filename, filename.split(".")[0])
    print(f"  [OK] {filename} — {len(text)} chars — alias: {source_short}")
    return {"text": text, "source": filename, "source_short": source_short}


# ─────────────────────────────────────────────────────────────────────────────
# Splitter
# ─────────────────────────────────────────────────────────────────────────────

def _split_documents(documents: list[dict]) -> list[dict]:
    """
    Divide los documentos en chunks con:
    - chunk_size=500: granularidad alta para mejor precision en recuperacion
    - chunk_overlap=80: preserva contexto entre chunks adyacentes
    - Separadores que respetan estructura de secciones
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=80,
        separators=["\n## ", "\n\n", "\n", ". ", " "],
        length_function=len,
    )

    chunks = []
    for doc in documents:
        parts = splitter.split_text(doc["text"])
        # Filtrar chunks demasiado cortos (encabezados solos, ruido)
        parts = [p.strip() for p in parts if len(p.strip()) >= 80]

        for i, part in enumerate(parts):
            chunks.append({
                "text":         part,
                "source":       doc["source"],
                "source_short": doc["source_short"],
                "chunk_index":  i,
                "total_chunks": len(parts),
            })

    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline principal
# ─────────────────────────────────────────────────────────────────────────────

def ingest(clean: bool = True) -> int:
    """
    Pipeline completo de ingesta.

    Args:
        clean: Si True, limpia la coleccion antes de reingestar
               para evitar duplicados.

    Returns:
        Numero de chunks ingresados.
    """
    print("\n=== INICIO DE INGESTA ===")

    vector_store = get_vector_store()

    # ── Limpiar coleccion existente ───────────────────────────────────────────
    if clean:
        collection = vector_store._collection
        existing   = collection.count()
        if existing > 0:
            print(f"Limpiando {existing} chunks existentes...")
            all_ids = collection.get()["ids"]
            collection.delete(ids=all_ids)
            print(f"  Coleccion limpiada.")
        else:
            print("  Coleccion ya vacia.")

    # ── Cargar documentos ─────────────────────────────────────────────────────
    print("\nCargando documentos...")
    documents = []
    for filename in DOCUMENT_FILES:
        doc = _load_document(filename)
        if doc:
            documents.append(doc)

    if not documents:
        raise RuntimeError("No se encontro ningun documento para ingestar.")

    # ── Segmentar ─────────────────────────────────────────────────────────────
    print("\nSegmentando...")
    chunks = _split_documents(documents)

    from collections import Counter
    dist = Counter(c["source_short"] for c in chunks)
    print(f"  Total chunks: {len(chunks)}")
    for src, count in sorted(dist.items()):
        print(f"    {src}: {count} chunks")

    # ── Ingestar en ChromaDB ──────────────────────────────────────────────────
    print("\nIngestando en ChromaDB...")
    texts     = [c["text"] for c in chunks]
    metadatas = [
        {
            "source":       c["source"],
            "source_short": c["source_short"],
            "chunk_index":  c["chunk_index"],
        }
        for c in chunks
    ]

    # Ingestar en lotes para evitar timeouts con modelos de embedding locales
    batch_size = 50
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i + batch_size]
        batch_meta  = metadatas[i:i + batch_size]
        vector_store.add_texts(texts=batch_texts, metadatas=batch_meta)
        print(f"  Batch {i // batch_size + 1}: {len(batch_texts)} chunks ingresados")

    total = vector_store._collection.count()
    print(f"\n=== INGESTA COMPLETADA: {total} chunks en ChromaDB ===\n")
    return total


if __name__ == "__main__":
    ingest(clean=True)
