# CU-19 — Interpretación de daños en vehículos

## Qué es el proyecto

Un prototipo que ayuda a un perito o tramitador de seguros a convertir la foto de un vehículo dañado y los datos del siniestro en un **informe de peritaje orientativo**. Combina la detección de daños heredada de PIIA1, una segunda opinión con visión, el cálculo determinista de reparación y cobertura y la recuperación de pólizas y legislación con fuentes.

**Este README presenta el proyecto completo; la Entrega 2 añade su arquitectura y sus decisiones de implementación.** Las funcionalidades tienen distintos estados de desarrollo; describir el flujo objetivo no significa que la integración completa ya esté implementada o evaluada. La [arquitectura](ARCHITECTURE.md) explica cómo se conectan las piezas y los [ADRs](decisions/) recogen las decisiones de implementación. El código adjunto sirve como contexto de esa arquitectura.

## Motivación

La inspección manual de daños requiere tiempo. Además, una detección automática puede ser un falso positivo: en las 500 imágenes analizadas de CarDD, las predicciones iniciales con score ≥ 0,3 presentan una precisión inferior al 15 % por clase (medición y límites en [confianza de los hallazgos](specs/agente-confianza-hallazgos.md)). Convertirlas directamente en afirmaciones económicas produciría presupuestos con daños no confirmados.

Queremos estudiar si una segunda opinión de visión y una separación explícita entre hallazgos confirmados, pendientes y rechazados permiten elaborar un informe más claro y trazable. Las cifras se calculan mediante la herramienta de Plexus, no las inventa un modelo de lenguaje. El RAG aporta los textos que respaldan las conclusiones y el informe declara cuándo faltan fuentes.

El destinatario es una persona que revisa el siniestro. El prototipo no sustituye su criterio ni toma decisiones vinculantes.

## Alcance

El recorrido objetivo es:

1. **Subir una foto** en una pestaña de la web. El flujo consume la detección de PIIA1 y entrega sus resultados al Agente 1. Las detecciones guardadas de 500 imágenes de CarDD se conservan como base reproducible de evaluación y desarrollo. Ese export se identifica por el SHA-256 de su `_manifest.json` (ver [evaluación y trazabilidad](specs/evaluacion-trazabilidad.md)).
2. **Interpretar los daños:** pieza, severidad, veredicto de visión, caja y nivel de confianza. Los hallazgos se muestran sin edición; los dudosos no se presentan como confirmados.
3. **Proponer una categoría de vehículo y un coche de referencia.** La persona confirma o corrige la elección. Si el vehículo es `desconocido`, el presupuesto usa el vehículo de mayor coste como techo prudente (decisión con el profesorado del 3 de noviembre; cómo puede la persona elegir otro se fija en la spec de orquestación); un fallo técnico de la consulta detiene el flujo. No se identifica la marca y el modelo reales por la foto.
4. **Completar el contexto del siniestro:** vehículo elegido, taller, región, rol y demás datos necesarios; póliza cuando corresponda. El cálculo exige un `vehiculo_id` válido antes de empezar.
5. **Calcular dos escenarios de reparación, cobertura e indemnización:** solo daños confirmados y confirmados más pendientes presupuestables. Las reglas y los importes proceden del cálculo determinista con el paquete sintético de Plexus.
6. **Recuperar pólizas y legislación con fuentes**, filtrando por póliza cuando proceda. Se compararán embeddings small y large; la planificación del RAG fija PostgreSQL/pgvector local y su evaluación con 25 preguntas.
7. **Generar, comprobar, mostrar y descargar el informe Markdown.** Se distinguen los dos escenarios, las dudas y los límites de las fuentes; un importe inconsistente impide publicarlo.

