# Agente 1 — Analista de daños (multimodal)

Responsable: Lucía.

Lee las detecciones de PIIA-1 y la foto original. Por cada detección, un
modelo con visión (API de OpenAI) da una segunda opinión: ¿hay de verdad un
daño de esa clase?, ¿sobre qué pieza?, ¿con qué severidad? Con eso, y con el
score de PIIA-1, decide qué hallazgos son fiables y produce la lista de
"findings" que consumen el Agente 2 (`../agente_recuperacion/`) y el Agente 3
(`../agente_redactor/`).

Además propone la **categoría del vehículo** (campo `vehiculo` de la salida), con
una consulta por imagen. Es una propuesta que la persona usuaria confirma o corrige
en la web: el Agente 2 sigue recibiendo el `vehiculo_id` como dato de entrada del
siniestro. Ver «Categoría del vehículo».

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
| `vision.py` | Manda a un modelo de OpenAI la foto con la caja + el recorte; valida su respuesta JSON (veredicto, pieza, severidad); cache opcional para no pagar dos veces lo mismo. `consultar_modelo` es la llamada con caché (clave: hash de modelo, prompt e imágenes) que comparten los hallazgos y la categoría del vehículo. |
| `vehiculo.py` | Categoría del vehículo: una consulta por imagen (foto completa reducida a 1.024 px, sin cajas), validación de la respuesta y traducción de la categoría al coche de referencia del catálogo de la empresa (`REFERENCIA`). Ver «Categoría del vehículo». |
| `agente1.py` | Encadena todo: `analizar_imagen(...)` devuelve (y opcionalmente guarda) el JSON final, con el campo `vehiculo`. |
| `generar_lote.py` | Genera la salida real del Agente 1 para un lote reproducible de imágenes del export (un JSON por imagen), la valida contra el contrato y resume llamadas (por hallazgo y de categoría del vehículo), tokens y reparto de niveles. Ver «Generar un lote real». |
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

## Categoría del vehículo

`analizar_imagen` añade a la salida un objeto `vehiculo` con `categoria`,
`vehiculo_id_referencia`, `confianza`, `descripcion` y `modelo` (Issue #28,
[ADR 0001](../../../../../docs/adr/0001-categoria-vehiculo-contrato-agente1.md)).
La herramienta de costes de la empresa necesita un coche de su catálogo y las
fotos de CarDD no lo traen: el modelo de visión estima la categoría y el sistema
propone el coche que la representa.

| Categoría | Coche de referencia |
|---|---|
| `A` | V24 — Fiat 500 |
| `B` | V07 — Renault Clio |
| `C` | V02 — SEAT León |
| `SUV-B` | V08 — Renault Captur |
| `SUV-C` | V11 — Peugeot 3008 |
| `FURG` | V09 — Renault Kangoo |
| `C-PREMIUM` | V26 — Mercedes-Benz Clase A |
| `D-PREMIUM` | V25 — BMW Serie 3 |

- **Una consulta por imagen**, no por hallazgo, con la foto completa reducida a
  1.024 px de lado largo (sin ampliarla) y sin cajas dibujadas. Se hace también si
  la imagen no tiene hallazgos candidatos y, con `--cache-dir`, no se paga dos veces.
- **Coche de referencia**: la tabla `REFERENCIA` de `vehiculo.py`;
  `probar_vehiculo_stub.py` comprueba contra `vehiculos.csv` que cada coche existe y
  es de esa categoría. `desconocido` (camión, autobús, moto o foto en la que no se
  distingue el tipo) no tiene coche de referencia: `vehiculo_id_referencia` es
  `null` y la persona usuaria elige en la web.
- **La respuesta se valida, nunca se acepta tal cual**: una categoría fuera de la
  lista, un texto que no es JSON o una respuesta vacía dan `desconocido` con
  confianza `baja`; una confianza fuera de `alta`/`media`/`baja`, o `alta` con
  `desconocido`, se guarda como `baja`.
- **Un fallo del proveedor no se disfraza de `desconocido`**: la excepción llega a
  quien llama a `analizar_imagen` y no se escribe ningún fichero de salida.
