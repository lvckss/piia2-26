# Agentes — PIIA2

Sistema multiagente que genera el informe de peritaje (costes, cobertura e
indemnización) a partir de la salida de detección de daños de PIIA-1
(`../ml/`) y de los datos del siniestro.

Diseño completo, contrato entre agentes y decisiones tomadas con la empresa:
[`../../specs/piia2-arquitectura-multiagente.md`](../../specs/piia2-arquitectura-multiagente.md).

```text
agentes/
  agente_multimodal/     # Agente 1 — visión: ¿hay daño?, ¿qué pieza?, ¿qué severidad? (Lucía)
  agente_recuperacion/   # Agente 2 — costes y cobertura (Víctor) + RAG de normativa (Lucas)
  agente_redactor/       # Agente 3 — informe de peritaje en markdown (Víctor)
  orquestador/           # (por crear) integración de los tres agentes con Google ADK (Lucas)
  ejemplos_contrato/     # JSON de ejemplo del contrato entre agentes, con cifras reales
```

Cada subcarpeta tiene su propio `README.md`. Las guías paso a paso están en
`../../specs/` y organizadas por contenido (no por persona):
`agente2-costes-cobertura-guia.md`, `agente2-rag-normativa-guia.md`,
`agente3-informe-guia.md` e `integracion-adk-guia.md`. El reparto y el plan por
hitos, en `piia2-arquitectura-multiagente.md`.

## Paquete de datos de la empresa

La empresa entregó `piia2_paquete_datos.zip` (herramienta de costes, catálogo
de piezas y reglas, pólizas, legislación y preguntas de evaluación). Se
extrae en la raíz del repo como `piia2_paquete_datos/`. Está en
`.gitignore`: **cada miembro lo extrae en su copia, no se sube a git**.

## Problemas conocidos

**`TypeError: Decompressor.decompress() got an unexpected keyword argument
'output_buffer_limit'`** al llamar a la API de OpenAI. No es de la clave ni de
nuestro código: en algunas instalaciones de Anaconda el paquete `brotli` es en
realidad `brotlipy` (antiguo), que no entiende lo que le pide la librería HTTP
del SDK de OpenAI al leer respuestas comprimidas con `br`. Soluciones, de
menos a más invasiva:

1. **Crear el cliente sin pedir brotli** (lo hace ya `crear_cliente_openai()` en
   `agente_multimodal/agente1.py`; usadlo, o en vuestro propio código):
   `OpenAI(default_headers={"Accept-Encoding": "gzip, deflate"})`.
2. Usar un entorno virtual limpio (`python -m venv .venv`) en vez del Anaconda base.
3. Actualizar la librería de brotli: `pip install -U brotlicffi`.

## Reglas comunes

- La API Key de OpenAI va solo en la variable de entorno `OPENAI_API_KEY`;
  nunca en el repo ni en el chat. El id del modelo, en `OPENAI_MODEL`.
- Nadie hace commits directos en `main`: rama + PR que mergea el equipo.
- Cada agente se prueba aislado con `ejemplos_contrato/`, sin esperar a los
  otros dos.
