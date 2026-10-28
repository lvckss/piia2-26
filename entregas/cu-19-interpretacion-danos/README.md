# CU-19 — Interpretación de daños en vehículos

## Qué es el proyecto

Este proyecto continúa el trabajo de PIIA1, donde se desarrolló un pipeline de segmentación de daños en vehículos basado en SAM3 y evaluado sobre CarDD. En PIIA2 se construye encima de esa salida un **sistema multiagente multimodal que imita el comportamiento de un perito de seguros**: a partir de la foto de un vehículo dañado y de los datos del siniestro, interpreta los daños, estima su reparación y la cobertura de la póliza, y redacta un informe de peritaje.

El punto de partida son los **resultados de detección de PIIA1 ya guardados**: se generaron una sola vez para 500 imágenes de CarDD (particiones `val` y `test`) y PIIA2 los consume como entrada. **No se ejecuta SAM3 en línea.**

El sistema se organiza en tres agentes, coordinados por una orquestación:

1. **Agente 1 — Analista de daños (multimodal).** Mira la foto, no solo el JSON de detecciones: da una segunda opinión con un modelo de visión sobre cada detección (¿hay un daño de verdad?), identifica la pieza afectada y su severidad y asigna a cada hallazgo un nivel de confianza (`confirmed` o `needs_review`). Está en planificación que además estime la categoría del vehículo cuando no se dispone del coche, para el recorrido web ([Issue #28](https://github.com/lvckss/piia2-26/issues/28), retomada el 2026-10-27); hasta que se acepte e implemente, el vehículo es un dato de entrada obligatorio del siniestro.
2. **Agente 2 — Costes, cobertura y normativa.** Calcula el coste de reparación con la herramienta de costes que entregó la empresa, determina la pérdida total, la cobertura de la póliza y una indemnización estimada, y recupera de una base de datos vectorial los fragmentos de pólizas y legislación que justifican la cobertura y la pérdida total, cuando los hay.
3. **Agente 3 — Redactor.** Genera el informe de peritaje agregado en markdown. Las cifras las calcula el código, y una comprobación automática verifica que todas las cifras en euros del informe coinciden con las del Agente 2.

El resultado se orienta a asistir a peritos o tramitadores de siniestros de una aseguradora durante la inspección, no a sustituir su criterio profesional.

## Motivación

La inspección manual de imágenes de vehículos requiere tiempo y puede variar entre personas. Un detector de daños por sí solo tampoco basta para un peritaje: con las detecciones de PIIA1 a score ≥ 0,3, la precisión es inferior al 15 % en todas las clases de CarDD (medido sobre las 500 imágenes exportadas; ver [`specs/agente-confianza-hallazgos.md`](specs/agente-confianza-hallazgos.md)), de modo que tratar cada detección como un hecho produciría informes con daños y costes falsos presentados con autoridad.

El proyecto busca estudiar hasta qué punto un sistema de agentes puede convertir esas detecciones, con muchos falsos positivos, en un informe consistente, trazable y con cifras comprobables, dejando claro qué parte del resultado es firme y cuál requiere revisión. Al finalizar se pretende disponer de una ejecución reproducible de punta a punta, de la foto y los datos del siniestro al informe, y de una evaluación que muestre los aciertos, los errores y las limitaciones de cada pieza.

## Alcance

El proyecto incluye:

- la **entrada**: los resultados de detección de PIIA1 ya guardados para 500 imágenes de CarDD y los datos del siniestro (taller, póliza y demás parámetros que necesita la herramienta de costes), descritos en [`specs/interpretacion-danos-imagen.md`](specs/interpretacion-danos-imagen.md) y en [`specs/piia2-arquitectura-multiagente.md`](specs/piia2-arquitectura-multiagente.md);
- el **Agente 1**: segunda opinión de visión, pieza, severidad y veredicto de cada hallazgo ([`specs/interpretacion-danos-imagen.md`](specs/interpretacion-danos-imagen.md)), niveles de confianza y filtro previo de detecciones ([`specs/agente-confianza-hallazgos.md`](specs/agente-confianza-hallazgos.md)); la categoría del vehículo cuando no se dispone del coche, en planificación para el recorrido web ([Issue #28](https://github.com/lvckss/piia2-26/issues/28)); mientras no se acepte e implemente, el `vehiculo_id` es un dato de entrada obligatorio;
- el **Agente 2**: costes, pérdida total, cobertura e indemnización orientativas ([`specs/30-costes-cobertura.md`](specs/30-costes-cobertura.md)) y recuperación de pólizas y legislación desde una base de datos vectorial ([Issue #32](https://github.com/lvckss/piia2-26/issues/32));
- el **Agente 3**: informe de peritaje en markdown con cifras comprobadas ([`specs/31-informe-peritaje.md`](specs/31-informe-peritaje.md));
- la **orquestación** de los tres agentes de punta a punta ([Issue #33](https://github.com/lvckss/piia2-26/issues/33), prueba de viabilidad de Google ADK, e [Issue #34](https://github.com/lvckss/piia2-26/issues/34));
- la **evaluación** de cada pieza con datos etiquetados o sintéticos, y el registro de la configuración y la procedencia de los resultados ([`specs/evaluacion-trazabilidad.md`](specs/evaluacion-trazabilidad.md)).

Los **procedimientos de reparación** salen de las reglas de la herramienta de costes de la empresa (clase de daño, zona y severidad determinan la acción de reparación); la base de datos vectorial recupera **pólizas y legislación**.

Las capacidades enlazadas a una Issue (la recuperación de pólizas y legislación y la orquestación) tienen su especificación en elaboración: se publicarán en `specs/` conforme se integren.

Quedan fuera del alcance:

- una tasación económica vinculante;
- la aprobación o rechazo automático de reparaciones o indemnizaciones;
- la identificación de propietarios, matrículas o personas;
- ejecutar SAM3 en línea o mejorar la detección de PIIA1;
- una interfaz de usuario, una API o la visualización de resultados sobre la imagen (el código de PIIA1 que lo hacía se conserva en `app/`, sin ampliarse);
- el informe en PDF: el informe se genera en markdown;
- una aplicación preparada para uso comercial sin supervisión humana;
- garantizar resultados fiables en imágenes o tipos de daño no representados en los datos de evaluación.

Los precios, los tiempos de reparación, los vehículos y las pólizas son **datos sintéticos** entregados por la empresa; solo la legislación es real. Por eso todas las cifras económicas y de cobertura son **orientativas y no vinculantes**.

## Equipo

| Integrante | Rol inicial | Contacto |
|---|---|---|
| Lucía Luis Castaño | Desarrollo e investigación de IA | lucia.luis.castano@rai.usc.gal |
| Víctor Hidalgo Carreira | Desarrollo e investigación de IA | victor.hidalgo@rai.usc.gal |
| Lucas García Ruiz | Desarrollo e investigación de IA | lucas.garcia0@rai.usc.es |

Los roles son iniciales y podrán concretarse conforme se repartan las
responsabilidades de producto, datos, modelos e integración.

## Estructura

```text
cu-19-interpretacion-danos/
├── README.md
├── TAREAS.md
├── specs/
└── app/
    ├── agentes/
    ├── ml/
    ├── server/
    ├── frontend/
    ├── bd/
    ├── docker/
    ├── docs/
    └── notes/
```

- `README.md`: presenta el problema, la motivación, el alcance y el equipo.
- `TAREAS.md`: checklist histórico de la mejora de robustez del pipeline de detección de PIIA1.
- `specs/`: especificaciones, arquitectura y guías del proyecto (tabla más abajo).
- `app/`: código del proyecto. Su propio [README](app/README.md) explica cómo se ejecuta cada parte.
  - `app/agentes/`: **PIIA2**. [`agente_multimodal/`](app/agentes/agente_multimodal/) contiene el Agente 1 con sus pruebas; [`agente_recuperacion/`](app/agentes/agente_recuperacion/) y [`agente_redactor/`](app/agentes/agente_redactor/) son las carpetas de los Agentes 2 y 3 (por ahora, su README con el plan); [`ejemplos_contrato/`](app/agentes/ejemplos_contrato/) reúne JSON de ejemplo del contrato entre agentes. Su [README](app/agentes/README.md) describe el conjunto.
  - `app/ml/`, `app/server/`, `app/frontend/`, `app/bd/`, `app/docker/`, `app/docs/` y `app/notes/`: código, datos y documentación **heredados de PIIA1** (pipeline de detección y evaluador, API de inferencia, API y cliente web, esquema de datos, contenedor de la API de ML, documentación técnica y notas de diseño). No se amplían en PIIA2. Los archivos de configuración y de entorno de PIIA1 están en la raíz de `app/`.

### Contenido de `specs/`

| Archivo | Tipo | Contenido |
|---|---|---|
| [`interpretacion-danos-imagen.md`](specs/interpretacion-danos-imagen.md) | Spec funcional | Agente 1: de las detecciones guardadas y la foto a los hallazgos con pieza, severidad y veredicto. |
| [`agente-confianza-hallazgos.md`](specs/agente-confianza-hallazgos.md) | Spec funcional | Niveles de confianza (`confirmed`, `needs_review`), filtro previo de detecciones y su medición. |
| [`evaluacion-trazabilidad.md`](specs/evaluacion-trazabilidad.md) | Spec funcional | Evaluación y trazabilidad de los resultados. |
| [`30-costes-cobertura.md`](specs/30-costes-cobertura.md) | Spec funcional | Agente 2: de los hallazgos y los datos del siniestro a costes, pérdida total, cobertura e indemnización orientativas. |
| [`31-informe-peritaje.md`](specs/31-informe-peritaje.md) | Spec funcional | Agente 3: del resultado de los Agentes 1 y 2 al informe de peritaje en markdown, con las cifras comprobadas. |
| [`piia2-arquitectura-multiagente.md`](specs/piia2-arquitectura-multiagente.md) | Arquitectura | Diseño del sistema, contrato JSON entre agentes, decisiones tomadas con la empresa y plan. |
| [`agente2-costes-cobertura-guia.md`](specs/agente2-costes-cobertura-guia.md), [`agente2-rag-normativa-guia.md`](specs/agente2-rag-normativa-guia.md), [`agente3-informe-guia.md`](specs/agente3-informe-guia.md), [`integracion-adk-guia.md`](specs/integracion-adk-guia.md) | Guías | Guías de implementación de cada pieza, con código de referencia probado. |
| [`mejora-robustez-tipos-vehiculo.md`](specs/mejora-robustez-tipos-vehiculo.md) | Spec histórica | Mejora de robustez del detector de PIIA1; la parte de `vehicle_type` se implementó y se revirtió, y así consta en el documento. |
| [`14-validar-scores-confianza.md`](specs/14-validar-scores-confianza.md) | Plan de la [Issue #14](https://github.com/lvckss/piia2-26/issues/14) | Validación del rango del score antes de clasificar un hallazgo; su implementación se retiró y la tarea está pendiente de rehacerse. |
| [`37-adrs-decisiones-previas.md`](specs/37-adrs-decisiones-previas.md) | Plan de la [Issue #37](https://github.com/lvckss/piia2-26/issues/37) | Registro como ADRs de las decisiones estructurales previas del sistema: contrato entre agentes, proveedor de modelos, herramienta de costes y filtro previo de detecciones. |
