# Agente 3 — Redactor del informe (guía para Víctor)

Esta guía es autónoma: léela entera (tú o tu Claude) antes de tocar código.
Antes, lee también `specs/piia2-arquitectura-multiagente.md`: ahí está el
sistema completo, el contrato JSON entre agentes y las decisiones tomadas con
la empresa. No necesitas esperar a nadie ni haber terminado tus costes: tienes
ejemplos reales en `entregas/cu-19-interpretacion-danos/app/agentes/ejemplos_contrato/`.

**Orden recomendado:** haz primero `agente2-costes-cobertura-guia.md` (es lo más
rápido y te enseña de dónde salen las cifras que luego cuentas en el informe), y
después esta guía. El RAG de pólizas y legislación (el campo `normativa`) lo hace
Lucas; hasta que exista, `normativa` viene vacío y el informe lo soporta.

## Qué cambió respecto a la primera versión de esta guía

La empresa nos dio un paquete de datos con una herramienta de costes, y eso
enriquece el informe: ya no solo "hallazgo + procedimiento + precio", sino
coste desglosado en dos escenarios, daños asociados posibles, pérdida total,
cobertura de la póliza e indemnización con sus fuentes. Además se usa la API
de OpenAI (no Anthropic) y el informe sale en **markdown** (la empresa dijo que
el PDF, sobre todo con imágenes, es complejo y se vea más adelante).

## Qué recibes

Dos JSON, ya con el formato definitivo. Puedes trabajar con ellos desde el
primer día:

- `agente1_salida.json` — los hallazgos del Agente 1 (Lucía): por cada
  detección, `finding_id`, `category`, `score`, `confidence_tier`
  (`confirmed` / `needs_review`), `vision_verdict` (`confirmado`, `rechazado`,
  `incierto`), `pieza_id`, `severidad`, `vision_description`,
  `crop_image_path`...
- `agente2_salida.json` — el trabajo del Agente 2 (tus costes y cobertura; la
  `normativa` la rellena el RAG de Lucas): dos presupuestos
  (`escenarios.confirmados` y `escenarios.con_pendientes`, cada uno con
  `estimacion`, `cobertura` y los `hallazgos_incluidos`), los
  `hallazgos_fuera_del_coste`, el `valor_venal_eur`, y `normativa` (extractos
  con su fuente).
- `contexto_siniestro.json` — el coche, el taller y la póliza (ya vienen
  dentro de `agente2_salida.json["contexto"]`).

Los números de estos ejemplos están calculados con la herramienta real de la
empresa. Todo lo que no es legislación es sintético.

## Qué tienes que producir

Un informe de peritaje en markdown con estas secciones (el generador de
referencia de abajo ya las tiene):

1. **Cabecera**: imagen, fecha, vehículo, taller, póliza y aviso de que son
   datos sintéticos.
2. **Resumen**: cuántos daños hay de cada tipo, coste de las dos formas,
   pérdida total e indemnización.
3. **Daños confirmados**, con pieza, severidad y reparación.
4. **Daños pendientes de revisión**, **explicando por qué** están pendientes.
5. **Detecciones no incluidas en el coste** (rechazadas por la visión...).
6. **Desglose del coste** en dos columnas (solo confirmados / con pendientes).
7. **Posibles daños asociados** (`arrastres_posibles`: radiador, airbag...).
   Se muestran aparte; **no** entran en el coste.
8. **Cobertura e indemnización** y **fuentes consultadas** (la `normativa`).

**Los `confirmed` y los `needs_review` nunca se redactan igual**: los pendientes
van en su propia sección, con la advertencia de que requieren verificación
humana.

## El principio más importante: las cifras no las escribe el LLM

Un modelo de lenguaje puede inventarse un importe sin avisar, y un informe de
peritaje con un precio falso es peor que no tener informe. Por eso:

- **Todas las cifras, tablas y listas se generan con código** a partir de los
  JSON. Ninguna se calcula ni se escribe a mano.
- El LLM, como mucho, redacta un párrafo de resumen en lenguaje natural, y
  después se **comprueba automáticamente** que todos los importes del texto
  existen en la salida del Agente 2. Si no, se descarta su párrafo y se usa el
  resumen determinista.

## Paso 1 (puedes hacerlo ya): mirar informes reales

