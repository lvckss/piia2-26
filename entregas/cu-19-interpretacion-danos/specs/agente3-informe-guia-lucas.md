# Guía paso a paso — Agente 3: Redactor del informe [Lucas]

Lee primero [`piia2-arquitectura-multiagente.md`](piia2-arquitectura-multiagente.md)
para el contexto completo. Este documento es el detalle de tu pieza.

**Si abres Claude Code para esto:** pégale este archivo entero al principio
de la conversación y pídele que te ayude a implementarlo paso a paso. Tiene
todo el contexto que necesita para entender qué construir sin que se lo
tengas que explicar tú desde cero.

## Tu misión en una frase

Juntar los hallazgos de daño (Agente 1, Lucía) y los procedimientos/precios
recuperados (Agente 2, Víctor) en un informe de peritaje final, legible y
bien estructurado.

## Mientras no estás disponible (esta semana): tarea sin depender de nadie

No hace falta esperar a que Lucía y Víctor terminen para empezar. Puedes
adelantar esto sin tocar código:

1. **Busca 2-3 ejemplos reales de informes de peritaje de daños de vehículo**
   (búscalos en Google, aseguradoras suelen publicar ejemplos o plantillas).
   Fíjate en: qué secciones tienen, cómo describen cada daño, cómo presentan
   el coste total, qué tono usan.
2. **Diseña la plantilla de tu informe** en un documento aparte (markdown o
   Word, lo que prefieras): qué secciones va a tener el vuestro, en qué
   orden, qué campos por cada hallazgo. Esto luego se convierte directamente
   en el prompt/plantilla que usará el Agente 3 para generar el texto.

Cuando te incorpores, ya tienes medio camino andado del diseño sin haber
escrito una línea de código que dependiera de los otros dos.

## Lo que recibes (input)

Dos listas, unidas por `finding_id` — puedes escribirte varios ejemplos a
mano para probar tu parte sin esperar a nadie:

Del Agente 1 (Lucía):
```json
{
  "image_id": 123,
  "vehicle_type": "sedan",
  "findings": [
    {
      "finding_id": "123-1",
      "category": "lamp_broken",
      "score": 0.94,
      "confidence_tier": "confirmed",
      "vision_description": "Faro delantero derecho roto, cristal fragmentado visible.",
      "crop_image_path": "crops/123_lamp_broken_1.jpg"
    }
  ]
}
```

Del Agente 2 (Víctor), uno por cada `finding_id`:
```json
{
  "finding_id": "123-1",
  "repair_procedure": "Sustitución completa del conjunto óptico delantero derecho.",
  "estimated_price_eur": 180.0,
  "source_doc": "procedimientos_faros.md#faro-roto"
}
```

## Lo que tienes que producir (output)

Un informe agregado — markdown como mínimo (PDF si da tiempo, con alguna
librería tipo `weasyprint` o exportando el markdown). Debe incluir, como
mínimo:

- Cabecera: vehículo, fecha, resumen de cuántos daños se encontraron.
- Una sección por hallazgo: descripción, categoría, procedimiento de
  reparación, precio.
- **Los hallazgos `confirmed` y `needs_review` deben distinguirse
  visiblemente** — no los mezcles con la misma redacción (por ejemplo, los
  `needs_review` en una sección aparte con una nota de "pendiente de
  verificación").
- Coste total, calculado **dos veces**: solo con `confirmed`, y con todos —
  así quien lo lea sabe cuánto de la estimación es firme.

## Paso a paso (cuando te incorpores)

### 1. Define la plantilla como prompt

Con lo que investigaste en el paso "mientras no estás disponible", conviértelo
en una plantilla de prompt para un LLM (usando la API Key del caso). Algo así:

```python
PROMPT_TEMPLATE = """
Eres un perito de seguros redactando un informe de daños de vehículo.

Vehículo: {vehicle_type}

Daños confirmados:
{hallazgos_confirmados}

Daños pendientes de revisión (menciónalos aparte, sin darlos por seguros):
{hallazgos_pendientes}

Coste total confirmado: {coste_confirmado}€
Coste total estimado (incluyendo pendientes): {coste_total}€

Redacta un informe de peritaje profesional y claro con esta información.
"""
```

### 2. Implementa la función de agregación

```python
def generar_informe(findings: list[dict], procedimientos: list[dict], vehicle_type: str) -> str:
    procedimientos_por_id = {p["finding_id"]: p for p in procedimientos}

    confirmados = [f for f in findings if f["confidence_tier"] == "confirmed"]
    pendientes = [f for f in findings if f["confidence_tier"] == "needs_review"]

    coste_confirmado = sum(
        procedimientos_por_id[f["finding_id"]]["estimated_price_eur"]
        for f in confirmados
    )
    coste_total = coste_confirmado + sum(
        procedimientos_por_id[f["finding_id"]]["estimated_price_eur"]
        for f in pendientes
    )

    prompt = PROMPT_TEMPLATE.format(
        vehicle_type=vehicle_type,
        hallazgos_confirmados=_formatear(confirmados, procedimientos_por_id),
        hallazgos_pendientes=_formatear(pendientes, procedimientos_por_id),
        coste_confirmado=coste_confirmado,
        coste_total=coste_total,
    )

    # llamada al LLM con la API Key del caso — ver skill claude-api del repo
    return llamar_llm(prompt)
```

`_formatear` es una función tuya que convierte una lista de hallazgos +
sus procedimientos en texto legible para meter en el prompt.

### 3. Prueba con datos de ejemplo

Igual que Víctor: no necesitas que Lucía/Víctor hayan terminado. Escribe 3-4
hallazgos + sus procedimientos a mano (copiando el formato de arriba) y
genera un informe de prueba.

## Qué NO tienes que hacer

- No tienes que decidir tú los precios ni los procedimientos (eso es de
  Víctor) — solo consumir lo que te llega en el formato de arriba.
- No tienes que tocar el código de detección de PIIA-1.
- No hace falta esperar a los otros dos para empezar a diseñar/probar tu
  parte con datos inventados.

## Definición de terminado

- [ ] Plantilla de informe diseñada (basada en ejemplos reales investigados).
- [ ] `generar_informe(...)` produce un informe con secciones separadas para
      `confirmed`/`needs_review` y los dos cálculos de coste total.
- [ ] Probado de forma aislada con datos de ejemplo, sin depender del código
      real de Lucía ni de Víctor.
