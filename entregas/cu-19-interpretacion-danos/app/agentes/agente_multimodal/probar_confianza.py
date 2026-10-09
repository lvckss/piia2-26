"""Verifica AC-001–AC-007 del plan compacto v1 de #14:
https://github.com/lvckss/piia2-26/issues/14#issuecomment-6081037596

Datos sintéticos, unittest estándar y oráculos independientes de los umbrales
productivos. Ejecutar desde la raíz con python <ruta>/probar_confianza.py.
"""

from __future__ import annotations

import copy
import itertools
import json
import math
import unittest

from confianza import (
    CATEGORY_REVIEW_THRESHOLD,
    DEFAULT_REVIEW_THRESHOLD,
    classify_confidence,
    decidir_tier,
)
from hallazgos import construir_hallazgos


UMBRALES_ESPERADOS = {
    "dent": 0.7,
    "scratch": 0.7,
    "crack": 0.7,
    "lamp broken": 0.6,
    "glass shatter": 0.6,
    "tire flat": 0.6,
}
CLASES = {**UMBRALES_ESPERADOS, "clase desconocida": 0.8}
FUERA_DE_RANGO = (
    -0.1,
    1.1,
    math.nextafter(0.0, -math.inf),
    math.nextafter(1.0, math.inf),
)
NO_FINITOS = (math.nan, math.inf, -math.inf)
INVALIDOS = FUERA_DE_RANGO + NO_FINITOS
CONSENSOS = tuple(
    itertools.product(
        ("confirmado", "rechazado", "incierto", None),
        ("PIEZA", None),
        (True, False, None),
    )
)


def scores_validos(umbral: float) -> tuple[float | int, ...]:
    return (
        0.0, -0.0, 0, 1.0, 1,
        math.nextafter(umbral, -math.inf), umbral,
        math.nextafter(umbral, math.inf),
    )


def prediccion(indice: int, clase: str, score: float | int) -> dict:
    return {
        "instance_index": indice,
        "damage_class": clase,
        "score": score,
        "bbox_xywh": [indice, 2, 10, 20],
    }


