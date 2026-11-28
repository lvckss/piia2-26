# Evaluación de punta a punta con fotos reales (#46)

Plan: [v1 de la #46](https://github.com/lvckss/piia2-26/issues/46#issuecomment-6985712887). Lista fija de los 10 informes: [21-nov, antes de regenerar](https://github.com/lvckss/piia2-26/issues/46#issuecomment-7061409439). Los siniestros de contexto son **sintéticos** y no tienen relación con la foto; las cifras son orientativas.

## Ejecución evaluada

| Dato | Valor |
|---|---|
| Fecha | 2026-11-27 |
| Código | `main` `66942acfc784d67dd2f3974ff6da93fff4fc0e98` (sistema congelado desde entonces) |
| Muestra | 30 imágenes de CarDD (semilla 42), las mismas de las salidas versionadas |
| Modelo | `gpt-6-luna` (visión y justificaciones) |
| RAG | índice `text-embedding-3-small`, filtro por póliza de la #119 activado (`RAG_POLICY_TOPIC_FILTER=1`) |
| Agente 1 | Regenerado con caché nueva: **264 llamadas, 0 desde caché**, 1.305 s, código 0 |
| Informes | `evaluar_informes.py --completo --repetir`, código 0 |

Las salidas del Agente 1, los informes y la caché se conservan en local (contienen datos de la empresa y fotos de CarDD y no se versionan).

## AC-001 y AC-002 — Los 30 informes

El recorrido foto → Agente 1 → Agente 2 → Agente 3 → informe se ejecutó sin intervención manual: **30 de 30 informes, 0 errores técnicos**.

| Comprobación | Resultado |
|---|---|
| Informes generados | 30 de 30 |
| Informes con cifras que no salen del Agente 2 (`comprobar_cifras`) | 0 |
| Hallazgos del Agente 1 | 234 (737 detecciones descartadas antes por el filtro previo) |
| Confirmados | 94 |
| Pendientes de revisión | 3 |
| Fuera del coste | 137: 129 rechazados por la visión y 8 sin pieza o severidad |
| Entran por equivalencia (#88) | 0 |
| Temas del RAG con pasajes / sin pasajes / con error | 38 / 0 / 0 |
| Justificaciones (#97) generadas / descartadas / no generadas | 38 / 0 / 0 |
| Repetición con la misma entrada | 30 de 30 informes iguales |

La repetición usa las mismas salidas del Agente 1 y la caché de justificaciones, así que mide que el resto del recorrido es estable, no que el modelo lo sea: entre ejecuciones distintas el modelo de visión cambia en torno al 25 % de los hallazgos (ver [limitaciones](../limitaciones.md)).

## AC-003 — Revisión manual de los 10 informes

Revisora: **Lucía Luis Castaño**, 2026-11-28, una sola persona, con la hoja de revisión local; algunas respuestas dependen de la foto completa, de la que la hoja solo mostraba recortes. Tres respuestas se cambiaron tras releerlas con la autora el mismo día: «daños confirmados» de 001248 (por el hallazgo 1248-2, abajo) y «avisos de revisión humana» y «texto» de 000381 (contradecían la propia observación).

| Informe | Grupo | Daños confirmados | Daño principal omitido | Pieza y lado | Severidad | Importes | Avisos de revisión | Vehículo y procedencia | Texto |
|---|---|---|---|---|---|---|---|---|---|
| 000381 | demo | sí | no falta | lado mal | sí | sí | no | sí | no |
| 002859 | demo | sí | no falta | sí | sí | sí | sí | sí | no |
| 001281 | demo | sí | no falta | sí | sí | sí | sí | sí | no |
| 003806 | demo | sí | no falta | sí | sí | sí | sí | sí | no |
| 003478 | fallo conocido | sí | falta uno | sí | sí | sí | no | sí | no |
| 000702 | fallo conocido | sí | no falta | sí | subestimada | sí | sí | sí | no |
| 001248 | fallo conocido | en parte | falta uno | sí | subestimada | sí | no | sí | no |
| 001794 | control | sí | no falta | sí | subestimada | sí | sí | sí | no |
| 003020 | control | en parte | no falta | sí | sí | sí | sí | sí | no |
| 003637 | control | sí | falta uno | sí | sí | sí | sí | sí | no |

| Ítem | Resultado sobre los 10 |
|---|---|
| Daños confirmados correctos | 8 sí, 2 en parte (001248, 003020) |
| Sin daño principal omitido | 7; falta uno en 003478, 001248 y 003637 |
| Pieza y lado | 9 sí; lado mal en 000381 |
| Severidad | 7 sí; subestimada en 000702, 001248 y 001794 |
| Importes (aritmética y cobertura) | 10 sí |
| Avisos de revisión humana | 7 sí; no en 000381, 003478 y 001248 |
| Vehículo y procedencia | 10 sí |
| Texto del informe | 0 sí |

«Importes» comprueba que subtotal, IVA, total, franquicia e indemnización cuadran y que la cobertura es coherente con la póliza; no que los daños presupuestados sean los correctos.

### Observaciones por informe

- **000381:** el hallazgo 381-7 se confirma con score 0,42 sin aviso. Etiquetas internas y una línea suelta con los IDs. Importes y vehículo correctos.
- **002859:** grieta y abolladura de la aleta visibles. Confirmados del paragolpes con score de 0,34 a 0,50; 2859-19, que decide sustituir la pieza, no genera aviso.
- **001281:** parabrisas roto bien identificado. El resumen dice «no aplica» y la tabla «Pérdida total: No».
- **003806:** parabrisas roto visible. Categoría del vehículo no reconocida: se usa el de menor coste y el importe es orientativo a la baja.
- **003478:** el daño principal (óptica trasera muy rayada) no entra en el coste ni va a revisión; solo se confirma una marca leve con score 0,44.
- **000702:** el paragolpes está más dañado que «grieta / moderado» (se ve la estructura interior) y no se prevén daños asociados.
- **001248:** lateral trasero aplastado y estructura interior sin contemplar; la aleta figura como «abolladura moderada». **El hallazgo 1248-2 («óptica rota», score 0,87) es el faro de otro vehículo, aparcado al fondo**, y se presupuesta: el total es 1.184,90 € y sin él sería 973,11 € (**211,79 € de más**, calculado con la misma herramienta quitando ese hallazgo).
- **001794:** el frontal está más dañado (faro y paragolpes deformados, capó arrugado) y no se prevén daños asociados.
- **003020:** el pendiente del piloto está bien señalado; el recorte de 3020-16 parece un agujero y no un arañazo, y la rotura del paragolpes parece mayor que «grieta moderada».
- **003637:** aleta con arañazos superficiales que no se presupuestan (0 €) porque no se identificó la pieza o la severidad, aunque van a revisión humana; los descartes de grieta, abolladura y neumático son coherentes con la foto. La sección de pendientes dice «Ninguno» y a la vez avisa de dos revisiones.

## AC-004 — Antes (11-nov) y después (28-nov)

El «antes» es la [revisión de los 30 del 11-nov](https://github.com/lvckss/piia2-26/issues/54#issuecomment-6806373544), que anotó **tipos de fallo** por informe y no los ocho ítems; solo se compara lo que consta de cada informe. Son ejecuciones distintas del modelo y un formato de informe distinto, así que la comparación es descriptiva, **no sirve para estimar tasas** ni para atribuir las diferencias a las correcciones.

| Informe | 11-nov | 28-nov |
|---|---|---|
| 000381 | Sin daño omitido ni confirmado erróneo; un hallazgo real fuera del coste sin pasar a revisión | Sin daño omitido; lado mal; un confirmado dudoso sin aviso |
| 002859 | Sin daño omitido ni confirmado erróneo | Igual en los ítems de daños; fallo de texto |
| 001281 | Sin daño omitido ni confirmado erróneo; mismo daño en varias filas; descripción corrupta del modelo | Correcto salvo texto; las filas repetidas van agrupadas (#118) |
| 003806 | Sin daño omitido ni confirmado erróneo; mismo daño en varias filas | Correcto salvo texto; filas agrupadas; ahora el vehículo no se reconoce |
| 003478 | Daño principal omitido; informe a 0 € con un piloto rayado; etiqueta del detector | Sigue omitido y sin aviso |
| 000702 | Daño principal omitido; gravedad subestimada; falsos positivos | No se anota daño omitido; gravedad subestimada |
| 001248 | Daño principal omitido; hallazgo real perdido; **faro de otro vehículo cobrado** | Falta un daño; gravedad subestimada; **el faro de otro vehículo vuelve a cobrarse** |
| 001794 | Daño principal omitido; gravedad subestimada; falsos positivos | No se anota daño omitido; gravedad subestimada |
| 003020 | Dos paragolpes para uno (pieza o lado) | Pieza y lado correctos; confirmados correctos en parte |
| 003637 | Sin daño principal omitido (criterio del 11-nov); un hallazgo real fuera del coste | Se anota daño omitido: los arañazos van a revisión pero no se presupuestan |

## AC-005 — Fidelidad de las justificaciones

Es el [AC-011 de la spec 97](../../specs/97-justificacion-llm-normativa.md), sobre su propia lista de 10 informes: **11 de 11 justificaciones fieles y pertinentes**; cumple su criterio de éxito. Los tokens y el tiempo no se registraron. Tabla publicada en la #97: ENLACE_TABLA_97.

## AC-006 — Fallos y limitaciones, con su origen

| Fallo | Informes (de los 10) | Origen |
|---|---|---|
| Daño principal omitido o sin presupuestar | 003478, 001248, 003637 | Detector (PIIA 1) y modelo de visión (nuestro sistema) |
| Gravedad subestimada y sin daños asociados | 000702, 001248, 001794 | Modelo de visión y herramienta de la empresa (daños asociados solo con gravedad grave) |
| **Daño de otro vehículo presupuestado** | 001248 | Nuestro sistema: el detector marca daños reales de cualquier coche de la foto y no se comprueba a cuál pertenecen. La regla del AC-013 de la #54 solo actúa si la descripción menciona «otro vehículo» o «el fondo»; aquí dice «el SUV oscuro» |
| Lado equivocado | 000381 | Modelo de visión (nuestro sistema) |
| Confirmados con score bajo sin aviso | 000381, 002859, 003478, 001248 | Nuestro sistema: umbrales calibrados en la #44 (`dent`, `scratch` y `crack` desde 0,3) |
| Texto: etiquetas internas («score», «filtro previo», «segundo presupuesto», «V14», «D-PREMIUM») y línea suelta de IDs | los 10 | Nuestro sistema (informe) |
| Texto: «no aplica» frente a «No» en pérdida total; «pendientes: Ninguno» junto a un aviso de revisión | 001281, 003806, 003637 | Nuestro sistema (informe) |
| Vehículo no reconocido: se usa el de menor coste | 003806, 003478, 001794, 003020, 003637 (14 de los 30) | Modelo de visión; el informe lo avisa |
| Un solo revisor; siniestros sintéticos; muestra no representativa | todos | Datos y método |

La lista completa del sistema está en [limitaciones](../limitaciones.md). **Candidatos para la demo** según el criterio fijado (daños confirmados sin errores, sin daño principal omitido y vehículo reconocido): **001281** y **002859**.

## AC-007 — Repetición por otra persona

**Pendiente.** Falta que una persona distinta de quien documentó el comando lo ejecute y registre quién, en qué equipo y con qué datos. Sin clave ni red, desde `app/agentes/informes_reales/`:

```sh
python evaluar_informes.py
```

Con `--completo` (RAG y justificaciones) necesita la base de datos, el entorno del RAG y la clave.
