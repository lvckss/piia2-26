# Primeros informes reales en línea de comandos

Issue [#84](https://github.com/lvckss/piia2-26/issues/84) ·
[plan v1](https://github.com/lvckss/piia2-26/issues/84#issuecomment-6802745988).

Encadena las 30 salidas reales del Agente 1 guardadas en
[`../ejemplos_contrato/agente1_real/`](../ejemplos_contrato/agente1_real/) con el
Agente 2 (costes y cobertura) y el Agente 3 (informe), y deja un informe en
Markdown por imagen y un resumen. Sin API, sin RAG y sin web.

## Uso

Necesita el paquete de la empresa extraído en la raíz del repo
(`piia2_paquete_datos/`, fuera de git). Desde esta carpeta:

```bash
python generar_informes_reales.py             # informes en ./salida/ (ignorada por git)
python generar_informes_reales.py --destino /ruta/propia --hoy 2026-11-12
python probar_informes_reales.py              # pruebas del plan (AC-001 a AC-005)
```

El resultado es `<image_id>.md` por imagen y `resumen.md`, con una fila por
imagen: siniestro de origen, categoría, coche usado, rol, hallazgos por grupo,
totales con IVA de los dos escenarios, cifras que no salen del Agente 2 y
errores. El comando termina con código 1 si alguna imagen falla o tiene cifras
inventadas; en ese caso el informe de esa imagen no se deja en la carpeta,
aunque existiera de una ejecución anterior. Si la carpeta de salidas no existe
o no tiene ningún `*.json`, termina con código 2 e indica la ruta.

## Cómo se completan los datos que faltan

Las salidas del Agente 1 no traen datos del siniestro. Hasta que la web
(#34) los pida a la persona usuaria:

- **Contexto:** cada imagen, en orden de `image_id`, recibe un siniestro
  distinto de `siniestros_sinteticos.csv` de la empresa, elegido con
  `random.Random(84)`. Solo se usan su región, taller, acabado, tipo de pieza,
  rol, póliza (con rol propio), años y km; sus daños y su coche no.
- **Coche:** el de referencia de la categoría que propone el Agente 1 o, con
  `desconocido`, el de menor coste (`V14`, Dacia Sandero). Es una regla
  provisional: su sitio definitivo es el orquestador de la #34. El contexto lleva además
  `vehiculo_origen` (`referencia_confirmada` o `minimo_por_defecto`), que el informe usa para decir
  de dónde sale el coche (spec 34 v1.7; plan v1.2 de la #54, AC-021).
- **Fecha:** fija (`--hoy`), para que dos ejecuciones den los mismos archivos.

Los informes usan datos del paquete de la empresa: se generan en local y no se
suben al repositorio.

## Evaluación de punta a punta, Parte 1 (Issue #46)

[Plan v1 de la #46](https://github.com/lvckss/piia2-26/issues/46#issuecomment-6985712887)
(AC-001, AC-002 y AC-007). `evaluar_informes.py` genera los mismos informes que
`generar_informes_reales.py` y reúne en `resumen_evaluacion.md` las
comprobaciones automáticas del AC-002 sobre las 30: informes generados,
cifras que no salen del Agente 2, reparto de los hallazgos (confirmados,
pendientes de revisión y fuera del coste, con su motivo), hallazgos que entran
por equivalencia (#88), temas del RAG con pasajes, sin pasajes y con error,
justificaciones (#97) generadas, descartadas y no generadas con su motivo, y la
repetición con la misma entrada. Todo se informa tal cual, sin umbrales.

```bash
python evaluar_informes.py --repetir                  # solo costes; resumen en ./salida_evaluacion/ (ignorada por git)
python evaluar_informes.py --completo --repetir       # con agente2(): RAG y justificaciones (#32, #97)
python evaluar_informes.py --destino /ruta --hoy 2026-11-25 --salidas /ruta/salidas
python probar_evaluar_informes.py                     # pruebas de la Parte 1
```

- **Sin `--completo`** solo se calculan los costes: el RAG y las justificaciones constan
  como «no disponible», no como cero. **Con `--completo`** se usa `agente2()` de la #32:
  se ejecuta con el Python del entorno del RAG (`just rag-setup` crea `.venv-rag`; en
  Linux, macOS o WSL, `.venv-rag/bin/python evaluar_informes.py --completo`) y hace falta
  PostgreSQL con el índice y, para las justificaciones, la clave y la autorización de gasto
  (`RAG_QUERY_EXECUTE=1` y `RAG_QUERY_MAX_COST_USD`). Si `agente2` no se puede importar
  (por ejemplo, falta `openai`), el comando termina con código 2 y lo dice.
- Un `*.json` de la carpeta de salidas que no es una salida del Agente 1 (como el
  `resumen_lote.json` que escribe `generar_lote.py`) se omite; si no queda ninguna,
  termina con código 2.
- **`--repetir`** vuelve a generar cada informe y lista los que cambian. Con la
  justificación del LLM, la caché evita volver a pagar la misma consulta.
- Termina con código 1 si algún caso falla o un informe trae cifras que no salen del
  Agente 2, y con código 2 si no hay salidas del Agente 1 en la carpeta.
- Los informes de `salida_evaluacion/` salen de siniestros sintéticos de la empresa y de
  datos del paquete: se generan en local y no se suben al repositorio. Para la evidencia
  de la #46 se copian las tablas del resumen, no los informes.
