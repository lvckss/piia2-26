# Agente 1 — Analista de daños (multimodal)

Responsable: Lucía.

Lee las detecciones de PIIA-1 (`../../ml/`) y la imagen original, decide qué
hallazgos son fiables, y produce la lista de "findings" que consumen el
Agente 2 (`../agente_recuperacion/`) y el Agente 3 (`../agente_redactor/`).

Contrato de entrada/salida completo:
[`../../../specs/piia2-arquitectura-multiagente.md`](../../../specs/piia2-arquitectura-multiagente.md).
Diseño del filtro de confianza:
[`../../../specs/agente-confianza-hallazgos.md`](../../../specs/agente-confianza-hallazgos.md).

## Piezas

| Fichero | Qué hace |
|---|---|
| `confianza.py` | `classify_confidence`: `confirmed` / `needs_review` según clase y score. |
| `hallazgos.py` | Lee el JSON de PIIA-1 y construye la lista de findings del contrato. |
| `recorte.py` | Recorta cada hallazgo de la foto (con 15% de margen) y lo guarda en disco. |
| `vision.py` | Manda cada recorte a Claude y rellena `vision_description`. |
| `agente1.py` | Encadena todo: `analizar_imagen(...)` devuelve (y opcionalmente guarda) el JSON final. |

## Uso

```bash
export ANTHROPIC_API_KEY=...   # la API Key del caso
python agente1.py ejemplos/ejemplo_3_mixto_dificil.json \
  --imagen ruta/a/la/foto.jpg --crops-dir crops --salida hallazgos.json
```

`--imagen` hace falta cuando la foto no está en la ruta que lleva el JSON de
PIIA-1 (por ejemplo, el CarDD montado en Colab).

## Pruebas sin API Key

`probar_vision_stub.py` y `probar_agente1_stub.py` usan un cliente falso, así
que no necesitan API Key ni el paquete `anthropic`. `probar_con_imagenes_reales.py`
prueba el recorte con fotos del CarDD copiado en local
(`CarDD_release/`, no se sube a git).

Pendiente: sustituir los `CATEGORY_REVIEW_THRESHOLD` placeholder por valores
calibrados, y probar `vision.py` contra la API real cuando llegue la API Key.
