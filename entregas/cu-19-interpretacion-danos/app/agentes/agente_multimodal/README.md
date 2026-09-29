# Agente 1 — Analista de daños (multimodal)

Responsable: Lucía.

Lee las detecciones de PIIA-1 (`../../ml/`) y la imagen original, decide qué
hallazgos son fiables, y produce la lista de "findings" que consumen el
Agente 2 (`../agente_recuperacion/`) y el Agente 3 (`../agente_redactor/`).

Contrato de entrada/salida completo:
[`../../../specs/piia2-arquitectura-multiagente.md`](../../../specs/piia2-arquitectura-multiagente.md).
Diseño del filtro de confianza:
[`../../../specs/agente-confianza-hallazgos.md`](../../../specs/agente-confianza-hallazgos.md).
