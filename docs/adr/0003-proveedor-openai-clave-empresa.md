# ADR 0003: API de OpenAI con la clave de la empresa como proveedor de modelos

- Estado: Aceptado
- Fecha: 2026-10-19
- GitHub Issue: https://github.com/lvckss/piia2-26/issues/37
- Planes cubiertos (Issue/mini-spec/Spec): [entregas/cu-19-interpretacion-danos/specs/37-adrs-decisiones-previas.md](../../entregas/cu-19-interpretacion-danos/specs/37-adrs-decisiones-previas.md) — registro de una decisión ya vigente. La usan el Agente 1 (segunda opinión de visión) y, si se hace, el RAG (#32) y la orquestación (#33, #34).
- Planning PR: https://github.com/lvckss/piia2-26/pull/51
- Aceptación: Lucas García (`lvckss`), [revisión APPROVED del 2026-10-20](https://github.com/lvckss/piia2-26/pull/51#pullrequestreview-5588663399) sobre la versión `14b4b28` (aceptación expresa de los ADRs 0002, 0003, 0004 y 0005).
- Sustituye / sustituido por: no aplica. Registra una decisión anterior sin ADR (`specs/piia2-arquitectura-multiagente.md`, tabla «Decisiones tomadas y pendientes», fila «Proveedor y modelos»).

## Contexto y motivación

El Agente 1 necesita un modelo con visión que dé una segunda opinión sobre cada detección de PIIA-1 (¿hay daño?, ¿qué pieza?, ¿qué severidad?). La primera versión de la arquitectura (`d890c20`) dejaba abierto el proveedor («Claude o GPT con visión»). En la reunión con la empresa se fijó: la empresa da una clave de la API de OpenAI y un presupuesto de 50-100 € sin restricciones, recomienda un modelo concreto y pide probar varios y comparar si compensa el esfuerzo.

La decisión se usa ya en el código (`agente1.py`, `vision.py`) y condiciona la elección de framework (#33: Google ADK no está comprobado con modelos de OpenAI), pero no tiene ADR.

## Decisión

1. **Proveedor:** la API de OpenAI, con la clave que entregó la empresa. No se usan otros proveedores.
2. **Clave:** solo en la variable de entorno `OPENAI_API_KEY`; nunca en el repositorio, en ficheros versionados ni en el chat. Sin la variable, el cliente falla con un error explícito.
3. **Modelo:** el identificador exacto de la cuenta de la empresa, en la variable `OPENAI_MODEL` o en el parámetro `modelo`; no se fija en el código. Elegir o comparar modelos queda fuera de este ADR.
4. **Cliente:** se crea con `crear_cliente_openai()` (en `agente1.py`), sin pedir compresión `br` y con un timeout corto (ver «Consecuencias»).
5. **Coste controlado:** las respuestas se cachean por modelo, texto de la consulta e imágenes, y las evaluaciones que gastan dinero requieren pedirlo de forma explícita (`--ejecutar`).
6. **Pruebas sin red:** todo el código que llama al modelo recibe el cliente como parámetro, para probarlo con un cliente falso sin clave ni red.

## Alternativas consideradas

| Alternativa | Ventajas | Inconvenientes / motivo de descarte |
|---|---|---|
| **API de OpenAI con la clave de la empresa (elegida)** | Es lo que decide y paga la empresa; presupuesto suficiente; el modelo recomendado tiene visión y salida JSON. | Dependencia de un proveedor externo de pago; compatibilidad con ADK sin comprobar (#33). |
| Dejar el proveedor abierto, «Claude o GPT con visión» (primera versión de la arquitectura) | Libertad para elegir el mejor modelo. | No hay clave ni presupuesto de otro proveedor; la empresa fijó OpenAI. La arquitectura v2 lo dice expresamente: «usamos la API de OpenAI (no Anthropic)». |
| Fijar el identificador del modelo en el código | Más simple. | La empresa pide comparar varios modelos; con el modelo en una variable se cambia sin tocar código y la caché distingue respuestas por modelo. |

## Consecuencias

- **Beneficios:** sin coste para el equipo; el modelo se cambia por configuración; pruebas sin red con cliente falso.
- **Costes y riesgos conocidos:**
  - En algunas instalaciones de Anaconda, el paquete `brotli` es en realidad `brotlipy` y el SDK falla al leer respuestas comprimidas con `br` (`TypeError … output_buffer_limit`). Mitigado creando el cliente con `Accept-Encoding: gzip, deflate` (PR #6).
  - Por defecto el SDK espera hasta 10 minutos por llamada; se usa un timeout corto para que una llamada colgada no parezca un script parado.
  - Google ADK, que recomienda la empresa, no está comprobado con modelos de OpenAI; su viabilidad es la #33.
  - La salida de los hallazgos todavía no registra qué modelo se usó (Issue #45).
- **Tests y AC:** `probar_vision_stub.py` y `probar_agente1_stub.py` usan un cliente falso; ninguna prueba necesita `OPENAI_API_KEY`. Los planes de la #30 y la #31 exigen funcionar sin clave ni red (AC-008 y AC-012), porque sus cifras no dependen del modelo.

## Referencias y evidencia

- Decisión en [`specs/piia2-arquitectura-multiagente.md`](../../entregas/cu-19-interpretacion-danos/specs/piia2-arquitectura-multiagente.md), «Decisiones tomadas y pendientes» (texto de la reunión con la empresa; no hay otro documento primario en el repositorio: supuesto declarado).
- Cliente: `crear_cliente_openai()` en [`agente1.py`](../../entregas/cu-19-interpretacion-danos/app/agentes/agente_multimodal/agente1.py):

  ```python
  if not os.environ.get("OPENAI_API_KEY"):
      raise RuntimeError("Falta la variable de entorno OPENAI_API_KEY (la API Key del caso).")
  from openai import OpenAI
  return OpenAI(default_headers={"Accept-Encoding": "gzip, deflate"}, ...)
  ```

- Problema de `brotli` y su solución: [`app/agentes/README.md`](../../entregas/cu-19-interpretacion-danos/app/agentes/README.md), «Problemas conocidos».
- Caché por modelo, consulta e imágenes: `analizar_hallazgo` en [`vision.py`](../../entregas/cu-19-interpretacion-danos/app/agentes/agente_multimodal/vision.py).
- Documentación oficial del SDK: https://github.com/openai/openai-python
