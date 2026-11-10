# Agente 2 — Normativa: RAG sobre pólizas y legislación (guía para Lucas)

Esta guía es autónoma: léela entera (tú o tu Claude) antes de tocar código.
Antes, lee también `specs/piia2-arquitectura-multiagente.md`: ahí está el
sistema completo y el contrato JSON entre agentes. Tienes ejemplos reales en
`entregas/cu-19-interpretacion-danos/app/agentes/ejemplos_contrato/`.

## Tu trabajo en el proyecto

Tienes **dos piezas abiertas**, que son las que más incertidumbre técnica
tienen del proyecto:

1. **Integración con Google ADK** (`integracion-adk-guia.md`). Empieza por su
   *Paso 0* (una prueba mínima de si ADK funciona bien con un modelo de OpenAI):
   es corta y decide el plan de todo el sistema, así que conviene hacerla
   primero.
2. **Esta guía: el RAG de normativa** (la parte C del Agente 2), que es la
   BBDD vectorial que pide el enunciado de PIIA2.

Víctor hace los costes y la cobertura (`agente2-costes-cobertura-guia.md`) y el
informe (`agente3-informe-guia.md`). Entre su trabajo y el tuyo hay **un único
punto de contacto**: la función que tú escribes y él usa.

```text
buscar_normativa(pregunta: str, k: int = 4, poliza_id: str = "") -> list[dict]
# cada elemento: {"tema": ..., "extracto": ..., "fuente": ...}
```

Mantén exactamente esa firma. Víctor trabaja con `normativa: []` hasta que
exista, y su informe ya lo soporta.

## Qué cambió respecto a la primera versión de esta guía

La empresa nos dio un paquete de datos (`piia2_paquete_datos.zip`). Los precios
ya no se buscan en un RAG: la empresa entrega una herramienta de costes hecha.
El RAG pasa a ser de **pólizas y legislación**, para citar la fuente de cada
afirmación (cobertura, franquicia, pérdida total...), y se evalúa con las 25
preguntas que trae el paquete.

## Preparación

1. **Extrae el paquete** en la raíz del repo, de modo que exista
   `piia2-26/piia2_paquete_datos/` (con `data/`, `docs/`, `scripts/`...).
   Está en `.gitignore`: **no lo subas a git**. Lee su `README.md`.
2. **Mira los ejemplos** de `app/agentes/ejemplos_contrato/`: `agente2_salida.json`
   trae el campo `normativa` con la forma que tiene que devolver tu función.
3. **Python**: `pip install chromadb openai`.
4. **API Key**: la clave de OpenAI que dio la empresa va **solo** en la variable
   de entorno `OPENAI_API_KEY`. Nunca en un fichero del repo, nunca pegada en el
   chat. (Si el equipo decide otro modelo de embeddings, usad el que indique la
   empresa.)
5. **Git**: nadie hace commits directos en `main`. Crea una rama
   (`feat/agente2-rag`), sube la rama y abre un PR que mergeará el equipo. La
   skill `.agents/skills/semantic-commits-and-push` hace esto.

Trabaja en `entregas/cu-19-interpretacion-danos/app/agentes/agente_recuperacion/`
(ficheros `normativa_rag.py` y `evaluar_rag.py`; Víctor trabaja en el mismo
directorio pero en `costes_y_cobertura.py`, así que no os pisáis).

## El RAG sobre pólizas y legislación

Aquí construyes la **base de datos vectorial** del enunciado de PIIA2.

### Qué indexar

| Fuente | Cómo trocearlo | Metadatos |
|---|---|---|
| `docs/polizas_sinteticas/*.md` (4 pólizas) | Una sección por cada `## N. Título` (8 por póliza, ≤ 600 caracteres). | `tipo="poliza"`, `poliza_id` (el nombre del fichero sin `.md`), `seccion` |
| `docs/legal/*.txt` (7 textos reales) | Por artículo, y cortando los artículos largos en ventanas de 1.500 caracteres con 200 de solape. | `tipo="legal"`, `fuente` (nombre del fichero), `seccion` (p. ej. `Artículo dieciséis`) |

**Ojo: "trocear por artículo" no funciona tal cual**, ya lo comprobé con los
ficheros reales:

- La Ley 50/1980 (`BOE-A-1980-22501.txt`) escribe los artículos con letras
  (`Artículo dieciséis.`), no con cifras, y de ahí salen 3 de las 9 preguntas
  legales de evaluación. La expresión regular tiene que aceptar las dos formas.
