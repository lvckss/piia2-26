# Agente 2 — Costes, cobertura y normativa (guía para Víctor)

Esta guía es autónoma: léela entera (tú o tu Claude) antes de tocar código.
Antes, lee también `specs/piia2-arquitectura-multiagente.md`: ahí está el
sistema completo y el contrato JSON entre agentes. No necesitas el código de
Lucía ni el de Lucas para trabajar: tienes ejemplos reales en
`entregas/cu-19-interpretacion-danos/app/agentes/ejemplos_contrato/`.

## Qué cambió respecto a la primera versión de esta guía

La empresa nos dio un paquete de datos (`piia2_paquete_datos.zip`) y eso
**cambia tu trabajo**. Ya **no** hay que inventar una tabla de precios ni
procedimientos de reparación ni usar un RAG para los precios: la empresa
entrega una herramienta de costes hecha (`estimar_coste`). Tu agente pasa a
tener **tres piezas**:

| Pieza | Qué hace | Dificultad |
|---|---|---|
| **A. Costes** | Convierte los hallazgos del Agente 1 en dos presupuestos (solo confirmados / con pendientes) llamando a la tool de la empresa. | Baja (código de referencia abajo) |
| **B. Cobertura** | Pérdida total, cobertura de la póliza e indemnización estimada. | Media (código de referencia abajo) |
| **C. Normativa (RAG)** | Búsqueda vectorial sobre pólizas y legislación para citar la fuente de cada afirmación. | La parte principal y más vistosa: la BBDD vectorial que pide el enunciado |

## Preparación

1. **Extrae el paquete** en la raíz del repo, de modo que exista
   `piia2-26/piia2_paquete_datos/` (con `data/`, `docs/`, `scripts/`...).
   Está en `.gitignore`: **no lo subas a git**. Lee su `README.md` (5 min).
2. **Mira los ejemplos** de `app/agentes/ejemplos_contrato/`:
   - `agente1_salida.json`: lo que recibes del Agente 1.
   - `contexto_siniestro.json`: datos del coche/taller/póliza (entrada).
   - `agente2_salida.json`: **lo que tienes que producir**. Sus cifras están
     calculadas con la tool real: tu salida debe coincidir.
3. **Python**: la tool y las piezas A y B solo usan la librería estándar. La
   pieza C necesita `pip install chromadb openai`.
4. **API Key**: la clave de OpenAI que dio la empresa va **solo** en la
   variable de entorno `OPENAI_API_KEY`. Nunca en un fichero del repo, nunca
   pegada en el chat. (Si el equipo decide otro modelo de embeddings, usad el
   que indique la empresa.)
5. **Git**: nadie hace commits directos en `main`. Crea una rama
   (`feat/agente2-...`), sube la rama y abre un PR que mergeará el equipo. La
   skill `.agents/skills/semantic-commits-and-push` hace esto.

Trabaja en `entregas/cu-19-interpretacion-danos/app/agentes/agente_recuperacion/`.

## Pieza A — Costes

### Qué recibes y qué produces

Recibes los *hallazgos* del Agente 1. Cada uno trae, entre otros, `finding_id`,
`clase_tool` (p. ej. `lamp_broken`), `pieza_id` (p. ej. `FARO_DEL_D`),
`severidad` (`leve|moderado|grave`), `confidence_tier` (`confirmed` o
`needs_review`), `vision_verdict` y `regla_coste_aplicable`.

Los repartes en tres grupos:

- **confirmados** (`confirmed`): entran en los dos presupuestos.
- **pendientes**: `needs_review`, pero con pieza, severidad y regla de coste.
  Entran solo en el presupuesto "con pendientes".
- **fuera del coste**: los rechazados por la visión, o sin pieza/severidad, o
  sin regla. Se anotan con su motivo y no se presupuestan.

### Por qué hace falta la comprobación de regla

La tool **no da error** si le pasas una combinación que no conoce (por
ejemplo una abolladura en un parabrisas): devuelve coste 0 con una línea de
tipo `aviso`. Si dejaras pasar eso, el informe mostraría un daño con 0 €. El
Agente 1 ya lo marca en `regla_coste_aplicable`; tú solo tienes que respetarlo.

