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
| `seleccion.py` | Filtro previo: qué detecciones de PIIA-1 llegan al modelo de visión (`glass shatter` con score ≥ 0,5; en el resto las 2 mejores por imagen y clase). Medido con 500 imágenes: 3.712 llamadas en vez de 18.507. |
| `hallazgos.py` | Lee el JSON de PIIA-1, aplica el filtro previo y construye los findings del contrato (con `resumen_filtro_previo`). |
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

## Analizar y evaluar con las detecciones exportadas

Requiere haber descargado el export de Colab y extraído en
`piia2_detecciones/baseline_500/` (raíz del repo, en `.gitignore`).

```bash
# curvas precisión/recall por clase y umbral, efecto de quitar duplicados, llamadas por filtro
python analizar_detecciones.py ../../../../../piia2_detecciones/baseline_500

# comparar modelos de visión. POR DEFECTO SOLO CUENTA LAS LLAMADAS, NO GASTA NADA:
python evaluar_vision.py --modelos ID_MODELO_1 ID_MODELO_2
# prueba barata con 5 imágenes y un modelo:
python evaluar_vision.py --modelos ID_MODELO_1 --n-imagenes 5 --ejecutar
# comparación completa (40 imágenes, ~310 llamadas por modelo):
python evaluar_vision.py --modelos ID_MODELO_1 ID_MODELO_2 --ejecutar
```

`evaluar_vision.py` mide, por clase y modelo, cuántos aciertos de PIIA-1
confirma la visión y cuántos falsos positivos rechaza; calcula la precisión y el
recall de `confirmed` para cada umbral de score (con y sin visión), que es lo
que decide los `CATEGORY_REVIEW_THRESHOLD`; y cuenta los tokens realmente
facturados (lo que sale de la cache no cuenta). Tiene un tope
`--max-llamadas` (600 por modelo por defecto) por si se pide una muestra
demasiado grande. Resultados en `piia2_detecciones/evaluacion_vision/`.
No puede medir si la pieza y la severidad son correctas (CarDD no trae esas
etiquetas): eso se revisa a mano en una muestra.

## Pruebas sin API Key

`probar_vision_stub.py`, `probar_agente1_stub.py`, `probar_seleccion_stub.py` y
`probar_evaluar_vision_stub.py` usan un cliente falso de OpenAI, así que no
necesitan API Key ni el paquete `openai`. Estas dos últimas usan además el
export real y las fotos del CarDD en local si están (si no, se saltan esa parte).
`probar_con_imagenes_reales.py` prueba el recorte con fotos del CarDD en local
(`CarDD_release/`, no se sube a git).

## Pendiente

- Ejecutar `evaluar_vision.py --ejecutar` con la API real y comparar varios
  modelos.
- Con esos resultados, fijar los 6 `CATEGORY_REVIEW_THRESHOLD` (hoy
  placeholders; los datos dicen que no valen tal cual, ver
  `specs/agente-confianza-hallazgos.md`).
