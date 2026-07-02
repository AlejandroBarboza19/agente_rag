from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import JsonOutputParser

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_SYSTEM_PROMPT_PATH = _PROMPTS_DIR / "system_prompt.txt"
_ANSWER_PROMPT_PATH  = _PROMPTS_DIR / "answer_prompt.txt"


def _load_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class LLMService:
    """
    Servicio LLM construido sobre LangChain.

    - El system prompt se inyecta como SystemMessage fija (sin interpolación),
      lo que evita que las llaves del JSON de ejemplo sean interpretadas como
      variables de template.
    - El human prompt usa ChatPromptTemplate con las variables del afiliado.
    """

    def __init__(self):
        self._llm = ChatOpenAI(
            model=settings.model_name,
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=0.1,
            max_tokens=1024,
        )

        # System prompt: se carga como texto plano, sin interpolación de vars
        system_text = _load_prompt(_SYSTEM_PROMPT_PATH)
        answer_template = _load_prompt(_ANSWER_PROMPT_PATH)

        # Solo el human message usa variables de template
        self._prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_text),
            HumanMessagePromptTemplate.from_template(answer_template),
        ])

        self._parser = JsonOutputParser()
        self._chain  = self._prompt | self._llm | self._parser

    def generate(self, prompt_vars: dict) -> dict:
        """
        Invoca el chain con las variables del prompt y retorna un dict.

        Args:
            prompt_vars: Variables requeridas por answer_prompt.txt.

        Returns:
            Dict con claves: estado, explicacion, justificacion, condiciones.
        """
        logger.info(f"Invocando LLM — modelo: {settings.model_name}")

        try:
            result = self._chain.invoke(prompt_vars)
            logger.info(f"Estado determinado: {result.get('estado')}")
            return result

        except Exception as exc:
            logger.error(f"Error al invocar el LLM: {exc}")
            return {
                "estado":        "Error",
                "explicacion":   f"No se pudo obtener respuesta del modelo: {exc}",
                "justificacion": "Error interno",
                "condiciones":   None,
            }
