# ADR 0007: Orquestación ADK, interfaz web y ejecuciones efímeras

- Estado: Propuesto
- Fecha: 2026-10-27
- Versión: propuesta v1.3 (2026-11-10); conserva v1 `733c5d0`, v1.1 `9a65c26` y v1.2 `5ed9ca6`. Incorpora V25 fijo elegido por Lucas, procedencia y límites propuestos, orden CLI primero y disparador de revisión ADK.
- GitHub Issue: https://github.com/lvckss/piia2-26/issues/34
- Planes cubiertos: [34-orquestacion-web.md](../../specs/34-orquestacion-web.md), coordinación, frontera web/Python, estado temporal y Compose.
- Planning PR: https://github.com/lvckss/piia2-26/pull/60 — draft.
- Aceptación: pendiente de revisión humana del documento completo, los contratos y las alternativas. Las decisiones de producto de Lucas no equivalen a aceptar este ADR.
- Sustituye / sustituido por: no sustituye un ADR aceptado. Reutiliza las responsabilidades base de los ADRs 0002–0005; se apoya en #28/ADR 0001 y #32/ADR 0006 ya aceptados en main. El contrato nuevo de procedencia requiere revisión propia.

## Contexto y motivación

La guía de integración de #34 propone ADK o Python directo y un ejemplo desde
archivos de CarDD. La prueba #33/#52 integrada en `main` `d5dd44d` acredita
viabilidad mínima de ADK con OpenAI y una tool que conserva su importe. No
acredita la integración completa ni convierte sus dependencias en las del producto.

Lucas ha elegido ADK y un recorrido desde una pestaña de la web: subir una
imagen, ver los daños sin editarlos, confirmar/corregir el vehículo, completar
datos y mostrar/descargar Markdown. Ha elegido no tener historial. #28/#69 y
ADR 0001 ya están integrados: `desconocido` entrega referencia nula y los
AC-009/010 se transfirieron a #34/#31. Lucas decide el 2026-11-10 usar V25 fijo
si el vehículo es `desconocido` y la persona no elige, sobre las propuestas de
Lucía y Víctor registradas en #34. Los fallos técnicos detienen el flujo.
La regla vive en una sola función del orquestador para CLI y web; #30 recibe
siempre vehículo válido. El formato de procedencia sigue propuesto a Víctor.

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
   ejecución. Se reutilizan sesiones/eventos y workflows de ADK; el precio lo
   calcula código y no mejora por adoptar el framework. #52 probó ADK 2.12.0 y
   LiteLLM 1.106.0, no las APIs nativas de esta integración. El smoke CLI del hito
   del 10 de noviembre valida fases, aislamiento, orden y detención. Si falla,
   se registra y se propone Python directo al equipo; cambiar requiere revisar
   este ADR y AC-005, sin aplicar la alternativa automáticamente. No añadir un modelo que elija el orden o reescriba cifras. La
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
   #34 propone `contexto.vehiculo_origen`: `referencia_confirmada`,
   `seleccion_usuario` o `maximo_por_defecto`; no un objeto separado. Para
   categoría válida `desconocido` sin elección, una función común CLI/web
   resuelve V25 fijo y construye el origen en servidor. V25 calcula también
   valor venal, pérdida total e indemnización; la pérdida total no es fiable
   para el coche real. No se calcula el máximo exacto entre los 27 modelos.
   La predicción `vehiculo` queda intacta, incluida su referencia nula. #31 debe
   aceptar este contrato y añadir un AC nuevo, sin reutilizar el retirado.
   Pantalla e informe conservan la frase literal y el aviso adicional de la
   Spec. Este diseño sigue propuesto, sin atribuir aceptación a Víctor. Conservar el
   `diagnostico_rag` acordado con #32/#31 y sus avisos preliminares.
