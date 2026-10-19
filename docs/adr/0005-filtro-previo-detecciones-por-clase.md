# ADR 0005: Filtro previo por clase de las detecciones que se envían al modelo de visión

- Estado: Propuesto
- Fecha: 2026-10-19
- GitHub Issue: https://github.com/lvckss/piia2-26/issues/37
- Planes cubiertos (Issue/mini-spec/Spec): [entregas/cu-19-interpretacion-danos/specs/37-adrs-decisiones-previas.md](../../entregas/cu-19-interpretacion-danos/specs/37-adrs-decisiones-previas.md) — registro de una decisión ya vigente, especificada en `specs/agente-confianza-hallazgos.md` («Filtro previo»).
- Planning PR: <URL; completar al abrirla>
- Aceptación: <revisor y referencia de revisión; completar al aceptar>
- Sustituye / sustituido por: no aplica. Registra una decisión anterior sin ADR.

## Contexto y motivación

PIIA-1 deja unas 37 detecciones por imagen (score ≥ 0,3). Con las 500 imágenes exportadas de CarDD (`val` y `test`) son 18.507 detecciones, el 97 % falsas en `dent`, `scratch` y `crack`. Mandarlas todas al modelo de visión ([ADR 0003](0003-proveedor-openai-clave-empresa.md)) costaría 18.507 llamadas, una por detección. Hace falta decidir qué detecciones llegan a la visión sin perder los daños que PIIA-1 sí encuentra y sin que nada desaparezca sin rastro.

La decisión está medida e implementada (`seleccion.py`, commit `83c8155`), pero no tiene ADR.

## Decisión

1. **Filtro por clase** (`FILTRO_PREVIO` en `seleccion.py`): en `glass shatter`, las detecciones con score ≥ 0,5; en `lamp broken`, `tire flat`, `dent`, `scratch` y `crack`, las 2 mejores por imagen y clase; en una clase desconocida, también las 2 mejores.
2. **Nada se descarta en silencio:** las detecciones que no pasan el filtro quedan contadas por clase en `resumen_filtro_previo` del contrato ([ADR 0002](0002-contrato-json-entre-agentes.md)).
3. **Ninguna clase se excluye:** todas pasan por el mismo filtro y por la segunda opinión.
4. **El filtro decide solo qué se consulta**, no la confianza final: eso lo decide `decidir_tier` (umbral por clase, veredicto de visión y posibilidad de presupuestar).

## Alternativas consideradas

| Alternativa | Ventajas | Inconvenientes / motivo de descarte |
|---|---|---|
| **Filtro por clase: score ≥ 0,5 en `glass shatter` y top-2 por imagen en el resto (elegida)** | 3.712 llamadas en vez de 18.507 (un 80 % menos), conservando el 97 % del recall de PIIA-1 en `glass shatter`, el 94 % en `lamp broken` y el 100 % en `tire flat`. | Los valores de *k* se eligieron mirando las mismas 500 imágenes: resultado algo optimista. |
| Mandar todas las detecciones a la visión | Máximo recall posible. | 18.507 llamadas para 500 imágenes; casi todas sobre falsos positivos. |
| Un umbral de score para todas las clases | Simple. | El score solo separa en `glass shatter` (a ≥ 0,8, 67 % de precisión con 93,5 % de recall); en `lamp broken` y `tire flat` casi no separa (precisión a ≥ 0,8: 25 % y 16 %). |
| Top-3 en lugar de top-2 en `dent` | Algo más de recall. | 337 llamadas más por +4 puntos de recall: no compensa. |
| Excluir `dent`, `scratch` y `crack` | Ahorra la mayor parte de las llamadas. | Decisión de diseño de no excluir ninguna clase: necesitan el mismo rigor, y excluirlas haría desaparecer daños sin rastro. |

## Consecuencias

- **Beneficios:** coste de la visión acotado (≈ 3.700 llamadas para 500 imágenes); trazabilidad de lo descartado.
- **Límites aceptados:**
  - El techo lo pone SAM3: en `dent`, `scratch` y `crack`, ni con las 5 mejores por imagen se recupera más del 26 %, 25 % y 48 %. Un daño que PIIA-1 no marca no llega al informe; se declara como limitación.
  - `is_true_positive` infravalora a la visión en `dent`, `scratch` y `crack` (CarDD no anota todos los daños), así que las medidas en esas clases son relativas.
  - Los umbrales de `decidir_tier` siguen siendo placeholders; su calibración es la Issue #44.
- **Tests y AC:** `probar_seleccion_stub.py` verifica casos pequeños y, con el export presente, las cifras reales (18.507 → 3.712 y los mínimos de recall); `specs/agente-confianza-hallazgos.md` lo recoge como criterio verificado.

## Referencias y evidencia

- Medición completa y razonamiento: [`specs/agente-confianza-hallazgos.md`](../../entregas/cu-19-interpretacion-danos/specs/agente-confianza-hallazgos.md), «Filtro previo».
- Implementación: [`seleccion.py`](../../entregas/cu-19-interpretacion-danos/app/agentes/agente_multimodal/seleccion.py):

  ```python
  FILTRO_PREVIO = {
      "glass shatter": {"score_min": 0.5},
      "lamp broken": {"top_k": 2}, "tire flat": {"top_k": 2},
      "dent": {"top_k": 2}, "scratch": {"top_k": 2}, "crack": {"top_k": 2},
  }
  ```

- Reproducción (medido; con el export de 500 imágenes en local):

  ```bash
  cd entregas/cu-19-interpretacion-danos/app/agentes/agente_multimodal
  python probar_seleccion_stub.py                  # asserts 18507 -> 3712 y recall mínimo por clase
  python analizar_detecciones.py <carpeta del export>   # curvas de precisión y recall por clase y umbral
  ```
