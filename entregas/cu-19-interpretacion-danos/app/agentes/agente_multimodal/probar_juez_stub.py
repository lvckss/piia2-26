"""Prueba juez_vision.py sin API Key ni datos reales (Issue #44, AC-008 y AC-009):
la herramienta que etiqueta hallazgos con un modelo juez (misma pregunta y mismas
condiciones que la persona, sin ver la respuesta de la vision), su cache, el tope de
llamadas, los fallos y el acuerdo entre las etiquetas del juez y las humanas.
Cada prueba cita su AC con la forma "Plan v1.2 de #44 + AC-008".

    python probar_juez_stub.py
"""

from __future__ import annotations

import base64
import contextlib
import io
import json
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from etiquetado import CABECERA_CSV, leer_etiquetas
from juez_vision import (
    JuezAbortado,
    LimiteDeLlamadas,
    acuerdo,
    construir_prompt,
    formatear_acuerdo,
    juzgar_hallazgo,
    juzgar_lote,
    main,
    parsear_juicio,
)

# el color rojo del recorte codifica la etiqueta que "ve" el cliente falso
ROJO = {"si": 240, "otra": 160, "no": 80, "dudo": 10}
SECRETO = "DESCRIPCION_SECRETA_DE_LA_VISION"


def etiqueta_de_rojo(valor: int) -> str:
    return "si" if valor > 200 else "otra" if valor > 120 else "no" if valor > 45 else "dudo"


class ClienteFalso:
    """Imita `client.chat.completions.create`. Sin `respuesta_fija`, decide la etiqueta leyendo el
    color del recorte de la peticion, asi el resultado no depende del orden de las llamadas (hilos)."""

    def __init__(self, respuesta_fija: str | None = None, fallar: bool = False) -> None:
        self.llamadas: list[dict] = []
        self.respuesta_fija = respuesta_fija
        self.fallar = fallar
        self._cerrojo = threading.Lock()
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._crear))

    def _crear(self, **kwargs):
        with self._cerrojo:
            self.llamadas.append(kwargs)
        if self.fallar:
            raise RuntimeError("fallo de red simulado")
        if self.respuesta_fija is not None:
            texto = self.respuesta_fija
        else:
            partes = kwargs["messages"][0]["content"]
            url = next(p["image_url"]["url"] for p in partes if p["type"] == "image_url")
            imagen = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
            texto = json.dumps({"etiqueta": etiqueta_de_rojo(imagen.convert("RGB").getpixel((4, 4))[0]), "motivo": "visto en el recorte"})
        mensaje = SimpleNamespace(content=texto)
        return SimpleNamespace(choices=[SimpleNamespace(message=mensaje)], usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20))


def crear_salidas(base: Path, etiquetas: dict[str, str], categorias: dict[str, str] | None = None) -> list[dict]:
    """Salidas del Agente 1 inventadas en `base`, con un recorte de color por hallazgo (el color es la etiqueta)."""
    (base / "crops").mkdir(parents=True, exist_ok=True)
    salidas: dict[int, dict] = {}
    for k, (finding_id, etiqueta) in enumerate(etiquetas.items()):
        image_id = int(finding_id.split("-")[0])
        ruta = f"crops/{finding_id}.jpg"
        # el verde distingue un recorte de otro: dos recortes iguales compartirian clave de cache
        Image.new("RGB", (16, 16), (ROJO[etiqueta], 20 + 7 * k, 30)).save(base / ruta, format="JPEG", quality=95)
        salida = salidas.setdefault(image_id, {"image_id": image_id, "resumen_filtro_previo": {}, "findings": []})
        salida["findings"].append(
            {
                "finding_id": finding_id,
                "category": (categorias or {}).get(finding_id, "dent"),
                "score": 0.55,
                "vision_verdict": "confirmado",
                "pieza_id": "PARAG_DEL",
                "vision_description": SECRETO,
                "crop_image_path": ruta,
            }
        )
    lista = [salidas[i] for i in sorted(salidas)]
    for s in lista:
        (base / f"{s['image_id']:06d}.json").write_text(json.dumps(s), encoding="utf-8")
    return lista


ETIQUETAS = {"1-1": "si", "1-2": "otra", "2-1": "no", "2-2": "dudo", "3-1": "si", "3-2": "no"}


def plano(salidas: list[dict]) -> list[dict]:
    return [{**h, "image_id": s["image_id"]} for s in salidas for h in s["findings"]]


