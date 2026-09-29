# Agentes — PIIA2

Sistema multiagente que genera el informe de peritaje a partir de la salida
de detección de daños de PIIA-1 (`../ml/`).

Documentación completa del diseño y el contrato entre agentes:
[`../../specs/piia2-arquitectura-multiagente.md`](../../specs/piia2-arquitectura-multiagente.md).

```text
agentes/
  agente_multimodal/     # Agente 1 — interpreta detecciones + imagen (Lucía)
  agente_recuperacion/   # Agente 2 — RAG sobre BBDD vectorial (Víctor)
  agente_redactor/       # Agente 3 — redacta el informe final (Lucas)
```

Cada subcarpeta tiene su propio `README.md` con la guía paso a paso de esa
pieza.