- Sin tope, hay "artículos" de 76.000 y hasta 488.000 caracteres (los anexos y
  disposiciones finales cuelgan del último artículo). Por eso se cortan en
  ventanas.
- `BOE-A-2026-3803.txt` es una resolución corta y sin artículos: queda como
  2 fragmentos.

Con este troceado salen unos **1.500 fragmentos** (1.489 legales + 32 de
pólizas) y unos 400.000 tokens de texto: embeberlo cuesta céntimos.

```python
import re

MARCA_ARTICULO = re.compile(r"(?m)^(Art[íi]culo\s+[\wáéíóúüñ]+(?:\s+(?:bis|ter|quater))?)\b[.\s]")
MAX_CAR, SOLAPE = 1500, 200


def ventanas(texto, max_car=MAX_CAR, solape=SOLAPE):
    if len(texto) <= max_car:
        return [texto]
    salida, ini = [], 0
    while ini < len(texto):
        salida.append(texto[ini: ini + max_car])
        if ini + max_car >= len(texto):
            break
        ini += max_car - solape
    return salida


def trocear_legal(texto):
    """Devuelve [(seccion, fragmento), ...]."""
    marcas = list(MARCA_ARTICULO.finditer(texto))
    trozos = []
    if marcas and texto[: marcas[0].start()].strip():
        trozos.append(("preambulo", texto[: marcas[0].start()].strip()))
    for i, m in enumerate(marcas):
        fin = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        trozos.append((m.group(1).strip(), texto[m.start(): fin].strip()))
    if not marcas:
        trozos.append(("documento", texto.strip()))
    return [(sec, v) for sec, cuerpo in trozos for v in ventanas(cuerpo)]


def trocear_poliza(texto):
    """Devuelve [(seccion, fragmento), ...] con una sección '## N. Título' por fragmento."""
    partes = re.split(r"(?m)^## ", texto)
    return [(p.splitlines()[0].strip(), "## " + p.strip()) for p in partes[1:]]
```

(Los ficheros legales están en UTF-8: ábrelos con `encoding="utf-8"`.)

### Indexar con embeddings y ChromaDB

Un *embedding* convierte un texto en un vector de números; textos de
significado parecido quedan cerca. ChromaDB guarda los vectores y busca los
más cercanos a una pregunta. La base se guarda en disco en
`agente_recuperacion/chroma_db/` (carpeta generada, está en `.gitignore`: se
regenera ejecutando el script de indexado).

Esqueleto de `normativa_rag.py` (los nombres de las funciones de las
librerías son los habituales, pero **compruébalos en la documentación de la
versión que instales**; el modelo de embeddings es un ejemplo, usa el que
indique la empresa):

```python
import os
from pathlib import Path

import chromadb
from openai import OpenAI

DOCS = Path(__file__).resolve().parents[5] / "piia2_paquete_datos" / "docs"
CHROMA_DIR = Path(__file__).resolve().parent / "chroma_db"
MODELO_EMBEDDINGS = os.environ.get("OPENAI_EMBEDDINGS_MODEL", "text-embedding-3-small")

# lee OPENAI_API_KEY del entorno. La cabecera evita un fallo conocido con brotli
# en algunos Anaconda (ver app/agentes/README.md, "Problemas conocidos")
cliente = OpenAI(default_headers={"Accept-Encoding": "gzip, deflate"})


def embeber(textos, lote=100):
    vectores = []
    for i in range(0, len(textos), lote):
        r = cliente.embeddings.create(model=MODELO_EMBEDDINGS, input=textos[i: i + lote])
        vectores.extend(d.embedding for d in r.data)
    return vectores


def coleccion():
    bd = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return bd.get_or_create_collection("normativa", metadata={"hnsw:space": "cosine"})


def indexar():
    ids, textos, metadatos = [], [], []
    for f in sorted((DOCS / "polizas_sinteticas").glob("*.md")):
        for n, (seccion, texto) in enumerate(trocear_poliza(f.read_text(encoding="utf-8"))):
            ids.append(f"{f.stem}-{n}")
            textos.append(texto)
            metadatos.append({"tipo": "poliza", "poliza_id": f.stem, "seccion": seccion,
                              "fuente": f"docs/polizas_sinteticas/{f.name}"})
    for f in sorted((DOCS / "legal").glob("*.txt")):
        for n, (seccion, texto) in enumerate(trocear_legal(f.read_text(encoding="utf-8"))):
            ids.append(f"{f.stem}-{n}")
            textos.append(texto)
            metadatos.append({"tipo": "legal", "poliza_id": "", "seccion": seccion,
                              "fuente": f"docs/legal/{f.name}"})
    col = coleccion()
    for i in range(0, len(ids), 500):
        sl = slice(i, i + 500)
        col.add(ids=ids[sl], documents=textos[sl], metadatas=metadatos[sl],
                embeddings=embeber(textos[sl]))
    print(f"{len(ids)} fragmentos indexados")


def buscar_normativa(pregunta, k=4, poliza_id=""):
    """Los k fragmentos más cercanos a la pregunta. Si se da poliza_id, solo
    se consideran esa póliza y la legislación."""
    filtro = {"$or": [{"poliza_id": poliza_id}, {"tipo": "legal"}]} if poliza_id else None
    r = coleccion().query(query_embeddings=embeber([pregunta]), n_results=k, where=filtro)
    return [{"tema": pregunta, "extracto": doc, "fuente": f"{m['fuente']}#{m['seccion']}"}
            for doc, m in zip(r["documents"][0], r["metadatas"][0])]
```