def probar_prompt_ciego() -> None:
    """Plan v1.2 de #44 + AC-008: el juez recibe la clase, un solo recorte y la misma pregunta que la
    persona, y nunca la descripcion ni el veredicto de la vision."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        salidas = crear_salidas(base, {"1-1": "si"}, {"1-1": "scratch"})
        cliente = ClienteFalso()
        juicio = juzgar_hallazgo(cliente, "modelo-falso", None, base / salidas[0]["findings"][0]["crop_image_path"], "scratch", None, None)
        assert juicio == {"etiqueta": "si", "motivo": "visto en el recorte"}, juicio
        peticion = cliente.llamadas[0]
        partes = peticion["messages"][0]["content"]
        texto = next(p["text"] for p in partes if p["type"] == "text")
        assert "scratch" in texto and "dano de esa clase" in texto.lower().replace("ñ", "n")
        assert sum(p["type"] == "image_url" for p in partes) == 1, "el juez ve solo el recorte, como la persona"
        for prohibido in (SECRETO, "confirmado", "rechazado", "incierto", "veredicto", "pieza"):
            assert prohibido not in texto, f"el prompt no debe mencionar {prohibido!r}"
        assert peticion["model"] == "modelo-falso" and "reasoning_effort" not in peticion
        assert construir_prompt("dent") != construir_prompt("crack")
        for etiqueta in ("si", "otra", "no", "dudo"):
            assert f'"{etiqueta}"' in texto
        cliente2 = ClienteFalso()
        juzgar_hallazgo(cliente2, "m", "xhigh", base / "crops/1-1.jpg", "dent", None, None)
        assert cliente2.llamadas[0]["reasoning_effort"] == "xhigh"
        cliente3 = ClienteFalso()
        juzgar_hallazgo(cliente3, "m", None, base / "crops/1-1.jpg", "dent", None, None, formato_json=False)
        assert "response_format" not in cliente3.llamadas[0]
    print("prompt ciego ok")


def probar_parseo() -> None:
    """Plan v1.2 de #44 + AC-008: la respuesta se valida; una etiqueta fuera de las cuatro o un texto sin
    JSON no se acepta ni se inventa."""
    assert parsear_juicio('{"etiqueta": "si", "motivo": "hay una abolladura"}') == {"etiqueta": "si", "motivo": "hay una abolladura"}
    assert parsear_juicio('```json\n{"etiqueta": "otra"}\n```') == {"etiqueta": "otra", "motivo": ""}
    assert parsear_juicio('Mi respuesta: {"etiqueta": "dudo", "motivo": "borroso"} gracias')["etiqueta"] == "dudo"
    for malo in ('{"etiqueta": "quizas"}', '{"etiqueta": null}', "no hay json", "", '{"motivo": "sin etiqueta"}', "[1, 2]"):
        assert parsear_juicio(malo) is None, malo
    print("parseo ok")


def probar_en_seco_y_ejecucion_con_cache() -> None:
    """Plan v1.2 de #44 + AC-008: sin ejecutar no se llama a la API y se cuentan las llamadas; al ejecutar
    sale una etiqueta valida por hallazgo y una segunda ejecucion sale de la cache sin llamar."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        salidas = crear_salidas(base, ETIQUETAS)
        cache = base / "cache"
        cliente = ClienteFalso()
        plan = juzgar_lote(plano(salidas), base, cliente, "modelo-falso", None, cache, max_llamadas=100, ejecutar=False)
        assert cliente.llamadas == [] and plan["plan"] == {"en_alcance": 6, "en_cache": 0, "por_pagar": 6}, plan["plan"]
        res = juzgar_lote(plano(salidas), base, cliente, "modelo-falso", None, cache, max_llamadas=100, ejecutar=True)
        assert len(cliente.llamadas) == 6 and res["fallos"] == [], res["fallos"]
        assert res["etiquetas"] == ETIQUETAS, res["etiquetas"]
        assert res["uso"]["llamadas"] == 6 and res["uso"]["prompt_tokens"] == 600 and res["uso"]["completion_tokens"] == 120
        assert all(d["motivo"] == "visto en el recorte" for d in res["detalle"].values())
        otra = ClienteFalso()
        res2 = juzgar_lote(plano(salidas), base, otra, "modelo-falso", None, cache, max_llamadas=100, ejecutar=True)
        assert otra.llamadas == [] and res2["etiquetas"] == ETIQUETAS and res2["uso"]["llamadas"] == 0 and res2["uso"]["desde_cache"] == 6
        plan2 = juzgar_lote(plano(salidas), base, otra, "modelo-falso", None, cache, max_llamadas=100, ejecutar=False)
        assert plan2["plan"] == {"en_alcance": 6, "en_cache": 6, "por_pagar": 0}
        distinto = ClienteFalso()
        juzgar_lote(plano(salidas)[:1], base, distinto, "otro-modelo", None, cache, max_llamadas=100, ejecutar=True)
        assert len(distinto.llamadas) == 1, "otro modelo no reutiliza la cache de este"
        mas_esfuerzo = ClienteFalso()
        juzgar_lote(plano(salidas)[:1], base, mas_esfuerzo, "modelo-falso", "xhigh", cache, max_llamadas=100, ejecutar=True)
        assert len(mas_esfuerzo.llamadas) == 1, "otro esfuerzo de razonamiento tampoco"
    print("en seco, ejecucion y cache ok")


