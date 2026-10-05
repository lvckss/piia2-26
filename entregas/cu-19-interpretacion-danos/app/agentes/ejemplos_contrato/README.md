# Ejemplos del contrato entre agentes

Un mismo siniestro (imagen 160, un Volkswagen Golf con póliza
`P-TR-FR300`) en cada punto de la cadena, para que cada agente se desarrolle y
se pruebe sin esperar a los otros.

| Fichero | Qué es | Cómo está hecho |
|---|---|---|
| `contexto_siniestro.json` | Entrada del siniestro: coche, taller, póliza, edad y km. | A mano. |
| `agente1_salida.json` | Lo que produce el Agente 1 (y reciben el 2 y el 3). | **A mano** (bboxes, scores y veredictos inventados, con el formato real). Mezcla 5 casos: confirmado, rechazado por la visión, pendiente por score bajo, pendiente con visión incierta y confirmado con `severidad: grave`. |
| `agente2_salida.json` | Lo que produce el Agente 2 (y recibe el 3). | **Calculado con la tool real de la empresa** (`estimar_coste`) y la lógica de cobertura de `generate_claims.py`. Solo `normativa` es un ejemplo escrito a mano (lo que devolvería el RAG). |

Las cifras de `agente2_salida.json` son una referencia: la salida del Agente 2
(sin `normativa`) tiene que coincidir con ella (ver
`../../../specs/agente2-costes-cobertura-guia.md`).

Todo es sintético salvo la legislación citada. No hay fotos en este ejemplo:
las rutas de `crop_image_path` son ilustrativas.
