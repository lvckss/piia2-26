# Agentes — PIIA2

Sistema multiagente que genera el informe de peritaje (costes, cobertura e
indemnización) a partir de la salida de detección de daños de PIIA-1
(`../ml/`) y de los datos del siniestro.

Diseño completo, contrato entre agentes y decisiones tomadas con la empresa:
[`../../specs/piia2-arquitectura-multiagente.md`](../../specs/piia2-arquitectura-multiagente.md).

```text
agentes/
  agente_multimodal/     # Agente 1 — visión: ¿hay daño?, ¿qué pieza?, ¿qué severidad? (Lucía)
  agente_recuperacion/   # Agente 2 — costes (tool de la empresa), cobertura y RAG (Víctor)
  agente_redactor/       # Agente 3 — informe de peritaje en markdown (Lucas)
  ejemplos_contrato/     # JSON de ejemplo del contrato entre agentes, con cifras reales
```

Cada subcarpeta tiene su propio `README.md`, y las guías paso a paso de los
agentes 2 y 3 están en `../../specs/`.

## Paquete de datos de la empresa

La empresa entregó `piia2_paquete_datos.zip` (herramienta de costes, catálogo
de piezas y reglas, pólizas, legislación y preguntas de evaluación). Se
extrae en la raíz del repo como `piia2_paquete_datos/`. Está en
`.gitignore`: **cada miembro lo extrae en su copia, no se sube a git**.

## Reglas comunes

- La API Key de OpenAI va solo en la variable de entorno `OPENAI_API_KEY`;
  nunca en el repo ni en el chat. El id del modelo, en `OPENAI_MODEL`.
- Nadie hace commits directos en `main`: rama + PR que mergea el equipo.
- Cada agente se prueba aislado con `ejemplos_contrato/`, sin esperar a los
  otros dos.
