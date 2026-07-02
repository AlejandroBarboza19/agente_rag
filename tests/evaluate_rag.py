"""
evaluate_rag.py
===============
Módulo de Evaluación Autónoma del Agente RAG de Cobertura Médica.

Ejecutar desde la raíz del proyecto:
    python -m tests.evaluate_rag

Métricas evaluadas
------------------
- Precisión de clasificación  : estado generado vs. estado esperado (ground truth)
- Trazabilidad de fuentes      : presencia de la fuente esperada en 'justificacion'
- Score global                 : promedio ponderado de ambas métricas

Golden Dataset
--------------
Cada caso define:
  - id          : identificador único del escenario
  - categoria   : tipo de regla de negocio evaluada
  - afiliado_id : ID real en el Excel (o mock si no existe)
  - query       : consulta del usuario
  - expected_estado  : resultado esperado exacto
  - expected_fuente  : fuente documental que debe aparecer en justificacion
  - descripcion : descripción legible del escenario
"""

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── Añadir raíz del proyecto al path ─────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.dependencies import get_consultation_service  # noqa: E402

# ── Constantes ────────────────────────────────────────────────────────────────
VALID_ESTADOS = {"Cubierto", "No cubierto", "Cubierto con condiciones"}

# ─────────────────────────────────────────────────────────────────────────────
# Modelo de caso de prueba
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TestCase:
    id: str
    categoria: str
    afiliado_id: str
    query: str
    expected_estado: str
    expected_fuente: str          # substring esperado en 'justificacion'
    descripcion: str
    weight: float = 1.0           # peso relativo del caso en el score global


@dataclass
class CaseResult:
    case: TestCase
    actual_estado: str
    actual_justificacion: str
    actual_fuentes: list
    estado_ok: bool
    fuente_ok: bool
    score: float                  # 0.0 | 0.5 | 1.0
    error: Optional[str] = None
    latency_s: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Golden Dataset
# ─────────────────────────────────────────────────────────────────────────────