5. **Estado efímero, sin historial de casos.** Mantener estado y artefactos
   temporales hasta descarga/descartado/caducidad, sin tablas de casos ni su
   listado en la web. Las subidas no se incorporan a CarDD. Reinicios/caducidad
   pueden perder el caso y se comunican, sin prometer reanudación durable ni
   repetirlo automáticamente. La descarga no elimina inmediatamente el
   resultado mientras siga disponible en pantalla. Límites iniciales propuestos:
   10 MiB, 20.000.000 píxeles, 60 minutos de inactividad y dos casos retenidos
   por proceso. Son valores conservadores sin medición de carga; ver reglas
   de capacidad, actividad y limpieza en la Spec. Polling no renueva caducidad
   y una etapa en curso termina o vence timeout antes de limpiar.
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
| Python directo | Cableado pequeño y sencillo; mismas funciones deterministas. | Menos dependencias para el orden fijo; alternativa si falla el smoke CLI de ADK del 10 de noviembre. Requiere decisión humana, revisión de ADR/AC-005 y registro antes de cambiar, sin recortar web. |
| Coordinador LLM que decide qué tools llamar | Flexible para recorridos variables. | El recorrido está fijado; introduce llamadas y riesgo de saltarse pasos o reformular cifras sin una necesidad identificada. |
| Mantener únicamente un comando con archivos de CarDD | Reduce trabajo de interfaz y subida. | No cumple la entrada web con una imagen nueva elegida por Lucas. |
| Una petición HTTP larga hasta el informe | Menos estados y operaciones. | No encaja con la confirmación/corrección del vehículo entre las fases ni con consultar progreso sin repetir trabajo. |
| Historial en PostgreSQL y cola durable | Facilita reanudar tras reinicios y consultar casos anteriores. | Añade persistencia y semántica de recuperación que no se han pedido; Lucas ha elegido salida al terminar, sin historial. |
| Estado efímero y límites configurados, propuesta | Suficiente para el uso local acordado y reduce componentes. | Pierde el caso al reiniciar; exige errores claros, limpieza y no repetir llamadas en silencio. |
| Compose independiente para cada parte | Reutiliza el despliegue actual de ML con pocos cambios. | No cumple levantar el conjunto con un único Compose y puede duplicar bases de datos/configuraciones. |

## Consecuencias

- La integración pasa a tener dos fronteras explícitas: HTTP web/Python y los
  JSON entre agentes. Cada una se prueba sin utilizar mocks de funciones privadas.
- Categoría #28/ADR 0001 y RAG #32/ADR 0006 están aceptados e integrados;
  #72/#75 siguen abiertos. No se presenta el índice, `agente2()` ni el informe
  como entregados en main por el hecho de tener planes aceptados.
- El contrato nuevo de procedencia y el AC consumidor de #31 siguen pendientes
  de revisión. La política fija V25 fue elegida por Lucas; la frase «vehículo de
  mayor coste» de Lucía se conserva por instrucción, con la limitación explícita
  de que V25 no es necesariamente el máximo exacto para cualquier siniestro.
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
- [RAG v1.6](https://github.com/lvckss/piia2-26/blob/8a38e02310f8cb3b5e2994684715fe34dfee4613/entregas/cu-19-interpretacion-danos/specs/32-rag-normativa.md), ADR 0006 Aceptado;
  [categoría v1.3.2](https://github.com/lvckss/piia2-26/blob/8a38e02310f8cb3b5e2994684715fe34dfee4613/entregas/cu-19-interpretacion-danos/specs/28-categoria-vehiculo.md), ADR 0001 Aceptado;
  [informe v2.1](https://github.com/lvckss/piia2-26/blob/8a38e02310f8cb3b5e2994684715fe34dfee4613/entregas/cu-19-interpretacion-danos/specs/31-informe-peritaje.md).
- Decisiones de [Lucía](https://github.com/lvckss/piia2-26/issues/34#issuecomment-6611207541),
  [Víctor](https://github.com/lvckss/piia2-26/issues/34#issuecomment-6657185939) y
  [frase literal](https://github.com/lvckss/piia2-26/issues/34#issuecomment-6736461374).
  La v1.3 recoge además la elección de Lucas de V25 fijo en sesión del 2026-11-10.
- [ADK: secuencia nativa](https://adk.dev/agents/workflow-agents/sequential-agents/)
  y [agentes personalizados](https://adk.dev/agents/custom-agents/), consultadas
  el 2026-10-26. La compatibilidad de las versiones de producto se comprobará
  durante implementación, sin dar por hecho que el experimento cubra estas APIs.
- Código y despliegue inspeccionados en `main` `8a38e02`: referencias concretas
  en «Estado actual y evidencia» de la Spec. No se han ejecutado modelos,
  instalado dependencias ni realizado pruebas funcionales para este borrador.