La [spec de orquestación](https://github.com/lvckss/piia2-26/pull/60) reúne el recorrido web, las confirmaciones y los errores. **Su diseño técnico y el ADR 0007 siguen como propuesta en revisión**: incluirlos en esta entrega no los da por aprobados ni habilita su implementación. Las specs de categoría y RAG ya tienen su planificación revisada; eso tampoco acredita que el código esté terminado.

Se incluye también la evaluación reproducible de las piezas: configuración, datos usados, calidad y limitaciones. El objetivo del proyecto completo es levantar la aplicación con un único Compose local. **En esta entrega todavía no existe ningún Compose; el Compose completo es una evolución de la #34, no un compromiso de la entrega.** No se indexa con servicios de pago al arrancar.

Queda fuera del alcance:

- una tasación vinculante, la aprobación automática de reparaciones o la resolución de un expediente de seguro;
- identificar propietarios, personas, matrículas o el modelo exacto del coche desde la imagen;
- entrenar o mejorar el detector de PIIA1; la orquestación reutiliza su servicio, sin investigar otro detector;
- editar los daños desde la interfaz, mantener un historial de casos o generar PDF;
- integrar sistemas reales de aseguradoras o talleres;
- ampliar en esta versión el RAG a un motor completo de exclusiones y plazos: queda como evolución requerida, separada del respaldo documental inicial;
- garantizar fiabilidad en daños que el detector no proponga o en condiciones no cubiertas por la evaluación.

Los vehículos, precios, tiempos de reparación y pólizas de Plexus son **sintéticos**; la legislación es real. Las cifras de reparación y cobertura son orientativas y no vinculantes. Recuperar una cita no equivale a verificar una conclusión. Si faltan fuentes suficientes, el informe lo advierte expresamente y requiere revisión.

## Equipo

| Integrante | Responsabilidad | Contacto |
|---|---|---|
| Lucía Luis Castaño | Visión, datos y evaluación; coordinación de la entrega | lucia.luis.castano@rai.usc.es |
| Víctor Hidalgo Carreira | Costes, cobertura e informe | victor.hidalgo@rai.usc.es |
| Lucas García Ruiz | RAG, orquestación e integración | lucas.garcia0@rai.usc.es |

## Estructura y guía de lectura

```text
cu-19-interpretacion-danos/
├── README.md        # visión del proyecto, alcance y equipo
├── ARCHITECTURE.md  # arquitectura de la solución: diagrama, componentes y flujo
├── specs/           # funcionalidades y sus criterios de aceptación (la de orquestación, en revisión)
├── decisions/       # ADRs de las decisiones de implementación (0001–0006)
├── docs/            # registro de ADRs, workflow y material de apoyo
│   ├── adr/
│   ├── guias/
│   ├── historico/
│   └── templates/
└── app/             # código y documentación adjuntos como contexto
```

### Specs funcionales que se evalúan

Cada fichero explica qué construir, por qué, sus restricciones y los criterios verificables. Los estados de verificación se incluyen como información de desarrollo: un criterio pendiente no es una afirmación de que la funcionalidad ya esté implementada. Los IDs se mantienen para conservar la trazabilidad.

| Funcionalidad | Spec | Resultado definido |
|---|---|---|
| Interpretación visual de daños | [interpretacion-danos-imagen.md](specs/interpretacion-danos-imagen.md) | De predicciones e imagen a hallazgos con pieza, severidad y veredicto. |
| Confianza y filtro de hallazgos | [agente-confianza-hallazgos.md](specs/agente-confianza-hallazgos.md) | Distinguir confirmados y pendientes, registrando lo filtrado. |
| Categoría del vehículo | [28-categoria-vehiculo.md](specs/28-categoria-vehiculo.md) | Proponer un segmento y su representante, o declarar `desconocido`. |
| Costes y cobertura | [30-costes-cobertura.md](specs/30-costes-cobertura.md) | Dos escenarios de coste y su cobertura e indemnización orientativas. |
| Recuperación documental y Agente 2 | [32-rag-normativa.md](specs/32-rag-normativa.md) | Fuentes de póliza/legislación, diagnóstico de recuperación y composición con costes. |
| Informe de peritaje | [31-informe-peritaje.md](specs/31-informe-peritaje.md) | Markdown con cifras comprobadas y advertencias diferenciadas. |
| Orquestación web | [34-orquestacion-web.md](https://github.com/lvckss/piia2-26/pull/60) | Recorrido foto → confirmación → informe; propuesta técnica en revisión. |
| Evaluación y trazabilidad | [evaluacion-trazabilidad.md](specs/evaluacion-trazabilidad.md) | Medidas reproducibles por componente y límites de la evaluación. |

Para seguir la cadena principal, leer visión → categoría → costes → RAG → informe → orquestación. Confianza y evaluación describen cómo se controlan las dudas y cómo se comprobarán los resultados.

### Arquitectura y decisiones (Entrega 2)

- [ARCHITECTURE.md](ARCHITECTURE.md): diagrama, componentes y flujo de punta a punta de la solución.
- [decisions/](decisions/): decisiones de implementación en el formato de la asignatura (copia de [docs/adr/](docs/adr/README.md), que conserva su historial de aceptación). Cada una recoge decisión, motivación, alternativas y referencias:
  - [ADR 0001: Categoría del vehículo estimada por visión en el contrato del Agente 1](decisions/0001-categoria-vehiculo-contrato-agente1.md)
  - [ADR 0002: Contrato JSON entre agentes, con todos los hallazgos y su nivel de confianza](decisions/0002-contrato-json-entre-agentes.md)
  - [ADR 0003: API de OpenAI con la clave de la empresa como proveedor de modelos](decisions/0003-proveedor-openai-clave-empresa.md)
  - [ADR 0004: Costes con la herramienta y los datos de la empresa, no con precios propios](decisions/0004-herramienta-costes-datos-empresa.md)
  - [ADR 0005: Filtro previo por clase de las detecciones que se envían al modelo de visión](decisions/0005-filtro-previo-detecciones-por-clase.md)
  - [ADR 0006: RAG con PostgreSQL, comparación de embeddings y estado de recuperación](decisions/0006-rag-postgresql-estado-recuperacion.md)

### Material de apoyo

- [Índice de documentación](docs/README.md): decisiones, guías anteriores y mapa de documentos reubicados.
- [Registro de ADRs](docs/adr/README.md): decisiones 0001–0006 aceptadas con su evidencia; el [ADR 0007](https://github.com/lvckss/piia2-26/pull/60) sigue Propuesto (PR #60).
- [Workflow](docs/workflow.md) y [template de Spec](docs/templates/spec-template.md): procedimientos internos, no funcionalidades adicionales.
- [Diseño previo multiagente](docs/piia2-arquitectura-multiagente.md), `docs/guias/` y `docs/historico/`: referencias de apoyo con sus decisiones y versiones históricas. Los contratos vigentes de esta entrega son los de `specs/`; una guía anterior no los sustituye.
- [Aplicación](app/README.md): backend, frontend, ML, contenedores y agentes adjuntos. Se conserva el código del corte original y no se presenta como una integración completa del flujo objetivo.
