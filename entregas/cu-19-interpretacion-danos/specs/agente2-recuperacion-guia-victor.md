# Guía paso a paso — Agente 2: Recuperación (RAG) [Víctor]

Lee primero [`piia2-arquitectura-multiagente.md`](piia2-arquitectura-multiagente.md)
para el contexto completo. Este documento es el detalle de tu pieza.

**Si abres Claude Code para esto:** pégale este archivo entero al principio
de la conversación y pídele que te ayude a implementarlo paso a paso. Tiene
todo el contexto que necesita para entender qué construir sin que se lo
tengas que explicar tú desde cero.

## Tu misión en una frase

Dado un hallazgo de daño (lo que produce el Agente 1 de Lucía), buscar en una
base de datos vectorial el procedimiento de reparación y el precio que le
corresponde, y devolverlo en el formato que espera el Agente 3 de Lucas.

## Lo que recibes (input)

Un JSON como este, uno por cada hallazgo (no hace falta esperar a que Lucía
termine el Agente 1 de verdad — puedes inventarte varios de estos a mano para
probar tu parte por separado):

```json
{
  "finding_id": "123-1",
  "category": "lamp_broken",
  "score": 0.94,
  "confidence_tier": "confirmed",
  "vision_description": "Faro delantero derecho roto, cristal fragmentado visible."
}
```

## Lo que tienes que devolver (output)

```json
{
  "finding_id": "123-1",
  "repair_procedure": "Sustitución completa del conjunto óptico delantero derecho.",
  "estimated_price_eur": 180.0,
  "source_doc": "procedimientos_faros.md#faro-roto"
}
```

## Paso a paso

### 1. Crea los datos: tabla de precios + procedimientos

Esto es lo primero, antes de tocar código. Necesitas dos cosas (pueden ser
ficheros de texto/markdown/csv, no hace falta nada sofisticado):

- **Tabla de precios sintética.** Un CSV o JSON con una fila por combinación
  categoría de daño + parte del vehículo + precio estimado en euros. Ejemplo:

  ```csv
  categoria,parte,precio_eur
  lamp_broken,faro_delantero,180
  lamp_broken,faro_trasero,140
  glass_shatter,parabrisas,320
  glass_shatter,ventanilla,150
  tire_flat,neumatico,90
  dent,puerta,250
  scratch,puerta,90
  crack,parabrisas,280
  ```

  Hacen falta las 6 categorías de daño (`lamp_broken`, `glass_shatter`,
  `tire_flat`, `dent`, `scratch`, `crack`) — ninguna se excluye del informe,
  ver `agente-confianza-hallazgos.md`. `dent`/`scratch`/`crack` simplemente
  llegan con más frecuencia como `needs_review` en vez de `confirmed`, pero
  cuando sí llegan, el Agente 2 necesita poder recuperar su procedimiento y
  precio igual que para las otras 3.

- **Procedimientos de reparación.** Un documento de texto por categoría (o
  uno solo con varias secciones), describiendo en 2-4 frases cómo se repara
  cada tipo de daño. No hace falta que sea real/preciso — sintético vale,
  pero que suene coherente. Ejemplo (`procedimientos_faros.md`):

  ```markdown
  ## faro-roto
  Sustitución completa del conjunto óptico. Se retira el paragolpes si es
  necesario para acceder al anclaje, se desconecta el cableado, se instala
  el faro nuevo y se recalibra la orientación del haz de luz.
  ```

Guarda estos ficheros donde tenga sentido en el repo, por ejemplo
`entregas/cu-19-interpretacion-danos/app/agentes/agente_recuperacion/data/`.

### 2. Monta la base vectorial

No hace falta un servidor aparte — en Colab, la opción más simple es
**FAISS** o **ChromaDB**, ambas corren en memoria/local:

```bash
pip install chromadb
```

```python
import chromadb

client = chromadb.Client()
collection = client.create_collection("procedimientos_reparacion")

# cada "documento" es un trozo de texto de tus procedimientos
collection.add(
    documents=[
        "Sustitución completa del conjunto óptico delantero. Se retira...",
        "Sustitución del cristal del parabrisas completo...",
        # ...
    ],
    metadatas=[
        {"categoria": "lamp_broken", "parte": "faro_delantero"},
        {"categoria": "glass_shatter", "parte": "parabrisas"},
    ],
    ids=["lamp_broken_faro_delantero", "glass_shatter_parabrisas"],
)
```

Chroma genera los embeddings automáticamente con un modelo por defecto (no
necesitas la API Key para este paso si no quieres). Si prefieres usar
embeddings de la API (más calidad), consulta la skill `claude-api` para
saber cómo pedirlos.

### 3. Implementa la búsqueda

```python
def buscar_procedimiento(finding: dict) -> dict:
    query = f"{finding['category']} {finding.get('vision_description', '')}"
    resultados = collection.query(query_texts=[query], n_results=1)

    documento = resultados["documents"][0][0]
    metadata = resultados["metadatas"][0][0]

    precio = buscar_precio(metadata["categoria"], metadata["parte"])  # tu tabla de precios

    return {
        "finding_id": finding["finding_id"],
        "repair_procedure": documento,
        "estimated_price_eur": precio,
        "source_doc": f"{metadata['categoria']}.md#{metadata['parte']}",
    }
```

`buscar_precio` es una función tuya que lee el CSV/JSON de precios del paso 1
y devuelve el precio para esa categoría+parte (o un precio por defecto de esa
categoría si no hay parte exacta).

### 4. Prueba tu pieza de forma aislada

No necesitas el Agente 1 real para probar esto — usa 3-4 hallazgos de
ejemplo escritos a mano (copiando el formato de "Lo que recibes" de arriba)
y comprueba que `buscar_procedimiento` te devuelve algo razonable para cada
uno.

## Qué NO tienes que hacer

- No tienes que tocar el código de detección de PIIA-1 (`ml/StrategyPipeline/`).
- No tienes que esperar a que Lucía o Lucas terminen sus partes.
- No hace falta un vector store en la nube — todo esto corre local en Colab.

## Definición de terminado

- [ ] Tabla de precios y procedimientos creados para las 6 clases de daño.
- [ ] Base vectorial montada y consultable.
- [ ] `buscar_procedimiento(finding)` devuelve el JSON de salida correcto
      para al menos un ejemplo de cada una de las 6 clases.
- [ ] Probado de forma aislada, sin depender del código de Lucía ni de Lucas.
