# Limitaciones conocidas del sistema

Estado: **2026-11-28**, para el AC-009 del [plan v1.2 de la #54](https://github.com/lvckss/piia2-26/issues/54#issuecomment-7107366100) (con las [v1.3](https://github.com/lvckss/piia2-26/issues/54#issuecomment-7138153208) y [v1.4](https://github.com/lvckss/piia2-26/issues/54#issuecomment-7139264465)) y el AC-006 del [plan de la #46](https://github.com/lvckss/piia2-26/issues/46#issuecomment-6985712887). Las cifras son de la **ejecución definitiva del 2026-11-27** (30 imágenes de CarDD, con el RAG y el modelo reales, `main` `66942ac`), de la [evaluación de punta a punta](evidencias/46-evaluacion-punta-a-punta.md) (revisión manual de 15 informes distintos por una sola persona) y de las comparaciones controladas de la #54. Las que vienen de pruebas anteriores lo indican.

Cada limitación consta con su origen, porque no todas son nuestras:

- **Detector (PIIA 1):** el sistema de detección y segmentación que alimenta al Agente 1.
- **Modelo de visión:** la segunda opinión del Agente 1 (`gpt-6-luna`).
- **Herramienta de la empresa:** los datos y reglas de coste que entrega la empresa y que el Agente 2 usa sin modificarlos.
- **Nuestro sistema:** lo que construimos nosotros (Agentes 1 a 3, RAG, informe).
- **Datos y método:** cómo se ha probado.

## Detector (PIIA 1)

| Limitación | Evidencia | Efecto en el informe |
|---|---|---|
| Un daño que PIIA 1 no marca no llega al informe | En `dent`, `scratch` y `crack`, ni con las 5 mejores detecciones por imagen se recupera más del 26 %, 25 % y 48 % de los daños anotados ([ADR 0005](adr/0005-filtro-previo-detecciones-por-clase.md)) | El informe lo avisa («solo se analizan los daños detectados»). En la revisión definitiva falta un daño principal o su presupuesto en 3 de 10 informes (003478, 001248 y 003637; en 003637 los arañazos se detectan pero no se presupuestan) |
| Varias detecciones de un mismo daño | Tres detecciones del mismo parabrisas en 1281 y 3806; también en 2859 y 1248 | **Mejorado en la [#118](https://github.com/lvckss/piia2-26/pull/118):** los confirmados de la misma pieza y la misma reparación van en una fila (en 1281, las tres en una). Los pendientes no se agrupan, porque cada uno lleva su motivo. **El coste nunca se duplicó**: en las salidas versionadas, en 1281 son 203,22 € con las tres detecciones y con una |

## Modelo de visión

| Limitación | Evidencia | Efecto en el informe |
|---|---|---|
| **El resultado cambia entre ejecuciones** con las mismas fotos | Tres ejecuciones sobre las mismas 30 imágenes (la versionada, la del 21-nov y la definitiva del 27-nov), comparadas por parejas: cambian del **21 al 24 %** de los 234 hallazgos en algún campo (veredicto 11 a 13 %, pieza 17 a 19 %, severidad 13 a 15 %) y la **categoría del vehículo en 7 de 30** imágenes. Solo entre 2 y 5 de 30 imágenes salen idénticas | Un informe puede salir distinto al regenerarlo. Las repeticiones iguales de las pruebas se deben a la caché de respuestas |
| No se puede fijar la variación con parámetros | `gpt-6-luna` rechaza `temperature=0` («solo admite el valor por defecto»); con `seed` fijo, dos ejecuciones difieren en 8 de 26 hallazgos (31 %) frente a 38 % sin fijar, en una muestra pequeña | No hay una palanca de determinismo por esta vía. Por eso se conservan las entradas y salidas de la ejecución evaluada |
| El lado izquierdo/derecho es poco fiable | Medido antes: acierto de 18 de 29 hallazgos decidibles (62 %, intervalo de Wilson 44 a 77 %). Una variante del prompt se probó y no se adoptó (22 de 29, pero 29 veredictos distintos) | En la revisión definitiva, lado mal en 000381 |
| Severidad subestimada | En la revisión definitiva, 3 de 10 informes (000702, 001248 y 001794), sin daños asociados previstos | Costes más bajos de lo que parece por la foto |
| Confirmados con score bajo | Los umbrales calibrados en la [#44](https://github.com/lvckss/piia2-26/issues/44) dejan `dent`, `scratch` y `crack` confirmados desde 0,3. Anotados en la revisión definitiva en 000381, 002859, 003478 y 001248 | **No es un error: es el umbral elegido** con la segunda opinión del modelo. El informe muestra el score, pero no avisa de que es bajo |
| La categoría del vehículo es `desconocido` en muchas imágenes | **14 de 30** en la ejecución definitiva (11 en la versionada y 15 en la del 21-nov); 5 de los 10 informes revisados | Se usa el coche de menor coste (V14, Dacia Sandero): su valor venal y la pérdida total no son los del coche real. **El informe lo dice en la cabecera** ([#114](https://github.com/lvckss/piia2-26/pull/114) y [#115](https://github.com/lvckss/piia2-26/pull/115)). En la web, la persona elige el coche |

## Herramienta de la empresa (costes y reglas)

| Limitación | Evidencia | Efecto en el informe |
|---|---|---|
| Faltan reglas de coste para algunas combinaciones | La tabla de reglas tiene 45 reglas; no hay arañazo ni cristal roto en ópticas ni grieta en neumáticos. Las [equivalencias de la #88](adr/0008-equivalencias-reglas-coste.md) cubren solo 1 o 2 casos de las 30 imágenes | Esos hallazgos quedan «sin regla de coste» y fuera del importe, listados como «requieren revisión humana» |
| El cambio de luna se computa como mano de obra de «mecánica» | 1281 y 3806 | Categoría discutible; no se puede cambiar sin tocar los datos de la empresa |
| **La herramienta presupuesta una sola reparación por pieza y la elige por severidad, no por alcance** | Medido por Víctor en las 30 salidas versionadas ([#54](https://github.com/lvckss/piia2-26/issues/54#issuecomment-7138240559)): el coste **no suma** las reparaciones de una misma pieza (en 2859, 702 y 381 es el de la sustitución o el desabollado). Pero en **000082 y 001245** un arañazo moderado («pintar el panel») gana a una grieta leve que exige reparar el plástico, y el coste queda por debajo: **50,20 € y 41,50 € sin IVA** | **Presentación resuelta en la [#118](https://github.com/lvckss/piia2-26/pull/118):** la tabla dice cuál se presupuesta y que las demás quedan incluidas. **Limitación abierta:** cambiar la regla toca una decisión del [ADR 0004](adr/0004-herramienta-costes-datos-empresa.md) («salida tal cual»), sube cifras y no cabía antes del corte. Queda como evolución |
| Franquicia, límite y matriz de coberturas | La cobertura sale de la matriz de la póliza; las fuentes del RAG solo la explican | **Resuelto:** el informe lo dice con una frase fija antes de las fuentes (AC-019, [#114](https://github.com/lvckss/piia2-26/pull/114)) |

## Nuestro sistema

| Limitación | Evidencia | Efecto en el informe |
|---|---|---|
| El RAG puede recuperar fuentes poco pertinentes | Búsqueda vectorial de las 4 mejores sin umbral. En las pruebas anteriores, 1281 recibía fuentes de incendio y homologación para un cristal, y 82 artículos de incendio | **Corregido para los tres temas de cobertura ([#119](https://github.com/lvckss/piia2-26/pull/119), AC-024)** con un filtro que viene apagado (`RAG_POLICY_TOPIC_FILTER=1`). Activado en la ejecución definitiva: 38 de 38 temas con pasajes y, en 82 y 1281, sin incendio ni homologación. Fuera de esos tres temas la búsqueda no cambia. En 001281 y 001008 el pasaje trata de colisión y el daño es un parabrisas o un pinchazo (marcado pertinente, con ese matiz) |
| La recuperación no basta en todas las preguntas | Revisión de las 25 preguntas del [benchmark de la #32](https://github.com/lvckss/piia2-26/issues/32#issuecomment-7196320140): **23 de 25** suficientes con `small` y con `large`, hit@4 de 25 de 25. Fallan la 24 (ningún pasaje identifica la norma que reforma el baremo) y la 25 (no permiten establecer el intervalo completo de artículos 61 a 66). Se mantiene `small` por coste | Se alcanza el mínimo acordado. **Es una revisión asistida por Codex con criterio aceptado por Lucas, no una revisión humana independiente** de las 25 preguntas: Lucas juzgó la 24 y aceptó el criterio del asistente en la 25 y el resto. Encontrar la fuente correcta no garantiza que los pasajes respondan |
| Un informe sin hallazgos confirmados queda casi vacío | 003637: 0 confirmados, 0 pendientes y 7 fuera del coste, con arañazos visibles | **Mejorado (AC-017, #114):** la cobertura dice «No aplica: no hay daños que presupuestar» y 2 detecciones van a revisión humana. Sigue siendo un informe sin daños presupuestables |
| **Se presupuestan daños de otro vehículo** | En 001248, el hallazgo 1248-2 es el faro de un coche aparcado al fondo y entra en el coste: 211,79 € de 1.184,90 €. La regla del AC-013 de la #54 solo actúa si la descripción sitúa el daño en «otro vehículo» o en «el fondo»; aquí decía «el SUV oscuro» | El importe puede incluir daños ajenos al siniestro. Nada comprueba a qué vehículo pertenece cada detección; requiere revisión humana |
| Texto del informe: etiquetas internas e incoherencias | «PIIA 1» y otras jergas se corrigieron en la [#114](https://github.com/lvckss/piia2-26/pull/114) ([comparación controlada](https://github.com/lvckss/piia2-26/issues/54#issuecomment-7137773223): «PIIA» de 31 informes a 0, sin cambiar importes). La revisión definitiva aún anota «score», «filtro previo», «segundo presupuesto», «V14», «D-PREMIUM», una línea suelta de IDs, «no aplica» frente a «No» en la pérdida total y «pendientes: Ninguno» junto a un aviso | Los 10 informes revisados tienen algún fallo de texto. No se han visto diferencias en las cifras por ello |
| Fidelidad de las justificaciones del LLM, medida en pequeño | Definitiva: 38 de 38 generadas; en los 10 informes del [AC-011 de la #97](https://github.com/lvckss/piia2-26/issues/97#issuecomment-7239125068), 11 de 11 fieles y pertinentes. En 000381, 002536 y 002632 el fragmento citado no incluye la letra b) del art. 36 (el contenido es correcto). Citas con cifras: de 3 a 11 de 22 en la [comparación controlada](https://github.com/lvckss/piia2-26/issues/54#issuecomment-7161287415) | Cumple el criterio, con una sola revisora y 11 textos. No se registraron tokens ni tiempo |

## Web de peritaje (#34)

La demo web ([#117](https://github.com/lvckss/piia2-26/pull/117)) está integrada y validada a mano por Lucas ([evidencia](https://github.com/lvckss/piia2-26/issues/34#issuecomment-7196507258)): usa las **detecciones ya exportadas** de 500 imágenes de CarDD y llama al modelo de visión real; no ejecuta el detector. La Issue **sigue en curso** porque falta acreditar parte de la Spec v1.7:

| Pendiente | Qué falta |
|---|---|
| Despliegue conjunto (AC-013) | Compose con todos los servicios, preparación, salud y reinicio. Hoy `compose.yaml` solo tiene PostgreSQL |
| Integración real documentada (AC-014) | Tabla de 3 a 5 imágenes identificadas y leídas, con configuración y resultados. La validación de varias imágenes no anotó sus IDs |
| Imagen nueva | El recorrido foto → detector real → agentes → informe no está acreditado; la demo documental lo deja aparte |
| Limpieza tras una caída (AC-012) | Evidencia de que los temporales se retiran al reiniciar tras una terminación abrupta |
| RAG real en la web | La integración de la web con el RAG autorizado y la cobertura final del servidor |

## Datos y método

| Limitación | Detalle |
|---|---|
| **Muestra pequeña y no representativa** | 30 imágenes elegidas para cubrir las 6 clases con aciertos de PIIA 1; el reparto de confirmados y de necesita revisión no se puede extrapolar |
| **Los siniestros del contexto son sintéticos** | Región, taller, póliza, edad y km salen de un siniestro sintético de la empresa asignado a cada foto; no tienen relación con ella |
| **Un solo revisor** | La revisión manual la hace una persona; los ítems del protocolo la hacen repetible, pero no hay acuerdo entre revisores |
| **Revisión sobre 15 informes distintos** | 10 de la #46 y 10 de la #97; la hoja mostraba recortes y algunas respuestas dependen de la foto completa. No sirve para estimar tasas |
| **La comparación antes y después no mide por sí sola una corrección** | Dos ejecuciones del modelo difieren en algo más de un 20 % (ver arriba), así que no toda diferencia es efecto de un arreglo. Por eso las correcciones se miden con las mismas entradas guardadas (informe y citas) y la comparación entre ejecuciones distintas es solo descriptiva |
| **La comparación de las citas cuenta casos de tema y póliza** | 11 casos con respuesta guardada del modelo, no las 38 justificaciones de los 30 informes |
| **No es una tasación** | Los informes son orientativos, usan datos sintéticos y no sustituyen a una valoración pericial |

## Lo que no se ha podido medir

- La fidelidad de las justificaciones fuera de los 10 informes revisados, y su coste en tokens y tiempo.
- Una revisión humana independiente de la calidad del RAG (la de las 25 preguntas es asistida).
- Los pendientes de la web de la tabla anterior.
- El efecto del filtro de la #119 sobre el texto del modelo frente a no usarlo (no se generaron las dos versiones en la misma ejecución).
- Las tasas de acierto del sistema completo: con 30 imágenes y un revisor solo hay indicios, no estimaciones.
- El comportamiento con fotos distintas de CarDD.