Busca 3 o 4 ejemplos de informes o presupuestos de peritación de daños de
vehículos (de aseguradoras, talleres o peritos) y apunta: qué secciones
tienen, en qué orden, cómo presentan piezas / mano de obra / pintura /
materiales, y el vocabulario que usan ("valoración de daños", "baremo",
"pérdida total"...). `piia2_paquete_datos/fuentes_descarga.md` (sección 1)
enlaza material de CESVIMAP sobre baremos de pintura y carrocería. Lo que
encuentres es lo que justifica tu plantilla en la defensa.

## Paso 2: preparar el entorno y ejecutar el generador de referencia

1. Extrae `piia2_paquete_datos.zip` en la raíz del repo, de modo que exista
   `piia2-26/piia2_paquete_datos/`. Está en `.gitignore`: **no lo subas a
   git**.
2. Trabaja en `entregas/cu-19-interpretacion-danos/app/agentes/agente_redactor/`.
3. Crea `informe.py` con este código. Solo usa la librería estándar y ya está
   probado con los ejemplos:

```python
import csv
import re
from datetime import date
from pathlib import Path


def _raiz_repo() -> Path:
    for carpeta in [Path(__file__).resolve(), *Path(__file__).resolve().parents]:
        if (carpeta / ".git").exists():
            return carpeta
    raise RuntimeError("No se encontro la raiz del repo (.git)")


DATA = _raiz_repo() / "piia2_paquete_datos" / "data"


def _leer_csv(nombre):
    with open(DATA / nombre, encoding="utf-8") as f:
        return list(csv.DictReader(f))


PIEZAS = {r["pieza_id"]: r for r in _leer_csv("piezas.csv")}
VEHICULOS = {r["vehiculo_id"]: r for r in _leer_csv("vehiculos.csv")}
POLIZAS = {r["poliza_id"]: r for r in _leer_csv("polizas.csv")}
REGLAS = {(r["clase_cardd"], r["zona_tipo"], r["severidad"]): r["accion"] for r in _leer_csv("reglas_dano.csv")}

ACCION_TEXTO = {
    "sustituir": "Sustituir la pieza",
    "sustituir_pintar": "Sustituir la pieza y pintarla",
    "reparar_pintar": "Reparar (desabollar) y pintar",
    "reparar_plastico_pintar": "Reparar el plástico y pintar",
    "pintar_panel": "Pintar el panel",
    "pulido": "Pulir / repasar",
    "reparar_impacto": "Reparar el impacto con resina",
    "reparar_pinchazo": "Reparar el pinchazo",
    "sustituir_neumatico": "Sustituir el neumático y alinear",
}
CLASE_TEXTO = {
    "dent": "abolladura", "scratch": "arañazo", "crack": "grieta",
    "glass_shatter": "rotura de cristal", "lamp_broken": "óptica rota", "tire_flat": "neumático pinchado",
}
MOTIVO_FUERA = {
    "rechazado_por_vision": "El modelo de visión no ve el daño (probable falso positivo)",
    "sin_pieza_o_severidad": "No se pudo identificar la pieza o la severidad",
    "sin_regla_de_coste": "No hay regla de coste para esta combinación de daño, pieza y severidad",
}


def eur(x):
    """1233.55 -> '1.233,55 €' (formato español)."""
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def _pieza(f):
    return PIEZAS[f["pieza_id"]]["nombre"] if f["pieza_id"] else "—"


def _reparacion(f):
    if not f["pieza_id"] or not f["severidad"]:
        return "—"
    zona = PIEZAS[f["pieza_id"]]["zona_tipo"]
    accion = REGLAS.get((f["clase_tool"], zona, f["severidad"]))
    return ACCION_TEXTO.get(accion, "—")


def _motivos_pendiente(f):
    motivos = []
    if f["score_tier"] == "needs_review":
        motivos.append(f"score de detección bajo ({f['score']:.2f})")
    if f["vision_verdict"] != "confirmado":
        motivos.append(f"la visión lo ve {f['vision_verdict']}")
    if f["regla_coste_aplicable"] is not True:
        motivos.append("sin regla de coste")
    return "; ".join(motivos) or "pendiente de verificación"


def _tabla_hallazgos(hallazgos, con_motivo=False):
    cab = "| ID | Pieza | Daño | Severidad | Reparación | " + ("Por qué está pendiente |" if con_motivo else "Score |")
    sep = "|---|---|---|---|---|---|"
    filas = []
    for f in hallazgos:
        ultima = _motivos_pendiente(f) if con_motivo else f"{f['score']:.2f}"
        filas.append(
            f"| {f['finding_id']} | {_pieza(f)} | {CLASE_TEXTO.get(f['clase_tool'], f['category'])} | "
            f"{f['severidad'] or '—'} | {_reparacion(f)} | {ultima} |"
        )
    return "\n".join([cab, sep, *filas])


def _imagenes(hallazgos):
    return "\n".join(f"![{f['finding_id']}]({f['crop_image_path']}) " for f in hallazgos if f.get("crop_image_path"))


def generar_informe(agente1, agente2, hoy=None):
    """Informe de peritaje en markdown. TODAS las cifras salen de `agente2`:
    ninguna se calcula ni se escribe a mano aquí."""
    hoy = hoy or date.today().isoformat()
    ctx = agente2["contexto"]
    veh = VEHICULOS[ctx["vehiculo_id"]]
    esc_conf = agente2["escenarios"]["confirmados"]
    esc_pend = agente2["escenarios"]["con_pendientes"]
    por_id = {f["finding_id"]: f for f in agente1["findings"]}
    # PIIA-1 puede dar decenas de detecciones por imagen; el Agente 1 solo manda al modelo de visión las candidatas
    total_detecciones = agente1.get("resumen_filtro_previo", {}).get("detecciones_totales", len(agente1["findings"]))

    confirmados = [por_id[i] for i in esc_conf["hallazgos_incluidos"]]
    pendientes = [por_id[i] for i in esc_pend["hallazgos_incluidos"] if i not in esc_conf["hallazgos_incluidos"]]
    fuera = agente2["hallazgos_fuera_del_coste"]

    poliza = POLIZAS.get(ctx["poliza_id"], {}).get("producto", "Terceros (RC obligatoria)")
    est_c, est_p = esc_conf["estimacion"], esc_pend["estimacion"]
    cob_c, cob_p = esc_conf["cobertura"], esc_pend["cobertura"]
    si_no = lambda b: "Sí" if b else "No"

    md = [
        f"# Informe de peritaje — imagen {agente2['image_id']}",
        "",
        f"**Fecha:** {hoy} · **Vehículo:** {veh['marca']} {veh['modelo']} · **Taller:** {ctx['tipo_taller']} ({ctx['region']}) · **Póliza:** {poliza}",
        "",
        "> Informe generado automáticamente con datos sintéticos de prototipo. No sustituye a una valoración pericial.",
        "",
        "## Resumen",
        "",
        f"- Detecciones de PIIA-1: **{total_detecciones}**; analizadas por la visión: **{len(agente1['findings'])}** — "
        f"{len(confirmados)} confirmados, {len(pendientes)} pendientes de revisión, {len(fuera)} no incluidos en el coste.",
        f"- Coste de reparación **solo con daños confirmados**: {eur(est_c['subtotal_sin_iva_eur'])} sin IVA ({eur(est_c['total_con_iva_eur'])} con IVA).",
        f"- Coste **incluyendo los pendientes**: {eur(est_p['subtotal_sin_iva_eur'])} sin IVA ({eur(est_p['total_con_iva_eur'])} con IVA).",
        f"- Pérdida total (valor venal {eur(agente2['valor_venal_eur'])}, umbral {agente2['umbral_perdida_total']:.0%}): "
        f"{si_no(cob_c['perdida_total'])} con los confirmados, {si_no(cob_p['perdida_total'])} con los pendientes.",
        f"- Indemnización estimada: {eur(cob_c['indemnizacion_estimada_eur'])} (confirmados) — {eur(cob_p['indemnizacion_estimada_eur'])} (con pendientes).",
        "",
        "## Daños confirmados",
        "",
        _tabla_hallazgos(confirmados) if confirmados else "_Ninguno._",
        "",
        _imagenes(confirmados),
        "",
        "## Daños pendientes de revisión",
        "",
        "Se incluyen en el segundo presupuesto, pero **no están confirmados**: requieren verificación humana.",
        "",
        _tabla_hallazgos(pendientes, con_motivo=True) if pendientes else "_Ninguno._",
        "",
        _imagenes(pendientes),
        "",
        "## Detecciones no incluidas en el coste",
        "",
    ]
    if fuera:
        md += [f"- {por_id[x['finding_id']]['category']} ({x['finding_id']}): {MOTIVO_FUERA[x['motivo']]}." for x in fuera]
    else:
        md += ["_Ninguna._"]

    d_c, d_p = est_c["desglose"], est_p["desglose"]
    filas = [
        ("Piezas", "piezas"), ("Mano de obra de chapa", "mano_obra_chapa"), ("Mano de obra de pintura", "mano_obra_pintura"),
        ("Mano de obra de mecánica", "mano_obra_mecanica"), ("Materiales de pintura", "materiales_pintura"), ("Otros", "otros"),
    ]
    md += [
        "",
        "## Desglose del coste",
        "",
        "| Concepto | Solo confirmados | Con pendientes |",
        "|---|---:|---:|",
        *[f"| {nombre} | {eur(d_c[k])} | {eur(d_p[k])} |" for nombre, k in filas],
        f"| **Subtotal sin IVA** | **{eur(est_c['subtotal_sin_iva_eur'])}** | **{eur(est_p['subtotal_sin_iva_eur'])}** |",
        f"| IVA | {eur(est_c['iva_eur'])} | {eur(est_p['iva_eur'])} |",
        f"| **Total con IVA** | **{eur(est_c['total_con_iva_eur'])}** | **{eur(est_p['total_con_iva_eur'])}** |",
        "",
        "## Posibles daños asociados (no incluidos en el coste)",
        "",
    ]
    arrastres = est_p["arrastres_posibles"]
    if arrastres:
        md += ["En impactos de esta gravedad suelen verse afectadas también estas piezas; hay que revisarlas en taller:", ""]
        md += [f"- {PIEZAS[a['pieza_id']]['nombre']} (probabilidad {a['probabilidad']:.0%}, por daño en {PIEZAS[a['origen']]['nombre'].lower()})"
               for a in arrastres]
    else:
        md += ["_Ninguno previsto._"]

    md += [
        "",
        "## Cobertura e indemnización",
        "",
        f"- Póliza: {poliza}.",
        f"- Cubierto (solo confirmados): {si_no(cob_c['cubierto'])} — {cob_c['motivo']}. Franquicia: {eur(cob_c['franquicia_eur'])}.",
        f"- Indemnización estimada: {eur(cob_c['indemnizacion_estimada_eur'])} con los confirmados; {eur(cob_p['indemnizacion_estimada_eur'])} con los pendientes.",
        "",
        "## Fuentes consultadas",
        "",
    ]
    md += [f"- {n['tema']}: «{n['extracto']}» ({n['fuente']})" for n in agente2["normativa"]] or ["_Sin fuentes._"]
    return "\n".join(md) + "\n"


def importes_en_euros(texto):
    """Todos los importes '1.233,55 €' que aparecen en el informe, como float."""
    return [float(m.replace(".", "").replace(",", ".")) for m in re.findall(r"(\d{1,3}(?:\.\d{3})*,\d{2}) €", texto)]


def _numeros(obj):
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        yield round(float(obj), 2)
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _numeros(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _numeros(v)


def comprobar_cifras(informe, agente2):
    """Devuelve los importes del informe que NO están en la salida del Agente 2
    (lista vacía = ninguna cifra inventada)."""
    permitidas = set(_numeros(agente2))
    return [x for x in importes_en_euros(informe) if round(x, 2) not in permitidas]
```

