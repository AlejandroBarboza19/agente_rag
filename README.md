# Agente RAG — Cobertura Médica

Asistente inteligente que responde consultas sobre cobertura de planes de salud. Le das el ID del afiliado y la consulta, y el sistema cruza los documentos del plan con los datos del afiliado para decirte si está cubierto, por qué, y en qué condiciones.

## Cómo correrlo

La forma más rápida es con Docker. El compose levanta la ingesta primero y después la API, así no hay que hacer nada manual.

### Requisitos previos

- Docker Desktop corriendo
- Los archivos `DOC1_Manual_de_Beneficios.docx`, `DOC2_Terminos_y_Condiciones.docx`, `DOC3_Criterios_de_Necesidad_Medica.docx` y `BD_afiliados.xlsx` en la carpeta `data/`
- Una API key de OpenRouter

### 1. Configurar el .env

```bash
cp .env.example .env
```

Abre `.env` y agrega tu key:

```
OPENROUTER_API_KEY=sk-or-...
```

### 2. Levantar

```bash
docker compose up --build
```

Eso hace todo: instala dependencias, indexa los documentos en ChromaDB y levanta la API en `http://localhost:8000`.

Si los documentos ya estaban indexados de una corrida anterior, ChromaDB los conserva en el volumen y la ingesta es instantánea.

### 3. Probar

Abre `http://localhost:8000` para usar la interfaz web, o usa la API directamente:

```bash
curl -X POST http://localhost:8000/api/consulta \
  -H "Content-Type: application/json" \
  -d '{"afiliado_id": "A-00001", "consulta": "¿Está cubierta una resonancia magnética?"}'
```

Respuesta:

```json
{
  "estado": "Cubierto con condiciones",
  "explicacion": "...",
  "justificacion": "Fuente #1 (DOC1): ...",
  "condiciones": "Requiere autorización previa",
  "fuentes": ["DOC1", "DOC2"]
}
```

### 4. Correr la evaluación

```bash
docker compose run --rm agente_rag python -m tests.evaluate_rag
```

Resultados:

```
Casos evaluados          : 13
Casos perfectos (1.0)    : 12/13
Precisión clasificación  : 100.0%
Trazabilidad de fuentes  : 91.7%
Score global ponderado   : 96.9%
```

---

## Cómo está estructurado

```
agente_rag/
├── app/
│   ├── api/            # rutas y schemas de entrada/salida
│   ├── core/           # config, logger
│   ├── models/         # modelo Pydantic del afiliado
│   ├── prompts/        # system_prompt.txt y answer_prompt.txt
│   ├── rag/            # ingesta, embeddings, vector store
│   ├── repositories/   # lectura del Excel
│   ├── services/       # lógica: consultation, rag, llm, excel
│   ├── static/
│   ├── templates/
│   └── main.py
├── data/               # documentos DOCX y BD_afiliados.xlsx
├── tests/
│   └── evaluate_rag.py
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## Por qué tomé cada decisión

**FastAPI**
Porque es el estándar para APIs en Python cuando el rendimiento importa y quieres tipado automático con Pydantic. También genera documentación interactiva en `/docs` sin configuración extra.

**LangChain para la orquestación**
Necesitaba conectar el modelo de embeddings, el vector store y el LLM en un chain. LangChain tiene integraciones nativas con ChromaDB, HuggingFace y OpenAI-compatible APIs, lo que redujo bastante el código de pegamento. El chain queda declarativo: `prompt | llm | parser`.

**ChromaDB como vector store**
Es local, no necesita infraestructura adicional y persiste en disco. Para el volumen de documentos de este proyecto (3 docs, ~38 chunks) es más que suficiente y no agrega complejidad operacional.

**paraphrase-multilingual-MiniLM-L12-v2 para embeddings**
Modelo multilingüe que soporta 50+ idiomas incluyendo español técnico, sin fine-tuning. ~120MB, corre completamente local sin costo por llamada ni dependencia de APIs externas. Más rápido que alternativas más pesadas en CPU, lo que lo hace ideal para despliegue en Docker. Para producción con mayor volumen de consultas, usar una API de embeddings como `text-embedding-3-small` de OpenAI reduciría la latencia al eliminar la carga del modelo en memoria, a cambio de agregar una dependencia externa y costo por uso.

**Gemini 2.5 Flash via OpenRouter**
Flash es el punto justo entre velocidad y capacidad de razonamiento para este tipo de tarea. Lo uso vía OpenRouter para no acoplarme a la API de Google directamente y poder cambiar de modelo cambiando una variable de entorno.

**Lógica determinista antes del LLM**
Las reglas de mora y suspensión son binarias: o el afiliado está al día o no lo está. No tiene sentido mandarle eso al modelo cuando se puede resolver con datos del Excel. Separar esto del LLM también garantiza que esos casos nunca fallen por alucinación.

**chunk_size=500**
Con 1000 chars los chunks mezclaban temas distintos del mismo documento y el RAG no recuperaba DOC1 para queries de cobertura básica. Con 500 cada chunk es temáticamente coherente y la recuperación mejoró. Lo validé corriendo la evaluación antes y después del cambio.

**Prompts en archivos .txt**
Para poder editarlos sin tocar código. También resuelve un problema concreto: cuando el prompt tiene ejemplos en JSON con llaves `{}`, LangChain los interpreta como variables de template. Al cargar el system prompt como `SystemMessage` fijo en vez de pasarlo por el template, ese problema desaparece.

**Docker multistage**
El stage `builder` tiene gcc y las herramientas de compilación. El stage `runtime` solo copia los paquetes ya compilados. La imagen final no tiene build tools, lo que la hace más pequeña y reduce la superficie de ataque.
