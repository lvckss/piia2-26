# Interpretación de daños a partir de una imagen (Agente 1)

> Esta spec sustituye a la de PIIA1, que describía el flujo imagen → daños con una API y una interfaz de demostración. Esos criterios se retiran por la decisión de alcance de PIIA2 (sin interfaz, sin API y sin ejecutar SAM3 en línea) y siguen en el historial de git.

## Qué construir

El Agente 1 (analista multimodal de PIIA2) convierte las detecciones de PIIA1 de una imagen, ya guardadas, junto con la foto en una lista de **hallazgos** revisables. Para cada detección candidata, un modelo de visión da una segunda opinión mirando la foto con la zona marcada y su recorte ampliado, e indica:

- el **veredicto**: `confirmado`, `rechazado` o `incierto`;
- la **pieza** afectada (`pieza_id`), elegida de las 35 piezas del catálogo de la empresa (`piezas.csv`);
- la **severidad**: `leve`, `moderado` o `grave`;
- una **descripción** breve en español;
- `regla_coste_aplicable`: si la herramienta de costes de la empresa tiene una regla para esa clase de daño, zona de la pieza y severidad.

**Entrada.** El JSON de detecciones de PIIA1 de una imagen (`image_id`, `image_path`, `image_width`, `image_height` y `predictions[]` con `instance_index`, `damage_class`, `score`, `bbox_xywh`…) y la foto. Las detecciones se generaron una sola vez para 500 imágenes de CarDD (`val` y `test`); no se ejecuta SAM3.

**Salida** (contrato Agente 1 → Agente 2 y Agente 3; ejemplo en [`ejemplos_contrato/agente1_salida.json`](../app/agentes/ejemplos_contrato/agente1_salida.json)). Un JSON con `image_id`, `resumen_filtro_previo` y `findings[]`. Cada hallazgo tiene:

| Campo | Contenido |
|---|---|
| `finding_id` | `<image_id>-<instance_index>` |
| `category`, `clase_tool` | Clase de daño de PIIA1 y su nombre para la herramienta de costes (espacios sustituidos por guiones bajos) |
| `score`, `score_tier` | Puntuación de PIIA1 y nivel de confianza solo por score |
| `confidence_tier` | Nivel de confianza final (ver [`agente-confianza-hallazgos.md`](agente-confianza-hallazgos.md)) |
| `bbox_xywh` | Caja de la detección |
| `vision_verdict`, `pieza_id`, `severidad`, `regla_coste_aplicable`, `vision_description` | Resultado de la segunda opinión de visión |
| `crop_image_path` | Recorte de la zona, guardado en disco |

