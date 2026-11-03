# Etiquetas de la calibración de umbrales (Issue #44)

Estas etiquetas sostienen los umbrales de `confianza.py` (`dent`, `scratch` y `crack` a 0,3; `lamp broken`, `glass shatter` y `tire flat` siguen en 0,6). Se versionan para que las cifras de la spec y de la Issue #44 se puedan reproducir sin depender de datos locales. Solo llevan ids y etiquetas: **ningún recorte ni imagen de CarDD** (esos siguen en `piia2_detecciones/`, ignorada por git).

Formato común: CSV con la cabecera `finding_id,etiqueta`; `finding_id` es `<image_id>-<n>`, el del Agente 1; las etiquetas son `si`, `otra`, `no` y `dudo`, la respuesta a «¿hay un daño de esta clase en la caja?». `etiquetado.leer_etiquetas` los lee tal cual.

| Fichero | Filas | Qué es |
|---|---|---|
| `confirmados_bajo_umbral.csv` | 60 | Etiquetas **humanas** del 2026-10-25: hallazgos de `dent`, `scratch` y `crack` que la visión confirmó con score por debajo de 0,7 (tramos 0,3-0,5 y 0,5-0,7). 43 `si`, 9 `otra`, 8 `dudo`. Una sola persona, con el score y la respuesta de la IA a la vista. |
| `etiquetas_revision_44.csv` | 60 | Revisión humana dirigida del 2026-10-28: los 60 candidatos de `dent`, `scratch` y `crack` con score entre 0,3 y 0,7 que el juez marcó `dudo` (56) o `no` (4). Una sola persona, en una página **ciega** (recorte y clase de la caja, sin score, sin respuesta de la IA y sin la etiqueta del juez). 25 `si`, 9 `otra`, 1 `no`, 25 `dudo`. |
| `etiquetas_juez.csv` | 3.712 | Etiquetas del juez (`gpt-6.1-terra`, esfuerzo `high`) para todos los hallazgos del lote de 500 imágenes, ejecutado el 2026-10-28: 1.388 `si`, 1.326 `otra`, 607 `dudo`, 391 `no`. Son las que usa el criterio de los umbrales. |
| `etiquetas_juez_con_revision.csv` | 3.712 | **Derivado:** igual que `etiquetas_juez.csv`, salvo que en los 60 ids de la revisión se pone la etiqueta humana (35 cambian). Solo sirve para comprobar que los umbrales no cambian con esa revisión. |
| `resumen_juez.json` | | Modelo, esfuerzo, hash del prompt (`abe617f3…`), llamadas, tokens y fallos (ninguno) de la ejecución del juez. |

## Lo que estas etiquetas no son

- **Las del juez son de un modelo, no verdad humana.** Su validación con personas es pequeña: las 60 de `confirmados_bajo_umbral.csv`, todas de `dent`, `scratch` y `crack`. Con las 49 comparables (sin `dudo`) el juez coincide exactamente en 41 (84 %, intervalo de Wilson 71-91 %) y coincide en «hay daño» en las 49; no hay ningún `no` humano en esa muestra, así que kappa (0,34) no es interpretable.
- **No hay ninguna etiqueta humana de `lamp broken`, `glass shatter` ni `tire flat`**, y de los `no` del juez solo se han contrastado 4, los de la revisión (la persona puso `si` en 2, `no` en 1 y `dudo` en 1). Los umbrales de esas tres clases (que no cambian) descansan solo en el juez.
- El README del agente describe una muestra ciega de validación más (`etiquetas_humanas_120.csv`); no se ha etiquetado, y la validación del juez es la de las 60.

## Reproducir las cifras

Desde `app/agentes/agente_multimodal/`:

```bash
# acuerdo del juez con las 60 humanas: 60 comunes, 49 comparables, 41 coinciden
python juez_vision.py acuerdo --humanas etiquetas/confirmados_bajo_umbral.csv --juez etiquetas/etiquetas_juez.csv

# repartos, ids y consistencia entre los cinco ficheros
python probar_etiquetado_stub.py

# umbrales del criterio de la D-6 y tabla antes y después (necesita las salidas del Agente 1 de las 500 imágenes, locales)
python tabla_umbrales.py --salidas ../../../../../piia2_detecciones/salida_agente1_500 \
    --etiquetas etiquetas/etiquetas_juez.csv --resumen etiquetas/resumen_juez.json --criterio --desde-partida
```

## Mantenimiento

Son el historial de la calibración de la #44: no se editan. Si se recalibra (cambia la estrategia, el prompt, el juez o el dataset), las etiquetas nuevas se añaden como ficheros nuevos, con su fecha, el modelo y el hash del prompt, sin sobrescribir estas.