Cada resultado de `buscar_normativa` tiene la forma de un elemento de
`normativa` del contrato (`tema`, `extracto`, `fuente`).

### Evaluarlo con las 25 preguntas de la empresa

`data/preguntas_evaluacion.csv` tiene `tipo`, `pregunta`, `respuesta_esperada`
y `fuente` (16 de pólizas, 9 legales). Escribe `evaluar_rag.py`:

1. Para cada pregunta, llama a `buscar_normativa(pregunta, k=4)`.
2. **hit@4** = la `fuente` esperada aparece entre las 4 fuentes recuperadas.
3. Imprime el hit@4 total y por tipo (`poliza`/`legal`), y lista las preguntas
   que fallan.

Es normal que las preguntas de póliza fallen al principio: las 4 pólizas son
casi iguales y la pregunta nombra la póliza ("Todo Riesgo con franquicia 300
EUR"). Pistas para mejorar: pasar `poliza_id` (filtro), añadir el nombre de la
póliza al texto del fragmento, probar otro `k`, otro tamaño de ventana.
**Objetivo razonable: hit@4 ≥ 80 %**. Apunta qué cambió cada mejora: eso es lo
que se cuenta en la defensa.

Opcional, si sobra tiempo: pasar al LLM la pregunta y los fragmentos
recuperados y comparar su respuesta con `respuesta_esperada`.

## Entregable

1. `normativa_rag.py` con `indexar()` y `buscar_normativa(...)` (firma de arriba).
2. `evaluar_rag.py` con el hit@4 de las 25 preguntas y qué mejoró cada cambio.
3. Una función `agente2()` que junta tu parte con la de Víctor. Hasta que él
   termine, pruébala con la salida de ejemplo:

```python
from costes_y_cobertura import estimar_siniestro   # lo escribe Víctor
from normativa_rag import buscar_normativa


def agente2(salida_agente1, contexto):
    resultado = estimar_siniestro(salida_agente1, contexto)
    pid = contexto["poliza_id"]
    resultado["normativa"] = (
        buscar_normativa("cobertura de daños propios por colisión", poliza_id=pid, k=2)
        + buscar_normativa("pérdida total e indemnización", poliza_id=pid, k=2)
    )
    return resultado
```

Con `rol: tercero_perjudicado` no hay `poliza_id`: en ese caso usa solo
legislación (`poliza_id=""`).

## Qué NO tienes que hacer

- No hagas los costes ni la cobertura: es la guía de Víctor.
- No toques la detección de PIIA-1 ni el Agente 1 de Lucía.
- No subas a git el paquete de la empresa, la base `chroma_db/` ni la clave.

## Definición de terminado

- [ ] Índice vectorial creado (~1.500 fragmentos) y `buscar_normativa` funciona.
- [ ] `evaluar_rag.py` da el hit@4 de las 25 preguntas, anotando qué mejoró.
- [ ] `agente2()` devuelve el JSON completo del contrato.
- [ ] Todo en una rama con su PR; nada de claves ni datos de la empresa en git.

Después, sigue con `integracion-adk-guia.md` (Paso 1 en adelante).
