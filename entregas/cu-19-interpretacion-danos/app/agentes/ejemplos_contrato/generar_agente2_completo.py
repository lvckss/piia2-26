"""Genera `agente2_salida_completa.json`: la salida de `agente2()` (#32, #97) para el ejemplo del contrato.

Usa el `agente2()` real (costes, temas, diagnostico y justificacion) con el RAG y el LLM simulados, para que
el ejemplo sea reproducible sin PostgreSQL, sin clave y sin gasto:
- el RAG devuelve, por tema, el pasaje literal de la poliza `P-TR-FR300` del paquete de la empresa;
- el LLM es un cliente falso con un texto y unas citas escritos a mano que cumplen las reglas del ADR 0009.

Plan: specs/97-justificacion-llm-normativa.md (slice 4). Necesita `piia2_paquete_datos/` y `psycopg`
(dependencia de `normativa_rag`, aunque aqui no se conecta a la base).

    python generar_agente2_completo.py      (desde esta carpeta)
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "agente_recuperacion"))
import agente2  # noqa: E402

POLIZA = AQUI.parents[4] / "piia2_paquete_datos" / "docs" / "polizas_sinteticas" / "P-TR-FR300.md"
FUENTE = "docs/polizas_sinteticas/P-TR-FR300.md#2. Coberturas incluidas"
APARTADO_POR_TEMA = {"Daños de cristal": "2.2 ", "Daños propios por colisión": "2.3 "}
RESPUESTAS = {
    "Daños de cristal": {
        "texto": "La póliza cubre la rotura de lunas (parabrisas, lunas laterales y luneta) con un límite por "
                 "anualidad.",
        "citas": ["**Rotura de lunas** (parabrisas, lunas laterales y luneta) con límite de 1500 EUR por anualidad"],
    },
    "Daños propios por colisión": {
        "texto": "La póliza cubre los daños propios por colisión, vuelco, atropello de animales y actos "
                 "vandálicos, con una franquicia por siniestro.",
        "citas": ["**Daños propios por colisión, vuelco, atropello de animales y actos vandálicos** con "
                  "franquicia de 300 EUR por siniestro."],
    },
}


def _clave(tema: str) -> str:
    return next(k for k in APARTADO_POR_TEMA if tema.startswith(k))


def _rag_simulado(tema: str, k: int = 4, poliza_id: str = "") -> list[dict]:
    lineas = POLIZA.read_text(encoding="utf-8").splitlines()
    pasaje = next(l for l in lineas if l.startswith(APARTADO_POR_TEMA[_clave(tema)]))
    return [{"tema": tema, "extracto": pasaje, "fuente": FUENTE}]


class _Cliente:
    """Cliente falso con la forma de `client.chat.completions.create` (ADR 0003)."""

    def __init__(self) -> None:
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, model: str, messages: list[dict], response_format: dict):
        tema = json.loads(messages[-1]["content"])["tema"]
        texto = json.dumps(RESPUESTAS[_clave(tema)], ensure_ascii=False)
        mensaje = type("M", (), {"content": texto})()
        return type("R", (), {"choices": [type("C", (), {"message": mensaje})()], "usage": None})()


def main() -> int:
    a1 = json.loads((AQUI / "agente1_salida.json").read_text(encoding="utf-8"))
    contexto = json.loads((AQUI / "contexto_siniestro.json").read_text(encoding="utf-8"))
    agente2.buscar_normativa = _rag_simulado
    with tempfile.TemporaryDirectory() as cache:
        salida = agente2.agente2(a1, contexto, cliente=_Cliente(), modelo="ejemplo", autorizado=True, cache_dir=cache)
    destino = AQUI / "agente2_salida_completa.json"
    destino.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    estados = [j["estado"] for j in salida["justificaciones"]]
    print(f"{destino.name}: diagnostico {salida['diagnostico_rag']['estado']}, justificaciones {estados}")
    return 0 if estados and all(e == "generada" for e in estados) else 1


if __name__ == "__main__":
    sys.exit(main())
