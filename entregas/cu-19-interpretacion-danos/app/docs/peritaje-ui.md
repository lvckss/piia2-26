# Pestaña Peritaje

Issue [#34](https://github.com/lvckss/piia2-26/issues/34). [Complemento UI v2: documentos, AC-016–018](https://github.com/lvckss/piia2-26/issues/34#issuecomment-7138654855). Plan: [Spec 34 v1.7](../../specs/34-orquestacion-web.md) y [complemento UI v1 / AC-015](https://github.com/lvckss/piia2-26/issues/34#issuecomment-7135966562). Arquitectura: [ADR 0007](../../docs/adr/0007-orquestacion-adk-web-efimera.md), aceptado mediante #60.

La pestaña **Peritaje**, en `/peritaje`, convive con Playground y Explorar dataset. Conserva componentes, tipografía y aspecto de la aplicación existente. Permite elegir una imagen original con los servicios y filtros del explorador o subir JPEG/PNG. Seleccionar y navegar no inicia inferencia.

En la demo local se elige una de las 500 imágenes de `app/bd/subset_500/`, cuyos documentos contienen predicciones de PIIA 1 ya exportadas. El selector muestra solo ese lote y no ofrece subidas nuevas. SAM3 no se carga ni se ejecuta; el Agente 1 sí consulta GPT al pulsar el botón. Una imagen del explorador general, como `000009.jpg`, puede no pertenecer a ese lote.

El recorrido es: imagen → «Analizar imagen» → resultados de solo lectura → confirmar/elegir vehículo y completar el siniestro → «Generar informe» → Markdown visible y descargable. La categoría desconocida muestra V14 y las advertencias acordadas; el navegador no fabrica `vehiculo_origen`. La póliza solo se envía para rol propio. Los datos y presupuestos los produce el servidor.

En **Siniestro**, «Datos para el presupuesto» empieza plegado y muestra un resumen de los valores actuales. Los valores iniciales acordados para la demo son 3 años, 42.000 km, Madrid, taller multimarca, pintura sólida, pieza OEM, vehículo propio y Terceros Básico. Son editables y se conservan al plegar el bloque y al actualizar los catálogos. Solo se preseleccionan opciones que existen en el catálogo; si falta alguna, debe completarse antes de generar el informe. El aviso visible incluso con el bloque cerrado explica que, en un sistema integrado, estos datos se cargarían desde el cliente y su póliza en la aseguradora, mientras esta demo usa ejemplos modificables.

Confirmar la propuesta actualiza el campo **Vehículo** y conserva `referencia_confirmada`; cambiar el selector registra `seleccion_usuario`. Se mantienen el caso desconocido/V14 y la omisión de póliza para tercero. Criterio humano y Test Plan: [concreción UI v3, AC-003/004](https://github.com/lvckss/piia2-26/issues/34#issuecomment-7139477864).

## Estado de integración

Este incremento implementa el **cliente web**, las rutas Hono y el servicio Python de orquestación. Hono transporta `/api/catalogos` y `/api/peritajes` al servicio interno; Python ejecuta PIIA 1 → Agente 1 y, tras recibir contexto válido, Agente 2 → informe → verificación de cifras. Los proveedores reales se conectan desde `agentes/orquestador/pipeline.py`; los dobles de ML/visión solo existen en tests. Compose completo y el recorrido con modelos reales siguen pendientes en #34.

Los esquemas de `server/models/` necesarios para reutilizar el explorador se incluyen como código fuente: antes una regla de ignorado de pesos `models/` también los excluía del repositorio. Las carpetas de modelos, imágenes, credenciales y resultados locales siguen ignoradas.

## Ejecutar y comprobar

Desde `app/`, instalar dependencias con `bun install`; desde `app/frontend/`, ejecutar también `bun install`. Arrancar el backend con su configuración habitual y `bun run dev` desde `app/`; arrancar Vite con `bun run dev` desde `app/frontend/`. La UI usa los proxies `/api` y `/dataset` existentes.

Desde la carpeta de la entrega, preparar e iniciar el servicio Python en otra terminal:

```sh
just orquestador-setup
PERITAJE_DETECTION_SOURCE=export just orquestador
```

El orquestador escucha en `127.0.0.1:8004`; Hono usa `ORQUESTADOR_URL` si se necesita otra dirección. `PERITAJE_DETECTION_SOURCE=export` selecciona la lectura de documentos. `PERITAJE_EXPORT_DIR` y `PERITAJE_DATASET_DIR` permiten cambiar las rutas del lote y los originales. Si se selecciona la vía `api` (valor por defecto del código para preservar el recorrido original), el detector debe estar iniciado en `http://127.0.0.1:8001`, configurable mediante `ML_API_URL`. Su arranque está documentado en [ML API](../docker/ml-api/README.md); `PROJECT_MODELS_DIR` permite indicar la carpeta local de pesos al contenedor. El orquestador lee `.env` de la entrega y `app/.env` sin sobrescribir variables ya exportadas. Necesita `OPENAI_API_KEY` válida y `OPENAI_MODEL` con un identificador disponible en esa cuenta. No existe un modelo por defecto ni se habilita gasto RAG automáticamente.

La vía API es independiente del modo de documentos y permanece pendiente de su verificación completa. El detector puede estar en otra máquina: configurar `ML_API_URL` con la URL base de su API, sin añadir `/v1/damage-assessment`. La web no necesita cargar los pesos en el PC del navegador. Antes de reenviar una imagen tras corregir la conexión, pulsar «Nuevo peritaje»: un caso fallido no se reejecuta automáticamente.

El servidor verifica nombre/ID, dimensiones, píxeles originales, índices y geometría del documento antes de visión. No utiliza `ground_truth`, `is_true_positive`, `best_iou` ni las rutas de Colab para resolver hallazgos. Conserva ID, índices, clases, scores y bbox de las predicciones exportadas; el ID opaco de ejecución es distinto del `image_id` de la foto. Un nombre de archivo coincidente con píxeles diferentes se rechaza. No hay fallback silencioso a inferencia.

El análisis es asíncrono: los POST aceptados responden 202 y el GET informa del progreso o del fallo de etapa. Un detector apagado produce `ML_NO_DISPONIBLE`; un 401 de OpenAI produce `VISION_NO_DISPONIBLE`. No se publica ni permite descargar un informe que falle `comprobar_cifras()`.

El servicio conserva dos casos por defecto (`PERITAJE_CAPACITY`) y caduca los inactivos a los 3600 segundos (`PERITAJE_TTL_SECONDS`). Polling y descarga no renuevan ese plazo; no se borran casos en ejecución. El barrido periódico funciona cada 30 segundos. Se utiliza un único proceso Python; varios workers no comparten la deduplicación. Descartar y el apagado ordenado eliminan los temporales propios. La limpieza de temporales tras una terminación abrupta sigue pendiente.

Para instalar el navegador de pruebas desde `app/frontend/`:

```sh
bunx playwright install chromium --only-shell
```

Checks:

```sh
# Desde app/
bun run test:peritaje
bun test server/routes/peritajesRoute.test.ts server/routes/peritajes.integration.test.ts

# Desde app/agentes/orquestador/, con dependencias y paquete local preparados
../../../.venv-rag/bin/python -m unittest -v test_exportados test_workflow

# Desde app/frontend/
bun run build
bunx tsc -b
bunx eslint src/features/peritaje src/lib/dataset-url.ts src/routes/peritaje.tsx tests/peritaje playwright.config.ts
```

Puede usarse `PLAYWRIGHT_BROWSERS_PATH` para ubicar el navegador fuera del directorio por defecto. Playwright levanta Vite con Node en `127.0.0.1:5183` (puerto aislado del servidor de desarrollo). Sus respuestas son deterministas y no consultan ML/OpenAI, PostgreSQL ni los archivos de CarDD. Los resultados y trazas se guardan localmente y no se versionan.

Trazabilidad: los nombres de las pruebas indican los AC de la Spec o del complemento. Verifican acciones explícitas, filtros y original, límites de bytes/píxeles, confirmación/selección, tercero, 422 recuperable, claves y doble clic, polling y caso perdido, estados RAG, errores y contrato, descarga UTF-8, HTML inerte, descarte y navegación móvil/explorador.

## Contrato que consume el cliente

El cliente valida las respuestas con `src/features/peritaje/api.ts`. Catálogos: arrays `vehiculos`, `polizas`, `regiones`, `tipos_taller`, `acabados` y `tipos_pieza`, con opciones `{id, nombre}`. Son datos del servidor, no valores inventados por el formulario.

La fase A envía multipart `file`; ambos POST llevan `Idempotency-Key`. La fase B envía `{contexto, seleccion_vehiculo?}` y nunca envía findings, tiers ni procedencia libre. Para contexto corregido se crea otra clave; un reintento explícito del mismo contenido conserva la suya.

Las respuestas de ejecución contienen `ejecucion_id`, `estado`, `etapa`, `analisis`, `resultado`, `error`; los tres últimos son anulables según la fase. `analisis` conserva `image_id`, `vehiculo` y `findings` públicos del Agente 1. `resultado` contiene `markdown` y `agente2` con `diagnostico_rag`. Solo se muestra y descarga en `completada`, sin error, y se rechaza un GET que devuelva el ID de otro caso. Estos detalles de serialización concretan el contrato de la Spec.

No hay historial ni reenvío automático de POST. Un fallo de polling exige consulta explícita y no reinicia el análisis. Descartar usa DELETE; si el servidor no confirma la limpieza, conserva el caso y muestra el error. La descarga conserva los mismos bytes UTF-8 del Markdown recibido; el renderizador deshabilita HTML crudo y no carga imágenes incluidas en el texto generado.

La suite Python verifica, con ML/visión inyectados, costes e informe reales, contexto corregible, procedencia, cero detecciones, igualdad de bytes, bloqueo de cifras, idempotencia, capacidad y caducidad. Las pruebas Hono verifican el transporte y las rutas reales. La demo de documentos se comprobó con una imagen (001422) y GPT real: análisis, contexto, costes, informe, descarga literal, cero cifras ajenas y descarte. El RAG estuvo sin autorización de ejecución y el informe lo señaló como preliminar. El recorrido original con inferencia ML para imágenes nuevas, Compose, la limpieza tras caída del proceso y la lectura humana de 3–5 informes permanecen pendientes. Estas comprobaciones no acreditan la DoD completa de #34.

## Liberar casos retenidos — ajuste UI v5

Por petición de Lucas, el botón **Liberar casos**, en la esquina inferior derecha, llama a `DELETE /api/peritajes`. Descarta los casos terminados, fallidos o pendientes de datos y elimina sus temporales; si incluye al caso mostrado, la vista vuelve al inicio. Si aún hay consultas activas, las conserva y muestra su número: no promete cancelar llamadas ya enviadas a GPT. La respuesta contiene IDs descartados y número de casos en curso. Mantiene el límite y la protección de las ejecuciones activas del ADR 0007 (REUSE_ADR); no introduce persistencia ni otros servicios.

Las cajas y el panel de daños se rigen por [UI v4, AC-019/020](https://github.com/lvckss/piia2-26/issues/34#issuecomment-7139877038). El usuario pidió detener las comprobaciones automáticas y validar él mismo; la comprobación final de este botón y del conjunto queda pendiente de su validación. Verificación manual prevista: liberar dos casos retenidos, volver al inicio si se descarta el actual y comprobar el mensaje cuando queden análisis en curso. No se declaran comprobaciones no ejecutadas ni DoD global satisfecha.
