"""Pruebas de scripts/verificar_entrega.py.

Plan v1.2 de #49 (https://github.com/lvckss/piia2-26/issues/49#issuecomment-6590271954):
AC-001 (estructura), AC-002 (copias de decisions/) y AC-004 (enlaces).
Cada prueba cita su AC. Los casos son carpetas sintéticas en un directorio temporal;
no se lee ningún dato de CarDD ni ninguna clave.
"""

from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import verificar_entrega as v  # noqa: E402

ADR = """# ADR {n}: Título {n}

- Estado: {estado}
- Aceptación: revisión de prueba

## Contexto y motivación

Ver la [spec](../../specs/s.md), el [otro ADR](0002-b.md#decision) y la [web](https://example.com/x).

## Decisión

Se decide algo.

## Alternativas consideradas

Otras opciones.

## Referencias y evidencia

- [spec](../../specs/s.md)
- Ancla local: [arriba](#decision)

```text
[esto no es un enlace](../../no-existe.md)
```
"""

SPEC = """# Spec {n}

## Qué construir

Algo.

## Por qué

Porque sí.

## Restricciones y supuestos

Ninguna.

## Acceptance Criteria

| ID | Resultado |
|---|---|
| AC-001 | Algo observable. |
"""


def escribir(ruta: Path, texto: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto, encoding="utf-8", newline="\n")


def crear_caso(raiz: Path, adrs: dict[str, str] | None = None) -> Path:
    """Caso mínimo válido: README, ARCHITECTURE, dos specs y tres ADRs (dos Aceptados)."""
    caso = raiz / "caso"
    escribir(caso / "README.md", "# Caso\n\nVer [specs](specs/s.md).\n")
    escribir(caso / "ARCHITECTURE.md", "# Arquitectura\n\n## Componentes\n\nA.\n\n## Flujo\n\nB.\n")
    escribir(caso / "specs/s.md", SPEC.format(n=1))
    escribir(caso / "specs/otra-spec.md", SPEC.format(n=2))
    adrs = adrs or {
        "0001-a.md": ADR.format(n="0001", estado="Aceptado"),
        "0002-b.md": ADR.format(n="0002", estado="Aceptado"),
        "0003-c.md": ADR.format(n="0003", estado="Propuesto"),
    }
    for nombre, texto in adrs.items():
        escribir(caso / "docs/adr" / nombre, texto)
    escribir(caso / "docs/adr/README.md", "# Registro\n")
    return caso


class CasoTemporal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.caso = crear_caso(Path(self.tmp.name))

    def leer(self, ruta: str) -> str:
        return (self.caso / ruta).read_text(encoding="utf-8")


