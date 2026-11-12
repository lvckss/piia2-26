# ADR 0008: Equivalencias versionadas para las combinaciones sin regla de coste

- Estado: Propuesto
- Fecha: 2026-11-12
- GitHub Issue: https://github.com/lvckss/piia2-26/issues/88
- Planes cubiertos (Issue/mini-spec/Spec): [entregas/cu-19-interpretacion-danos/specs/88-equivalencias-reglas-coste.md](../../specs/88-equivalencias-reglas-coste.md) — el comportamiento de los Agentes 1, 2 y 3 ante un hallazgo cuya combinación de clase, zona y severidad no tiene regla en `reglas_dano.csv`.
- Planning PR: [#89](https://github.com/lvckss/piia2-26/pull/89)
- Aceptación: <revisor y referencia de revisión; completar al aceptar>
- Sustituye / sustituido por: amplía el [ADR 0004](0004-herramienta-costes-datos-empresa.md) (punto 3 y primer coste de sus consecuencias) sin sustituirlo; el resto del 0004 sigue vigente.

## Contexto y motivación

La herramienta de costes de la empresa decide qué reparación aplicar con `reglas_dano.csv` (45 reglas: clase de daño × zona de la pieza × severidad → acción). Cuando la IA confirma un daño con pieza y severidad y la combinación no tiene regla, la herramienta devuelve coste 0 con un aviso y, según el [ADR 0004](0004-herramienta-costes-datos-empresa.md), el Agente 1 lo marca con `regla_coste_aplicable = false` y el Agente 2 lo deja fuera del coste (`sin_regla_de_coste`). Aparecen daños reales sin presupuestar: en las 500 imágenes hay 1.746 hallazgos no rechazados por la IA y 37 (2,1 %) tienen pieza y severidad pero ninguna regla, 36 de ellos confirmados; en las 30 salidas versionadas son 3 hallazgos y el informe `003478` sale a 0 € con un piloto raspado ([medición del 2026-11-12](https://github.com/lvckss/piia2-26/issues/88)).

El tutor de la entidad respondió el 2026-11-12 que los datos pueden no ajustarse del todo a las imágenes, que se pueden modificar las reglas y recomendó no presentarlas como propias en el informe. El punto 3 del ADR 0004 dice que el equipo no inventa tablas de precios, tiempos ni procedimientos de reparación, de modo que ampliar el comportamiento exige una decisión nueva, con aceptación humana.

## Decisión

1. **Tabla de equivalencias versionada** en `app/agentes/comun/equivalencias_reglas.csv`, con las columnas `clase_origen`, `zona_tipo`, `clase_destino`, `severidad_minima` y `motivo`. Una equivalencia solo se usa cuando la combinación de origen **no** tiene regla propia en la tabla de la empresa; la regla de la empresa siempre prevalece.
2. **Solo se reutilizan reglas existentes.** La regla efectiva de una combinación sin regla es la de `(clase_destino, zona_tipo, max(severidad, severidad_minima))` de la tabla de la empresa. No se crean acciones, operaciones, precios ni tiempos nuevos: el punto 3 del ADR 0004 se mantiene en lo que prohíbe y se amplía en que permite reutilizar un procedimiento existente para una combinación vecina.
3. **Se aplica donde se consumen las reglas, sin cambiar el contrato.** El Agente 1 marca `regla_coste_aplicable = true` con la regla efectiva; el Agente 2 traduce los `danos` a la clase y severidad efectivas al llamar a la herramienta y al calcular la cobertura; el Agente 3 usa la acción de la regla efectiva en el texto de la reparación. Los campos del hallazgo (`category`, `clase_tool`, `severidad` y los demás, 13 en total, [ADR 0002](0002-contrato-json-entre-agentes.md)) no cambian: el hallazgo conserva la clase detectada y la severidad que dio el modelo.
4. **Un módulo y una tabla comunes** (`app/agentes/comun/`), importados por los tres agentes, evitan que cada uno tenga su copia de la tabla.
5. **Las equivalencias iniciales** salen de la medición sobre las 500 imágenes:

   | Clase de origen × zona | Destino | Severidad mínima | Hallazgos en las 500 | Motivo |
   |---|---|---|---:|---|
   | `glass_shatter` × `optica` | `lamp_broken` | — | 14 | Todas las reglas de óptica son «sustituir»: un cristal roto de faro o piloto se sustituye como una óptica rota |
   | `lamp_broken` × `cristal` | `glass_shatter` | — | 3 | Un cristal roto etiquetado como óptica rota se trata como cristal roto |
   | `crack` × `neumatico` | `tire_flat` | `moderado` | 5 | Una grieta de neumático no se repara: la severidad leve de `tire_flat` es «reparar pinchazo», así que se parte de moderado («sustituir neumático») |
   | `lamp_broken` × `retrovisor` | `crack` | — | 2 | Un retrovisor roto etiquetado como óptica rota se trata como grieta de retrovisor («sustituir y pintar») |

6. **Sin equivalencia, siguen fuera del coste** y visibles como «requieren revisión humana»: `scratch` en cristal (7 hallazgos; la tabla de la empresa solo contempla impacto, grieta y cristal roto en cristal), `scratch` en neumático (2), `scratch` en óptica (2), `crack` en estructura (1) y `glass_shatter` en panel metálico (1).
7. **El informe no marca las equivalencias** como reglas propias (recomendación del tutor). La constancia queda en este ADR, en la tabla y en la documentación técnica.

## Alternativas consideradas

| Alternativa | Ventajas | Inconvenientes / motivo de descarte |
|---|---|---|
| **Equivalencias versionadas aplicadas por consumo (elegida)** | Reproducible y revisable; el contrato y los datos del hallazgo no cambian; la regla de la empresa prevalece; reversible borrando una fila | Los tres agentes dependen de un módulo común; hay que mantener sus pruebas |
| Mantener el ADR 0004 tal cual: dejar esos daños fuera del coste | No cambia nada; el Agente 3 los muestra como «requieren revisión humana» | 36 hallazgos confirmados por la IA sin presupuestar y informes a 0 € con daño visible; reduce el valor del sistema |
| Cambiar `clase_tool` en el Agente 1 a la clase equivalente | El Agente 2 no necesitaría cambios | Rompe la definición de `clase_tool` (la clase con guiones bajos, [AC-002 de la spec del Agente 1](../../specs/interpretacion-danos-imagen.md)), esconde la clase detectada y el informe mostraría la clase equivalente; obligaría a cambiar la severidad también para la severidad mínima |
| Añadir filas a `reglas_dano.csv` del paquete | Una sola tabla | El paquete es de la empresa y no se versiona: no es reproducible y cada persona tendría una tabla distinta |
| Modificar la herramienta de la empresa | Lo más directo | Código ajeno que no versionamos; contradice el ADR 0004 |
| Aplicarlo solo en el Agente 2 | Un solo punto | El Agente 1 seguiría marcando «sin regla» y el hallazgo no llegaría a `confirmed`; el Agente 3 no encontraría la acción de la reparación |

## Consecuencias

- **Beneficios:** 24 de los 37 hallazgos sin regla de las 500 imágenes pasan a presupuestarse; los otros 13 siguen visibles para revisión humana. La decisión queda documentada y el contrato no se toca.
- **Costes y riesgos:**
  - Los importes de los informes cambian para los hallazgos afectados; una equivalencia mal elegida sobrestima o subestima. Cada una lleva su motivo, es revisable y la severidad mínima de la grieta de neumático es un supuesto explícito.
  - El caso que motivó la Issue, el informe `003478` (arañazo en un piloto), sigue a 0 €: no se equipara un arañazo a una óptica rota porque todas las reglas de óptica son «sustituir» y se sobrestimaría el importe. Consta como limitación, no se oculta.
  - Las salidas versionadas del Agente 1 y los ejemplos del contrato que contengan hallazgos afectados cambian `regla_coste_aplicable` y `confidence_tier`; hay que actualizarlos de forma determinista, sin llamar a la API.
  - Si falta o está mal formado el CSV, los agentes fallan con un error claro en lugar de ignorar la tabla.
- **Tests y AC:** [`specs/88-equivalencias-reglas-coste.md`](../../specs/88-equivalencias-reglas-coste.md) (AC-001 a AC-009). Las pruebas existentes de los tres agentes protegen el comportamiento preservado.

## Referencias y evidencia

- Medición del 2026-11-12 sobre las 500 salidas del Agente 1 (locales, no versionadas) y `reglas_dano.csv` del paquete: 37 de 1.746 hallazgos sin regla por combinación de clase y zona (cristal roto en óptica 14, arañazo en cristal 7, grieta en neumático 5, óptica rota en cristal 3, arañazo en neumático 2, arañazo en óptica 2, óptica rota en retrovisor 2, otros 2); medido, no supuesto.
- Reglas de óptica, neumático y retrovisor de `reglas_dano.csv` (paquete de la empresa, fuera de git): todas las de óptica son «sustituir»; `tire_flat` leve es «reparar pinchazo» y moderado y grave son «sustituir neumático»; `crack` en retrovisor es «sustituir y pintar» en las tres severidades.
- Respuesta del tutor de la entidad del 2026-11-12, por correo, resumida: los datos pueden no ajustarse del todo a las imágenes y se pueden modificar las reglas.
- Decisión de Lucía Luis Castaño del 2026-11-12: la lista no necesita validación del tutor; la elabora el equipo (supuesto aceptado, revisable en la Planning PR).
