# Spec: Orquestación desde la web, de una imagen subida al informe

- GitHub Issue: https://github.com/lvckss/piia2-26/issues/34
- Estado: Borrador v1, 2026-10-27.
- ADR decision: NEW_ADR.
- ADR: [0007 — Orquestación ADK y ejecución web efímera](https://github.com/lvckss/piia2-26/blob/plan/34-orquestacion-web/docs/adr/0007-orquestacion-adk-web-efimera.md), Propuesto.
- Justificación: adopta ADK como dependencia del producto, define una frontera HTTP entre web y servicio Python y el ciclo de vida de las ejecuciones. Los ADRs 0002–0005 aceptados cubren contratos, proveedor, costes y filtro previo; no cubren estas decisiones.
- Plan vigente / versión: v1 en `plan/34-orquestacion-web`; el comentario de planificación de #34 fija el commit publicado. Continúa el [registro de alcance](https://github.com/lvckss/piia2-26/issues/34#issuecomment-6426795027).
- Riesgo y revisión previa: sí, por NEW_ADR y por el acuerdo del equipo. Impacto en cifras y fuentes del informe, frontera entre servicios, subida de archivos y nuevas dependencias de #28/#31/#32. La implementación y sus planes deben revisarse por los responsables afectados; el documento completo todavía no tiene aceptación humana.
- Planning PR: pendiente de publicar desde esta rama; será draft mientras se acuerdan las dependencias indicadas al final.

## Qué construir

Una pestaña independiente de la web que permita subir una imagen, ver el
diagnóstico de daños, confirmar o corregir el vehículo propuesto, completar el
contexto y obtener el informe formateado y descargable como Markdown.

El recorrido tiene dos fases, separadas por la intervención del usuario:

1. **Analizar imagen:** subida y normalización → PIIA 1 → Agente 1, incluida la
   categoría de #28 → resultados de daños sin edición y propuesta de vehículo.
2. **Generar informe:** contexto validado y vehículo confirmado/corregido →
   `agente2()` de #32, que integra costes de #30 y RAG → Agente 3 de #31 →
   verificación de cifras → presentación y descarga de los mismos bytes Markdown.

No hay historial de casos. La ejecución conserva únicamente el estado y los
archivos temporales necesarios para completar estas dos fases y descargar el
resultado. El índice del RAG y los datos del explorador mantienen su persistencia.

### Decisiones de Lucas y propuestas técnicas

Lucas confirmó en la conversación del 2026-10-26/27: entrada desde la web,
pestaña separada y una imagen subida; recuperar la categoría automática con
confirmación/corrección del vehículo; mostrar los daños sin permitir editar
pieza ni severidad; mostrar y descargar Markdown, sin historial; utilizar ADK.
Las decisiones iniciales constan en el registro de alcance enlazado arriba y
en la [solicitud de retomar #28](https://github.com/lvckss/piia2-26/issues/28#issuecomment-6426798908).
El objetivo de levantar el conjunto con Compose se conserva del diseño de #32.

Las rutas HTTP, estados, separación en servicios y forma de presentar la
procedencia del vehículo que siguen son **propuestas de este borrador**, para
revisar con el equipo. No se atribuye a Lucas ni a PRs anteriores la aprobación
anticipada de esos contratos ni del ADR 0007.

### Estado actual y evidencia

Snapshot leído: `main` `d5dd44d4ff89d64fecb7eeff83ef7a55b5b560af`.

- La web es React/Vite con TanStack Router. `app/frontend/src/routes/__root.tsx`
  contiene la navegación y `routes/explorer.tsx` el explorador. No existe la
  pestaña de peritaje.
- Bun/Hono sirve `/api/images`, `/api/instances` y el frontend compilado desde
  `app/server/app.ts`. No monta una ruta de peritaje. Los archivos de SAM3 en
  `server/routes/` no son una integración del flujo multiagente.
- PIIA 1 **ya admite una imagen subida**: `app/ml/api/routes/damage_assessment.py`,
  `POST /v1/damage-assessment`. Devuelve `vehicle_damage_assessment` con clase,
  bbox `x,y,width,height`, área y score; visualización opcional.
- `analizar_imagen` en `app/agentes/agente_multimodal/agente1.py` recibe un JSON
  de detecciones y una ruta de imagen. `hallazgos.py` espera `image_id` y
  `predictions`, con `instance_index`, `damage_class`, `bbox_xywh` y `score`.
  Hace falta adaptar la respuesta HTTP, no volver a detectar ni duplicar la visión.
- Costes está integrado por [#59](https://github.com/lvckss/piia2-26/pull/59):
  `estimar_siniestro` exige un vehículo válido y deja `normativa: []`.
- [#52](https://github.com/lvckss/piia2-26/pull/52), integrada en este snapshot,
  acredita una tool con ADK/OpenAI y conservación de su importe, no el flujo
  completo. Sus dependencias son propias del experimento; no constituyen un
  entorno de producto ya verificado.
- RAG: [#56](https://github.com/lvckss/piia2-26/pull/56), `c77a17c`, sigue draft,
  con `agente2()` y `diagnostico_rag` propuestos. Informe: spec v2 integrada por
  [#58](https://github.com/lvckss/piia2-26/pull/58); aún no existe `informe.py`.
- Categoría: [#29](https://github.com/lvckss/piia2-26/pull/29), `e180219`, tiene
  ADR 0001 Propuesto y fallback automático a categoría C. El nuevo recorrido
  pide selección al usuario con `desconocido`: esa adaptación sigue pendiente
  en #28, con Lucía. Los AC de origen del coche se retiraron en #30/#31.
- Hay Compose para ML en `app/docker/ml-api/`; no uno que levante el conjunto.
  El backend requiere `DATABASE_URL`, el schema vive en `app/bd/schema.sql` y
  los agentes localizan el paquete buscando `.git`: esto requiere resolver
  las rutas de datos en el empaquetado, no montar el historial Git como dependencia.

## Por qué

El resultado útil es un diagnóstico e informe sobre una imagen subida, con
las dudas y los límites visibles. Los componentes actuales funcionan de forma
aislada y sus formatos no se conectan automáticamente. La web debe completar
el recorrido sin exigir al usuario rutas locales, JSON de CarDD ni comandos.

El LLM interpreta la imagen; la herramienta de Plexus calcula; el RAG aporta
fuentes; el generador determinista redacta. La orquestación coordina estas
responsabilidades y detecta los fallos entre ellas.

## Alcance

- Incluido: pestaña y subida; formulario de contexto; adaptación PIIA 1 →
  Agente 1; integración de categoría; confirmación/corrección del vehículo;
  coordinación ADK; integración con #30/#31/#32; errores y progreso;
  comprobación de cifras; renderizado y descarga Markdown; ejecución efímera;
  Compose del conjunto; ejemplo reproducible y comprobación con 3–5 imágenes.
- Fuera de alcance: PDF, historial, cuentas de usuario y despliegue público;
  varias imágenes en una solicitud; edición manual de daños; identificar
  marca/modelo exactos desde la foto; implementar el clasificador de #28,
  el RAG de #32 o el informe de #31 dentro de esta Issue; cambiar reglas de
  costes, filtros o umbrales; comparar modelos; evaluación global de #46;
  APIs de aseguradoras/talleres y funciones nuevas de exclusiones/plazos.

La web amplía el alcance inicial de #34 por decisión explícita de Lucas. El
trabajo de #28 no se absorbe ni se reasigna desde este plan. El impacto en el
calendario y el contrato de procedencia se acuerdan con Lucía y Víctor antes
de Ready. No se reactivan silenciosamente los AC retirados de sus planes.

## Restricciones y supuestos

### Recorrido de usuario

- Una pestaña `/peritaje`, separada del explorador. Elegir una imagen y pulsar
  «Analizar imagen» inicia la fase de pago; elegir el archivo por sí solo no
  llama al proveedor. Se admiten JPEG y PNG decodificables; se rechazan archivos
  vacíos, múltiples archivos y contenido inválido antes de llamar a ML/OpenAI.
- Se normalizan orientación y píxeles una vez; PIIA 1, Agente 1 y categoría
  usan la misma imagen normalizada. La caja de un daño conserva las mismas
  coordenadas en todo el recorrido. El servidor asigna nombres e identificadores;
  el cliente no proporciona rutas de archivos.
- Tras el análisis se presentan hallazgos y niveles de confianza tal como los
  devuelve el Agente 1, sin controles para editar pieza, severidad o veredicto.
- La propuesta usa una categoría de `A`, `B`, `C`, `SUV-B`, `SUV-C`, `FURG`,
  `C-PREMIUM`, `D-PREMIUM` y su representante. La tabla y su calidad pertenecen
  a #28. `desconocido` requiere selección explícita de un vehículo del catálogo.
  Una respuesta incompleta o un fallo técnico no autorizan un coche por defecto.
- Se permite confirmar el representante o seleccionar otro vehículo del catálogo.
  Seleccionar un modelo confirma una elección del usuario, no que la foto haya
  permitido identificarlo. El informe conserva esa distinción.
- El contexto tiene los campos de #30: `vehiculo_id`, `region`, `tipo_taller`,
  `acabado`, `tipo_pieza`, `rol`, `edad_anios`, `km` y `poliza_id` para rol propio.
  Los desplegables proceden de los catálogos de Plexus; no se infiere póliza ni
  antigüedad desde la foto. Se preserva la rama de tercero perjudicado.
- «Generar informe» solo continúa con datos válidos. Corregir el contexto antes
  de enviarlo no vuelve a ejecutar PIIA 1, visión ni categoría. La primera versión
  no ofrece editar el caso una vez generado: se descarga o se inicia uno nuevo.

### Orquestación ADK

ADK coordina etapas en orden fijo, utilizando sus agentes/workflows nativos.
Se proponen adaptadores mínimos de `BaseAgent` para invocar las funciones
existentes y una secuencia por fase. No se añade un modelo coordinador que
decida qué agentes saltarse ni que reescriba las cifras. Las llamadas al modelo
siguen dentro de visión/categoría y embeddings, con su configuración existente.

- Fase A: PIIA 1 → adaptación de detecciones → Agente 1 con categoría de #28.
- Espera explícita de confirmación y contexto en la web; sin llamadas de pago.
- Fase B: `agente2(salida_agente1, contexto)` →
  `generar_informe(salida_agente1, salida_agente2, hoy=fecha_fijada)` →
  `comprobar_cifras(informe, salida_agente2)` → publicación.

`agente2()` calcula una sola vez mediante #30; no se llama antes a
`estimar_siniestro` para luego repetirlo dentro de `agente2()`. No se vuelven
a calcular tiers ni se modifica el JSON para promover hallazgos dudosos.
Cada ejecución tiene su estado ADK aislado; no comparte datos de otro caso.
La versión del framework y dependencias se fijarán y comprobarán al implementar,
partiendo de la prueba #33. Adoptar una API nueva de ADK exige comprobar su
compatibilidad; el experimento no acredita ya instalados los wrappers propuestos.

### Adaptación de imagen y procedencia del vehículo

La respuesta de PIIA 1 se transforma en el formato que consume `hallazgos.py`:
`image_id` propio del caso, `image_path` interno y `predictions`, cada una con
índice estable, clase, score y bbox xywh. Área, dimensiones y visualización
pueden acompañar; no se fabrican scores, clases ni hallazgos. La lista completa
llega al filtro previo del Agente 1; la orquestación no filtra por su cuenta.

El contexto entregado a costes siempre tiene `vehiculo_id` válido, resuelto
antes de llamar a #30. **Propuesta de frontera a acordar con #28/#31:** mantener
la predicción `vehiculo` del Agente 1 y transportar un objeto de procedencia
separado, con categoría propuesta, representante, vehículo seleccionado y
origen (`referencia_confirmada` o `seleccion_usuario`). No añadir campos al
contexto base ni restaurar el contrato retirado `vehiculo_origen` por este documento.

El informe final debe advertir del uso de un representante cuando corresponda.
La ubicación exacta de esa advertencia y cómo la consume #31 se deben revisar
con Víctor: su v2 actualmente muestra el modelo del contexto como dato de entrada.
Este borrador no simula que la dependencia esté resuelta ni permite entregar
un informe que presente el representante como coche identificado en la foto.

### Frontera HTTP propuesta

El navegador utiliza únicamente Bun/Hono bajo `/api/peritajes`; este accede
por red interna Compose al servicio Python de orquestación. Las rutas y el
schema de ejecución son parte de la revisión del ADR 0007, no APIs existentes.

| Operación pública propuesta | Petición | Resultado observable |
|---|---|---|
| `GET /api/peritajes/catalogos` | Sin archivo ni caso | Catálogos válidos para contexto/vehículo; sin inferencia ni llamadas de pago. |
| `POST /api/peritajes` | Multipart con una imagen y clave de idempotencia generada por la web | `202`, `ejecucion_id` opaco y estado de fase A. Petición inválida: error, sin inferencia. |
| `GET /api/peritajes/{id}` | Identificador de ejecución | Estado, etapa y resultados disponibles; nunca dispara trabajo. ID perdido/caducado: respuesta explícita, no un estado «procesando» infinito. |
| `POST /api/peritajes/{id}/informe` | Contexto, confirmación/selección del vehículo y clave de idempotencia | `202` para fase B. Contexto inválido: `422` por campo y se conserva la fase A. Estado incompatible: `409`. No se aceptan cambios de findings desde el navegador. |
| `GET /api/peritajes/{id}/informe.md` | Caso completado y verificado | `text/markdown; charset=utf-8`, descarga `.md`; los mismos bytes que recibe el renderizador. Antes de completar: `409`; caso no disponible: error explícito. |
| `DELETE /api/peritajes/{id}` | Descartar un caso que ya no está trabajando | Elimina estado y temporales; `204`. Caso trabajando: `409`; no promete cancelar una llamada de pago en curso. |

Estados públicos: `analizando`, `esperando_datos`, `generando_informe`,
`completada`, `error`. Etapas: `entrada`, `piia1`, `agente1`, `agente2`,
`agente3`, `verificacion`. La categoría forma parte de `agente1`; no hay una
segunda consulta de categoría desde la web. El estado público no expone el
historial interno de ADK ni rutas del host.

Respuesta de estado propuesta: `ejecucion_id`, `estado`, `etapa`, `analisis`,
`resultado` y `error`; los tres últimos son `null` hasta estar disponibles.
`analisis` expone `image_id`, resumen del filtro, hallazgos de solo lectura y
predicción de vehículo. Es una vista del JSON de Agente 1 que omite rutas
internas como `crop_image_path`; el original íntegro se conserva para los agentes.
`resultado` contiene `markdown`, salida de Agente 2 y procedencia del vehículo;
solo aparece en `completada`, tras la comprobación de cifras. `error` contiene
el objeto descrito abajo y solo es no nulo en estado de error.

La confirmación de fase B propone un cuerpo con `contexto` y
`seleccion_vehiculo`: tipo `referencia_confirmada` o `seleccion_usuario` y
`vehiculo_id`. Ambos IDs, el del contexto y el de la selección, deben coincidir.
Con referencia confirmada también debe coincidir con la propuesta de #28;
selección del usuario exige un ID válido del catálogo y conserva la predicción
original sin sobrescribirla. La procedencia se construye en el servidor con
estos datos y los de fase A, no a partir de un texto libre del navegador.

Errores propios del flujo: objeto con `codigo`, `etapa`, `mensaje` comprensible
y `reintentable`. Los detalles originales se registran sin credenciales ni
contenido de documentos/fotos. `diagnostico_rag` viaja íntegro y separado:
sus incidencias son parte del resultado preliminar, no un error fatal del caso.
Taxonomía propuesta: `ENTRADA_INVALIDA`, `ML_NO_DISPONIBLE`,
`VISION_NO_DISPONIBLE`, `CONTRATO_INVALIDO`, `COSTES_ERROR`, `INFORME_ERROR`,
`CIFRAS_INCONSISTENTES`, `TIMEOUT`, `EJECUCION_NO_DISPONIBLE`,
`ESTADO_INVALIDO`, `IDEMPOTENCIA_CONFLICTO` y `CAPACIDAD_AGOTADA`.
El error de una llamada nombra su etapa; un fallo de programación no se declara
reintentable por defecto. Estado/idempotencia en conflicto dan `409`, caso no
disponible `404`, capacidad agotada `503` y timeout de una llamada `504`.
Tamaño superior al límite da `413`, tipo no admitido `415`, archivo vacío o
indecodificable `400` y contexto inválido `422`.
Estos estados HTTP corresponden a peticiones rechazadas antes de aceptar el
trabajo o a fallos al contactar con un servicio. Si la operación ya devolvió
`202`, un fallo posterior se consulta con `GET` de estado: responde `200` para
el caso conocido, con `estado=error` y su objeto de error. No se confunde ese
fallo del caso con un fallo de transporte del polling.

### Ejecución efímera, repetición y fallos

- El proceso Python conserva el caso activo y sus artefactos en almacenamiento
  temporal; no crea tablas de historial ni una API para listar casos. Las
  subidas no se incorporan al dataset ni a la base de imágenes del explorador.
- La web conserva el identificador del caso en memoria durante esa vista.
  Cambiar o recargar la página no ofrece restauración ni historial. Un reinicio
  puede perder el caso; se comunica que debe iniciarse de nuevo, sin reejecución
  automática ni cobros ocultos.
- Estado, imagen, recortes y caché de visión del caso se eliminan al descartarlo
  o caducar, y los temporales de procesos anteriores se limpian al arrancar.
  La caducidad y los límites de tamaño, píxeles, casos activos y tiempos de
  llamada serán configuración documentada y fijada en la entrega; no se promete
  una latencia ni se inventa un presupuesto de recursos antes de medir.
- Mientras existe el caso, repetir la misma petición con la misma clave y
  contenido devuelve su ejecución/resultado sin duplicar llamadas; la misma
  clave con datos distintos produce `409`. La transición de fase B es atómica:
  dos clics no generan dos informes. Tras caducar no hay garantía de deduplicación
  persistente; la web no reenvía una ejecución perdida automáticamente.
- Errores de entrada conservan los resultados previos. Fallos técnicos de PIIA 1,
  visión, costes, informe o verificación detienen el caso con su etapa y no
  publican un informe terminado. No se reintenta el recorrido entero en silencio;
  los reintentos internos existentes del proveedor se documentan y contabilizan.
- Un RAG `parcial`, `sin_resultados` o `error` permite terminar con el aviso
  preliminar de #56/#58, las citas válidas y los motivos por tema. `recuperadas`
  no significa validación jurídica; `no_aplica` no es un fallo. Datos sin daños
  siguen el escenario vacío de #30, no se inventan daños para producir un coste.
- Markdown se presenta con HTML crudo deshabilitado o saneado. Texto recuperado
  o descripciones no pueden ejecutar código en la web. El contenido de descarga
  se conserva como texto, sin convertirlo a PDF ni completarlo con un LLM.

### Compose y entorno

Se propone un `compose.yaml` en la raíz del proyecto entregado,
`entregas/cu-19-interpretacion-danos/`, para que forme parte de la carpeta que
se entrega a la asignatura. Desde la raíz del repo se podrá usar
`docker compose -f entregas/cu-19-interpretacion-danos/compose.yaml up --build`.
Es el Compose global previsto junto a #32, no una segunda PostgreSQL ni un
despliegue independiente del RAG. Su ubicación se coordina en la #56.

- Servicios: web/backend Bun que sirve el frontend compilado, orquestador Python
  con ADK, servicio ML existente y PostgreSQL con pgvector. El frontend de Vite
  en desarrollo no debe ser una dependencia del arranque normal del conjunto.
- PostgreSQL utiliza un volumen persistente, schema del backend e índice RAG
  separado. Se inicializa el schema antes de aceptar peticiones. Un entorno
  sin CarDD puede tener el explorador vacío y aun así procesar una foto subida;
  cargar CarDD continúa siendo una preparación explícita.
- El paquete de Plexus, modelos de PIIA 1 y, cuando se utilice, CarDD se montan
  desde ubicaciones locales configurables y de solo lectura. La clave se aporta
  por entorno. No se copian a la imagen ni al repositorio.
- Los agentes necesitan poder localizar el paquete sin depender de `.git` dentro
  del contenedor. Incluir en #34 la adaptación mínima de localización/configuración,
  preservando el uso local documentado; coordinar esos cambios con #28/#30/#31/#32.
  No se modifican por ello algoritmos, cifras ni formatos base de los agentes.
- Se conservan las opciones CPU/GPU de ML y sus requisitos reales. La entrega
  documenta la máquina usada y prueba el perfil que funcionó; arrancar un
  contenedor no acredita inferencia ni rendimiento en cualquier equipo.
- Arrancar Compose no indexa con OpenAI ni lanza evaluaciones o análisis de pago.
  Preparación del RAG, configuración y comprobación de modelos se documentan
  antes del primer uso. Sin índice válido, se aplica el diagnóstico de #32;
  sin modelos ML o configuración de visión válidos, se informa del impedimento.

### Clarify

| Incertidumbre | Clasificación | Evidencia y efecto |
|---|---|---|
| Web, imagen subida, edición y salida | Resuelta por Lucas en la conversación | Pestaña independiente; una imagen; daños sin edición; vehículo corregible; Markdown visible/descargable; sin historial. Se fija la versión de estas decisiones en #34. |
| Framework | Resuelta por Lucas | ADK tras #33/#52. La secuencia nativa y el servicio efímero son propuestas técnicas de este borrador, no resultados de una integración ya probada. |
| Categoría y procedencia | Bloqueante para Ready | #28 solicitada de nuevo; #29/ADR 0001 deben adaptarse con Lucía. Acordar con Víctor cómo llega la procedencia al informe y revisar el plan afectado. |
| RAG | Bloqueante para Ready | #56/ADR 0006 propuestos: acordar contrato definitivo y reparto de Compose. No se presupone aceptación por #58. |
| Contrato web/Python y límites configurados | Propuesta para revisión | La tabla HTTP, idempotencia y estado efímero deben acordarse en esta Planning PR. Valores operativos se fijan con evidencia del entorno en la implementación; las pruebas inyectan límites controlados. |
| Modelo concreto y dependencias | Comprobación de entorno | Visión por configuración y embeddings según #32; no elegir aquí otro modelo de chat ni copiar automáticamente las dependencias del experimento. Registrar versiones/acceso al preparar la implementación. |
| Plazo y reparto de trabajo | Coordinación pendiente | La web y recuperar #28 amplían el trabajo respecto al plan del 20 de octubre. Acordar el calendario con Lucía/Víctor; no mantener como acreditada la estimación original de cinco días. |

## Comportamiento que debe preservarse

- Explorador y rutas de imágenes/instancias siguen funcionando; no se cargan
  las nuevas subidas como datos de CarDD. → AC-001, AC-012, AC-013.
- Clases, scores, cajas, filtro previo, findings y confianza de Agente 1 se
  conservan; no se admite su edición en la web. → AC-002, AC-006.
- #30 conserva vehículo obligatorio, fórmulas, dos escenarios, claves de
  cobertura y escenario vacío. `agente2()` de #32 añade fuentes/diagnóstico
  según su contrato, conservando cifras y entradas. → AC-004 a AC-007.
- #31 conserva su informe determinista y avisos RAG; la advertencia de vehículo
  necesita adaptación explícita acordada, no reactivar AC-010 por inferencia.
  → AC-007 a AC-009.
- La categoría de #28 y su calidad se entregan en esa Issue. No se elimina el
  requerimiento de revisión y ADR aceptado por llamarla desde #34. → AC-003.

## Failure modes y requisitos no funcionales

| Condición | Comportamiento observable | Cobertura |
|---|---|---|
| Archivo vacío, inválido o por encima de límites configurados | Rechazo antes de inferencia/pago; mensaje de entrada. | AC-001 |
| Respuesta ML incompatible o geometría no válida | Error de etapa PIIA 1; no se fabrican detecciones ni se continúa con datos alterados. | AC-002, AC-011 |
| Categoría desconocida o contexto incompleto | Pedir selección/corrección; ningún coche por defecto ni cálculo prematuro. | AC-003, AC-004 |
| Error de visión, costes o informe | Detención explícita, sin informe final ni éxito aparente. | AC-011 |
| Falta de fuentes o fallo tipado del RAG | Resultado preliminar, causas por tema, citas buenas conservadas. | AC-007 |
| Cifra inventada en el informe | Bloqueo de publicación/descarga; error de verificación. | AC-009 |
| Doble clic, polling y peticiones duplicadas | Sin repetir inferencia, visión, costes ni generación. | AC-005, AC-010 |
| Reinicio/caducidad del caso | Indicación de caso no disponible, sin restauración automática. | AC-010, AC-012 |
| Texto del modelo/documento con HTML ejecutable | Se muestra sin ejecución de código; Markdown descargado íntegro. | AC-012 |
| Modelos/paquete no disponibles o despliegue incompleto | Diagnóstico de preparación con ruta/configuración del servidor; no éxito basado solo en contenedores arrancados. | AC-013 |

## Acceptance Criteria

| ID | Dado / Cuando | Resultado esperado y condición de éxito |
|---|---|---|
| AC-001 | Abrir la web; subir JPEG/PNG válido y, por separado, archivo vacío/no imagen/múltiple/superior al límite configurado. | Existe pestaña de peritaje separada del explorador. Una imagen válida inicia fase A al pulsar «Analizar imagen»; seleccionar archivo no llama a proveedores. Los inválidos muestran causa y generan cero llamadas a ML/visión. El explorador sigue accesible. |
| AC-002 | Respuesta ML guionizada con cero, una y varias detecciones; también respuesta malformada. | La adaptación entrega todas las predicciones al Agente 1, con clase/score/bbox conservados e índices estables y únicos para el caso. Imagen normalizada y cajas son coherentes. Cero detecciones es válido; estructura inválida detiene antes del Agente 1. |
| AC-003 | #28 propone categoría válida y representante, o `desconocido`; el usuario confirma o corrige. | Se presenta la propuesta y se resuelve un vehículo válido del catálogo antes de fase B. `desconocido` sin selección impide presupuestar. No se asigna categoría C en silencio. La predicción original y la elección posterior se distinguen mediante el contrato de procedencia acordado. |
| AC-004 | Enviar contexto válido de rol propio y de tercero, y contexto inválido/ausente. | Se pasan los campos de #30 sin inventarlos; póliza obligatoria solo en rol propio. Error por campo antes del cálculo, conservando fase A para corregirlo. Confirmar vehículo o completar datos no vuelve a llamar a PIIA 1/visión. |
| AC-005 | Ejecutar ambas fases con dependencias que registran llamadas. | Se usa el runtime nativo ADK, con orden PIIA 1 → Agente 1; tras contexto válido, `agente2()` → Agente 3 → verificación. No se llama al coste antes de `agente2()` ni se añade un LLM para coordinar/redactar cifras. Una fase fallida no ejecuta sus sucesoras. |
| AC-006 | Findings con confirmados, pendientes y rechazados, y escenario sin daños. | La web solo muestra los resultados, sin permitir cambiar daños; una petición con findings editados se rechaza. Los JSON de entrada al cálculo y al informe conservan hallazgos y tiers, y los dos escenarios y sus cifras coinciden con la ejecución directa de #30/#32 para el mismo contexto. |
| AC-007 | Respuestas `diagnostico_rag` en los cinco estados y con citas parciales. | JSON e informe conservan el diagnóstico acordado con #32/#31. `parcial`, `sin_resultados` y `error` producen aviso preliminar y causas por tema, sin perder citas buenas. `recuperadas` no se presenta como verificación; `no_aplica` no genera fallo técnico. |
| AC-008 | Un representante confirmado y un vehículo seleccionado por el usuario producen informe. | La procedencia se conserva hasta la salida. Con representante, informe y pantalla advierten que el modelo es una referencia de presupuesto, sin presentarlo como identificado en la foto. Con selección, se indica que es aportado por el usuario. Se cumple mediante el contrato/adaptación de #28/#31 aceptados. |
| AC-009 | Informe correcto y otro con un importe inventado respecto a salida de Agente 2. | Se ejecuta `comprobar_cifras` antes de publicar. Correcto: sus cifras y escenarios corresponden a Agente 2. Inventado: error `CIFRAS_INCONSISTENTES`, sin informe terminado ni descarga. El LLM no recibe el encargo de reescribir el presupuesto. |
| AC-010 | Consultar progreso; repetir cada POST con misma clave/contenido, con contenido distinto y durante ejecución; reiniciar/caducar caso. | GET no ejecuta etapas. Repetir devuelve el mismo caso/resultado y recuento de llamadas; reutilización conflictiva da `409`. Doble envío de fase B inicia una sola generación. Caso perdido deja de mostrarse como procesando y no se reenvía automáticamente. |
| AC-011 | Simular por separado fallos de ML, visión/categoría, costes, informe, contrato y timeout. | Se comunica código, etapa, mensaje y posibilidad de reintento sin credenciales/rutas privadas. No se oculta como RAG vacío, no se publica informe final y no se reejecuta el flujo en silencio. Los fallos esperados propios del RAG siguen AC-007. |
| AC-012 | Completar, renderizar y descargar un informe; descartar/caducar caso y reiniciar; incluir texto con HTML en fuentes/descripciones. | Pantalla y `.md` corresponden a los mismos bytes UTF-8; nombre descargable y contenido de tipo Markdown. No se ejecuta HTML recibido. No existe historial ni se añaden imágenes/casos a las tablas del explorador. Se eliminan estado, subidas, recortes y caché temporal al limpiar el caso; no se borran datos ni índices persistentes. |
| AC-013 | Entorno limpio con modelos/paquete/configuración documentados; levantar Compose y reiniciar; también retirar una dependencia de preparación. | El mismo Compose levanta web/backend, orquestador, ML y PostgreSQL/pgvector y permite el recorrido. Schema inicializado, rutas resolubles sin depender de `.git` y volumen RAG persistente; sin indexado ni llamadas de pago al arrancar. Preparación ausente produce impedimento explícito. Se registra el perfil/máquina realmente comprobado. |
| AC-014 | Flujo integrado, modelos reales y 3–5 imágenes distintas mediante la pestaña. | Cada imagen llega al informe y descarga con las cifras de Agente 2; se documentan modelo, estrategia/umbrales de PIIA 1, contexto, resultado, advertencias, llamadas/tokens/coste disponible y limitaciones. Una persona lee cada informe. Los casos de tercero, sin daños, RAG parcial y categoría desconocida se comprueban además con dobles si la muestra real no los contiene. No sustituye la evaluación #46. |

## Test Plan

### Fronteras y estrategia

- **S1 — Web y HTTP públicos:** pestaña, formulario, estados y descarga a través
  de Hono y servicio Python; probar como usuario/consumidor, no handlers privados.
- **S2 — PIIA 1 → Agente 1 y categoría:** servicio ML guionizado y cliente de
  visión falso; JSON completo antes/después, sin modificar las funciones internas.
- **S3 — Runtime ADK → funciones públicas de agentes:** registro de invocaciones,
  salidas de costes/diagnóstico y generador; usar ADK real con proveedores falsos.
- **S4 — Integración real:** herramientas de Plexus, agentes, PostgreSQL y ML;
  dependencias y datos locales identificados por versión/hash, fuera de Git.
- **S5 — Despliegue y ciclo de vida:** Compose, HTTP, descarga y limpieza observable.

TDD para rutas, adaptación, estados, errores y preservación de cifras: primero
pruebas que fallen por comportamiento ausente con el harness ejecutable, después
implementación y refactor. No usar errores de importación como Red. Reutilizar
los dobles de visión y las pruebas de contrato de los agentes; no crear otro
framework de agentes ni un runner de pruebas propio.

Pruebas Python previstas con `python -m unittest discover -s
app/agentes/orquestador/tests -v`, desde la carpeta del caso, y pruebas web/HTTP
mediante `bun run test:peritaje` en `app/`. Ambos son comandos **a crear en la
implementación**, no checks existentes ni ejecutados en esta planificación.
El harness web debe permitir comprobar navegación y acciones de usuario con
ML/OpenAI falsos; su herramienta se fija al implementar, manteniendo estos casos.

Para la integración probabilística, baseline con los componentes ya evaluados
en #28/#32/visión → tabla del flujo real → corregir el cableado si hay gap →
repetir conservando resultados. No se crea un umbral nuevo de precisión para
#34 ni se usa un test unitario rojo artificial para medir calidad del modelo.

| Referencia | Seam | Estrategia y caso | Datos / entorno | Pasos previstos | Evidencia |
|---|---|---|---|---|---|
| `specs/34-orquestacion-web.md#AC-001` | S1 | TDD: navegación, archivo válido/inválido y cero llamadas prematuras. | Imagen sintética y entradas inválidas; ML/visión falsos. | Harness web/HTTP; pulsar carga y análisis por separado. | Red/Green y recuentos. |
| `specs/34-orquestacion-web.md#AC-002` | S2 | TDD: adaptar cero/una/varias detecciones y rechazar formato inválido. | Respuesta ML guionizada, imagen con orientación conocida y bboxes. | Suite Python; capturar entrada pública del Agente 1. | Red/Green; comparación de clases, scores y geometría. |
| `specs/34-orquestacion-web.md#AC-003` | S1 + S2 | TDD: confirmar/corregir y desconocido sin fallback. | Catálogo real; contrato de #28 revisado, cliente falso. | Formulario y peticiones; comprobar vehículo de fase B. | Red/Green y procedencia. |
| `specs/34-orquestacion-web.md#AC-004` | S1 + S3 | TDD: contexto inválido, corrección y rol tercero. | Contextos del contrato y copias inválidas; datos Plexus. | Suite HTTP; contador de fases antes/después. | Red/Green; mensajes y llamadas sin duplicar. |
| `specs/34-orquestacion-web.md#AC-005` | S3 | TDD: ejecución nativa y orden con detención en fallos. | ADK real, funciones públicas/proveedores falsos con registro. | Suite Python por fase y recorrido completo. | Red/Green; secuencia de invocaciones. |
| `specs/34-orquestacion-web.md#AC-006` | S1 + S3 + S4 | TDD y regresión: daños inmutables, dos escenarios y caso vacío. | Ejemplos de contrato; paquete real; salida directa de #30/#32 como referencia independiente. | Suites Python/HTTP; comparar JSON y rechazar edición de findings. | Igualdad de campos/entradas y escenarios. |
| `specs/34-orquestacion-web.md#AC-007` | S1 + S3 | TDD: los cinco estados RAG y conservación de citas parciales. | Contrato final #56; respuestas guionizadas. | Ejecutar fase B y revisar JSON/Markdown con #31. | Red/Green; texto de aviso y temas afectados. |
| `specs/34-orquestacion-web.md#AC-008` | S1 + S3 | TDD: representante y vehículo del usuario claramente diferenciados. | Contrato de procedencia y adaptación #31 aceptados. | Formulario → Agente 3 → pantalla y descarga. | Red/Green; cabecera y advertencia coherentes. |
| `specs/34-orquestacion-web.md#AC-009` | S3 | TDD: informe correcto e importe inventado bloqueado. | Salida Agente 2 del contrato y generador guionizado con importe añadido. | Suite Python/HTTP; comprobar ausencia de descarga en error. | Red/Green; error y cifras originales conservadas. |
| `specs/34-orquestacion-web.md#AC-010` | S1 + S3 + S5 | TDD: polling, reenvíos, concurrencia y caso perdido. | Proveedores con contadores; fase detenida por el doble; reinicio del servicio. | Repetir GET/POST; enviar dos confirmaciones simultáneas; reiniciar/caducar. | Recuentos y estados; ninguna llamada duplicada. |
| `specs/34-orquestacion-web.md#AC-011` | S1 + S3 | TDD: un fallo de cada etapa, timeout y respuesta de contrato inválida. | Dobles públicos; límites de tiempo controlados por el test. | Inyectar fallos por separado y consultar estado/descarga. | Red/Green; códigos y detención sin éxito aparente. |
| `specs/34-orquestacion-web.md#AC-012` | S1 + S5 | TDD: Markdown idéntico, sin HTML ejecutable, sin historial y limpieza. | Informe UTF-8, texto HTML, directorio temporal y DB de prueba. | Descargar dos veces; comparar bytes; descartar/caducar/reiniciar; consultar DB. | Red/Green; artefactos eliminados y persistencia ajena intacta. |
| `specs/34-orquestacion-web.md#AC-013` | S4 + S5 | Integración: conjunto reproducible, sin pago al arrancar y preparación ausente. | Docker, versiones/modelos/paquete registrados; DB vacía; índice preparado explícitamente. | Compose global desde raíz; verificar salud, flujo y reinicio; repetir sin dependencia. | Comandos y resultados reales, perfil/hardware y llamadas. |
| `specs/34-orquestacion-web.md#AC-014` | S1 + S4 | Eval de integración: 3–5 imágenes y lectura humana, con baseline conservada. | Imágenes autorizadas identificadas por hash; modelos reales; contextos registrados. | Recorrido web autorizado y tabla por caso; repetir si cambia integración. | Informes, comprobación de cifras y límites; sin fotos/clave en Git. |

## Implementation Plan

| Slice | Objetivo observable | AC | Fronteras/componentes | Dependencias | Verificación |
|---|---|---|---|---|---|
| 1 — Entrada web y adaptación | Pestaña, subida válida y respuesta PIIA 1 consumible por Agente 1. | AC-001, AC-002 | React, Hono, servicio Python y cliente ML. | Plan/ADR aceptados; contrato ML existente. | Filas AC-001/002; pruebas sin modelo real. |
| 2 — Diagnóstico y vehículo | Fase A con ADK, daños sin edición y vehículo confirmable/corregible. | AC-003, AC-004, AC-005, AC-006 | Runtime nativo, Agente 1/#28, catálogo y formulario. | #28 replanificada y contrato integrado para la integración final. | Filas AC-003 a AC-006 con dobles y catálogo. |
| 3 — Informe comprobado | Fase B con #32/#31, diagnóstico RAG, procedencia y cifras verificadas. | AC-005, AC-006, AC-007, AC-008, AC-009 | Agente 2/3 y contratos compartidos. | #30 integrada; #32/#31 y procedencia aceptados; integración final con código real. | Filas AC-005 a AC-009. |
| 4 — Ciclo de vida y salida | Ejecución asíncrona sin duplicados, errores explícitos, Markdown y limpieza. | AC-010, AC-011, AC-012 | HTTP, estado temporal, UI y descarga. | Slices 1–3; puede desarrollarse con dobles públicos. | Filas AC-010 a AC-012. |
| 5 — Entorno y evidencia | Compose único, preparación reproducible y 3–5 casos reales. | AC-013, AC-014 | Contenedores, configuración, documentación de uso. | Componentes integrados; datos/modelos locales; acceso al proveedor. | Filas AC-013/014; regresiones pertinentes y diff. |

## Pendientes para Ready

1. Revisión humana del documento completo, contratos HTTP/ciclo de vida y ADR
   0007; aceptación registrada y Planning PR integrada con head final aprobado.
   Revisora prevista para la PR de Lucas: Lucía, según el reparto del equipo.
2. Coordinar y revisar #28/#29 con Lucía: `desconocido`, confirmación y contrato
   de procedencia. Acordar con Víctor la adaptación del informe y el plan
   afectado. No aceptar ni implementar decisiones nuevas sobre sus contratos
   a partir de este borrador; conservar IDs y revisiones de versiones anteriores.
3. Aceptar e integrar #56/ADR 0006 y acordar con #32 que este plan consume
   `diagnostico_rag`, `agente2()` y el mismo Compose. Las pruebas finales
   requieren el código de #28/#31/#32, no solo su existencia en un plan.
4. Revisar el impacto de alcance/calendario con el equipo. Preparación del
   entorno, parámetros operativos y acceso al proveedor deben documentarse
   antes de las verificaciones reales; no hay resultados de este flujo aún.

### Resultado de analyze

| Comprobación | Resultado |
|---|---|
| Trazabilidad del alcance | Web/subida → AC-001/002; categoría/contexto → AC-003/004/008; ADK → AC-005; resultados sin edición → AC-006; RAG → AC-007; cifras → AC-009; estados/errores → AC-010/011; Markdown sin historial → AC-012; Compose → AC-013; recorrido real → AC-014. |
| Cada AC tiene verificación y slice | AC-001 a AC-014, con Test Plan y al menos una slice. |
| Preservación | Contratos base y costes protegidos; #28 y procedencia requieren adaptación explícita. Ningún AC retirado se restaura desde #34. |
| Decisión arquitectónica | NEW_ADR por ADK de producto, frontera HTTP y despliegue/estado. ADR 0007 Propuesto, sin sustituir la aceptación de 0001/0006. |
| Estado del diseño | Borrador para acordar fronteras con consumidores; no Ready. Propuestas técnicas separadas de decisiones de producto confirmadas. |
| Trabajo ya verificado | Inspección de código, contratos y documentación; el experimento #33 está integrado. No se ha ejecutado este flujo, instalado dependencias ni llamado a modelos para planificarlo. |

## Definition of Done

La DoD global del workflow y de #34 sigue vigente. Esta Spec añade:

| Condición específica | Evidencia requerida |
|---|---|
| Los 14 AC verificados con versiones de componentes y datos identificadas. | Trazabilidad y resultados en Implementation PR, Red/Green/Refactor y comparación de integración real. |
| Una imagen nueva llega desde la web al Markdown comprobado. | Ejecución con PIIA 1, visión, categoría, costes, RAG e informe reales; no basta una salida precalculada de CarDD. |
| 3–5 imágenes documentadas y leídas por una persona. | Tabla de resultados, incidencias, configuración y costes disponibles; sin inventar cifras de consumo ausentes. |
| Despliegue y ciclo de vida reproducibles. | Compose, pasos de preparación, parámetros operativos, prueba de reinicio/limpieza y perfil/hardware usado. |
| Uso y límites actualizados en la carpeta del caso. | README de orquestación y enlaces desde README del caso, contratos acordados y guía de ejecución vigente. |
| Entrega sin datos/modelos/claves ni temporales. | Revisión del diff; solo archivos del producto y documentación autorizados. |

Referencias técnicas de diseño: [ADK, secuencia nativa](https://adk.dev/agents/workflow-agents/sequential-agents/)
y [agentes personalizados nativos](https://adk.dev/agents/custom-agents/), consultadas
el 2026-10-26. Fundamentan la propuesta; no acreditan su ejecución con las
versiones del producto ni sustituyen el plan de pruebas.