def probar_tope_de_llamadas() -> None:
    """Plan v1.2 de #44 + AC-008: si las llamadas por pagar superan el tope no se hace ninguna."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        salidas = crear_salidas(base, ETIQUETAS)
        cliente = ClienteFalso()
        try:
            juzgar_lote(plano(salidas), base, cliente, "m", None, base / "cache", max_llamadas=5, ejecutar=True)
            raise AssertionError("debia negarse a pasar del tope")
        except LimiteDeLlamadas as e:
            assert "6" in str(e) and "5" in str(e)
        assert cliente.llamadas == []
        res = juzgar_lote(plano(salidas)[:5], base, cliente, "m", None, base / "cache", max_llamadas=5, ejecutar=True)
        assert len(res["etiquetas"]) == 5
    print("tope de llamadas ok")


def probar_respuestas_invalidas_y_fallos() -> None:
    """Plan v1.2 de #44 + AC-008: una respuesta sin etiqueta valida no se convierte en etiqueta, queda como
    fallo, no se guarda en la cache y se reintenta; los fallos seguidos de la API abortan la pasada."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        salidas = crear_salidas(base, ETIQUETAS)
        cache = base / "cache"
        mala = ClienteFalso(respuesta_fija='{"etiqueta": "quizas"}')
        res = juzgar_lote(plano(salidas), base, mala, "m", None, cache, max_llamadas=100, ejecutar=True)
        assert res["etiquetas"] == {} and len(res["fallos"]) == 6 and all("etiqueta" in f["motivo"] for f in res["fallos"])
        buena = ClienteFalso()
        res = juzgar_lote(plano(salidas), base, buena, "m", None, cache, max_llamadas=100, ejecutar=True)
        assert len(buena.llamadas) == 6 and res["etiquetas"] == ETIQUETAS and res["fallos"] == []
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        muchos = {f"{i}-1": "si" for i in range(1, 31)}
        salidas = crear_salidas(base, muchos)
        caida = ClienteFalso(fallar=True)
        try:
            juzgar_lote(plano(salidas), base, caida, "m", None, base / "cache", max_llamadas=100, ejecutar=True)
            raise AssertionError("debia abortar tras fallos seguidos")
        except JuezAbortado as e:
            assert "seguidos" in str(e) and len(e.parcial["fallos"]) >= 5
        assert len(caida.llamadas) < 30, "no debe seguir pagando llamadas cuando todo falla"
    print("respuestas invalidas y fallos ok")