### Código de referencia

Crea `costes_y_cobertura.py` con estas partes juntas, en este orden. Ya está
probado contra la tool real.

```python
import csv
import sys
from pathlib import Path


def _raiz_repo() -> Path:
    for carpeta in [Path(__file__).resolve(), *Path(__file__).resolve().parents]:
        if (carpeta / ".git").exists():
            return carpeta
    raise RuntimeError("No se encontro la raiz del repo (.git)")


PAQUETE = _raiz_repo() / "piia2_paquete_datos"
sys.path.insert(0, str(PAQUETE / "scripts"))
from estimar_coste import estimar_coste, valor_venal  # noqa: E402


def _leer_csv(nombre: str, clave: str) -> dict[str, dict]:
    with open(PAQUETE / "data" / nombre, encoding="utf-8") as f:
        return {fila[clave]: fila for fila in csv.DictReader(f)}


POLIZAS = _leer_csv("polizas.csv", "poliza_id")
PIEZAS = _leer_csv("piezas.csv", "pieza_id")
```

El reparto de hallazgos:

```python
def clasificar_hallazgos(findings):
    """Reparte los hallazgos del Agente 1 en tres grupos:
    - confirmados: entran en los dos escenarios de coste,
    - pendientes: solo en el escenario "con pendientes" (hay pieza, severidad
      y regla de coste, pero falta confirmacion),
    - fuera: no se pueden presupuestar, con el motivo."""
    confirmados, pendientes, fuera = [], [], []
    for f in findings:
        if f["confidence_tier"] == "confirmed":
            confirmados.append(f)
        elif f["vision_verdict"] == "rechazado":
            fuera.append({"finding_id": f["finding_id"], "motivo": "rechazado_por_vision"})
        elif not f["pieza_id"] or not f["severidad"]:
            fuera.append({"finding_id": f["finding_id"], "motivo": "sin_pieza_o_severidad"})
        elif f["regla_coste_aplicable"] is not True:
            fuera.append({"finding_id": f["finding_id"], "motivo": "sin_regla_de_coste"})
        else:
            pendientes.append(f)
    return confirmados, pendientes, fuera


def _danos(hallazgos):
    return [
        {"clase": f["clase_tool"], "pieza_id": f["pieza_id"], "severidad": f["severidad"]}
        for f in hallazgos
    ]
```

Un detalle de la tool que conviene saber: si dos daños caen en la misma
pieza, se queda con el más severo; y a partir de `grave` añade una diagnosis
con escáner.

## Pieza B — Cobertura, pérdida total e indemnización

Es una función **determinista** (sin LLM): replica la lógica con la que la
empresa generó sus siniestros (`piia2_paquete_datos/scripts/generate_claims.py`,
líneas 87-103). Reglas, resumidas:

- **Pérdida total**: el coste sin IVA alcanza o supera `umbral × valor_venal`.
  El umbral sale de `polizas.csv` (0,75 en `P-TR-FR300`, 0,8 en `P-TR-SF`, 0 en
  las de terceros = nunca) y es 1,0 si el rol es `tercero_perjudicado`.
- **Tercero perjudicado**: cubre la RC obligatoria; indemniza el coste con IVA
  (o el valor venal si hay pérdida total).
- **Solo cristales** y la póliza cubre lunas: `min(coste con IVA, límite anual)
  − franquicia de lunas`.
- **Daños propios por colisión** (si la póliza los cubre): el coste con IVA
  (o, en pérdida total, el valor venal, **más un 10 %** si el criterio de la
  póliza es `valor_venal_mas_10pct`) **menos la franquicia**.
- Si la póliza no cubre nada de esto: no cubierto, indemnización 0.