class CopiasTests(CasoTemporal):
    def test_ac002_genera_solo_los_aceptados_con_nota_y_enlaces_reescritos(self):
        """Plan v1.2 de #49 + AC-002: una copia por ADR Aceptado, con nota y enlaces reescritos."""
        escritos = v.generar(self.caso)
        self.assertEqual(sorted(escritos), ["0001-a.md", "0002-b.md"])
        self.assertFalse((self.caso / "decisions/0003-c.md").exists())
        copia = self.leer("decisions/0001-a.md")
        lineas = copia.split("\n")
        self.assertEqual(lineas[0], "# ADR 0001: Título 0001")
        self.assertIn("Copia de [`docs/adr/0001-a.md`](../docs/adr/0001-a.md)", lineas[2])
        self.assertIn("- Estado: Aceptado", copia)
        self.assertIn("](../specs/s.md)", copia)            # enlace al caso: un nivel menos
        self.assertNotIn("](../../specs/s.md)", copia.split("```")[0])
        self.assertIn("](0002-b.md#decision)", copia)       # entre ADRs: sin cambio
        self.assertIn("](https://example.com/x)", copia)    # absoluto: sin cambio
        self.assertIn("[esto no es un enlace](../../no-existe.md)", copia)  # código: intacto

    def test_ac002_copias_correctas_no_dan_errores(self):
        """Plan v1.2 de #49 + AC-002: las copias recién generadas pasan la comprobación."""
        v.generar(self.caso)
        self.assertEqual(v.comprobar_copias(self.caso), [])

    def test_ac002_control_negativo_sin_copias(self):
        """Plan v1.2 de #49 + AC-002: sin decisions/ faltan las copias de los Aceptados."""
        errores = v.comprobar_copias(self.caso)
        self.assertEqual(len(errores), 2)
        self.assertTrue(all("falta" in e for e in errores))

    def test_ac002_copia_editada_falla(self):
        """Plan v1.2 de #49 + AC-002: una copia que cambia el texto del ADR se detecta."""
        v.generar(self.caso)
        ruta = self.caso / "decisions/0001-a.md"
        ruta.write_text(ruta.read_text(encoding="utf-8").replace("Se decide algo.", "Se decide otra cosa."),
                        encoding="utf-8", newline="\n")
        errores = v.comprobar_copias(self.caso)
        self.assertEqual(len(errores), 1)
        self.assertIn("0001-a.md", errores[0])
        self.assertIn("difiere", errores[0])

    def test_ac002_copia_sin_nota_falla(self):
        """Plan v1.2 de #49 + AC-002: una copia sin la nota de cabecera se detecta."""
        v.generar(self.caso)
        ruta = self.caso / "decisions/0002-b.md"
        lineas = ruta.read_text(encoding="utf-8").split("\n")
        del lineas[1:3]
        ruta.write_text("\n".join(lineas), encoding="utf-8", newline="\n")
        errores = v.comprobar_copias(self.caso)
        self.assertEqual(len(errores), 1)
        self.assertIn("nota de cabecera", errores[0])

    def test_ac002_copia_de_adr_no_aceptado_falla(self):
        """Plan v1.2 de #49 + AC-002: no puede haber copia de un ADR que no esté Aceptado."""
        v.generar(self.caso)
        escribir(self.caso / "decisions/0003-c.md", self.leer("docs/adr/0003-c.md"))
        errores = v.comprobar_copias(self.caso)
        self.assertEqual(len(errores), 1)
        self.assertIn("no está Aceptado", errores[0])

    def test_ac002_regenerar_sigue_al_original(self):
        """Plan v1.2 de #49 + AC-002: si el ADR cambia, regenerar vuelve a dejar la copia correcta."""
        v.generar(self.caso)
        ruta = self.caso / "docs/adr/0001-a.md"
        ruta.write_text(ruta.read_text(encoding="utf-8") + "\nNota posterior.\n", encoding="utf-8", newline="\n")
        self.assertEqual(len(v.comprobar_copias(self.caso)), 1)
        v.generar(self.caso)
        self.assertEqual(v.comprobar_copias(self.caso), [])


class EnlacesTests(CasoTemporal):
    def test_ac004_enlaces_resuelven_tras_generar(self):
        """Plan v1.2 de #49 + AC-004: con las copias reescritas no hay enlaces rotos."""
        v.generar(self.caso)
        documentos, enlaces, errores = v.comprobar_enlaces(self.caso)
        self.assertEqual(errores, [])
        self.assertGreaterEqual(documentos, 8)
        self.assertGreaterEqual(enlaces, 10)

    def test_ac004_control_negativo_copia_sin_reescribir(self):
        """Plan v1.2 de #49 + AC-004: una copia con los enlaces sin reescribir da enlaces rotos."""
        v.generar(self.caso)
        escribir(self.caso / "decisions/0001-a.md", self.leer("docs/adr/0001-a.md"))
        _, _, errores = v.comprobar_enlaces(self.caso)
        self.assertEqual(len(errores), 2)  # los dos `../../specs/s.md`
        self.assertTrue(all("decisions/0001-a.md" in e and "sale de la carpeta" in e for e in errores))

    def test_ac004_enlace_a_archivo_inexistente(self):
        """Plan v1.2 de #49 + AC-004: un enlace a un archivo que no existe se detecta."""
        escribir(self.caso / "README.md", "# Caso\n\nVer [nada](specs/no-existe.md).\n")
        _, _, errores = v.comprobar_enlaces(self.caso)
        self.assertEqual(len(errores), 1)
        self.assertIn("no existe", errores[0])

    def test_ac004_distingue_mayusculas_como_github(self):
        """Plan v1.2 de #49 + AC-004: en GitHub (Linux) `S.md` no es `s.md`, aunque Windows las confunda."""
        escribir(self.caso / "README.md", "# Caso\n\nVer [spec](specs/S.md).\n")
        _, _, errores = v.comprobar_enlaces(self.caso)
        self.assertEqual(len(errores), 1)
        self.assertIn("no existe", errores[0])

    def test_ac004_ignora_codigo_externos_y_anclas(self):
        """Plan v1.2 de #49 + AC-004: bloques de código, URLs y anclas no cuentan como enlaces relativos."""
        solo = Path(self.tmp.name) / "solo"
        escribir(solo / "README.md",
                 "# Caso\n\n[web](https://example.com) [ancla](#caso) `[x](../../nada.md)`\n\n```\n[y](../../nada.md)\n```\n")
        documentos, enlaces, errores = v.comprobar_enlaces(solo)
        self.assertEqual((documentos, enlaces, errores), (1, 0, []))

    def test_ac004_el_caso_real_no_tiene_enlaces_rotos(self):
        """Plan v1.2 de #49 + AC-004: guarda sobre la carpeta real del caso en este checkout."""
        _, _, errores = v.comprobar_enlaces(v.CASO)
        self.assertEqual(errores, [])


