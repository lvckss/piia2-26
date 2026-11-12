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
[`../../../specs/piia2-arquitectura-multiagente.md`](../../../docs/piia2-arquitectura-multiagente.md).
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
| `evaluar_vehiculo.py` | Validación manual de la categoría del vehículo (AC-011 de la Spec 28), en tres pasos: `muestra` copia 20 fotos y una plantilla de juicios, `consultar --ejecutar` pregunta al modelo (una llamada por foto) y `evaluar` la compara con el juicio a ciegas de una persona (coincidencia, matriz de confusión y referencia de la categoría más frecuente). Su docstring explica el flujo. |
| `evaluar_lado.py` | Evaluación de una variante del prompt del lado izquierdo/derecho (Issue #54, AC-012), en tres pasos: `plan` comprueba fotos y recortes y cuenta las llamadas sin tocar la API, `ejecutar` hace una llamada por hallazgo de las 30 salidas versionadas con el prompt de la variante (una sola vez; gasta presupuesto) y `evaluar` compara con la línea base y las etiquetas de lado y dice si se cumplen las dos condiciones de adopción (al menos 24 de 29 decidibles y como mucho 25 veredictos distintos de 234). Las etiquetas y los resultados no se versionan. |
| `agente1.py` | Encadena todo: `analizar_imagen(...)` devuelve (y opcionalmente guarda) el JSON final, con el campo `vehiculo`. |
| `generar_lote.py` | Genera la salida real del Agente 1 para un lote reproducible de imágenes del export (un JSON por imagen), la valida contra el contrato y resume llamadas (por hallazgo y de categoría del vehículo), tokens y reparto de niveles. Ver «Generar un lote real». |
| `etiquetado.py` | Etiquetado manual para calibrar los umbrales (Issue #44): elige la muestra, genera la página de etiquetado y calcula la precisión por clase y tramo de score con intervalo. Ver «Etiquetar para calibrar los umbrales». |
| `juez_vision.py` | Un modelo más potente etiqueta los hallazgos en las mismas condiciones que una persona (solo recorte y clase) y se mide su acuerdo con las etiquetas humanas. Caché, tope de llamadas y `--ejecutar` explícito. Ver «Juez de visión». |
| `tabla_umbrales.py` | Tabla reproducible de precisión por clase y tramo de score, y acumulada por umbral, con las etiquetas del juez (Issue #44, AC-003) y, con `--criterio`, los umbrales que salen del criterio de la D-6. Calcula, no cambia nada. Ver «Tabla de precisión por clase y umbral». |
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
[ADR 0001](../../../docs/adr/0001-categoria-vehiculo-contrato-agente1.md)).
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

## Comparación de dos modelos de visión

Ejecutada el 6 de noviembre de 2026 con
`python evaluar_vision.py --modelos gpt-6-luna gpt-6.1-terra --ejecutar`. Cumple el criterio 5
de la spec de arquitectura (comparar con números al menos dos modelos de visión). Los
resultados en bruto (`resultados_<modelo>.json`) están en
`piia2_detecciones/evaluacion_vision_comparacion/`, que no se sube a git.

**Qué se comparó.** Las mismas 40 imágenes (semilla 42, al menos 8 aciertos de PIIA-1 por
clase), con 309 detecciones: 49 aciertos de PIIA-1 y 260 falsos positivos según CarDD. Mismo
prompt y mismas imágenes para los dos modelos y una sola ejecución por modelo. Se aplican los
umbrales calibrados en la Issue #44 (0,3 en `dent`, `scratch` y `crack`; 0,6 en el resto).
«Confirmada» sigue la regla de `confianza.decidir_tier`: la detección supera el umbral de su
clase, la visión la confirma y se conoce la pieza con una regla de coste. Nada se descarta: lo
que no se confirma queda en `needs_review`.

| | Pasan el umbral | Confirmadas | Aciertos entre las confirmadas | Precisión | Aciertos conservados | Sin confirmar (de 309) |
|---|---:|---:|---:|---:|---:|---:|
| Solo umbral de PIIA-1 | 283 | 283 | 49 | 17,3 % | 49 de 49 | 26 |
| `gpt-6-luna` | 283 | 147 | 48 | 32,7 % | 48 de 49 (98,0 %) | 162 (52 %) |
| `gpt-6.1-terra` | 283 | 101 | 39 | 38,6 % | 39 de 49 (79,6 %) | 208 (67 %) |

Por clase, con las detecciones confirmadas y, entre paréntesis, cuántas son aciertos reales:

| Clase | Umbral | Pasan el umbral (aciertos) | `gpt-6-luna` | `gpt-6.1-terra` |
|---|---:|---:|---:|---:|
| `dent` | 0,3 | 65 (8 de 8) | 32 (8) | 26 (7) |
| `scratch` | 0,3 | 56 (8 de 8) | 47 (7) | 33 (5) |
| `crack` | 0,3 | 78 (8 de 8) | 37 (8) | 19 (6) |
| `glass shatter` | 0,6 | 18 (8 de 8) | 9 (8) | 7 (7) |
| `lamp broken` | 0,6 | 34 (8 de 8) | 12 (8) | 9 (7) |
| `tire flat` | 0,6 | 32 (9 de 9) | 10 (9) | 7 (7) |

Tokens y tiempo:

| | Tokens de entrada | Tokens de salida | Tiempo |
|---|---:|---:|---:|
| `gpt-6.1-terra` (medido) | 565.471 | 47.262 | 1.176 s (unos 20 min) |
| `gpt-6-luna` (estimado) | unos 0,55–0,57 M | unos 0,12 M | no medido |

Lo de `gpt-6.1-terra` suma las 39 llamadas de la prueba previa y las 270 de la ejecución
completa. Las respuestas de `gpt-6-luna` salían de la caché, que no guarda los tokens, así
que su fila es una estimación a partir de sus lotes anteriores (unos 1.800 tokens de entrada
y 380–400 de salida por llamada). No hay precios por millón de tokens, así que no se da coste
en euros.

**Qué muestra.**

- `gpt-6.1-terra` es una versión más estricta de `gpt-6-luna`: de las 103 detecciones que
  confirma, `gpt-6-luna` también confirma 102, y no confirma ningún acierto que
  `gpt-6-luna` no confirme.
- `gpt-6-luna` confirma 51 detecciones que `gpt-6.1-terra` no: 9 son aciertos de PIIA-1 y
  42 no lo son.
- `gpt-6.1-terra` contesta «incierto» en 60 detecciones (19,4 %) y `gpt-6-luna` en 8
  (2,6 %). Con los neumáticos es muy prudente: deja en «incierto» 21 de los 30 falsos
  positivos de `tire flat`, mientras que `gpt-6-luna` rechaza el 96,7 %.
- Cuando los dos confirman (102 detecciones), coinciden en la pieza en 76 y en la severidad
  en 64. CarDD no trae pieza ni severidad, así que esta medida no dice cuál acierta.

**Límites.**

- Son 40 imágenes y una sola ejecución, sin intervalos. Hay 8 o 9 aciertos por clase: un
  87,5 % es 7 de 8. La muestra se eligió con un mínimo de aciertos por clase y no refleja
  la proporción real.
- Los dos modelos son de la familia `gpt-6.x`.
- La verdad es el acierto de PIIA-1 contra CarDD. En `dent`, `scratch` y `crack` CarDD no
  anota todo el daño, así que muchos «falsos positivos» son daño real: la precisión de los
  dos modelos está infravalorada y quitar más falsos positivos no significa ser mejor en
  esas clases.
- `gpt-6.1-terra` fue también el juez de la Issue #44. Aquí no se usa el juez, la verdad es
  CarDD, así que no hay circularidad.

**Decisión.** El Agente 1 sigue con `gpt-6-luna`: conserva el 98 % de los aciertos de
PIIA-1, y los umbrales de la Issue #44 y las validaciones de la categoría del vehículo se
hicieron con sus respuestas. `gpt-6.1-terra` queda como alternativa más estricta, con más
precisión a cambio de perder aciertos y de dejar más detecciones para revisión; usarlo
obligaría a recalibrar los umbrales.

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
- **Las de la #44 están versionadas** en `etiquetas/` (ver su `README.md`): las 60
  humanas, la revisión humana de 60 hallazgos que el juez dejó en `dudo` o `no`, las
  3.712 del juez, esas mismas con la revisión aplicada y el resumen de su ejecución. Solo
  llevan ids y etiquetas, no recortes.
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
ejecutado el 2026-10-28 con `gpt-6.1-terra` (esfuerzo `high`) sobre los 3.712
hallazgos del lote de 500 imágenes y sobre las 60 etiquetas humanas del 2026-10-25.
Sus etiquetas no se usan para decidir umbrales hasta que el juez se acepte (puerta
G-1 de la #44).

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
  API seguidos se aborta conservando lo hecho; `--hilos` paraleliza. Al ejecutar imprime una línea al
  enviar cada hallazgo (`>> id clase: enviando…`) y otra al recibirlo (`[n/total] id clase -> etiqueta (segundos,
  tokens) | motivo`, o `(cache)` si ya estaba), para ver en todo momento que trabaja.
- **Salida** (en `piia2_detecciones/juez/<modelo>/`, ignorada por git): `etiquetas_juez.csv`
  (`finding_id,etiqueta`, mismo formato que las humanas, así que la tabla de precisión
  las lee tal cual), `detalle_juez.json` (con el motivo) y `resumen_juez.json` (modelo,
  esfuerzo, hash del prompt, llamadas, tokens, fallos).
- **El acuerdo no fija ningún umbral por sí solo:** si el juez no alcanza un acuerdo
  aceptable con las personas, sus etiquetas no se usan para decidir umbrales.
  El criterio de aceptación se decide en el plan de la #44 antes de ver los resultados.

## Tabla de precisión por clase y umbral

Con las etiquetas del juez, `tabla_umbrales.py` calcula, sin llamar a ninguna API, qué
parte de lo que la visión confirma es daño real según el score y la clase. Es lo que
hay que mirar antes de fijar umbrales; **no cambia ninguno**: solo calcula. Los que
salieron de esta tabla y del criterio de la D-6 (`dent`, `scratch` y `crack` a 0,3; el
resto sigue en 0,6) ya están aplicados en `confianza.py`.

```bash
python tabla_umbrales.py \
    --salidas ../../../../../piia2_detecciones/salida_agente1_500 \
    --etiquetas ../../../../../piia2_detecciones/juez/gpt-6.1-terra/etiquetas_juez.csv \
    --export ../../../../../piia2_detecciones/baseline_500 \
    --resumen ../../../../../piia2_detecciones/juez/gpt-6.1-terra/resumen_juez.json \
    --salida ../../../../../piia2_detecciones/juez/gpt-6.1-terra/tabla_umbrales.md
```

`--export` y `--resumen` son opcionales: el primero añade la comparación con el
`is_true_positive` de PIIA-1 y el segundo cita modelo, esfuerzo y prompt del juez en
la cabecera. El informe se imprime por pantalla y, con `--salida`, también se guarda. Si falta un archivo o
las etiquetas no son válidas, termina con `ERROR: …` y código 2.

Con `--criterio` añade al informe los umbrales que salen del criterio de la D-6 (plan v1.4 de la
Issue #44) y la tabla antes y después: para cada clase, el valor más bajo de la rejilla (0,3 a 0,9)
para el que, entre los candidatos con score ≥ umbral, el límite inferior del intervalo de Wilson al
95 % de la proporción de daño real (`si` y `otra` del juez) llega al 95 % (`--minimo-wilson` lo
cambia), con al menos 5 casos decididos; los `dudo` y los hallazgos sin etiqueta no cuentan en el
denominador. Si ningún valor lo alcanza, se mantiene el umbral actual. Sigue sin cambiar
`confianza.py`: solo calcula y enseña. Como ese archivo ya tiene los calibrados, `--desde-partida`
toma como umbrales actuales los de partida (0,7 y 0,6) para reproducir la tabla antes y después.

- **Qué cuenta como candidato:** un hallazgo que la visión confirmó, con pieza y regla
  de coste aplicable. Es el que sería nivel firme si su score llegara al umbral de su
  clase (`confianza.decidir_tier`). En el lote de 500 imágenes hay 1.558.
- **Daño real y clase correcta:** «daño real» cuenta `si` y `otra` del juez; «clase
  correcta», solo `si`. Los `dudo` y los hallazgos sin etiqueta no entran en el
  denominador y se muestran aparte. Cada porcentaje lleva su intervalo de Wilson al 95 %.
- **Celdas con pocos casos:** con menos de 5 decididos la celda se marca «no
  concluyente»; no hay que sacar conclusiones de ella.
- **Secciones del informe:** (1) por clase y tramo de score de 0,1; (2) acumulado por
  umbral (candidatos con score ≥ umbral), con el umbral actual marcado y los hallazgos
  que ganaría o perdería cada umbral frente a él; (3) lo que la visión rechaza, para
  ver qué daño real se estaría dejando fuera; (4) candidatos que `is_true_positive`
  daba por fallo y qué dice el juez de ellos (solo con `--export`).
- **Límite que conviene recordar:** las etiquetas humanas no contienen ningún `no`,
  así que no se ha validado con una persona que el juez detecte los hallazgos sin
  daño. Un 100 % de «daño real» en una celda significa que el juez no puso ningún
  `no` ahí, no que una persona lo haya comprobado.

## Pruebas sin API Key

`probar_vision_stub.py`, `probar_agente1_stub.py`, `probar_vehiculo_stub.py`,
`probar_evaluar_vehiculo_stub.py`, `probar_seleccion_stub.py`,
`probar_evaluar_vision_stub.py`, `probar_lote_stub.py`, `probar_etiquetado_stub.py`,
`probar_juez_stub.py` y `probar_tabla_umbrales_stub.py` usan un cliente falso de OpenAI o ninguno,
así que no necesitan API Key ni el paquete `openai`. `probar_evaluar_vision_stub.py` y
`probar_lote_stub.py` usan además el export real y las fotos del CarDD en local, y
`probar_etiquetado_stub.py` y `probar_tabla_umbrales_stub.py`, las salidas reales del lote
de la #43 (y, el segundo, el export y las etiquetas del juez), si están (si no, se saltan
esa parte).
`probar_vehiculo_stub.py` comprueba además la tabla de coches de referencia contra
`vehiculos.csv` del paquete de la empresa (si no está, salta esa parte con aviso).
`probar_con_imagenes_reales.py` prueba el recorte con fotos del CarDD en local
(`CarDD_release/`, no se sube a git).

## Pendiente

- Los 6 `CATEGORY_REVIEW_THRESHOLD` ya están calibrados (Issue #44, medición con las 500
  imágenes y etiquetas de un modelo juez, no verdad humana): `dent`, `scratch` y `crack`
  a 0,3 y el resto en 0,6. Se recalibran si cambian la estrategia, el prompt, el juez o el
  dataset (ver `specs/agente-confianza-hallazgos.md`).