4. Pruébalo (`probar_informe.py`). Genera el informe y comprueba que
   **ningún importe en euros del texto es inventado**:

```python
import json
from pathlib import Path

from informe import comprobar_cifras, generar_informe

EJ = Path(__file__).resolve().parents[1] / "ejemplos_contrato"
agente1 = json.loads((EJ / "agente1_salida.json").read_text(encoding="utf-8"))
agente2 = json.loads((EJ / "agente2_salida.json").read_text(encoding="utf-8"))

informe = generar_informe(agente1, agente2)
Path("informe_ejemplo.md").write_text(informe, encoding="utf-8")

inventadas = comprobar_cifras(informe, agente2)
assert not inventadas, f"importes que no están en la salida del Agente 2: {inventadas}"
print("Informe generado en informe_ejemplo.md; todas las cifras salen del Agente 2")
```

Abre `informe_ejemplo.md` en un visor de markdown y léelo como si fueras el
cliente: ¿se entiende?, ¿falta algo?, ¿qué cambiarías?

## Paso 3: hacerlo tuyo

El generador de referencia es una base, no el resultado final. Con lo que
investigaste en el paso 1, rediseña la plantilla: orden de secciones,
redacción de las tablas, qué se destaca primero. Mantén las reglas de oro:
confirmados y pendientes separados, dos escenarios de coste, cifras solo desde
los JSON y la comprobación automática de cifras.