**Dónde encaja.** Entre PIIA1 (detecciones guardadas) y el Agente 2 (costes y cobertura) y el Agente 3 (informe). El filtro previo de detecciones y el nivel de confianza se especifican en [`agente-confianza-hallazgos.md`](agente-confianza-hallazgos.md); la categoría del vehículo, propuesta de la [Issue #28](https://github.com/lvckss/piia2-26/issues/28) pendiente de aprobación (hoy el vehículo es un dato de entrada del siniestro, ver [`piia2-arquitectura-multiagente.md`](piia2-arquitectura-multiagente.md)), que añadiría el campo `vehiculo` a la salida.

## Por qué

Una detección por sí sola no sirve para un peritaje. A score ≥ 0,3, PIIA1 deja unas 37 detecciones por imagen y su precisión es inferior al 15 % en todas las clases de CarDD; además CarDD no trae la pieza ni la severidad, que es lo que necesita la herramienta de costes para presupuestar. La empresa propuso un modelo de visión como segunda opinión para limpiar los falsos positivos.

Esta funcionalidad convierte las detecciones en hallazgos con veredicto, pieza y severidad, y mantiene el vínculo con la zona de la imagen (caja y recorte) que originó cada conclusión, de modo que una persona pueda revisarla.

## Alcance

- **Incluido:** leer las detecciones guardadas; aplicar el filtro previo; recortar cada hallazgo candidato; consultar al modelo de visión, una vez por hallazgo y con caché; validar la respuesta; calcular `regla_coste_aplicable`; asignar el nivel de confianza; devolver el JSON del contrato.
- **Fuera de alcance:** detectar daños o ejecutar SAM3 (PIIA1 los deja guardados); una API, una interfaz o la visualización de resultados; validar ficheros subidos; estimar la categoría del vehículo (propuesta de la Issue #28); calcular costes o cobertura (Agente 2); redactar el informe (Agente 3); comparar modelos de visión.

## Restricciones y supuestos

- Las detecciones y la foto son ficheros ya existentes en disco. La foto se localiza con el `image_path` del JSON o con una ruta alternativa indicada al ejecutar (por ejemplo, el CarDD montado en Colab).
- Se hace una consulta por hallazgo candidato, con dos imágenes: la foto completa con la zona marcada con una caja roja y un recorte ampliado. La respuesta es un JSON. Las respuestas se guardan en caché por modelo, texto de la consulta e imágenes, de modo que la misma consulta no se paga dos veces.
- **La respuesta del modelo se valida y nunca se acepta tal cual.** Un veredicto fuera de `confirmado`, `rechazado` o `incierto` se trata como `incierto`; una pieza que no está en el catálogo o una severidad fuera de `leve`, `moderado` y `grave` se descarta; un `rechazado` no conserva pieza ni severidad.
- El modelo y la clave son los de la empresa: el identificador del modelo va en `OPENAI_MODEL` (o en el parámetro `modelo`) y la clave en `OPENAI_API_KEY`; nunca se guardan en el repositorio.
- No se identifican personas, propietarios ni matrículas: la consulta solo pregunta por el daño de la zona marcada.
- **La segunda opinión es orientativa.** No se puede medir contra CarDD si la pieza y la severidad son correctas, porque CarDD no trae esas etiquetas: hace falta revisar a mano una muestra.
- La salida de los hallazgos no registra todavía el modelo de visión usado (la caché sí lo guarda).
- El vehículo es hoy un dato de entrada del siniestro, no algo que el Agente 1 deduzca. Si se aprueba e integra la propuesta de la Issue #28, la salida ganaría el campo `vehiculo` y el criterio AC-001, que fija las claves de la salida, se actualizaría.

## Criterios de aceptación

**Cómo leer la columna de verificación.** *Verificado*: el comando se ejecuta y pasa. *Parcial*: parte del criterio está verificada y se indica cuál. *Pendiente*: no hay verificación todavía, con el motivo o la Issue que la cubrirá. Los comandos se ejecutan desde `app/agentes/agente_multimodal/`; algunos usan el paquete de datos de la empresa (`piia2_paquete_datos/`) o el export de 500 imágenes en local y se saltan con un aviso si no están.

| ID | Dado / Cuando | Resultado esperado | Verificación y estado |
|---|---|---|---|
| AC-001 | Las detecciones de una imagen y su foto, al ejecutar el Agente 1 con un cliente de visión simulado. | La salida tiene exactamente las claves `image_id`, `resumen_filtro_previo` y `findings`. Cada hallazgo tiene exactamente los campos `finding_id`, `category`, `clase_tool`, `score`, `score_tier`, `confidence_tier`, `bbox_xywh`, `vision_verdict`, `pieza_id`, `severidad`, `regla_coste_aplicable`, `vision_description` y `crop_image_path`. | `python probar_agente1_stub.py` compara el conjunto de claves. **Verificado.** |
| AC-002 | El mismo caso. | `clase_tool` es la clase con los espacios sustituidos por guiones bajos; `vision_verdict` es `confirmado`, `rechazado` o `incierto`; `vision_description` no está vacía; el recorte de cada hallazgo existe en disco; el JSON guardado en la ruta de salida es idéntico al devuelto. | `python probar_agente1_stub.py`. **Verificado.** |
| AC-003 | Una respuesta del modelo que no es JSON; una pieza inventada; un rechazo que trae pieza y severidad; una pieza válida sin regla para su clase y severidad; o una respuesta válida envuelta en un bloque de código. | Sin JSON: veredicto `incierto` y sin pieza. Pieza inventada: sin pieza y sin `regla_coste_aplicable`. Rechazo: sin pieza ni severidad. Pieza válida sin regla: `regla_coste_aplicable` falso. El bloque de código se acepta. En ningún caso se lanza una excepción. | `python probar_vision_stub.py` (`probar_parseo`). **Verificado.** |
| AC-004 | Una imagen con tres hallazgos candidatos y un cliente simulado con caché. | Se hace una consulta por hallazgo, con el modelo indicado, formato de respuesta JSON y dos imágenes adjuntas en `data:image/jpeg;base64`. Repetir la consulta con la caché activa no hace ninguna llamada nueva, y el contador de uso suma solo las llamadas reales. | `python probar_vision_stub.py` (`probar_enriquecer`). **Verificado.** |
| AC-005 | Una imagen con 9 detecciones de las que el filtro previo deja 6. | Solo las 6 candidatas se convierten en hallazgos, y `resumen_filtro_previo` registra `detecciones_totales`, `candidatas` y `descartadas_por_clase`: ninguna detección desaparece sin dejar rastro. | `python probar_seleccion_stub.py` (`probar_casos_pequenos`). **Verificado.** |
| AC-006 | El catálogo de la empresa extraído en `piia2_paquete_datos/`. | Contiene 35 piezas y 45 reglas de daño. | `python probar_vision_stub.py` (`probar_catalogo_real`). **Verificado** con el paquete presente. |
| AC-007 | La salida de un hallazgo. | Registra el modelo de visión con el que se obtuvo. | **Pendiente.** La salida actual no lo incluye (solo la caché). La Issue #28 lo añade para `vehiculo`; para los hallazgos lo cubre la [Issue #45](https://github.com/lvckss/piia2-26/issues/45). |
| AC-008 | El texto de la consulta de visión que se envía al modelo. | No pide matrículas, propietarios ni personas: solo el tipo de daño, la pieza y la severidad de la zona marcada. | **Pendiente de prueba automática.** El texto actual (`PROMPT_TEMPLATE` en [`vision.py`](../app/agentes/agente_multimodal/vision.py)) lo cumple al leerlo. |