```python
def calcular_cobertura(contexto, estimacion, danos):
    """Pérdida total, cobertura e indemnización. Replica la lógica con la que
    la empresa generó los siniestros (scripts/generate_claims.py)."""
    subtotal = estimacion["subtotal_sin_iva_eur"]
    total_iva = estimacion["total_con_iva_eur"]
    vv = valor_venal(contexto["vehiculo_id"], contexto["edad_anios"], contexto["km"])

    es_tercero = contexto["rol"] == "tercero_perjudicado"
    poliza = None if es_tercero else POLIZAS[contexto["poliza_id"]]
    umbral = 1.0 if es_tercero else float(poliza["umbral_perdida_total"])
    perdida_total = bool(danos) and umbral > 0 and subtotal >= umbral * vv

    if not danos:
        return {"cubierto": False, "motivo": "Sin daños presupuestables", "franquicia_eur": 0.0,
                "perdida_total": False, "indemnizacion_estimada_eur": 0.0}

    solo_cristal = all(PIEZAS[d["pieza_id"]]["zona_tipo"] == "cristal" for d in danos)

    if es_tercero:
        cubierto, franquicia = True, 0.0
        motivo = "Daños a tercero: RC obligatoria (LRCSCVM art. 7)"
        indemnizacion = vv if perdida_total else total_iva
    elif solo_cristal and poliza["cubre_lunas"] == "1":
        cubierto = True
        franquicia = float(poliza["franquicia_lunas_eur"])
        motivo = "Cobertura de lunas"
        indemnizacion = min(total_iva, float(poliza["limite_lunas_anual_eur"])) - franquicia
    elif poliza["cubre_danos_propios_colision"] == "1":
        cubierto = True
        franquicia = float(poliza["franquicia_danos_propios_eur"])
        motivo = "Pérdida total" if perdida_total else "Daños propios por colisión"
        if perdida_total:
            mas_10 = poliza["criterio_indemnizacion_perdida_total"] == "valor_venal_mas_10pct"
            base = vv * (1.10 if mas_10 else 1.0)
        else:
            base = total_iva
        indemnizacion = base - franquicia
    else:
        cubierto, franquicia, indemnizacion = False, 0.0, 0.0
        motivo = "Póliza sin cobertura de daños propios para este siniestro"

    return {
        "cubierto": cubierto,
        "motivo": motivo,
        "franquicia_eur": franquicia,
        "perdida_total": perdida_total,
        "indemnizacion_estimada_eur": round(max(0.0, indemnizacion), 2) if cubierto else 0.0,
    }
```

Y la función que junta todo y produce el JSON del contrato para el Agente 3
(`normativa` se rellena con la pieza C):

```python
def _escenario(contexto, hallazgos):
    danos = _danos(hallazgos)
    estimacion = estimar_coste(
        contexto["vehiculo_id"], danos,
        region=contexto["region"], tipo_taller=contexto["tipo_taller"],
        acabado=contexto["acabado"], tipo_pieza=contexto["tipo_pieza"],
    )
    return {
        "hallazgos_incluidos": [f["finding_id"] for f in hallazgos],
        "estimacion": estimacion,
        "cobertura": calcular_cobertura(contexto, estimacion, danos),
    }


def estimar_siniestro(salida_agente1, contexto):
    """Salida del Agente 2 para el Agente 3 (contrato en
    specs/piia2-arquitectura-multiagente.md). `normativa` (extractos del RAG)
    se anade aparte: ver buscar_normativa()."""
    confirmados, pendientes, fuera = clasificar_hallazgos(salida_agente1["findings"])
    umbral = 1.0 if contexto["rol"] == "tercero_perjudicado" else float(
        POLIZAS[contexto["poliza_id"]]["umbral_perdida_total"]
    )
    return {
        "image_id": salida_agente1["image_id"],
        "contexto": contexto,
        "valor_venal_eur": valor_venal(contexto["vehiculo_id"], contexto["edad_anios"], contexto["km"]),
        "umbral_perdida_total": umbral,
        "escenarios": {
            "confirmados": _escenario(contexto, confirmados),
            "con_pendientes": _escenario(contexto, confirmados + pendientes),
        },
        "hallazgos_fuera_del_coste": fuera,
        "normativa": [],
    }
```

### Cómo comprobar que lo hiciste bien