def probar_hilos() -> None:
    """Plan v1.2 de #44 + AC-008: con varios hilos salen las mismas etiquetas y el mismo numero de llamadas."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        muchos = {f"{i}-{j}": ["si", "otra", "no", "dudo"][(i + j) % 4] for i in range(1, 11) for j in (1, 2, 3)}
        salidas = crear_salidas(base, muchos)
        cliente = ClienteFalso()
        res = juzgar_lote(plano(salidas), base, cliente, "m", None, base / "cache", max_llamadas=100, ejecutar=True, hilos=6)
        assert res["etiquetas"] == muchos and len(cliente.llamadas) == 30 and res["uso"]["llamadas"] == 30
    print("hilos ok")


def probar_acuerdo() -> None:
    """Plan v1.2 de #44 + AC-009: acuerdo exacto, kappa de Cohen, matriz y acuerdo de «daño real» frente a
    «no», con los `dudo` aparte, calculados a mano en un caso pequeno."""
    h = dict(zip([f"{i}-1" for i in range(1, 11)], ["si", "si", "si", "no", "no", "no", "si", "si", "no", "no"]))
    j = dict(zip([f"{i}-1" for i in range(1, 11)], ["si", "si", "no", "no", "no", "si", "si", "si", "no", "no"]))
    r = acuerdo(h, j)
    assert r["n"] == 10 and r["coinciden"] == 8 and abs(r["acuerdo"] - 0.8) < 1e-9 and abs(r["kappa"] - 0.6) < 1e-9, r
    assert abs(r["kappa_dano_real"] - 0.6) < 1e-9 and r["humano_real_juez_no"] == 1 and r["humano_no_juez_real"] == 1
    assert r["humano_no_juez_no"] == 4 and r["humano_no"] == 5 and r["matriz"]["si"]["si"] == 4 and r["matriz"]["no"]["si"] == 1
    lo, hi = r["intervalo_acuerdo"]
    assert 0.48 < lo < 0.5 and 0.94 < hi < 0.96, (lo, hi)
    # `otra` cuenta como daño real; `dudo` queda fuera y se cuenta aparte
    h2 = {"1-1": "si", "2-1": "otra", "3-1": "no", "4-1": "dudo", "5-1": "si", "9-9": "si"}
    j2 = {"1-1": "otra", "2-1": "si", "3-1": "no", "4-1": "si", "5-1": "dudo", "8-8": "no"}
    r2 = acuerdo(h2, j2)
    assert r2["comunes"] == 5 and r2["n"] == 3 and r2["dudo_humano"] == 1 and r2["dudo_juez"] == 1, r2
    assert r2["coinciden"] == 1 and r2["acuerdo_dano_real"] == 1.0 and r2["sin_juzgar"] == 1 and r2["sin_humano"] == 1
    sin_variacion = acuerdo({"1-1": "si", "2-1": "si"}, {"1-1": "si", "2-1": "si"})
    assert sin_variacion["acuerdo"] == 1.0 and sin_variacion["kappa"] is None, "con una sola etiqueta el kappa no esta definido"
    vacio = acuerdo({"1-1": "dudo"}, {"1-1": "dudo"})
    assert vacio["n"] == 0 and vacio["acuerdo"] is None and vacio["kappa"] is None
    texto = formatear_acuerdo(r)
    assert "80 %" in texto and "0,60" in texto and "|" in texto
    print("acuerdo ok")


def probar_cli() -> None:
    """Plan v1.2 de #44 + AC-008 y AC-009: la linea de comandos exige un alcance, en seco no llama, escribe el
    CSV en el formato de las etiquetas humanas, y `acuerdo` compara dos CSV."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        crear_salidas(base, ETIQUETAS)
        salida = base / "juez"
        cache = base / "cache"
        comun = ["--salidas", str(base), "--modelo", "modelo-falso", "--salida", str(salida), "--cache-dir", str(cache)]
        cliente = ClienteFalso()
        fabrica = lambda: cliente  # noqa: E731
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            assert main(["juzgar", *comun], crear_cliente=fabrica) == 2
        assert "--todos" in err.getvalue() and "--ids" in err.getvalue() and cliente.llamadas == []
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            assert main(["juzgar", *comun, "--todos"], crear_cliente=fabrica) == 0
        assert cliente.llamadas == [] and "6" in out.getvalue() and "ejecutar" in out.getvalue().lower() and not (salida / "etiquetas_juez.csv").exists()
        humanas = base / "humanas.csv"
        humanas.write_text(CABECERA_CSV + "\n1-1,si\n2-1,no\n3-1,si\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            assert main(["juzgar", *comun, "--ids", str(humanas), "--ejecutar"], crear_cliente=fabrica) == 0
        assert len(cliente.llamadas) == 3
        etiquetas = leer_etiquetas(salida / "etiquetas_juez.csv")
        assert etiquetas == {"1-1": "si", "2-1": "no", "3-1": "si"}, etiquetas
        resumen = json.loads((salida / "resumen_juez.json").read_text(encoding="utf-8"))
        assert resumen["modelo"] == "modelo-falso" and resumen["llamadas_facturadas"] == 3 and resumen["etiquetados"] == 3 and len(resumen["prompt_sha256"]) == 64
        detalle = json.loads((salida / "detalle_juez.json").read_text(encoding="utf-8"))
        assert detalle["1-1"]["etiqueta"] == "si" and "motivo" in detalle["1-1"]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            assert main(["acuerdo", "--humanas", str(humanas), "--juez", str(salida / "etiquetas_juez.csv")], crear_cliente=fabrica) == 0
        assert "100 %" in out.getvalue()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            assert main(["juzgar", *comun, "--ids", str(base / "no_existe.csv")], crear_cliente=fabrica) == 2
        assert "ERROR" in err.getvalue()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            assert main(["juzgar", *comun, "--todos", "--max-llamadas", "2", "--ejecutar"], crear_cliente=lambda: ClienteFalso()) == 2
        assert "tope" in err.getvalue().lower() or "supera" in err.getvalue().lower()
    print("linea de comandos ok")


def main_pruebas() -> None:
    probar_prompt_ciego()
    probar_parseo()
    probar_en_seco_y_ejecucion_con_cache()
    probar_tope_de_llamadas()
    probar_respuestas_invalidas_y_fallos()
    probar_hilos()
    probar_acuerdo()
    probar_cli()
    print("Todo ok: juez.")


if __name__ == "__main__":
    main_pruebas()
