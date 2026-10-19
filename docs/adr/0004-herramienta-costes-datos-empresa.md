# ADR 0004: Costes con la herramienta y los datos de la empresa, no con precios propios

- Estado: Propuesto
- Fecha: 2026-10-19
- GitHub Issue: https://github.com/lvckss/piia2-26/issues/37
- Planes cubiertos (Issue/mini-spec/Spec): [entregas/cu-19-interpretacion-danos/specs/37-adrs-decisiones-previas.md](../../entregas/cu-19-interpretacion-danos/specs/37-adrs-decisiones-previas.md) — registro de una decisión ya vigente. La consume el plan de la #30 (`specs/30-costes-cobertura.md`) y, a través de sus cifras, el de la #31.
- Planning PR: <URL; completar al abrirla>
- Aceptación: <revisor y referencia de revisión; completar al aceptar>
- Sustituye / sustituido por: no aplica. Registra una decisión anterior sin ADR (`specs/piia2-arquitectura-multiagente.md`, versión 2; `specs/agente2-costes-cobertura-guia.md`, «Qué cambió respecto a la primera versión de esta guía»).

## Contexto y motivación

El Agente 2 tiene que convertir los hallazgos (clase de daño, pieza y severidad) en un presupuesto, y decidir pérdida total, cobertura e indemnización. En la primera versión de la arquitectura (`d890c20`), el equipo iba a inventar una tabla de precios y procedimientos sintéticos y recuperarlos con una base vectorial. Después, la empresa entregó un paquete de datos (`piia2_paquete_datos.zip`) con una herramienta de costes determinista, catálogos de vehículos, piezas y reglas, cuatro pólizas sintéticas, legislación real y 1.200 siniestros sintéticos con coste facturado para evaluar.

La decisión se usa en las guías y en el plan de la #30, pero no tiene ADR, y condiciona otras: la #28 existe porque la herramienta exige un `vehiculo_id` del catálogo.

## Decisión

1. **Coste:** se calcula con `estimar_coste(vehiculo_id, danos, region, tipo_taller, acabado, tipo_pieza)` de `piia2_paquete_datos/scripts/estimar_coste.py`, con `danos = [{clase, pieza_id, severidad}]`. Su salida se usa tal cual en `escenarios.*.estimacion` ([ADR 0002](0002-contrato-json-entre-agentes.md)).
2. **Valor venal y cobertura:** `valor_venal(vehiculo_id, edad_anios, km)` de la misma herramienta y `polizas.csv`, con las reglas de cobertura con las que la empresa generó sus siniestros (`scripts/generate_claims.py`), replicadas en código determinista.
3. **Sin precios propios:** el equipo no inventa tablas de precios, tiempos ni procedimientos de reparación. Los procedimientos son las reglas de `reglas_dano.csv` (clase × zona × severidad → acción).
4. **Traducción a cargo del equipo:** CarDD no da pieza ni severidad; obtenerlas a partir de la imagen es trabajo del Agente 1 (lo que la empresa deja explícitamente al equipo).
5. **Distribución:** el paquete no se sube a git (`.gitignore`); cada miembro lo extrae en `<raíz del repo>/piia2_paquete_datos/`.
6. **Carácter orientativo:** todo lo que no es legislación es sintético; las cifras son orientativas y no vinculantes.

## Alternativas consideradas

| Alternativa | Ventajas | Inconvenientes / motivo de descarte |
|---|---|---|
| **Herramienta y datos de la empresa (elegida)** | Determinista y ya probada por la empresa; trae evaluación (1.200 siniestros sintéticos con coste facturado); evita inventar y validar precios. | Exige un `vehiculo_id` de un catálogo de 27 modelos (ver #28); no da error ante una combinación desconocida (devuelve 0 € con un aviso). |
| Tabla de precios y procedimientos sintéticos propios, recuperados con una base vectorial (primera versión de la arquitectura) | Independiente de terceros. | Precios inventados sin forma de validarlos; trabajo duplicado; la base vectorial pasó a usarse para pólizas y legislación (#32). Sustituida al recibir el paquete. |
| Dataset sintético propio de precios por categoría de vehículo, pieza y gravedad (propuesta del equipo tras la reunión, recogida en el ADR 0001 de la [PR #29](https://github.com/lvckss/piia2-26/pull/29)) | No depende del catálogo de 27 modelos. | Abandona la herramienta y su evaluación y obliga a inventar y validar precios. |

## Consecuencias

- **Beneficios:** cifras reproducibles y comprobables; el informe (#31) puede verificar que cada importe sale de esta herramienta.
- **Costes y riesgos:**
  - Una combinación sin regla devuelve coste 0 con una línea de aviso: el Agente 1 lo marca en `regla_coste_aplicable` y el Agente 2 deja esos hallazgos fuera del coste (`sin_regla_de_coste`), para que no aparezca un daño de 0 €.
  - Si dos daños caen en la misma pieza, la herramienta se queda con el más severo; a partir de `grave` añade una diagnosis con escáner.
  - El error de la herramienta frente al coste facturado es el suelo del sistema: MAPE 9,39 % con los 249 siniestros de `val` y `test` (medido por Lucía en la revisión de la PR #40; ver `specs/30-costes-cobertura.md#AC-011`).
  - El paquete fuera de git obliga a que cada persona lo tenga extraído; las pruebas que lo usan deben avisar si falta.
- **Tests y AC:** `specs/30-costes-cobertura.md` (AC-001 a AC-007 y AC-011) usa la herramienta real como dependencia, sin simularla.

## Referencias y evidencia

- Contenido del paquete y qué es real o sintético: `piia2_paquete_datos/README.md` (fuera de git; en local tras extraer el zip).
- Firma de la herramienta (`piia2_paquete_datos/scripts/estimar_coste.py`):

  ```python
  from estimar_coste import estimar_coste, valor_venal
  estimacion = estimar_coste("V05", [{"clase": "lamp_broken", "pieza_id": "FARO_DEL_D", "severidad": "grave"}],
                             region="Madrid", tipo_taller="multimarca", acabado="metalizado", tipo_pieza="oem")
  valor_venal("V05", 3, 42000)   # 17491.54, el valor de ejemplos_contrato/agente2_salida.json
  ```

- Guía del Agente 2 con el código de referencia: [`specs/agente2-costes-cobertura-guia.md`](../../entregas/cu-19-interpretacion-danos/specs/agente2-costes-cobertura-guia.md).
- Arquitectura v2: [`specs/piia2-arquitectura-multiagente.md`](../../entregas/cu-19-interpretacion-danos/specs/piia2-arquitectura-multiagente.md), «Qué trae ya hecho el paquete de la empresa».
- Primera versión, sustituida: `git show d890c20:entregas/cu-19-interpretacion-danos/specs/piia2-arquitectura-multiagente.md`.