class PruebasConfianza(unittest.TestCase):
    """Cada nombre de test referencia el AC del permalink indicado arriba."""

    def test_AC001_clasificacion_valida_y_umbrales_preservados(self) -> None:
        self.assertEqual(CATEGORY_REVIEW_THRESHOLD, UMBRALES_ESPERADOS)
        self.assertEqual(DEFAULT_REVIEW_THRESHOLD, 0.8)
        for clase, umbral in CLASES.items():
            for score in scores_validos(umbral):
                with self.subTest(clase=clase, score=score, tipo=type(score).__name__):
                    esperado = "confirmed" if score >= umbral else "needs_review"
                    self.assertEqual(classify_confidence(clase, score), esperado)

    def test_AC002_rechaza_fuera_de_rango_incluso_adyacentes(self) -> None:
        for clase, score in itertools.product(CLASES, FUERA_DE_RANGO):
            with self.subTest(clase=clase, score=score):
                with self.assertRaises(ValueError):
                    classify_confidence(clase, score)

    def test_AC003_rechaza_nan_e_infinitos(self) -> None:
        for clase, score in itertools.product(CLASES, NO_FINITOS):
            with self.subTest(clase=clase, score=score):
                with self.assertRaises(ValueError):
                    classify_confidence(clase, score)

    def test_AC004_diagnostico_en_ambas_funciones(self) -> None:
        for clase, score, funcion in itertools.product(
            CLASES, INVALIDOS, (classify_confidence, decidir_tier)
        ):
            with self.subTest(clase=clase, score=score, funcion=funcion.__name__):
                argumentos = (clase, score)
                if funcion is decidir_tier:
                    argumentos += (None, None, None)
                with self.assertRaises(ValueError) as error:
                    funcion(*argumentos)
                mensaje = str(error.exception).lower()
                for fragmento in ("score de confianza", "inválido", "debe ser finito", "[0, 1]"):
                    self.assertIn(fragmento, mensaje)

    def test_AC005_rechazo_precede_a_todo_consenso(self) -> None:
        for clase, score, consenso in itertools.product(CLASES, INVALIDOS, CONSENSOS):
            with self.subTest(clase=clase, score=score, consenso=consenso):
                with self.assertRaises(ValueError):
                    decidir_tier(clase, score, *consenso)

    def test_AC006_preserva_consenso_con_scores_validos(self) -> None:
        for clase, umbral in CLASES.items():
            for score, consenso in itertools.product(scores_validos(umbral), CONSENSOS):
                vision, pieza, regla = consenso
                with self.subTest(clase=clase, score=score, consenso=consenso):
                    confirma = (
                        score >= umbral and vision == "confirmado"
                        and pieza is not None and regla is True
                    )
                    esperado = "confirmed" if confirma else "needs_review"
                    self.assertEqual(decidir_tier(clase, score, *consenso), esperado)

    def test_AC007_preserva_hallazgos_resumen_y_json_validos(self) -> None:
        # Orden deliberadamente distinto de score/índice; expectativa del filtro
        # independiente de seleccionar_candidatos y de constantes productivas.
        casos = (
            (7, "dent", "dent", 0.9, "confirmed"),
            (2, "glass shatter", "glass_shatter", 0.45, "needs_review"),
            (9, "lamp broken", "lamp_broken", 0.6, "confirmed"),
            (3, "dent", "dent", 0.8, "confirmed"),
            (1, "dent", "dent", 0, "needs_review"),
            (6, "clase desconocida", "clase_desconocida", 1, "confirmed"),
        )
        deteccion = {
            "image_id": 42,
            "predictions": [prediccion(i, clase, score) for i, clase, _, score, _ in casos],
        }
        original = copy.deepcopy(deteccion)
        for filtrar in (False, True):
            with self.subTest(filtrar=filtrar):
                incluidos = (7, 9, 3, 6) if filtrar else (7, 2, 9, 3, 1, 6)
                findings = []
                for indice, clase, tool, score, tier in casos:
                    if indice in incluidos:
                        findings.append({
                            "finding_id": f"42-{indice}",
                            "category": clase,
                            "clase_tool": tool,
                            "score": score,
                            "score_tier": tier,
                            "confidence_tier": tier,
                            "bbox_xywh": [indice, 2, 10, 20],
                            "vision_verdict": None,
                            "pieza_id": None,
                            "severidad": None,
                            "regla_coste_aplicable": None,
                            "vision_description": None,
                            "crop_image_path": None,
                        })
                esperado = {
                    "image_id": 42,
                    "resumen_filtro_previo": {
                        "detecciones_totales": 6,
                        "candidatas": 4 if filtrar else 6,
                        "descartadas_por_clase": {"dent": 1, "glass shatter": 1} if filtrar else {},
                    },
                    "findings": findings,
                }
                resultado = construir_hallazgos(deteccion, filtrar=filtrar)
                self.assertEqual(resultado, esperado)
                self.assertEqual(json.dumps(resultado), json.dumps(esperado))
                self.assertEqual(json.loads(json.dumps(resultado)), esperado)
                self.assertEqual(deteccion, original)
                for finding in resultado["findings"]:
                    indice = int(finding["finding_id"].split("-")[1])
                    entrada = next(p for p in deteccion["predictions"] if p["instance_index"] == indice)
                    self.assertIs(finding["score"], entrada["score"])

    def test_AC007_propaga_invalidos_sin_filtro(self) -> None:
        for clase, score in itertools.product(CLASES, INVALIDOS):
            with self.subTest(clase=clase, score=score):
                deteccion = {
                    "image_id": 42,
                    "predictions": [
                        prediccion(1, "dent", 0.9),
                        prediccion(2, clase, score),
                    ],
                }
                with self.assertRaises(ValueError):
                    construir_hallazgos(deteccion, filtrar=False)

    def test_AC007_propaga_candidata_invalida_con_filtro(self) -> None:
        deteccion = {
            "image_id": 42,
            "predictions": [prediccion(1, "lamp broken", 1.1)],
        }
        with self.assertRaises(ValueError):
            construir_hallazgos(deteccion)


if __name__ == "__main__":
    unittest.main(verbosity=2)
