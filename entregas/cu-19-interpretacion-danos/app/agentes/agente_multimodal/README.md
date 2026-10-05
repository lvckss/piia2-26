# Agente 1 — Analista de daños (multimodal)

Responsable: Lucía.

Lee las detecciones de PIIA-1 y la foto original. Por cada detección, un
modelo con visión (API de OpenAI) da una segunda opinión: ¿hay de verdad un
daño de esa clase?, ¿sobre qué pieza?, ¿con qué severidad? Con eso, y con el
score de PIIA-1, decide qué hallazgos son fiables y produce la lista de
"findings" que consumen el Agente 2 (`../agente_recuperacion/`) y el Agente 3
(`../agente_redactor/`).

Contrato de entrada/salida completo:
[`../../../specs/piia2-arquitectura-multiagente.md`](../../../specs/piia2-arquitectura-multiagente.md).
Diseño del filtro de confianza:
[`../../../specs/agente-confianza-hallazgos.md`](../../../specs/agente-confianza-hallazgos.md).

## Piezas

| Fichero | Qué hace |
|---|---|
| `confianza.py` | `classify_confidence` (solo score) y `decidir_tier` (score + visión + pieza con regla de coste). |
| `catalogo.py` | Lee `piezas.csv` y `reglas_dano.csv` del paquete de la empresa; valida que una pieza/severidad se pueda presupuestar. |
| `hallazgos.py` | Lee el JSON de PIIA-1 y construye los findings del contrato. |
| `recorte.py` | Recorta cada hallazgo (con 15 % de margen) y dibuja la caja sobre la foto completa. |
| `vision.py` | Manda a un modelo de OpenAI la foto con la caja + el recorte; valida su respuesta JSON (veredicto, pieza, severidad); cache opcional para no pagar dos veces lo mismo. |
| `agente1.py` | Encadena todo: `analizar_imagen(...)` devuelve (y opcionalmente guarda) el JSON final. |
| `colab/` | Notebook para exportar las detecciones de PIIA-1 (SAM3) de ~500 imágenes, una sola vez, con cada detección marcada como acierto/falso positivo. |

## Uso

```bash
export OPENAI_API_KEY=...      # la clave que dio la empresa (nunca en el repo)
export OPENAI_MODEL=...        # el id exacto del modelo en la cuenta de la empresa
python agente1.py ejemplos/ejemplo_3_mixto_dificil.json \
  --imagen ruta/a/la/foto.jpg --crops-dir crops --cache-dir cache --salida hallazgos.json
```

`--imagen` hace falta cuando la foto no está en la ruta que lleva el JSON de
PIIA-1. Necesita el paquete de datos de la empresa extraído en
`piia2_paquete_datos/` (raíz del repo).

## Pruebas sin API Key

`probar_vision_stub.py` y `probar_agente1_stub.py` usan un cliente falso de
OpenAI, así que no necesitan API Key ni el paquete `openai`.
`probar_con_imagenes_reales.py` prueba el recorte con fotos del CarDD en local
(`CarDD_release/`, no se sube a git).

## Pendiente

- Probar `vision.py` contra la API real y comparar varios modelos (misma
  muestra de 30-50 imágenes del export, medido con `is_true_positive`).
- Sustituir los `CATEGORY_REVIEW_THRESHOLD` placeholder por valores calibrados
  con la curva precisión/recall de las detecciones exportadas.
