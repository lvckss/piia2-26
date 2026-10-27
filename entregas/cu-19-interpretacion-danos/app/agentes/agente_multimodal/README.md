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
| `generar_lote.py` | Genera la salida real del Agente 1 para un lote reproducible de imágenes del export (un JSON por imagen), la valida contra el contrato y resume llamadas, tokens y reparto de niveles. Ver «Generar un lote real». |
| `etiquetado.py` | Etiquetado manual para calibrar los umbrales (Issue #44): elige la muestra, genera la página de etiquetado y calcula la precisión por clase y tramo de score con intervalo. Ver «Etiquetar para calibrar los umbrales». |
| `juez_vision.py` | Un modelo más potente etiqueta los hallazgos en las mismas condiciones que una persona (solo recorte y clase) y se mide su acuerdo con las etiquetas humanas. Caché, tope de llamadas y `--ejecutar` explícito. Ver «Juez de visión». |
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

## Generar un lote real

`generar_lote.py` ejecuta el Agente 1 (`analizar_imagen`) sobre un lote
reproducible del export de 500 imágenes y deja la salida lista para los
Agentes 2 y 3 (Issue #43). Elige 30 imágenes con semilla 42 y al menos 3
aciertos de PIIA-1 por clase (unas 234 llamadas al modelo).

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
  catálogo). Una imagen que falla (foto ausente o ilegible, error de la API,
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
- **Ojo**: el lote se elige con `is_true_positive` para cubrir las 6 clases, así
  que el reparto de `confirmed` y `needs_review` no es representativo de la
  distribución real.
- Regenerar tras cambiar los umbrales de `confianza.py` no cuesta llamadas
  mientras no cambien el prompt ni los recortes.

## Etiquetar para calibrar los umbrales

`is_true_positive` no es una vara fiable en `dent`, `scratch` y `crack` (CarDD no
anota todos los daños), así que la precisión de lo que la visión confirma se
estima con etiquetas manuales (Issue #44). `etiquetado.py` hace tres cosas:

```bash
# 1. elegir la muestra y generar la página de etiquetado (no gasta API)
python etiquetado.py muestra --salidas ../../../../../piia2_detecciones/salida_agente1_500
# 2. etiquetar en el navegador y bajar el CSV; guardarlo (solo ids y etiquetas) en etiquetas/
# 3. calcular la tabla de precisión por clase y tramo
python etiquetado.py tabla --salidas ../../../../../piia2_detecciones/salida_agente1_500     --etiquetas etiquetas/confirmados_bajo_umbral.csv [--resultados <resultados_modelo.json>]
```

- **Muestra:** hallazgos que la visión confirmó, de `dent`, `scratch` y `crack`, con
  score por debajo del umbral actual de su clase y dentro de dos tramos (0,3-0,5 y
  0,5-0,7), hasta 10 por clase y tramo (semilla 42, reproducible). Lo que ya pasa el
  umbral no se etiqueta: su nivel no cambia si el umbral baja. La **tanda 1** es el
  tramo 0,5-0,7; la **tanda 2** (0,3-0,5), solo si la primera no deja clara la
  conclusión.
- **Página:** un solo archivo HTML, sin red, con los recortes incrustados. Se escribe
  en `piia2_detecciones/etiquetado/` (ignorada por git) y no se deja escribir dentro
  de `entregas/`, porque lleva recortes de CarDD. Teclas: `s` sí, `o` hay un daño de
  otra clase, `n` no, `d` dudo, espacio para ver qué dice la IA (se mira primero el
  recorte), flechas para moverse. Las marcas se guardan en el navegador y se bajan
  con «Descargar CSV».
- **Etiquetas:** CSV con la cabecera `finding_id,etiqueta`. Pregunta: «¿hay un daño de
  esta clase en la caja?» (`si`, `otra`, `no`, `dudo`).
- **Tabla:** precisión de `confirmado` con intervalo de Wilson al 95 %, en dos
  versiones (solo `si`, y `si` + `otra` como daño real); `dudo` va aparte y no entra
  en el denominador; toda celda con menos de 5 casos sale como no concluyente. Con
  `--resultados` (el `resultados_<modelo>.json` de `evaluar_vision.py`) compara con
  `is_true_positive`: cuántos confirmados que PIIA-1 daba por fallo eran daño real.

## Juez de visión

Etiquetar a mano los 3.712 hallazgos del lote de 500 imágenes no es viable, así que
las etiquetas de la tabla de precisión las puede poner un modelo más potente (el
«juez») y **se mide cuánto coincide con las personas** antes de fiarse de él. Son
etiquetas de un modelo validadas con una muestra humana, no verdad humana. Estado:
herramienta implementada y probada con un cliente falso; **sin ejecutar todavía con
el modelo real**.

```bash
# 0. muestra de validación: 60 hallazgos nuevos (5 rechazados por la visión + 5 confirmados
#    con score alto, por clase) que no repiten los ya etiquetados. La página es CIEGA:
#    solo recorte y clase, sin score ni «La IA dice», igual que lo ve el juez.
python etiquetado.py validacion --salidas ../../../../../piia2_detecciones/salida_agente1_500     --excluir etiquetas/confirmados_bajo_umbral.csv
#    Al terminar de etiquetar, une las dos descargas (confirmados_bajo_umbral.csv y la nueva)
#    en etiquetas/etiquetas_humanas_120.csv, con una sola cabecera.
# 1. plan: cuenta las llamadas y las que ya están en caché. NO llama a la API ni escribe nada
python juez_vision.py juzgar --salidas ../../../../../piia2_detecciones/salida_agente1_500     --ids etiquetas/etiquetas_humanas_120.csv --modelo ID --esfuerzo xhigh
# 2. prueba barata con 10 hallazgos, y si el plan es el esperado, la ejecución de verdad
python juez_vision.py juzgar ... --limite 10 --ejecutar
python juez_vision.py juzgar ... --ids etiquetas/etiquetas_humanas_120.csv --ejecutar
# 3. acuerdo del juez con las personas (exacto con intervalo de Wilson, kappa de Cohen,
#    matriz de confusión y acuerdo en «hay daño real»)
python juez_vision.py acuerdo --humanas etiquetas/etiquetas_humanas_120.csv --juez ../../../../../piia2_detecciones/juez/ID/etiquetas_juez.csv
```

- **Mismas condiciones que la persona:** el juez ve el recorte y la clase de la caja,
  no el veredicto ni la descripción de la visión. Responde `si`, `otra`, `no` o `dudo`
  con un motivo corto, igual que la página de etiquetado.
- **Gasto controlado:** sin `--ejecutar` solo se imprime el plan. Con él, el tope
  `--max-llamadas` (300 por defecto) se comprueba antes de la primera llamada; la
  caché `piia2_detecciones/cache_juez/` evita pagar dos veces lo mismo (clave: modelo,
  esfuerzo, prompt y recorte); solo se guardan respuestas válidas; tras 5 fallos de
  API seguidos se aborta conservando lo hecho; `--hilos` paraleliza.
- **Salida** (en `piia2_detecciones/juez/<modelo>/`, ignorada por git): `etiquetas_juez.csv`
  (`finding_id,etiqueta`, mismo formato que las humanas, así que la tabla de precisión
  las lee tal cual), `detalle_juez.json` (con el motivo) y `resumen_juez.json` (modelo,
  esfuerzo, hash del prompt, llamadas, tokens, fallos).
- **El acuerdo no fija ningún umbral por sí solo:** si el juez no alcanza un acuerdo
  aceptable con las personas, sus etiquetas no se usan para decidir umbrales.
  El criterio de aceptación se decide en el plan de la #44 antes de ver los resultados.

## Pruebas sin API Key

`probar_vision_stub.py`, `probar_agente1_stub.py`, `probar_seleccion_stub.py`,
`probar_evaluar_vision_stub.py`, `probar_lote_stub.py`, `probar_etiquetado_stub.py`
y `probar_juez_stub.py` usan un cliente falso de OpenAI o ninguno, así que no necesitan API Key ni el
paquete `openai`. `probar_evaluar_vision_stub.py` usa además el export real y las
fotos del CarDD en local, y `probar_etiquetado_stub.py`, las salidas reales del
lote de la #43, si están (si no, se saltan esa parte).
`probar_con_imagenes_reales.py` prueba el recorte con fotos del CarDD en local
(`CarDD_release/`, no se sube a git).

## Pendiente

- Ejecutar `evaluar_vision.py --ejecutar` con la API real y comparar varios
  modelos.
- Con esos resultados, fijar los 6 `CATEGORY_REVIEW_THRESHOLD` (hoy
  placeholders; los datos dicen que no valen tal cual, ver
  `specs/agente-confianza-hallazgos.md`).