class EstructuraTests(CasoTemporal):
    def setUp(self):
        super().setUp()
        v.generar(self.caso)

    def test_ac001_caso_minimo_valido(self):
        """Plan v1.2 de #49 + AC-001: README, ARCHITECTURE, 2 specs y 2 ADRs bien formados."""
        self.assertEqual(v.comprobar_estructura(self.caso), [])

    def test_ac001_falta_architecture(self):
        """Plan v1.2 de #49 + AC-001: sin ARCHITECTURE.md la estructura falla."""
        (self.caso / "ARCHITECTURE.md").unlink()
        errores = v.comprobar_estructura(self.caso)
        self.assertEqual(len(errores), 1)
        self.assertIn("ARCHITECTURE.md", errores[0])

    def test_ac001_un_solo_adr_en_decisions(self):
        """Plan v1.2 de #49 + AC-001: decisions/ necesita al menos 2 ADRs."""
        (self.caso / "decisions/0002-b.md").unlink()
        errores = v.comprobar_estructura(self.caso)
        self.assertEqual(len(errores), 1)
        self.assertIn("al menos 2", errores[0])

    def test_ac001_adr_sin_alternativas(self):
        """Plan v1.2 de #49 + AC-001: cada ADR necesita decisión, motivación, alternativas y referencias."""
        ruta = self.caso / "decisions/0001-a.md"
        ruta.write_text(ruta.read_text(encoding="utf-8").replace("## Alternativas consideradas", "## Otro"),
                        encoding="utf-8", newline="\n")
        errores = v.comprobar_estructura(self.caso)
        self.assertEqual(len(errores), 1)
        self.assertIn("alternativas", errores[0])

    def test_ac001_nombre_que_no_es_kebab_case(self):
        """Plan v1.2 de #49 + AC-001: los nombres de archivo van en kebab-case."""
        (self.caso / "specs/otra-spec.md").rename(self.caso / "specs/Otra_Spec.md")
        errores = v.comprobar_estructura(self.caso)
        self.assertTrue(any("kebab-case" in e and "Otra_Spec.md" in e for e in errores), errores)

    def test_ac001_spec_funcional_sin_ids_de_criterio(self):
        """Plan v1.2 de #49 + AC-001: una spec funcional necesita criterios con ID."""
        ruta = self.caso / "specs/s.md"
        ruta.write_text(SPEC.format(n=1).replace("AC-001", "criterio"), encoding="utf-8", newline="\n")
        errores = v.comprobar_estructura(self.caso)
        self.assertEqual(len(errores), 1)
        self.assertIn("s.md", errores[0])


class CliTests(CasoTemporal):
    def test_comprobar_devuelve_0_si_todo_esta_bien_y_1_si_no(self):
        """Plan v1.2 de #49 + AC-002: el código de salida refleja el resultado."""
        self.assertEqual(v.main(["comprobar", "--snapshot", str(self.caso), "--ac", "002"]), 1)
        v.main(["generar", "--snapshot", str(self.caso)])
        self.assertEqual(v.main(["comprobar", "--snapshot", str(self.caso), "--ac", "002", "004", "001"]), 0)


if __name__ == "__main__":
    unittest.main()