- **Es una propuesta, no el `vehiculo_id` del siniestro**: el Agente 2 sigue
  exigiendo el `vehiculo_id` en el contexto; la web (#34) muestra la propuesta y la
  persona usuaria la confirma o la corrige.
- **Orientativo**: no identifica marca y modelo exactos (solo los menciona en la
  descripción si se reconocen) y el prompt no pide matrículas, propietarios ni
  personas. El acierto de la categoría no se puede medir contra CarDD: se valida a
  mano con una muestra (AC-011 de `../../../specs/28-categoria-vehiculo.md`).
- `evaluar_vision.py` y `analizar_detecciones.py` no hacen esta consulta: su recuento
  de llamadas no cambia.

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

## Generar un lote real

`generar_lote.py` ejecuta el Agente 1 (`analizar_imagen`) sobre un lote
reproducible del export de 500 imágenes y deja la salida lista para los
Agentes 2 y 3 (Issue #43). Elige 30 imágenes con semilla 42 y al menos 3
aciertos de PIIA-1 por clase: 234 llamadas por hallazgo más una de categoría del
vehículo por imagen (264 en total).

```bash
# 1. plan: cuenta las llamadas y las fotos que faltan. NO llama a la API ni escribe nada
python generar_lote.py

# 2. prueba barata con pocas imágenes (necesita OPENAI_API_KEY y OPENAI_MODEL)
python generar_lote.py --n-imagenes 3 --min-aciertos 1 --ejecutar

# 3. el lote completo (cuesta lo que diga el plan; --max-llamadas 300 es el tope por defecto)
python generar_lote.py --ejecutar
```

- **Qué deja** (por defecto en `piia2_detecciones/salida_agente1/`, ignorada por
  git): un `<image_id>.json` por imagen con el contrato del Agente 1
  (`../ejemplos_contrato/agente1_salida.json`), los recortes en `crops/` (con
  `crop_image_path` relativo a esa carpeta) y `resumen_lote.json`.
- **Qué comprueba**: cada salida pasa `validar_salida_agente1` (campos exactos,
  veredicto, nivel de confianza coherente con `decidir_tier`, pieza del
  catálogo; y, en `vehiculo`, categoría, confianza y coche de referencia). Una imagen que falla (foto ausente o ilegible, error de la API,
  salida no válida) no tira el lote: se lista al final y el código de salida es
  distinto de 0. Al repetir, lo ya consultado sale de la caché
  (`piia2_detecciones/cache_vision/`) y no se factura de nuevo.
- **Qué muestra**: una línea por cada llamada facturada (con su duración y sus
  tokens) y otra por cada imagen terminada, para ver que avanza; lo servido desde
  la caché no imprime línea de llamada.
- **Qué cuenta**: llamadas y tokens realmente facturados (lo servido desde la
  caché no cuenta) y el reparto de `confidence_tier` y `vision_verdict`. El coste
  en euros solo se calcula si pasas `--precio-entrada` y `--precio-salida` (euros
  por millón de tokens); no hay precios por defecto.
- **Categoría del vehículo**: es una consulta más por imagen. El plan y el tope
  `--max-llamadas` ya la incluyen; el resumen separa las facturadas
  (`llamadas_vehiculo_facturadas`) de las de hallazgos, y `hallazgos_desde_cache`
  cuenta solo hallazgos.
- **Ojo**: el lote se elige con `is_true_positive` para cubrir las 6 clases, así
  que el reparto de `confirmed` y `needs_review` no es representativo de la
  distribución real.
- Regenerar tras cambiar los umbrales de `confianza.py` no cuesta llamadas
  mientras no cambien el prompt ni los recortes.

## Pruebas sin API Key

`probar_vision_stub.py`, `probar_agente1_stub.py`, `probar_vehiculo_stub.py`,
`probar_seleccion_stub.py`,
`probar_evaluar_vision_stub.py` y `probar_lote_stub.py` usan un cliente falso de
OpenAI, así que no necesitan API Key ni el paquete `openai`. Las dos últimas
usan además el export real y las fotos del CarDD en local si están (si no, se
saltan esa parte).
`probar_vehiculo_stub.py` comprueba además la tabla de coches de referencia contra
`vehiculos.csv` del paquete de la empresa (si no está, salta esa parte con aviso).
`probar_con_imagenes_reales.py` prueba el recorte con fotos del CarDD en local
(`CarDD_release/`, no se sube a git).

## Pendiente

- Ejecutar `evaluar_vision.py --ejecutar` con la API real y comparar varios
  modelos.
- Con esos resultados, fijar los 6 `CATEGORY_REVIEW_THRESHOLD` (hoy
  placeholders; los datos dicen que no valen tal cual, ver
  `specs/agente-confianza-hallazgos.md`).
