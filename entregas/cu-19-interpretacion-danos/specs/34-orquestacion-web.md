# Spec: Orquestación desde la web, de una imagen subida al informe

- GitHub Issue: https://github.com/lvckss/piia2-26/issues/34
- Estado: Borrador v1.4, 2026-11-10.
- ADR decision: NEW_ADR.
- ADR: [0007 — Orquestación ADK y ejecución web efímera](../docs/adr/0007-orquestacion-adk-web-efimera.md), Propuesto.
- Justificación: adopta ADK como dependencia del producto, define una frontera HTTP entre web y servicio Python y el ciclo de vida de las ejecuciones. Los ADRs 0002–0005 aceptados cubren contratos, proveedor, costes y filtro previo; no cubren estas decisiones.
- Plan vigente / versión: v1.4 en la misma PR #60; el registro de #34 fija el commit publicado. Versiones conservadas: v1 `733c5d0`, v1.1 `9a65c26`, v1.2 `5ed9ca6` y v1.3 `06f4c08`. La v1.4 recoge las precisiones de Víctor sobre compatibilidad y validación de `contexto.vehiculo_origen` en AC-008 y su Test Plan; conserva los 14 IDs, los demás AC, la DoD y las decisiones de la v1.3. No acredita aceptación del documento completo ni del ADR 0007. Continúa el [registro de alcance](https://github.com/lvckss/piia2-26/issues/34#issuecomment-6426795027).
- Riesgo y revisión previa: sí, por NEW_ADR y por el acuerdo del equipo. Impacto en cifras y fuentes del informe, frontera entre servicios, subida de archivos y nuevas dependencias de #28/#31/#32. La implementación y sus planes deben revisarse por los responsables afectados; el documento completo todavía no tiene aceptación humana.
- Planning PR: https://github.com/lvckss/piia2-26/pull/60 — draft mientras se acuerdan las dependencias indicadas al final.

## Qué construir

Una pestaña independiente de la web que permita subir una imagen, ver el
diagnóstico de daños, confirmar o corregir el vehículo propuesto, completar el
contexto y obtener el informe formateado y descargable como Markdown.

El recorrido tiene dos fases, separadas por la intervención del usuario:

1. **Analizar imagen:** subida y normalización → PIIA 1 → Agente 1, incluida la
   categoría de #28 → resultados de daños sin edición y propuesta de vehículo.
2. **Generar informe:** contexto validado y vehículo resuelto (confirmado, elegido o V25 por defecto) →
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

Snapshot leído: `main` `8a38e02310f8cb3b5e2994684715fe34dfee4613` (2026-11-10).

- React/Vite y Bun/Hono sirven el explorador; no hay pestaña de peritaje ni
  ruta de orquestación montada en `app/server/app.ts`.
- PIIA 1 admite `POST /v1/damage-assessment` con imagen en
  `app/ml/api/routes/damage_assessment.py`. Su respuesta necesita adaptación
  a `hallazgos.py`: `image_id`, `image_path`, `predictions` con índice, clase,
  bbox xywh y score. No se repite la detección ni se inventan scores.
