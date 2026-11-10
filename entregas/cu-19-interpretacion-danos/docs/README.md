# Documentación de apoyo de CU-19

La puerta de entrada es el [README del proyecto](../README.md). Las
[specs funcionales](../specs/) contienen la definición presentada en la Entrega 1; la
[arquitectura](../ARCHITECTURE.md) y los [ADRs](../decisions/) son la Entrega 2. Este
directorio reúne sus decisiones y antecedentes.

- [Registro de ADRs](adr/README.md): 0001–0006 aceptados con sus revisiones;
  [0007 de orquestación](https://github.com/lvckss/piia2-26/pull/60), Propuesto (PR #60). [`decisions/`](../decisions/) es la
  copia de 0001–0006 en el formato de la asignatura.
- [Workflow](workflow.md), [template de Spec](templates/spec-template.md) y
  [template de ADR](adr/template.md): procedimientos del equipo.
- [Diseño previo multiagente](piia2-arquitectura-multiagente.md): contexto del
  reparto y de los contratos anteriores.
- Guías anteriores: [costes](guias/agente2-costes-cobertura-guia.md),
  [RAG](guias/agente2-rag-normativa-guia.md),
  [informe](guias/agente3-informe-guia.md) y
  [ADK](guias/integracion-adk-guia.md). Conservan ejemplos de versiones previas;
  la guía antigua del RAG usa ChromaDB, mientras la spec vigente usa PostgreSQL.
- Antecedentes: [validación de scores](historico/14-validar-scores-confianza.md),
  [registro de decisiones previas](historico/37-adrs-decisiones-previas.md) y
  [robustez de PIIA1](historico/mejora-robustez-tipos-vehiculo.md).

## Mapa de rutas de esta edición

| Ubicación anterior | Ubicación en la entrega |
|---|---|
| `docs/` en la raíz del fork | `docs/` dentro de la carpeta del caso |
| `specs/*-guia.md` | `docs/guias/` |
| `specs/piia2-arquitectura-multiagente.md` | `docs/piia2-arquitectura-multiagente.md` |
| Planes 14/37 y mejora histórica de PIIA1 en `specs/` | `docs/historico/` |

Se conservan numeración, IDs de AC, autores y revisiones de las versiones fuente.
Los enlaces fijados a commits históricos mantienen sus rutas de entonces. La
reorganización no acepta diseños nuevos ni elimina gates de implementación; los
metadatos de aceptación se refieren a las versiones citadas, no atribuyen una
aprobación nueva a esta edición documental de la entrega.

La definición funcional de la web está incluida como propuesta. Siguen pendientes
la revisión de #34/ADR 0007, el formato compartido de procedencia del vehículo y
su adaptación al informe. El proyecto no se declara listo para implementar esos
contratos por haberlos presentado en la asignatura.

Las rutas `docs/polizas_sinteticas/` y `docs/legal/` del paquete de Plexus no
pertenecen a esta carpeta y se mantienen sin cambios. Los documentos de workflow
que enlazan herramientas del fork usan versiones fijadas para que sigan siendo
consultables fuera de ese repositorio.
