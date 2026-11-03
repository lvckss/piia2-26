# ADR 0007: Orquestación ADK, interfaz web y ejecuciones efímeras

- Estado: Propuesto
- Fecha: 2026-10-27
- Versión: propuesta v1.2; actualiza las referencias a #28 v1.2 respecto a `9a65c26` y aclara que #34 define la procedencia y #31 la consume. El formato sigue pendiente de acuerdo; no cambia el resultado observable de los AC. Historial: v1 en `733c5d0`; v1.1 en `9a65c26`, reparto de Compose con #32.
- GitHub Issue: https://github.com/lvckss/piia2-26/issues/34
- Planes cubiertos: [34-orquestacion-web.md](../../entregas/cu-19-interpretacion-danos/specs/34-orquestacion-web.md), coordinación, frontera web/Python, estado temporal y Compose.
- Planning PR: https://github.com/lvckss/piia2-26/pull/60 — draft.
- Aceptación: pendiente de revisión humana del documento completo, los contratos y las alternativas. Las decisiones de producto de Lucas no equivalen a aceptar este ADR.
- Sustituye / sustituido por: no sustituye un ADR aceptado. Reutiliza las responsabilidades base de los ADRs 0002–0005; depende de acordar la ampliación de categoría de #28/ADR 0001 y el diagnóstico RAG de #32/ADR 0006.

## Contexto y motivación

La guía de integración de #34 propone ADK o Python directo y un ejemplo desde
archivos de CarDD. La prueba #33/#52 integrada en `main` `d5dd44d` acredita
viabilidad mínima de ADK con OpenAI y una tool que conserva su importe. No
acredita la integración completa ni convierte sus dependencias en las del producto.

