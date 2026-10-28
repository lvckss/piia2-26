# Notas de arquitectura: Explorer, Playground e inferencias

  ## Contexto del proyecto
  La webapp actual sirve como demo visual para explorar el dataset.

  El objetivo real del proyecto es investigar arquitecturas ad hoc para aumentar la robustez de SAM3 sin reentrenamiento, en escenarios zero-shot o few-shot.

  La idea es usar el dataset explorer como punto de entrada para seleccionar imágenes y después llevarlas a un Playground donde ejecutar distintos pipelines de inferencia, por ejemplo con
  SAHI.

  ## Estado actual del repo
  La parte más sólida ahora mismo es el explorer del dataset:
  - grid de imágenes
  - filtros
  - diálogo de detalle
  - API de imágenes paginada y filtrada

  Hay una base útil para frontend y backend, pero la parte de inferencia todavía no está integrada realmente:
  - la ruta SAM3 no está montada en la app
  - la ruta usa un path de imagen fake
  - el servicio ML tiene rutas hardcodeadas
  - no existe todavía persistencia de runs de inferencia

  ## Dirección propuesta
  Separar claramente dos áreas de producto:

  ### Explorer
  Responsabilidad:
  - navegar por el dataset
  - filtrar imágenes
  - inspeccionar anotaciones
  - seleccionar una imagen para experimentar

  ### Playground
  Responsabilidad:
  - cargar una imagen concreta por `imageId`
  - configurar un pipeline
  - ejecutar inferencia
  - visualizar resultados
  - comparar runs

  ## Flujo de usuario deseado
  1. El usuario navega por el Explorer.
  2. Selecciona una imagen del grid.
  3. Usa una acción como `Abrir en Playground`.
  4. La app navega a una ruta tipo `/playground?imageId=123`.
  5. El Playground carga la imagen y sus metadatos.
  6. El usuario elige pipeline y parámetros.
  7. Lanza una inferencia.
  8. Ve overlays, resultados y, si hay persistencia, historial de runs.

  ## Decisión importante
  El Playground no debería recibir la imagen completa desde frontend.

  Debe trabajar con un identificador estable:
  - `imageId`

  Eso hace que:
  - la URL sea reproducible
  - el backend resuelva siempre la ruta real de la imagen
  - el sistema sea más mantenible
  - no dependamos de estado volátil entre rutas

  ## Arquitectura recomendada

  ### Frontend
  Rutas separadas:
  - `/explorer`
  - `/playground`

  Navegación:
  - desde una tarjeta del explorer o desde el diálogo de imagen
  - enviar al playground con `imageId`

  UI del Playground:
  - panel principal con imagen y overlays
  - panel lateral con configuración del pipeline
  - sección con resultados e historial/comparación

  ## Backend
  Crear un concepto de "run de inferencia" o "run experimental".

  No pensar la inferencia como una llamada suelta al modelo, sino como una ejecución trazable.

  Rutas recomendadas:
  - `POST /api/runs`
  - `GET /api/runs/:id`
  - `GET /api/images/:id/runs`

  Responsabilidad del backend:
  - recibir `imageId`, pipeline, prompt y parámetros
  - resolver la ruta real de la imagen desde BD
  - delegar en el servicio ML
  - guardar el resultado del run
  - devolver el run y sus resultados

  ## Servicio ML
  No dejarlo como un único endpoint genérico sin estructura.

  Organizarlo como runners de pipeline:
  - `sam3-direct`
  - `sam3-sahi`
  - futuros pipelines ad hoc

  Ejemplo conceptual:
  - `runSam3Direct`
  - `runSam3WithSahi`

  ## SAHI
  Pipeline esperado:
  1. resolver imagen
  2. trocear en tiles
  3. ejecutar SAM3 por tile
  4. remapear resultados a coordenadas globales
  5. fusionar duplicados

  Primera implementación razonable:
  - soporte de boxes y masks
  - merge simple por IoU
  - visualización clara en el Playground

  ## Persistencia en BD
  Sí, tiene sentido ampliar el schema para guardar inferencias.

  Ahora mismo el schema solo modela:
  - imágenes
  - etiquetas
  - instancias base del dataset

  Para investigación y comparación entre pipelines, conviene guardar runs.

  ### Recomendación práctica
  Empezar con una tabla `inference_runs`.

  Campos mínimos:
  - `id`
  - `image_id`
  - `pipeline`
  - `prompt`
  - `params_json`
  - `status`
  - `result_json`
  - `created_at`
  - `finished_at`

  Esto permite:
  - reproducibilidad
  - historial por imagen
  - comparar configuraciones
  - revisar resultados más tarde

  Más adelante, si hace falta análisis más fino, separar:
  - `inference_runs`
  - `inference_predictions`
  - `inference_metrics`

  Pero no hace falta sobre-normalizar desde el principio.

  ## Decisión recomendada
  Sí:
  - crear ruta de inferencias/runs
  - actualizar schema
  - guardar resultados en BD

  No:
  - pasar paths de imagen desde frontend al servicio ML
  - dejar la inferencia como una acción efímera sin trazabilidad
  - meter lógica de experimento directamente en el explorer

  ## Prioridad de implementación
  1. Conectar Explorer con Playground mediante `imageId`
  2. Crear la ruta `playground`
  3. Diseñar contrato backend para runs
  4. Añadir persistencia mínima en BD
  5. Implementar `sam3-direct`
  6. Implementar `sam3-sahi`
  7. Añadir comparación de runs

  ## Conclusión
  La idea tiene sentido.

  La dirección correcta es:
  - Explorer para explorar dataset
  - Playground para ejecutar experimentos reproducibles sobre una imagen concreta
  - inferencias guardadas como runs persistentes en BD
  - pipelines intercambiables para comparar robustez sin reentrenamiento
