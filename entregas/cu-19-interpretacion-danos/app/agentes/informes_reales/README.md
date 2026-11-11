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
inventadas.

## Cómo se completan los datos que faltan

Las salidas del Agente 1 no traen datos del siniestro. Hasta que la web
(#34) los pida a la persona usuaria:

- **Contexto:** cada imagen, en orden de `image_id`, recibe un siniestro
  distinto de `siniestros_sinteticos.csv` de la empresa, elegido con
  `random.Random(84)`. Solo se usan su región, taller, acabado, tipo de pieza,
  rol, póliza (con rol propio), años y km; sus daños y su coche no.
- **Coche:** el de referencia de la categoría que propone el Agente 1 o, con
  `desconocido`, el de menor coste (`V14`, Dacia Sandero). Es una regla
  provisional: su sitio definitivo es el orquestador de la #34.
- **Fecha:** fija (`--hoy`), para que dos ejecuciones den los mismos archivos.

Los informes usan datos del paquete de la empresa: se generan en local y no se
suben al repositorio.