Lucas ha elegido ADK y un recorrido desde una pestaña de la web: subir una
imagen, ver los daños sin editarlos, confirmar/corregir el vehículo, completar
datos y mostrar/descargar Markdown. Ha elegido no tener historial. La v1.2 de
#28, publicada en #29 (`dca27ad`), ya planifica la categoría automática solo en
el Agente 1 y transfiere AC-009/010 a #34/#31. Con `desconocido` entrega una
referencia nula: #34 pide selección al usuario, sin asignar un compacto. Un
fallo técnico del proveedor se propaga y detiene el flujo (AC-007 de #28).
Su revisión e integración siguen pendientes, igual que acordar con el
responsable del informe el formato de procedencia definido por #34.

La web y backend son React/Bun/Hono; los agentes son Python. PIIA 1 ya ofrece
`POST /v1/damage-assessment` con archivo, pero su JSON necesita adaptación al
Agente 1. Hay Compose de ML, no del conjunto. La confirmación humana separa
dos fases y exige conservar el análisis sin repetir las consultas de pago.

Es una decisión estructural: fija un framework de producto, una API entre
componentes, el ciclo de vida de sus datos y cómo se despliegan. Los ADRs
previos no cubren esa frontera ni este recorrido.

## Decisión propuesta

1. **ADK nativo con orden fijo.** Usar sus workflows/agentes nativos y adaptadores
   mínimos para llamar a las funciones existentes, con estado independiente por
   ejecución. No añadir un modelo que elija el orden o reescriba cifras. La
   documentación de ADK describe `SequentialAgent` como secuencia determinista
   y `BaseAgent` como extensión para lógica propia; las APIs y dependencias se
   fijan y comprueban al implementar. No se construye otro framework de agentes.
2. **Dos fases.** PIIA 1 y Agente 1/categoría antes de la confirmación del usuario;
   `agente2()` → Agente 3 → verificador después. Una confirmación válida no
   vuelve a detectar ni a consultar visión. La categoría se implementa en #28,
   la composición del Agente 2 en #32 y el informe en #31.
3. **Puerta HTTP en Hono y servicio Python interno.** La web consume
   `/api/peritajes` con las operaciones y estados propuestos en la Spec. El
   backend accede al servicio Python por la red Compose. Peticiones asíncronas
   devuelven un identificador opaco; consultar progreso no ejecuta trabajo.
   La API de peritaje se valida de forma independiente del JSON de los agentes.
4. **Cálculos y procedencia preservados.** Resolver `vehiculo_id` antes de #30,
   conservar findings y cifras y comprobar el informe antes de publicarlo.
   #34 define aquí y en su Spec el contrato de procedencia; #31 lo consume
   para mostrarla en el informe. Revisar el formato con Víctor, respetando la
   predicción `vehiculo` de #28, sin restaurar unilateralmente campos o AC
   retirados. Conservar el
   `diagnostico_rag` acordado con #32/#31 y sus avisos preliminares.
5. **Estado efímero, sin historial de casos.** Mantener estado y artefactos
   temporales hasta descarga/descartado/caducidad, sin tablas de casos ni su
   listado en la web. Las subidas no se incorporan a CarDD. Reinicios/caducidad
   pueden perder el caso y se comunican, sin prometer reanudación durable ni
   repetirlo automáticamente. La descarga no elimina inmediatamente el
   resultado mientras siga disponible en pantalla.
6. **Idempotencia durante la vida del caso.** POST repetido con misma clave y
   contenido reutiliza el trabajo; contenido distinto con la misma clave da
   conflicto. Generar informe es una transición atómica. No hay garantía
   persistente de deduplicación después de perder el estado ni reintentos
   automáticos del flujo completo. Se registran los retries internos del SDK.
7. **Compose global en la carpeta entregada.** #34 es responsable del archivo
   `entregas/cu-19-interpretacion-danos/compose.yaml` y de integrar frontend
   compilado/backend, orquestador Python, ML y PostgreSQL. #32 aporta el servicio
   PostgreSQL/pgvector, volumen, schema RAG, comandos y dependencias Python del
   componente; #34 las integra en el entorno de los agentes. La base de datos
   puede comprobarse primero para #32; #34 verifica el conjunto completo.
   No hay segundo Compose ni otra PostgreSQL; el schema del backend queda
   separado de las tablas RAG. Datos/modelos externos se montan localmente;
   la localización del paquete se adapta sin exigir `.git` en los contenedores.
   Preparar índices de pago es una acción explícita, separada del arranque.
8. **Entrega de texto.** Renderizar Markdown sin ejecutar HTML recibido y
   descargar los mismos bytes UTF-8. No introducir PDF, historial ni edición
   de daños en esta versión. Mantener errores de entrada, fallos técnicos y
   ausencia/parcialidad de fuentes como resultados diferentes.

## Alternativas consideradas

| Alternativa | Ventajas | Costes / motivo de la propuesta |
|---|---|---|
| ADK nativo con secuencia fija, propuesta | Respeta la elección de Lucas y reutiliza el framework probado; orden y cifras controlados por código. | Añade dependencia/entorno ADK y adaptadores que hay que probar de extremo a extremo. |
| Python directo | Cableado pequeño y sencillo; mismas funciones deterministas. | Alternativa de recorte del plan del equipo, pero no es la elección actual de Lucas. Cambiar a ella requeriría registrar y revisar la decisión. |
| Coordinador LLM que decide qué tools llamar | Flexible para recorridos variables. | El recorrido está fijado; introduce llamadas y riesgo de saltarse pasos o reformular cifras sin una necesidad identificada. |
| Mantener únicamente un comando con archivos de CarDD | Reduce trabajo de interfaz y subida. | No cumple la entrada web con una imagen nueva elegida por Lucas. |
| Una petición HTTP larga hasta el informe | Menos estados y operaciones. | No encaja con la confirmación/corrección del vehículo entre las fases ni con consultar progreso sin repetir trabajo. |
| Historial en PostgreSQL y cola durable | Facilita reanudar tras reinicios y consultar casos anteriores. | Añade persistencia y semántica de recuperación que no se han pedido; Lucas ha elegido salida al terminar, sin historial. |
| Estado efímero y límites configurados, propuesta | Suficiente para el uso local acordado y reduce componentes. | Pierde el caso al reiniciar; exige errores claros, limpieza y no repetir llamadas en silencio. |
| Compose independiente para cada parte | Reutiliza el despliegue actual de ML con pocos cambios. | No cumple levantar el conjunto con un único Compose y puede duplicar bases de datos/configuraciones. |

## Consecuencias

- La integración pasa a tener dos fronteras explícitas: HTTP web/Python y los
  JSON entre agentes. Cada una se prueba sin utilizar mocks de funciones privadas.
- El plan de categoría #28 v1.2/#29 ya recoge `desconocido` sin referencia y
  una evaluación manual sin umbral del 70 %. Su revisión, aceptación del ADR
  0001 e implementación siguen pendientes; este ADR no las acredita.
- El informe debe distinguir representante de coche identificado. El plan #31
  actual no acredita esa adaptación; acordarla con Víctor bloquea Ready.
- El ADR 0006 del RAG sigue Propuesto en #56. Aceptar este ADR no lo acepta por
  transitividad ni entrega `agente2()` ni el índice.
- Los temporales necesitan limpieza y límites documentados; la base del
  explorador y el índice RAG conservan su persistencia. Sin historial no implica
  borrar esos datos ni eliminar el resultado antes de poder descargarlo.
- El servicio ML necesita modelos locales y hardware compatible. Se documentará
  el perfil probado; no se afirma que inferencia, latencia y recursos estén ya medidos.
- Web, subida, despliegue y recuperación de categoría amplían el plan original
  de #34. Debe acordarse el calendario; no se presenta como el mismo esfuerzo
  estimado antes de esos cambios.
- TDD en cableado, estado, errores, contratos y cifras; integración real sobre
  3–5 imágenes con lectura humana y métricas disponibles. La evaluación de
  calidad a mayor escala permanece en #46 y las de categoría/RAG en sus Issues.

## Referencias y evidencia

- [Registro de alcance de #34](https://github.com/lvckss/piia2-26/issues/34#issuecomment-6426795027)
  y [solicitud de retomar #28](https://github.com/lvckss/piia2-26/issues/28#issuecomment-6426798908).
- [Prueba ADK/OpenAI #52](https://github.com/lvckss/piia2-26/pull/52), integrada:
  evidencia de una tool, importe conservado y replay documentado; no prueba el
  presente servicio ni una ejecución de los tres agentes.
- [RAG #56](https://github.com/lvckss/piia2-26/pull/56), `c77a17c`, draft;
  [categoría #29](https://github.com/lvckss/piia2-26/pull/29), v1.2 en
  [`dca27ad`](https://github.com/lvckss/piia2-26/blob/dca27add4cf87fc460fb7516625672798552e3c4/entregas/cu-19-interpretacion-danos/specs/28-categoria-vehiculo.md),
  revisión e integración pendientes;
  [informe v2 #58](https://github.com/lvckss/piia2-26/pull/58), integrada.
- [ADK: secuencia nativa](https://adk.dev/agents/workflow-agents/sequential-agents/)
  y [agentes personalizados](https://adk.dev/agents/custom-agents/), consultadas
  el 2026-10-26. La compatibilidad de las versiones de producto se comprobará
  durante implementación, sin dar por hecho que el experimento cubra estas APIs.
- Código y despliegue inspeccionados en `main` `d5dd44d`: referencias concretas
  en «Estado actual y evidencia» de la Spec. No se han ejecutado modelos,
  instalado dependencias ni realizado pruebas funcionales para este borrador.