Con los ejemplos del contrato, tu salida (sin el campo `normativa`, que viene
del RAG) debe ser idéntica a `agente2_salida.json`. Prueba mínima
(`probar_costes.py`):

```python
import json
from pathlib import Path

from costes_y_cobertura import estimar_siniestro

EJ = Path(__file__).resolve().parents[1] / "ejemplos_contrato"
agente1 = json.loads((EJ / "agente1_salida.json").read_text(encoding="utf-8"))
contexto = json.loads((EJ / "contexto_siniestro.json").read_text(encoding="utf-8"))
esperado = json.loads((EJ / "agente2_salida.json").read_text(encoding="utf-8"))

obtenido = estimar_siniestro(agente1, contexto)
esperado["normativa"] = obtenido["normativa"] = []
assert obtenido == esperado, "tu salida no coincide con agente2_salida.json"
print("Pieza A y B ok")
```

Después prueba con **otros casos** para ver que no solo funciona el ejemplo:
cambia `rol` a `tercero_perjudicado`, la póliza a `P-TERC-BASICO` (no cubre
colisión), o provoca una pérdida total con el coche `V14` (Dacia Sandero),
`edad_anios: 16` y `km: 300000`: con los ejemplos del contrato debe salir
pérdida total **solo en el escenario `con_pendientes`** (coste sin IVA 935,85 €
frente a un umbral de 870 €, que es el 75 % del valor venal de 1.160 €) y no
en `confirmados` (560,80 €).

**Evaluación de esta parte** (sin fotos, con los siniestros sintéticos de la
empresa): para los siniestros `split == "val"` o `"test"` de
`data/siniestros_sinteticos.csv`, llama a `estimar_coste` con `danos_json` y
compara con `coste_facturado_sin_iva_eur`; el error medio esperado (MAPE) es de
≈ 9 %. Compara también tus banderas de pérdida total y cobertura con
`perdida_total` y `cobertura_aplica`.

## Pieza C — RAG sobre pólizas y legislación

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

cliente = OpenAI()  # lee OPENAI_API_KEY del entorno


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

Una función que, dado el JSON del Agente 1 y el contexto del siniestro,
devuelva el JSON del Agente 2 **completo**, con `normativa` rellenado por el
RAG (por ejemplo, un extracto de la cobertura de daños propios y otro de la
pérdida total de la póliza del siniestro):

```python
def agente2(salida_agente1, contexto):
    resultado = estimar_siniestro(salida_agente1, contexto)
    pid = contexto["poliza_id"]
    resultado["normativa"] = (
        buscar_normativa("cobertura de daños propios por colisión", poliza_id=pid, k=2)
        + buscar_normativa("pérdida total e indemnización", poliza_id=pid, k=2)
    )
    return resultado
```

## Más adelante: Google ADK

La empresa trabaja con Google ADK. Cuando las piezas funcionen como funciones
normales, se registran como *tools* de un agente (hay un ejemplo, sin probar,
en `piia2_paquete_datos/scripts/ejemplo_tool.py`). La empresa pasa los datos
estructurados como cadenas JSON para simplificar; haced lo mismo. **No
empieces por ADK**: primero que A, B y C funcionen y se prueben sin red.

## Qué NO tienes que hacer

- No inventes tablas de precios ni procedimientos: usa la tool de la empresa.
- No toques la detección de PIIA-1 ni el Agente 1 de Lucía.
- No subas a git el paquete de la empresa, la base `chroma_db/` ni la clave.
- No hace falta esperar a nadie: los ejemplos del contrato bastan.

## Definición de terminado

- [ ] `probar_costes.py` pasa: tu salida coincide con `agente2_salida.json`.
- [ ] Probados 3 casos más (tercero, póliza sin cobertura, pérdida total).
- [ ] Índice vectorial creado (~1.500 fragmentos) y `buscar_normativa` funciona.
- [ ] `evaluar_rag.py` da el hit@4 de las 25 preguntas, anotando qué mejoró.
- [ ] `agente2(...)` devuelve el JSON completo del contrato.
- [ ] Todo en una rama con su PR; nada de claves ni datos de la empresa en git.
