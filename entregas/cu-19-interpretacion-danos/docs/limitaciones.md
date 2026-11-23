# Limitaciones conocidas del sistema

Estado: **borrador del 2026-11-23**, para el AC-009 del [plan v1.2 de la #54](https://github.com/lvckss/piia2-26/issues/54#issuecomment-7107366100) y el AC-006 del [plan de la #46](https://github.com/lvckss/piia2-26/issues/46#issuecomment-6985712887). Las cifras son del **ensayo de punta a punta del 2026-11-21** (30 imágenes de CarDD, con el RAG y el modelo reales) y de una revisión manual de 11 informes por una sola persona. **Se actualizan con la ejecución definitiva del 2026-11-27**; lo que sigue marcado «pendiente» no se ha medido todavía.

Cada limitación consta con su origen, porque no todas son nuestras:

- **Detector (PIIA 1):** el sistema de detección y segmentación que alimenta al Agente 1.
- **Modelo de visión:** la segunda opinión del Agente 1 (`gpt-6-luna`).
- **Herramienta de la empresa:** los datos y reglas de coste que entrega la empresa y que el Agente 2 usa sin modificarlos.
- **Nuestro sistema:** lo que construimos nosotros (Agentes 1 a 3, RAG, informe).
- **Datos y método:** cómo se ha probado.

## Detector (PIIA 1)

| Limitación | Evidencia | Efecto en el informe |
|---|---|---|
| Un daño que PIIA 1 no marca no llega al informe | En `dent`, `scratch` y `crack`, ni con las 5 mejores detecciones por imagen se recupera más del 26 %, 25 % y 48 % de los daños anotados ([ADR 0005](adr/0005-filtro-previo-detecciones-por-clase.md)) | El informe lo avisa («solo se analizan los daños detectados»). En la revisión de 11 informes, 4 tenían un daño visible omitido (1248, 3806, 702 y 1794) |
| Varias detecciones de un mismo daño | Tres detecciones del mismo parabrisas en 1281 y 3806; también en 2859 y 1248 | Aparecen como filas separadas. **El coste no se duplica**: en 1281 son 203,22 € con las tres detecciones y con una |

## Modelo de visión

| Limitación | Evidencia | Efecto en el informe |
|---|---|---|
| **El resultado cambia entre ejecuciones** con las mismas fotos | Tres ejecuciones sobre las mismas 30 imágenes (la versionada, la caché de octubre y la fresca del 21-nov): cambian el **23 a 25 %** de los 234 hallazgos en algún campo (veredicto 11 a 13 %, pieza 17 a 19 %, severidad 14 a 15 %) y la **categoría del vehículo en 7 de 30** imágenes. Solo 3 de 30 imágenes salen idénticas entre la caché de octubre y la ejecución fresca | Un informe puede salir distinto al regenerarlo. Las repeticiones iguales de las pruebas se deben a la caché de respuestas |
| No se puede fijar la variación con parámetros | `gpt-6-luna` rechaza `temperature=0` («solo admite el valor por defecto»); con `seed` fijo, dos ejecuciones difieren en 8 de 26 hallazgos (31 %) frente a 38 % sin fijar, en una muestra pequeña | No hay una palanca de determinismo por esta vía |
| El lado izquierdo/derecho es poco fiable | Acierto de 18 de 29 hallazgos decidibles (62 %, intervalo de Wilson 44 a 77 %). Una variante del prompt se probó y no se adoptó (22 de 29, pero 29 veredictos distintos) | Informes con lados mal asignados o con izquierda y derecha en una misma foto (2859, 381, 3020) |
| Pieza o severidad equivocadas, con tendencia a subestimar | En la revisión de 11 informes, severidad subestimada en 5 (2859, 1248, 3020, 702 y 1794), pieza mal en 1248 y dudosa en 3478 | Costes más bajos de lo que parece por la foto (1248 y 1794) |
| Confirmados con score bajo | Los umbrales calibrados en la [#44](https://github.com/lvckss/piia2-26/issues/44) dejan `dent`, `scratch` y `crack` confirmados desde 0,3. Aparecen en 8 de los 11 informes revisados | **No es un error: es el umbral elegido** con la segunda opinión del modelo. El informe muestra el score, pero no avisa de que es bajo |
| La categoría del vehículo puede ser `desconocido` | Cambia en 7 de 30 imágenes entre ejecuciones | Se usa el coche de menor coste (V14, Dacia Sandero). **Pendiente:** que el informe lo diga (AC-021 del plan v1.2) |

## Herramienta de la empresa (costes y reglas)

| Limitación | Evidencia | Efecto en el informe |
|---|---|---|
| Faltan reglas de coste para algunas combinaciones | La tabla de reglas tiene 45 reglas; no hay arañazo ni cristal roto en ópticas ni grieta en neumáticos. Las [equivalencias de la #88](adr/0008-equivalencias-reglas-coste.md) cubren solo 1 o 2 casos de las 30 imágenes | Esos hallazgos quedan «sin regla de coste» y fuera del importe, listados como «requieren revisión humana» |
| El cambio de luna se computa como mano de obra de «mecánica» | 1281 y 3806 | Categoría discutible; no se puede cambiar sin tocar los datos de la empresa |
| Reparaciones que se solapan en una misma pieza | Grieta más sustitución o pulir más pintar sobre un mismo paragolpes (2859, 82, 381 y 702) | Posible sobrecoste. **Decisión pendiente** de Lucas y Víctor: cambiar el cálculo o dejarlo como limitación |
| Franquicia, límite y matriz de coberturas | La cobertura sale de la matriz de la póliza; las fuentes del RAG solo la explican | Correcto, pero el informe todavía no lo dice. **Pendiente:** AC-019 del plan v1.2 |

## Nuestro sistema

| Limitación | Evidencia | Efecto en el informe |
|---|---|---|
| El RAG recupera fuentes poco pertinentes a veces | Búsqueda vectorial de las 4 mejores sin umbral. En 1281 salen fuentes de incendio y homologación para un cristal con póliza Terceros Básico, y en 82 la «cláusula aplicable» devuelve artículos de incendio | La justificación es fiel a los pasajes, pero no pertinente al caso. La calidad del RAG (objetivo de 23 de 25 en la [#32](https://github.com/lvckss/piia2-26/issues/32)) **todavía no está medida** |
| Un informe sin hallazgos confirmados queda casi vacío | 003637: 0 confirmados, 0 pendientes y 7 fuera del coste | Se lee como «sin información útil». **Pendiente:** que diga que no hay daños que presupuestar (AC-017) |
| Lenguaje interno y resumen poco explicativo | «PIIA 1» en los 11 informes revisados; el resumen no explica las detecciones restantes en 10 | **Pendiente:** AC-014 y AC-015 del plan v1.2 |
| Las justificaciones del LLM dependen de la comparación literal de citas | Con la regla inicial se descartaban 15 de 38 justificaciones por una mayúscula o unos asteriscos; tras la [#112](https://github.com/lvckss/piia2-26/pull/112) y la [#113](https://github.com/lvckss/piia2-26/pull/113), 38 de 38 se generan | Resuelto en esas PR. La evaluación de fidelidad (AC-011 de la #97) **está pendiente** |

## Datos y método

| Limitación | Detalle |
|---|---|
| **Muestra pequeña y no representativa** | 30 imágenes elegidas para cubrir las 6 clases con aciertos de PIIA 1; el reparto de confirmados y de necesita revisión no se puede extrapolar |
| **Los siniestros del contexto son sintéticos** | Región, taller, póliza, edad y km salen de un siniestro sintético de la empresa asignado a cada foto; no tienen relación con ella |
| **Un solo revisor** | La revisión manual la hace una persona; los ítems del protocolo la hacen repetible, pero no hay acuerdo entre revisores |
| **Revisión exploratoria sobre 11 informes** | La del 23-nov no es la evaluación: la formal, de los 10 informes de la #46 y los 10 de la #97 (15 distintos), se hace sobre la ejecución definitiva |
| **La comparación antes y después no mide por sí sola una corrección** | Dos ejecuciones del modelo difieren en torno al 25 % (ver arriba), así que no toda diferencia es efecto de un arreglo |
| **No es una tasación** | Los informes son orientativos, usan datos sintéticos y no sustituyen a una valoración pericial |

## Lo que no se ha podido medir

- La calidad de recuperación del RAG (23 de 25) y la fidelidad de las justificaciones (AC-011 de la #97).
- Las tasas de acierto del sistema completo: con 30 imágenes y un revisor solo hay indicios, no estimaciones.
- El comportamiento con fotos distintas de CarDD.