Prueba **casos distintos** editando copias de los JSON de ejemplo (el informe
no debe romperse ni quedar raro):

- Un siniestro de **tercero perjudicado** (`rol: tercero_perjudicado`, sin
  `poliza_id`).
- **Ningún hallazgo confirmado** (todos pendientes o rechazados).
- **Todos rechazados** por la visión.
- Una **pérdida total**. Edita a mano una copia de `agente2_salida.json` y pon
  `perdida_total: true` en la cobertura de un escenario (o, cuando tengas tu
  código de costes, usa el coche `V14`, `edad_anios: 16` y `km: 300000`, que da
  pérdida total solo en el escenario `con_pendientes`). Comprueba que el informe
  explica la diferencia entre los dos escenarios.
- Un siniestro **sin `arrastres_posibles`** y otro sin `normativa`.

## Paso 4 (opcional): párrafo de resumen redactado por el LLM

Cuando lo anterior funcione, puedes pedir al modelo un párrafo introductorio.
La clave de OpenAI va **solo** en la variable de entorno `OPENAI_API_KEY`
(nunca en un fichero ni en el chat), y el id del modelo en `OPENAI_MODEL` (el
que figure en la cuenta de la empresa; la empresa pide probar varios modelos y
comparar si el esfuerzo compensa).

