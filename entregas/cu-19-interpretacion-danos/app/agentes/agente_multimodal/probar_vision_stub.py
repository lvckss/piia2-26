"""Prueba vision.py sin API Key real ni el paquete `anthropic` instalado.

Usa un cliente falso que imita la forma de la respuesta real del SDK de
Anthropic (`respuesta.content[0].text`), para comprobar que
`describir_dano`/`enriquecer_con_vision` construyen bien la peticion y leen
bien la respuesta -- no que el modelo describa danos de verdad (eso hace
falta la API Key real, el lunes)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hallazgos import cargar_detecciones, construir_hallazgos
from recorte import generar_recortes
from vision import enriquecer_con_vision


@dataclass
class _BloqueTexto:
    text: str


@dataclass
class _RespuestaFalsa:
    content: list[_BloqueTexto]


class ClienteFalso:
    """Imita `anthropic.Anthropic`: registra las llamadas recibidas y
    devuelve una descripcion falsa pero distinguible, para poder comprobar
    que cada finding recibe la suya y no la de otro."""

    def __init__(self) -> None:
        self.llamadas: list[dict] = []
        self.messages = self

    def create(self, model: str, max_tokens: int, messages: list[dict]) -> _RespuestaFalsa:
        self.llamadas.append({"model": model, "max_tokens": max_tokens, "messages": messages})
        bloque_texto = messages[0]["content"][1]["text"]
        categoria = bloque_texto.split("tipo '")[1].split("'")[0]
        return _RespuestaFalsa(content=[_BloqueTexto(text=f"[descripcion falsa de {categoria}]")])


def main() -> None:
    ejemplos_dir = Path(__file__).parent / "ejemplos"
    ejemplo_path = ejemplos_dir / "ejemplo_3_mixto_dificil.json"

    deteccion = cargar_detecciones(ejemplo_path)

    from PIL import Image
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        imagen_falsa = Image.new(
            "RGB", (deteccion["image_width"], deteccion["image_height"]), "gray"
        )
        fake_image_path = tmp_dir / f"{deteccion['image_id']}.jpg"
        imagen_falsa.save(fake_image_path)
        deteccion["image_path"] = str(fake_image_path)

        hallazgos = construir_hallazgos(deteccion)
        generar_recortes(deteccion, hallazgos, tmp_dir / "crops")

        cliente_falso = ClienteFalso()
        enriquecer_con_vision(hallazgos, cliente_falso)

    assert len(cliente_falso.llamadas) == 3, f"esperaba 3 llamadas, hubo {len(cliente_falso.llamadas)}"

    for finding in hallazgos["findings"]:
        print(
            f"  {finding['category']:15s} -> {finding['confidence_tier']:13s} "
            f"vision_description={finding['vision_description']!r}"
        )
        assert finding["category"] in finding["vision_description"]

    print("\nTodo ok: 3 llamadas registradas, cada finding con su propia descripcion.")


if __name__ == "__main__":
    main()