- Agente 1 y categoría están integrados (#69): `vehiculo` conserva la predicción;
  `desconocido` lleva `vehiculo_id_referencia: null`. Fallos del proveedor se
  propagan (AC-007 de #28); no autorizan el valor por defecto del orquestador.
- [Spec 28 v1.3.2](https://github.com/lvckss/piia2-26/blob/8a38e02310f8cb3b5e2994684715fe34dfee4613/entregas/cu-19-interpretacion-danos/specs/28-categoria-vehiculo.md) y
  [ADR 0001 Aceptado](https://github.com/lvckss/piia2-26/blob/8a38e02310f8cb3b5e2994684715fe34dfee4613/entregas/cu-19-interpretacion-danos/docs/adr/0001-categoria-vehiculo-contrato-agente1.md).
  Los AC-009/010 de #28 están transferidos a #34/#31. La medición de categoría
  cumple el mínimo provisional 12/20 y 4 coincidencias distintas de `desconocido`
  fijado en #78; no acredita calidad general ni se sustituye por un 70 % inventado.
- #30/#59 están integradas: `estimar_siniestro` exige `vehiculo_id` válido y
  devuelve ambos escenarios con `normativa: []`. No cambia su contrato de costes.
- RAG: [Spec 32 v1.6](https://github.com/lvckss/piia2-26/blob/8a38e02310f8cb3b5e2994684715fe34dfee4613/entregas/cu-19-interpretacion-danos/specs/32-rag-normativa.md), #56/#67 y ADR 0006
  Aceptado. #72 incorpora PostgreSQL e indexado en una PR aún abierta; búsqueda,
  composición y evaluación no están entregadas en main.
- Informe: spec v2.1 aceptada en #31, #58/#63/#70 integradas; implementación
  abierta en #75. La procedencia tendrá un AC nuevo acordado por Víctor;
  AC-010 retirado no se reactiva ni se reutiliza.
- #33/#52 prueba una tool con ADK 2.12.0, LiteLLM 1.106.0 y `gpt-6.1-sol`;
  no prueba el workflow nativo ni el recorrido completo. El resultado original
  acabó con código 1 por el comparador; la captura se revalidó localmente.
- ML tiene Compose en `app/docker/ml-api/`; el único Compose del conjunto se
  mantiene en la raíz del caso. #32 aporta PostgreSQL/pgvector y preparación;
  #34 integra el resto. Las rutas de datos deben funcionar sin `.git` en Docker.

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
trabajo del Agente 1 de #28 no se absorbe ni se reasigna desde este plan.
Se conserva el reparto: #34 resuelve el vehículo y define la procedencia;
#31 la muestra en el informe. La actualización v1.3 incorpora la decisión
humana de Lucas del 2026-11-10: V25 fijo si la categoría es `desconocido`
y la persona no elige otro vehículo. Contrato y calendario se revisan antes de Ready. No se reactivan
silenciosamente los AC retirados de sus planes.

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
  a #28. Con `desconocido` la persona puede elegir; si no elige, el
  orquestador resuelve `vehiculo_id = "V25"` (BMW Serie 3) y lo muestra como
  referencia por defecto. Una respuesta incompleta o un fallo técnico detienen
  el caso y no autorizan ese valor por defecto.
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

El contexto entregado a costes siempre tiene `vehiculo_id` válido. Una sola
función del orquestador resuelve el vehículo antes de llamar a #30 y es usada
por CLI y web. No se introduce otro fallback dentro de los Agentes 1, 2 o 3.

Contrato de procedencia: Víctor [acepta el formato v1.3 y fija dos precisiones](https://github.com/lvckss/piia2-26/pull/60#issuecomment-6773699753)
como responsable de #31. La v1.4 las incorpora; el documento completo y el
ADR 0007 siguen pendientes de revisión y aceptación por el equipo.

| Campo | Regla propuesta |
|---|---|
| `contexto.vehiculo_id` | Vehículo válido efectivamente usado para costes, valor venal, pérdida total e indemnización. |
| `contexto.vehiculo_origen` | Campo opcional para consumidores y entradas anteriores; si aparece, solo admite `referencia_confirmada` (se confirma el representante de #28), `seleccion_usuario` (se elige un coche válido) o `maximo_por_defecto` (categoría válida `desconocido` sin elección, se usa V25 fijo). El flujo nuevo CLI/web lo construye y conserva siempre. |
| `agente1.vehiculo` | Predicción original íntegra de #28, sin modificar `categoria` ni `vehiculo_id_referencia`; para `desconocido` la referencia sigue siendo `null`. |

No hay un objeto de procedencia separado. El campo aditivo se construye en el
servidor desde fase A y la acción del usuario; no se acepta un origen libre ni
un V25 por defecto declarado por el cliente. `seleccion_usuario` también cubre
elegir expresamente V25: es distinto de recibirlo por defecto. Confirmar una
referencia exige que coincida con el representante; Si no hay elección y la
categoría es reconocida, se exige confirmación/corrección antes de fase B.

Compatibilidad: si `contexto.vehiculo_origen` **no viene**, #31 trata
`contexto.vehiculo_id` como dato de entrada y no muestra aviso de procedencia;
el resto del informe se conserva. No se infiere un origen ni se añade un aviso
de V25 por el ID del coche a solas. Esto mantiene los ejemplos y ejecuciones
anteriores; no permite al flujo nuevo omitir o perder la procedencia que acaba
de construir. Una clave presente con valor inválido no equivale a una ausencia.

Si el campo viene, #31 valida su valor y coherencia antes de devolver informe:
`maximo_por_defecto` exige `contexto.vehiculo_id = "V25"`;
`referencia_confirmada` exige que ese ID coincida con
`agente1.vehiculo.vehiculo_id_referencia` (una referencia nula no puede confirmarse).
Un valor fuera de los tres o una incoherencia produce una excepción explícita
que nombra el campo/ID problemático. #34 comunica `CONTRATO_INVALIDO` en la
etapa de informe y no publica ni permite descargar un informe final. Elegir
V25 explícitamente con `seleccion_usuario` sigue siendo válido y distinto de
`maximo_por_defecto`. Se mantienen las demás validaciones de vehículo/contexto.

La salida de #30 ya conserva `contexto` íntegro: se verificará el paso del campo
aditivo sin modificar fórmulas, firmas ni los dos escenarios. #31 debe adaptar
su plan con un **AC de ID nuevo** que consuma estos valores; no se reutiliza
AC-010 retirado. AC-009/010 transferidos de #28 se trazan a AC-003/004/008 de
#34 y a ese AC nuevo de #31.

Decisiones humanas que fundamentan el cambio: [Lucía, 2026-11-03](https://github.com/lvckss/piia2-26/issues/34#issuecomment-6611207541),
[Víctor, 2026-11-05](https://github.com/lvckss/piia2-26/issues/34#issuecomment-6657185939),
y Lucas en esta sesión (2026-11-10): «Usar siempre el BMW Serie 3 que propone Víctor».
La cifra ≤0,3 % respecto al máximo en los 249 casos medidos no prueba que V25
sea el máximo exacto para cualquier siniestro: **no se evalúan los 27 coches
para escoger otro máximo**. Es una política fija provisional aceptada por Lucas.

Pantalla y contrato para #31 conservan literalmente la [frase fijada por Lucía](https://github.com/lvckss/piia2-26/issues/34#issuecomment-6736461374):

> Vehículo no identificado en la imagen: el presupuesto usa el vehículo de mayor coste como techo prudente. Es preferible que el importe sobre a que falte, porque un presupuesto corto dejaría la reparación sin cubrir.

Para `maximo_por_defecto`, el informe añade que el coche usado es V25/BMW Serie 3,
una referencia de cálculo. Pérdida total e indemnización se calculan también con
ese coche, como propone Víctor: el valor venal no es el del vehículo real y la
pérdida total no es fiable. La frase fija no sustituye este aviso ni implica que
se haya identificado el coche. No se introduce el estado «no evaluable» en #30.
El formato y las dos precisiones tienen la aceptación de Víctor enlazada arriba;
la adaptación de #31 con su AC nuevo y la aceptación/integración del plan
completo de #34/ADR 0007 siguen pendientes. La elección de Lucas de V25 no se
presenta como aprobación global de estos documentos.

### Frontera HTTP propuesta

El navegador utiliza únicamente Bun/Hono bajo `/api/peritajes`; este accede
por red interna Compose al servicio Python de orquestación. Las rutas y el
schema de ejecución son parte de la revisión del ADR 0007, no APIs existentes.

| Operación pública propuesta | Petición | Resultado observable |
|---|---|---|
| `GET /api/catalogos` | Sin archivo ni caso | Catálogos válidos para contexto/vehículo; sin inferencia ni llamadas de pago. |
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

La confirmación de fase B propone `contexto` y `seleccion_vehiculo` opcional:
tipo `referencia_confirmada` o `seleccion_usuario`, con `vehiculo_id`. Si hay
selección, ambos IDs deben coincidir; confirmar referencia debe coincidir además
con #28. Si no hay selección y la categoría válida es `desconocido`, el servidor
resuelve V25 y `maximo_por_defecto`; el cliente no fabrica el origen. En otra
categoría, selección ausente produce `422`. El contexto definitivo se valida
antes de costes y no sobrescribe la predicción original de Agente 1.

Errores propios del flujo: objeto con `codigo`, `etapa`, `mensaje` comprensible
y `reintentable`. Los detalles originales se registran sin credenciales ni
contenido de documentos/fotos. `diagnostico_rag` viaja íntegro y separado:
sus incidencias son parte del resultado preliminar, no un error fatal del caso.
Los códigos del flujo se alojan en `error`; los del RAG quedan en
`diagnostico_rag.consultas[].incidencias`, sin mezclarlos.
Taxonomía propuesta: `PERITAJE_ENTRADA_INVALIDA`, `ML_NO_DISPONIBLE`,
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
  Los valores provisionales propuestos figuran debajo; se documentan al
  implementar y se verifican con límites exactos, sin presentarlos como capacidad
  o rendimiento ya medidos.
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

### Valores operativos provisionales propuestos

| Parámetro | Valor inicial propuesto | Resultado y verificación previstos |
|---|---|---|
| Tamaño de imagen | 10 MiB (10 × 1024 × 1024 bytes) | Hasta el límite se valida y decodifica; un byte más da `413`, antes de ML/visión. |
| Píxeles decodificados | 20.000.000 | Exactamente el límite se admite; excederlo se rechaza antes de inferencia, sin reescalar en silencio. |
| Caducidad | 60 minutos de inactividad | Se cuenta desde la última transición de etapa o escritura válida, usando reloj del servidor; polling/descarga no prolongan la vida. No se borra una etapa en ejecución: primero termina o vence su timeout y después se aplica limpieza. |
| Casos activos/retendidos | 2 por proceso Python | Se reserva atómicamente al aceptar fase A; el tercero recibe `503 CAPACIDAD_AGOTADA` sin pago. Se libera al descartar o caducar. Un caso completado sigue ocupando plaza hasta entonces. |

Son límites conservadores para un prototipo local, **propuestos, no aceptados ni
validados por carga**. Tienen configuración documentada; cambiar capacidad tras
medir no cambia los AC, salvo que afecte al contrato revisado. Los timeouts por
servicio se fijan con el entorno en implementación y se inyectan en tests. Se
comprueban tamaño/píxeles en AC-001, capacidad e idempotencia en AC-010 y
caducidad/limpieza en AC-012. Un servidor con varios workers requiere otra
coordinación y revisión; no se presupone que el límite local sea global.

### Compose y entorno

Se propone un `compose.yaml` en la raíz del proyecto entregado,
`entregas/cu-19-interpretacion-danos/`, para que forme parte de la carpeta que
se entrega a la asignatura. Desde la raíz del repo se podrá usar
`docker compose -f entregas/cu-19-interpretacion-danos/compose.yaml up --build`.
**#34 es responsable de este archivo y de la integración global. #32 aporta
el servicio PostgreSQL con pgvector, su volumen, la preparación del schema RAG
y sus comandos de preparación, indexado, consulta y evaluación**, junto con
las dependencias Python del componente. #34 las incorpora al entorno de los
agentes. Es un único Compose y una única PostgreSQL, con tablas del explorador
y del RAG separadas; no se delega otra vez la ubicación a la #56.

La contribución de base de datos puede incorporarse primero al archivo común
para verificar la parte RAG antes del recorrido web completo. Su comprobación
pertenece al AC-013 de #32; el arranque y recorrido del conjunto, al AC-013 de
#34. Este reparto no acredita que los contenedores ya estén implementados.

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
| Categoría y procedencia | Formato aceptado por Víctor; adaptación consumidora pendiente | #28/#69 y ADR 0001 aceptados. Lucas elige V25 fijo el 2026-11-10. Víctor acepta los tres valores y fija compatibilidad/validaciones en el comentario enlazado en «Adaptación de imagen y procedencia»; v1.4 las recoge. Falta el AC nuevo de #31, sin restaurar AC-010, y la aceptación del plan/ADR completos. |
| RAG | Contrato aceptado; implementación pendiente | #56/#67 y ADR 0006 Aceptado; #34 consume `agente2()` y `diagnostico_rag` conservando sus estados. #72 aporta PostgreSQL y RAG al Compose común. Código real requerido para integración final. |
| Contrato web/Python y límites configurados | Propuestos para revisión | HTTP, idempotencia, estado efímero y límites iniciales 10 MiB / 20 millones de píxeles / 60 min / 2 casos. Son valores de partida, sin benchmark ni aceptación atribuida. |
| Modelo concreto y dependencias | Comprobación de entorno | Visión por configuración y embeddings según #32; no elegir aquí otro modelo de chat ni copiar automáticamente las dependencias del experimento. Registrar versiones/acceso al preparar la implementación. |
| Plazo y reparto de trabajo | Propuesta actualizada por hitos | Primero CLI y después web/HTTP, sin recortar AC. El hito del martes 10 no se acredita sin plan/ADR integrados y componentes reales; registrar motivo si no se llega. Calendario propuesto abajo. |

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
| Categoría válida desconocida o contexto incompleto | Si no se elige coche, resolver V25 con aviso; el resto de datos sigue siendo obligatorio. Un fallo técnico detiene el caso. | AC-003, AC-004, AC-011 |
| Error de visión, costes o informe | Detención explícita, sin informe final ni éxito aparente. | AC-011 |
| Procedencia ausente en una entrada anterior o llamada directa al informe | Mantener `vehiculo_id` como dato de entrada y el informe previo, sin aviso de procedencia. El flujo nuevo conserva siempre su origen resuelto. | AC-008 |
| Procedencia presente fuera del enum o incoherente con el vehículo/referencia | #31 lanza excepción explícita; #34 comunica `CONTRATO_INVALIDO` en informe, sin publicación ni descarga final. No se trata como campo ausente. | AC-008, AC-011 |
| Falta de fuentes o fallo tipado del RAG | Resultado preliminar, causas por tema, citas de consultas `recuperadas` conservadas. | AC-007 |
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
| AC-003 | #28 propone categoría válida y representante, o `desconocido`; la persona confirma, elige o no selecciona. | Se resuelve un vehículo válido antes de fase B. Con `desconocido` sin elección se usa V25 fijo; con elección válida se respeta esa elección. CLI y web usan la misma función y conservan predicción y procedencia. En el caso por defecto, pantalla y contrato del informe muestran literalmente: «Vehículo no identificado en la imagen: el presupuesto usa el vehículo de mayor coste como techo prudente. Es preferible que el importe sobre a que falte, porque un presupuesto corto dejaría la reparación sin cubrir.». No se calcula el máximo exacto entre los 27 coches ni se aplica V25 ante fallo técnico. |
| AC-004 | Enviar contexto válido de rol propio y de tercero, y contexto inválido/ausente. | Se pasan los campos de #30 sin inventarlos; póliza obligatoria solo en rol propio. Error por campo antes del cálculo, conservando fase A para corregirlo. Confirmar vehículo o completar datos no vuelve a llamar a PIIA 1/visión. |
| AC-005 | Ejecutar ambas fases con dependencias que registran llamadas. | Se usa el runtime nativo ADK, con orden PIIA 1 → Agente 1; tras contexto válido, `agente2()` → Agente 3 → verificación. No se llama al coste antes de `agente2()` ni se añade un LLM para coordinar/redactar cifras. Una fase fallida no ejecuta sus sucesoras. |
| AC-006 | Findings con confirmados, pendientes y rechazados, y escenario sin daños. | La web solo muestra los resultados, sin permitir cambiar daños; una petición con findings editados se rechaza. Los JSON de entrada al cálculo y al informe conservan hallazgos y tiers, y los dos escenarios y sus cifras coinciden con la ejecución directa de #30/#32 para el mismo contexto. |
| AC-007 | Respuestas `diagnostico_rag` en los cinco estados y con citas parciales. | JSON e informe conservan el diagnóstico acordado con #32/#31. `parcial`, `sin_resultados` y `error` producen aviso preliminar y causas por tema, sin perder citas de consultas `recuperadas`. `recuperadas` no se presenta como verificación; `no_aplica` no genera fallo técnico. |
| AC-008 | Representante confirmado, vehículo elegido y V25 por defecto; además, una entrada anterior sin origen y entradas con origen inválido o incoherente. | El flujo nuevo conserva `referencia_confirmada`, `seleccion_usuario` o `maximo_por_defecto` hasta la salida. Informe/pantalla distinguen las tres procedencias; con máximo por defecto muestran el aviso de AC-003 y la limitación del valor venal, pérdida total e indemnización calculados con V25. Sin el campo, #31 conserva el informe previo con `vehiculo_id` como entrada y sin aviso de procedencia. Con un valor fuera de los tres, máximo por defecto con ID distinto de V25 o referencia confirmada distinta de `vehiculo_id_referencia` (incluida referencia nula), #31 lanza una excepción explícita que nombra el campo/ID; #34 comunica error y no publica informe final. La aceptación de Víctor del formato/precisiones no sustituye el AC nuevo consumidor de #31 ni la aceptación del plan/ADR completos antes de Ready. |
| AC-009 | Informe correcto y otro con un importe inventado respecto a salida de Agente 2. | Se ejecuta `comprobar_cifras` antes de publicar. Correcto: el generador conserva los escenarios y los importes monetarios de Agente 2; el verificador detecta importes ajenos en euros, sin demostrar por sí solo la coherencia de escenarios. Inventado: error `CIFRAS_INCONSISTENTES`, sin informe terminado ni descarga. El LLM no recibe el encargo de reescribir el presupuesto. |
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
| `specs/34-orquestacion-web.md#AC-001` | S1 | TDD: navegación, archivo válido/inválido, límites de bytes y píxeles exactos y excedidos y cero llamadas prematuras. | Imagen sintética y entradas inválidas; ML/visión falsos. | Harness web/HTTP; pulsar carga y análisis por separado. | Red/Green y recuentos. |
| `specs/34-orquestacion-web.md#AC-002` | S2 | TDD: adaptar cero/una/varias detecciones y rechazar formato inválido. | Respuesta ML guionizada, imagen con orientación conocida y bboxes. | Suite Python; capturar entrada pública del Agente 1. | Red/Green; comparación de clases, scores y geometría. |
| `specs/34-orquestacion-web.md#AC-003` | S1 + S2 + S3 | TDD: confirmar/corregir; desconocido con selección y sin ella; fallo técnico sin fallback. | Catálogo real y #28 integrado; cliente falso. | CLI y HTTP con la misma función; comprobar V25/origen y frase literal, selección expresa de V25 diferenciada. | Red/Green; procedencia y texto; cero cálculo ante fallo técnico. |
| `specs/34-orquestacion-web.md#AC-004` | S1 + S3 | TDD: contexto inválido, corrección y rol tercero. | Contextos del contrato y copias inválidas; datos Plexus. | Suite HTTP; contador de fases antes/después. | Red/Green; mensajes y llamadas sin duplicar. |
| `specs/34-orquestacion-web.md#AC-005` | S3 | TDD: ejecución nativa y orden con detención en fallos. | ADK real, funciones públicas/proveedores falsos con registro. | Suite Python por fase y recorrido completo. | Red/Green; secuencia de invocaciones. |
| `specs/34-orquestacion-web.md#AC-006` | S1 + S3 + S4 | TDD y regresión: daños inmutables, dos escenarios y caso vacío. | Ejemplos de contrato; paquete real; salida directa de #30/#32 como referencia independiente. | Suites Python/HTTP; comparar JSON y rechazar edición de findings. | Igualdad de campos/entradas y escenarios. |
| `specs/34-orquestacion-web.md#AC-007` | S1 + S3 | TDD: los cinco estados RAG y conservación de citas parciales. | Contrato final #56; respuestas guionizadas. | Ejecutar fase B y revisar JSON/Markdown con #31. | Red/Green; texto de aviso y temas afectados. |
| `specs/34-orquestacion-web.md#AC-008` | S1 + S3 | TDD: tres procedencias, aviso V25/pérdida total, compatibilidad sin campo y rechazo de valores/coherencia inválidos. | Ejemplos anteriores sin origen; copias con los tres valores, valor inventado, máximo con V05, referencia V05 con ID V25 y referencia nula; selección explícita de V25 válida. AC nuevo consumidor pendiente en #31. | Llamada pública a #31 y recorrido CLI/formulario → informe → pantalla/descarga; comparar con informe previo, observar errores sin publicación y verificar que el flujo nuevo siempre transporta el origen. | Red/Green; ausencia sin aviso, errores explícitos con campo/ID, misma procedencia/cifras/advertencias y predicción intacta. |
| `specs/34-orquestacion-web.md#AC-009` | S3 | TDD: informe correcto e importe inventado bloqueado. | Salida Agente 2 del contrato y generador guionizado con importe añadido. | Suite Python/HTTP; comprobar ausencia de descarga en error. | Red/Green; error y cifras originales conservadas. |
| `specs/34-orquestacion-web.md#AC-010` | S1 + S3 + S5 | TDD: polling, reenvíos, concurrencia, tercera plaza y caso perdido. | Proveedores con contadores; fase detenida por el doble; reinicio del servicio. | Repetir GET/POST; enviar dos confirmaciones simultáneas; reiniciar/caducar. | Recuentos y estados; ninguna llamada duplicada. |
| `specs/34-orquestacion-web.md#AC-011` | S1 + S3 | TDD: un fallo de cada etapa, timeout y respuesta de contrato inválida. | Dobles públicos; límites de tiempo controlados por el test. | Inyectar fallos por separado y consultar estado/descarga. | Red/Green; códigos y detención sin éxito aparente. |
| `specs/34-orquestacion-web.md#AC-012` | S1 + S5 | TDD: Markdown idéntico, sin HTML ejecutable, sin historial y limpieza. | Informe UTF-8, texto HTML, directorio temporal y DB de prueba. | Descargar dos veces; comparar bytes; descartar/caducar a los 60 minutos con reloj controlado/reiniciar; polling sin renovar TTL; consultar DB. | Red/Green; artefactos eliminados y persistencia ajena intacta. |
| `specs/34-orquestacion-web.md#AC-013` | S4 + S5 | Integración: conjunto reproducible, sin pago al arrancar y preparación ausente. | Docker, versiones/modelos/paquete registrados; DB vacía; índice preparado explícitamente. | Compose global desde raíz; verificar salud, flujo y reinicio; repetir sin dependencia. | Comandos y resultados reales, perfil/hardware y llamadas. |
| `specs/34-orquestacion-web.md#AC-014` | S1 + S4 | Eval de integración: 3–5 imágenes y lectura humana, con baseline conservada. | Imágenes autorizadas identificadas por hash; modelos reales; contextos registrados. | Recorrido web autorizado y tabla por caso; repetir si cambia integración. | Informes, comprobación de cifras y límites; sin fotos/clave en Git. |

## Implementation Plan

| Slice | Objetivo observable | AC | Dependencias y verificación |
|---|---|---|---|
| 1 — Recorrido CLI primero | Foto → PIIA 1 → Agente 1 → resolución común de vehículo/contexto → Agente 2 → Agente 3 → comprobación → Markdown. | AC-002 a AC-009, AC-011 | Plan/ADR aceptados; #28/#30 integrados; #31/#32 reales para acreditar integración. TDD por fronteras y smoke ADK. Mientras falta RAG, `estimar_siniestro` con `normativa: []` permite un esqueleto parcial explícito, sin acreditar AC-007 ni el flujo completo. |
| 2 — Web y contrato HTTP | Pestaña, subida, hallazgos de solo lectura, confirmación y formulario sobre la misma resolución CLI. | AC-001 a AC-004, AC-006, AC-008 | Slice 1; HTTP propuesto revisado. Casos de entrada y formulario, mismo resultado que CLI con iguales datos. |
| 3 — Estado y entrega | Dos fases asíncronas, idempotencia, límites, errores, descarga y limpieza. | AC-005, AC-009 a AC-012 | Slices 1–2; pruebas de capacidad, TTL con reloj controlado, reenvíos, fallos y bytes. |
| 4 — Compose e integración real | Compose único y preparación reproducible; 3–5 imágenes con lectura humana. | AC-006, AC-007, AC-013, AC-014 | Componentes reales integrados y configuración/modelos/paquete identificados. Filas de integración y regresiones del Test Plan. |

### Calendario por martes (propuesto; sin recorte de alcance)

| Hito | Resultado y condición |
|---|---|
| Martes 10 de noviembre | Cerrar revisión del plan/ADR y primer Markdown CLI si los gates y agentes reales lo permiten. Si no, registrar exactamente dependencia y siguiente acción; no presentarlo como hecho. |
| Martes 17 de noviembre | CLI real verificable y conexión web/HTTP; ensayo de la rama limpia de Entrega 2 por Lucía. La documentación puede entregarse sin declarar implementadas piezas pendientes. |
| Martes 24 de noviembre | Completar ciclo de vida, Compose y 3–5 casos reales para congelación del proyecto el 27, si los componentes están disponibles. Retrasos se registran; ningún AC se rebaja sin decisión humana. |

Coordinación de entrega comunicada por Lucía el 2026-11-10: pendientes resueltos
o motivados por escrito el viernes 13, ensayo el martes 17 y PR al curso a más
tardar el viernes 20 para el plazo comunicado del lunes 23. `evaluacion/entrega-2.md`
aún dice lunes 16: esa discrepancia se comunica, no se modifica aquí el enunciado.
Estos hitos son objetivos de coordinación, no evidencia de implementación.

### ADK: razón y disparador de revisión

La elección de ADK se mantiene por decisión de Lucas y por reutilizar sesiones,
eventos y workflows del framework probado en #52. No se atribuye a un requisito
confirmado de la asignatura ni a una mejora de calidad del presupuesto. El
coste frente a Python directo son adaptadores y entorno adicionales. Punto de
partida reproducible: ADK 2.12.0 y LiteLLM 1.106.0 del experimento; las APIs
nativas propuestas necesitan su propia prueba.

Disparador técnico propuesto: si el smoke de la slice 1 (ambas fases nativas,
estado aislado, orden y detención en errores, sin modelo coordinador) no pasa
al cerrar el hito del 10 de noviembre, registrar el fallo y proponer Python
directo al equipo ese mismo día. Cambiar requiere revisar ADR 0007 y AC-005
antes de implementar esa alternativa; no hay cambio automático ni recorte de web.

## Pendientes para Ready

1. Revisión humana del documento v1.4 completo y aceptación/integración de
   Planning PR #60 y ADR 0007 sobre el head final. Lucía es la revisora prevista.
2. Víctor ya acepta el formato de `contexto.vehiculo_origen` con las dos
   precisiones recogidas en v1.4; debe incorporar aviso, compatibilidad y
   validación en un AC nuevo del plan #31. Ese plan consumidor sigue pendiente,
   sin reutilizar AC-010. #28/ADR 0001 y #32/ADR 0006 ya están aceptados en main;
   no se les atribuye aceptación del nuevo plan/ADR.
3. Revisar límites, HTTP, calendario y disparador ADK. Confirmar lector de
   los 3–5 informes y equipo/perfil ML; acceso al proveedor se comprueba antes
   de verificaciones de pago, sin suponer autorización de gasto por este plan.
4. Acreditar DoR de la nueva versión en #34 y registrar el commit publicado.
   Las implementaciones reales de #31/#32 siguen siendo dependencias para
   integración final; el esqueleto provisional no acredita su entrega.

### Resultado de analyze

| Comprobación | Resultado |
|---|---|
| Trazabilidad | 14 IDs conservados; cada AC tiene fila Test Plan y slice. AC-003/008 adaptados a decisiones de #34 y a V25 elegido por Lucas; AC-010 de #31 sigue retirado. |
| Preservación | Predicción #28 intacta; costes y dos escenarios #30 sin cambios; contrato RAG aceptado consumido sin reescribir cifras. Procedencia es ampliación propuesta a revisar con #31. |
| Decisión arquitectónica | NEW_ADR: 0007 sigue Propuesto; incorpora la política del orquestador y campo aditivo, sin modificar la salida de #28 ni las fórmulas de #30. No se crea otro ADR por la misma decisión. |
| Estado | Borrador v1.4, no Ready. Víctor acepta el formato de procedencia y sus precisiones, no el documento/ADR completos; el AC nuevo consumidor sigue pendiente. V25 es decisión de Lucas; los demás parámetros y calendario mantienen su revisión pendiente. |
| Actualización v1.4 | Petición de Lucas de recoger el comentario de Víctor en #60: campo opcional para compatibilidad y validación de valores/coherencia en el informe. Se precisa AC-008 y su Test Plan, conservando los otros 13 AC, IDs, cifras, frase de AC-003, política V25, calendario, disparador ADK y DoD. |
| Verificación | Revisión documental de AC, enlaces, tablas y diff. No se ha ejecutado el flujo ni una inferencia de pago durante esta planificación. |

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