```python
import os

from openai import OpenAI

PROMPT_RESUMEN = """Eres un perito de seguros. Redacta un párrafo breve (máximo 5 frases)
que resuma este siniestro para el asegurado, en español y con tono profesional.
Usa EXCLUSIVAMENTE los datos de abajo. No añadas ningún importe ni cifra que no aparezca aquí.
Distingue siempre lo confirmado de lo pendiente de revisión.

Datos:
{datos}
"""


def resumen_con_llm(agente2, texto_resumen_determinista):
    # la cabecera evita un fallo conocido con brotli en algunos Anaconda
    # (ver app/agentes/README.md, "Problemas conocidos")
    cliente = OpenAI(default_headers={"Accept-Encoding": "gzip, deflate"})
    r = cliente.chat.completions.create(
        model=os.environ["OPENAI_MODEL"],
        messages=[{"role": "user", "content": PROMPT_RESUMEN.format(datos=texto_resumen_determinista)}],
    )
    parrafo = (r.choices[0].message.content or "").strip()
    # si el modelo se inventó un importe, se descarta su párrafo
    if comprobar_cifras(parrafo, agente2):
        return None
    return parrafo
```

Si `resumen_con_llm` devuelve `None`, el informe sale con el resumen
determinista, que ya es correcto. Guarda cuántas veces el modelo se inventó una
cifra: es un dato bueno para la defensa.

## Más adelante: PDF y Google ADK

- **PDF**: la empresa lo deja para más adelante porque con imágenes es
  complejo. Las imágenes ya van enlazadas en el markdown por su ruta. Si
  sobra tiempo: markdown → HTML → PDF con una librería tipo `weasyprint`.
- **Google ADK**: la empresa trabaja con él. Cuando `generar_informe` funcione
  como función normal, Lucas la registra como *tool* de un agente (ver
  `integracion-adk-guia.md`). No empieces por ahí: tú solo mantén
  `generar_informe(agente1, agente2)` como función pura.

## Qué NO tienes que hacer

- No calcules ni decidas precios, pérdida total o indemnización: lo hace el
  Agente 2 y tú solo lo cuentas.
- No dejes que el LLM escriba importes.
- No toques la detección de PIIA-1, el Agente 1 ni el RAG de Lucas.
- No subas a git el paquete de la empresa ni ninguna clave.
- Git: nadie hace commits directos en `main`. Crea una rama, súbela y abre un
  PR que mergeará el equipo (la skill `.agents/skills/semantic-commits-and-push`
  lo hace).

## Definición de terminado

- [ ] Mirados 3-4 informes reales y plantilla propia justificada con ellos.
- [ ] `generar_informe(agente1, agente2)` produce markdown con las 8 secciones,
      con confirmados y pendientes separados y los dos escenarios de coste.
- [ ] `comprobar_cifras` pasa en todos los casos de prueba del paso 3.
- [ ] Probados los 5 casos del paso 3 sin que el informe se rompa.
- [ ] Todo en una rama con su PR; nada de claves ni datos de la empresa en git.