GOLDEN_DATASET: list[TestCase] = [

    # Grupo 1: Cobertura positiva - A-00002: Activo, Al dia, sin restricciones
    TestCase(
        id="COV-001",
        categoria="Cobertura positiva",
        afiliado_id="A-00002",
        query="Esta cubierta una consulta medica general?",
        expected_estado="Cubierto",
        expected_fuente="DOC1",
        descripcion="Afiliado activo, al dia. Consulta general debe estar cubierta.",
    ),
    TestCase(
        id="COV-002",
        categoria="Cobertura positiva",
        afiliado_id="A-00002",
        query="Tengo cobertura para examenes de laboratorio basicos?",
        expected_estado="Cubierto",
        expected_fuente="DOC1",
        descripcion="Laboratorios basicos cubiertos, afiliado activo sin restricciones.",
    ),
    # A-00005: Activo, Al dia, plan Esencial, sin preexistencia
    TestCase(
        id="COV-003",
        categoria="Cobertura positiva",
        afiliado_id="A-00005",
        query="Mi plan cubre medicamentos formulados por el medico?",
        expected_estado="Cubierto",
        expected_fuente="DOC1",
        descripcion="Afiliado Esencial activo, al dia. Medicamentos basicos cubiertos.",
    ),

    # Grupo 2: Exclusion por mora - A-00004: Activo, En mora, plan Clasico
    TestCase(
        id="MORA-001",
        categoria="Exclusion por mora",
        afiliado_id="A-00004",
        query="Puedo acceder a servicios medicos si estoy en mora?",
        expected_estado="No cubierto",
        expected_fuente="DOC2",
        descripcion="Afiliado Activo con mora. Cobertura suspendida segun DOC2.",
        weight=1.5,
    ),
    TestCase(
        id="MORA-002",
        categoria="Exclusion por mora",
        afiliado_id="A-00004",
        query="Puedo pedir una cirugia programada teniendo deuda pendiente?",
        expected_estado="No cubierto",
        expected_fuente="DOC2",
        descripcion="Cirugia programada bloqueada por mora en pagos.",
        weight=1.5,
    ),
    # A-00007: Activo, En mora, plan Premium
    TestCase(
        id="MORA-003",
        categoria="Exclusion por mora",
        afiliado_id="A-00007",
        query="Tengo cobertura para hospitalizacion con pagos pendientes?",
        expected_estado="No cubierto",
        expected_fuente="DOC2",
        descripcion="Afiliado Premium en mora. Hospitalizacion electiva bloqueada.",
        weight=1.5,
    ),

    # Grupo 3: Afiliacion suspendida - A-00023: Suspendido, En mora
    TestCase(
        id="SUS-001",
        categoria="Afiliacion suspendida",
        afiliado_id="A-00023",
        query="Tengo cobertura para consulta medica?",
        expected_estado="No cubierto",
        expected_fuente="DOC2",
        descripcion="Afiliado Suspendido. Sin cobertura activa.",
        weight=1.5,
    ),

    # Grupo 4: Periodo de carencia - A-00040: Activo, Al dia, 3 meses
    TestCase(
        id="CAR-001",
        categoria="Periodo de carencia",
        afiliado_id="A-00040",
        query="Puedo operarme con tan poco tiempo de afiliacion?",
        expected_estado="Cubierto con condiciones",
        expected_fuente="DOC2",
        descripcion="Afiliado con 3 meses. Cirugia electiva sujeta a carencia.",
        weight=1.2,
    ),
    # A-00051: Activo, Al dia, 1 mes
    TestCase(
        id="CAR-002",
        categoria="Periodo de carencia",
        afiliado_id="A-00051",
        query="Tengo cobertura para procedimientos especializados?",
        expected_estado="Cubierto con condiciones",
        expected_fuente="DOC2",
        descripcion="Afiliado con 1 mes. Aplica periodo de carencia.",
        weight=1.2,
    ),

    # Grupo 5: Preexistencias - A-00001: Activo, Al dia, preexistencia=Si
    TestCase(
        id="PREX-001",
        categoria="Preexistencia",
        afiliado_id="A-00001",
        query="Mi condicion preexistente esta cubierta por el plan?",
        expected_estado="Cubierto con condiciones",
        expected_fuente="DOC3",
        descripcion="Afiliado con preexistencia declarada. Cobertura condicionada segun DOC3.",
        weight=1.2,
    ),
    # A-00009: Activo, Al dia, preexistencia=Si, plan Premium
    TestCase(
        id="PREX-002",
        categoria="Preexistencia",
        afiliado_id="A-00009",
        query="Cubre medicamentos para enfermedades cronicas preexistentes?",
        expected_estado="Cubierto con condiciones",
        expected_fuente="DOC3",
        descripcion="Afiliado Premium con preexistencia. Medicamentos cronicos con condiciones.",
        weight=1.2,
    ),

    # Grupo 6: Autorizacion previa - A-00008: Activo, Al dia, autorizacion=Si
    TestCase(
        id="AUT-001",
        categoria="Autorizacion previa",
        afiliado_id="A-00008",
        query="Necesito autorizacion previa para una resonancia magnetica?",
        expected_estado="Cubierto con condiciones",
        expected_fuente="DOC1",
        descripcion="Afiliado con autorizacion previa registrada. Procedimiento condicionado.",
        weight=1.2,
    ),

    # Grupo 7: Afiliado inexistente
    TestCase(
        id="NEX-001",
        categoria="Afiliado no encontrado",
        afiliado_id="A-99999",
        query="Tengo cobertura para cualquier servicio?",
        expected_estado="No encontrado",
        expected_fuente="",
        descripcion="ID de afiliado inexistente en la base de datos.",
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Motor de evaluación
# ─────────────────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Normaliza texto para comparaciones case-insensitive."""
    return text.strip().lower()


def evaluate_case(service, case: TestCase) -> CaseResult:
    """Ejecuta un caso de prueba y retorna su resultado."""
    start = time.perf_counter()

    try:
        response = service.process(case.afiliado_id, case.query)
        latency  = time.perf_counter() - start

        actual_estado        = response.get("estado", "")
        actual_justificacion = response.get("justificacion", "") or ""
        actual_fuentes       = response.get("fuentes", [])

        # ── Métrica 1: precisión de clasificación ─────────────────────────
        estado_ok = _normalize(actual_estado) == _normalize(case.expected_estado)

        # ── Métrica 2: trazabilidad de fuentes ────────────────────────────
        if case.expected_fuente == "":
            # Casos sin fuente esperada (ej: afiliado no encontrado)
            fuente_ok = True
        else:
            fuente_ok = case.expected_fuente.lower() in actual_justificacion.lower()

        # ── Score del caso: 1.0 ambas OK | 0.5 solo estado | 0.0 ninguna ──
        if estado_ok and fuente_ok:
            score = 1.0
        elif estado_ok:
            score = 0.5
        else:
            score = 0.0

        return CaseResult(
            case=case,
            actual_estado=actual_estado,
            actual_justificacion=actual_justificacion,
            actual_fuentes=actual_fuentes,
            estado_ok=estado_ok,
            fuente_ok=fuente_ok,
            score=score,
            latency_s=latency,
        )

    except Exception as exc:
        latency = time.perf_counter() - start
        return CaseResult(
            case=case,
            actual_estado="ERROR",
            actual_justificacion="",
            actual_fuentes=[],
            estado_ok=False,
            fuente_ok=False,
            score=0.0,
            error=str(exc),
            latency_s=latency,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Reporter
# ─────────────────────────────────────────────────────────────────────────────

_GREEN  = "\033[92m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_BOLD   = "\033[1m"
_RESET  = "\033[0m"

def _icon(ok: bool) -> str:
    return f"{_GREEN}✓{_RESET}" if ok else f"{_RED}✗{_RESET}"


def print_report(results: list[CaseResult]) -> float:
    """Imprime el reporte completo y retorna el score global."""

    print(f"\n{'━'*72}")
    print(f"{_BOLD}  EVALUACIÓN AUTÓNOMA — AGENTE RAG DE COBERTURA MÉDICA{_RESET}")
    print(f"{'━'*72}\n")

    # ── Detalle por caso ──────────────────────────────────────────────────
    categories: dict[str, list[CaseResult]] = {}
    for r in results:
        categories.setdefault(r.case.categoria, []).append(r)

    for cat, cat_results in categories.items():
        cat_ok = sum(1 for r in cat_results if r.score == 1.0)
        print(f"{_CYAN}{_BOLD}▶ {cat} ({cat_ok}/{len(cat_results)} perfectos){_RESET}")

        for r in cat_results:
            score_color = _GREEN if r.score == 1.0 else (_YELLOW if r.score == 0.5 else _RED)
            print(f"  [{r.case.id}] {r.case.descripcion[:60]}")
            print(f"         Estado   : {_icon(r.estado_ok)} esperado={r.case.expected_estado!r:30} "
                  f"obtenido={r.actual_estado!r}")

            if r.case.expected_fuente:
                print(f"         Fuente   : {_icon(r.fuente_ok)} esperada={r.case.expected_fuente!r:30} "
                      f"{'encontrada' if r.fuente_ok else 'NO encontrada'} en justificacion")

            print(f"         Score    : {score_color}{r.score:.1f}{_RESET}  "
                  f"Latencia: {r.latency_s:.2f}s")

            if r.error:
                print(f"         {_RED}Error: {r.error}{_RESET}")

        print()

    # ── Métricas globales ─────────────────────────────────────────────────
    total_weight  = sum(r.case.weight for r in results)
    weighted_score = sum(r.score * r.case.weight for r in results) / total_weight if total_weight else 0

    precision_clasificacion = sum(1 for r in results if r.estado_ok) / len(results)
    trazabilidad_fuentes    = (
        sum(1 for r in results if r.fuente_ok and r.case.expected_fuente != "")
        / max(1, sum(1 for r in results if r.case.expected_fuente != ""))
    )
    avg_latency = sum(r.latency_s for r in results) / len(results)
    perfectos   = sum(1 for r in results if r.score == 1.0)

    print(f"{'━'*72}")
    print(f"{_BOLD}  RESUMEN GLOBAL{_RESET}")
    print(f"{'━'*72}")
    print(f"  Casos evaluados          : {len(results)}")
    print(f"  Casos perfectos (1.0)    : {perfectos}/{len(results)}")
    print(f"  Precisión clasificación  : {precision_clasificacion*100:.1f}%")
    print(f"  Trazabilidad de fuentes  : {trazabilidad_fuentes*100:.1f}%")
    print(f"  Score global ponderado   : {weighted_score*100:.1f}%")
    print(f"  Latencia promedio        : {avg_latency:.2f}s")
    print(f"{'━'*72}\n")

    # ── Tabla resumen (formato para documentación) ────────────────────────
    print(f"{_BOLD}  TABLA RESUMEN (Golden Dataset){_RESET}")
    print(f"  {'ID':<10} {'Categoría':<25} {'Esperado':<28} {'Obtenido':<28} {'Score':>5}")
    print(f"  {'-'*10} {'-'*25} {'-'*28} {'-'*28} {'-'*5}")
    for r in results:
        score_str = f"{r.score:.1f}"
        print(f"  {r.case.id:<10} {r.case.categoria:<25} "
              f"{r.case.expected_estado:<28} {r.actual_estado:<28} {score_str:>5}")
    print()

    return weighted_score


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{_BOLD}Inicializando servicios...{_RESET}")
    service = get_consultation_service()

    print(f"Ejecutando {len(GOLDEN_DATASET)} casos de prueba...\n")

    results = []
    for i, case in enumerate(GOLDEN_DATASET, 1):
        print(f"  [{i:02d}/{len(GOLDEN_DATASET)}] {case.id} — {case.descripcion[:55]}...", end=" ", flush=True)
        result = evaluate_case(service, case)
        icon   = "✓" if result.score == 1.0 else ("~" if result.score == 0.5 else "✗")
        print(f"{icon} ({result.latency_s:.1f}s)")
        results.append(result)

    global_score = print_report(results)

    # Exit code no-zero si score < 70%
    sys.exit(0 if global_score >= 0.70 else 1)


if __name__ == "__main__":
    main()
