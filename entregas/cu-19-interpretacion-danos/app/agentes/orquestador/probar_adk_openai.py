"""Prueba autónoma de viabilidad de #33; no es el orquestador del producto.

Plan: https://github.com/lvckss/piia2-26/issues/33#issuecomment-6289598174.
"""

from decimal import Decimal
import json
import os
from pathlib import Path

MODELO = "gpt-6.1-sol"
ESFUERZO = "high"
MAX_LLAMADAS = 2
MAX_SALIDA = 4096
TIMEOUT = 120

# Evita descargas auxiliares del catálogo de precios al importar LiteLLM.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
os.environ.setdefault("LITELLM_MODE", "PRODUCTION")


def cargar_clave(env_file):
    """AC-003: leer solo la clave, sin ejecutar el archivo ni interpolarlo."""
    from dotenv import dotenv_values

    clave = (dotenv_values(env_file, interpolate=False).get("OPENAI_API_KEY")
             if Path(env_file).is_file() else os.environ.get("OPENAI_API_KEY"))
    if not clave or not clave.strip():
        raise ValueError("Falta OPENAI_API_KEY; no se ha llamado a la API")
    return clave.strip()


def _importe(texto):
    def objeto(pares):
        if len(dict(pares)) != len(pares):
            raise ValueError("Claves JSON duplicadas")
        return dict(pares)

    try:
        dato = json.loads(texto, parse_float=Decimal, parse_int=Decimal,
                          object_pairs_hook=objeto)
        valor = dato["total"]
        if (set(dato) != {"total"} or not isinstance(valor, Decimal)
                or not valor.is_finite() or valor != Decimal("1233.55")):
            raise ValueError("El importe no coincide con la tool")
        return valor
    except (TypeError, KeyError, json.JSONDecodeError) as e:
        raise ValueError("Respuesta ausente o no comprobable") from e


def comprobar_evidencia(evidencia):
    """AC-002/003: acreditar solo el recorrido completo del ejemplo de juguete."""
    if evidencia["completed"] is not True or evidencia["ejecuciones_tool"] != 1:
        raise ValueError("Ejecución incompleta o tool no ejecutada exactamente una vez")
    llamadas, respuestas = evidencia["llamadas"], evidencia["respuestas"]
    if len(llamadas) != 1 or len(respuestas) != 1:
        raise ValueError("Falta evidencia de una llamada y su respuesta")
    llamada, respuesta = llamadas[0], respuestas[0]
    if (not llamada["id"] or llamada["id"] != respuesta["id"]
            or llamada["name"] != "importe_prueba" or llamada["args"] != {}
            or respuesta["name"] != "importe_prueba"):
        raise ValueError("La respuesta no corresponde a la tool invocada")
    _importe(respuesta["response"].get("result"))
    _importe(evidencia["final"])


async def ejecutar(clave, evidencia):
    """AC-001/002: recorrido nativo ADK → LiteLLM → Responses API → tool."""
    import litellm
    from google.adk.agents import Agent
    from google.adk.agents.run_config import RunConfig
    from google.adk.models.lite_llm import LiteLlm
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    litellm.suppress_debug_info = True
    litellm.disable_aiohttp_transport = True
    litellm.num_retries = 0

    def importe_prueba() -> str:
        """Devuelve el importe de la prueba en JSON; no recibe argumentos."""
        evidencia["ejecuciones_tool"] += 1
        return json.dumps({"total": 1233.55})

    agent = Agent(
        name="prueba_adk_openai",
        model=LiteLlm(model=f"openai/responses/{MODELO}", api_key=clave,
                      api_base="https://api.openai.com/v1", reasoning_effort=ESFUERZO,
                      num_retries=0, max_retries=0, timeout=60,
                      max_completion_tokens=MAX_SALIDA),
        instruction="Call importe_prueba exactly once. Then return only its JSON result, unchanged.",
        tools=[importe_prueba],
    )
    evidencia["registro_tool"] = True
    async with InMemoryRunner(agent=agent, app_name="prueba_33") as runner:
        await runner.session_service.create_session(
            app_name="prueba_33", user_id="prueba", session_id="prueba")
        async for event in runner.run_async(
            user_id="prueba", session_id="prueba",
            new_message=types.Content(role="user", parts=[types.Part(text="Obtén el importe de la tool.")]),
            run_config=RunConfig(max_llm_calls=MAX_LLAMADAS),
        ):
            if event.error_code:
                raise ValueError("ADK devolvió un evento de error")
            evidencia["llamadas"].extend(c.model_dump(mode="json") for c in event.get_function_calls())
            evidencia["respuestas"].extend(r.model_dump(mode="json") for r in event.get_function_responses())
            if event.usage_metadata:
                evidencia["usage"].append(event.usage_metadata.model_dump(mode="json", exclude_none=True))
            if event.is_final_response() and event.content:
                if event.finish_reason != types.FinishReason.STOP:
                    raise ValueError("Respuesta final incompleta o ambigua")
                evidencia["final"] = "".join(p.text for p in event.content.parts if p.text and not p.thought)
        evidencia["completed"] = True


def main():
    import argparse
    import asyncio
    from datetime import datetime, timezone
    from importlib.metadata import version
    import logging
    import time

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(__file__).resolve().parents[3] / ".env")
    parser.add_argument("--ejecutar", action="store_true", help="Autoriza una tentativa real con coste API")
    args = parser.parse_args()
    if not args.ejecutar:
        parser.error("La llamada real requiere --ejecutar")
    logging.basicConfig(level=logging.ERROR)
    evidencia = {"completed": False, "registro_tool": False, "ejecuciones_tool": 0,
                 "llamadas": [], "respuestas": [], "final": None, "usage": []}
    informe = {"fecha_utc": datetime.now(timezone.utc).isoformat(), "modelo": MODELO,
               "reasoning_effort": ESFUERZO, "max_llm_calls": MAX_LLAMADAS,
               "max_output_tokens": MAX_SALIDA, "timeout_seconds": TIMEOUT, "retries": 0,
               "versions": {}, "evidencia": evidencia, "success": False}
    inicio, clave = time.monotonic(), ""
    try:
        clave = cargar_clave(args.env_file)  # Antes de importar ADK o acceder a red.
        informe["versions"] = {n: version(n) for n in ["google-adk", "litellm", "openai", "python-dotenv"]}
        asyncio.run(asyncio.wait_for(ejecutar(clave, evidencia), timeout=TIMEOUT))
        comprobar_evidencia(evidencia)
        informe["success"] = True
    except Exception as e:
        informe["error"] = {"type": type(e).__name__, "status_code": getattr(e, "status_code", None),
                            "message": str(e).replace(clave, "[REDACTED]")[:700] if clave else str(e)[:700]}
    informe["duration_seconds"] = round(time.monotonic() - inicio, 3)
    print(json.dumps(informe, ensure_ascii=False, indent=2))
    return 0 if informe["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
