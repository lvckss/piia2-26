# Proyecto Integrador de IA II (PIIA2)

Repositorio de la asignatura **Proyecto Integrador de Inteligencia Artificial II**,
del primer cuatrimestre de 4º curso del Grado en Inteligencia Artificial de la
Universidad de Santiago de Compostela (ETSE).

Aquí conviven el **temario** de la asignatura, las **presentaciones** que se
usan en el aula en cada sesión y las **instrucciones de las entregas** que el
alumnado debe realizar a lo largo del curso.

## Qué es PIIA2

PIIA2 es una asignatura eminentemente práctica en la que trabajaréis **en equipo**
sobre un **reto real** propuesto por una entidad de la Red de entidades
colaboradoras de la USC para la formación en IA (Red ECIA-profesional). El
objetivo es diseñar, desarrollar y evaluar, de principio a fin, una solución
basada en IA aplicada a un problema práctico real.

Forma parte del módulo profesional que empieza en tercero con PIIA1 y desemboca
en las prácticas y la inserción laboral. Por eso el foco no está en la
complejidad técnica *per se*, sino en **generar valor real** y en trabajar
**como se trabaja fuera**: con control de versiones, seguimiento de tareas,
documentación viva y comunicación con el cliente.

## Motivación

El curso busca cerrar la distancia entre saber aplicar técnicas de IA y saber
llevar un proyecto de IA de extremo a extremo en un entorno profesional. Ya
tenéis el bagaje de *machine learning*, programación e ingeniería del software;
aquí aprenderéis lo que rodea a ese núcleo técnico y que marca la diferencia en
el mundo laboral:

- Trabajar de forma **colaborativa con Git** y flujos de *fork* y *pull request*.
- Usar el **seguimiento de tareas** como herramienta central para saber qué se
  ha hecho, qué queda y qué está bloqueado.
- Hacer **buen uso de los asistentes de IA**, produciendo documentación válida
  tanto para personas como para agentes (*spec-driven development*, ADRs).
- Conocer las **plataformas de datos** más utilizadas en la industria.
- Entender la **situación del profesional de Data & AI**, sus salidas y su
  crecimiento.

## Objetivos del curso

Al terminar el curso deberéis ser capaces de:

1. **Diseñar, desarrollar y evaluar** una solución de IA aplicada a un problema
   práctico real.
2. Trabajar bajo **tutorización dual**: el equipo docente y el tutor o tutora de
   la entidad que propone el caso de uso.
3. Entregar una **prueba de concepto o una solución completa**, según el tipo de
   proyecto.
4. **Prepararos para la inserción laboral**, adoptando prácticas y herramientas
   profesionales desde el primer día.

## Estructura horaria semanal

La asignatura combina **sesiones expositivas** (teoría de vanguardia, en formato
debate o seminario) con **sesiones interactivas** (trabajo y seguimiento del
proyecto).

- **Sesiones expositivas**: todos los **martes de 15:30 a 17:00**, únicamente
  durante las **semanas 1 a 7** (del 8 de septiembre al 20 de octubre). Después
  de octubre ya no hay expositivas: solo proyecto y seguimiento.
- **Sesiones interactivas**: comienzan la **semana del 14 de septiembre** y se
  distribuyen a lo largo de **todo el cuatrimestre**. Son el espacio de
  seguimiento del proyecto: revisiones tipo *daily* / *sprint review*,
  resolución de bloqueos técnicos y validación de decisiones de diseño.

> La franja de **19:00 a 20:00** queda reservada, pero solo se utiliza de forma
> excepcional cuando es realmente necesario.

### Calendario de sesiones expositivas

| Ses. | Fecha | Contenido |
|---|---|---|
| 1 | 8 de septiembre | Presentación, metodología y cuestionario inicial |
| 2 | 15 de septiembre | Git y seguimiento de tareas |
| 3 | 22 de septiembre | IA como asistente de desarrollo |
| 4 | 29 de septiembre | Arquitecturas y plataformas de datos |
| 5 | 6 de octubre | Mercado laboral e inserción profesional |
| 6 | 13 de octubre | Mercado laboral e inserción profesional |
| 7 | 20 de octubre | Mesa redonda con profesionales |

## Fechas importantes

Aquí están todas las fechas clave del cuatrimestre:

| Fecha | Evento |
|---|---|
| **Martes 15 de septiembre** | Publicación de los casos de uso en el Campus Virtual |
| **Domingo 19 de octubre (23:59)** | **Entrega 1** — Definición del proyecto (README + specs) |
| **Domingo 16 de noviembre (23:59)** | **Entrega 2** — Arquitectura y decisiones de implementación |
| **Viernes 18 de diciembre** | **Presentación final** ante tribunal profesional (placeholder) |

## Cómo se evalúa

La evaluación se articula en **seis componentes**, valorados por cuatro agentes
distintos:

| Peso | Componente | Quién evalúa |
|---|---|---|
| **30 %** | Valoración del tutor o tutora de la entidad | Tutor de la entidad |
| **20 %** | Presentación final ante el tribunal | Tribunal profesional externo |
| **20 %** | Seguimiento del proyecto | Equipo docente |
| **20 %** | Entregas (especificaciones y diseño técnico) | Equipo docente |
| **5 %** | Participación | Equipo docente |
| **5 %** | Evaluación por pares | Compañeros de equipo |

> **El único requisito obligatorio es el visto bueno del tutor o tutora de la
> entidad.** Sin ese visto bueno, la calificación no tiene en cuenta la
> evaluación externa y supone un suspenso automático. Además, la suma total debe
> alcanzar al menos 5 puntos para superar la materia.

### Participación y evaluación por pares

Estos dos componentes, de un 5 % cada uno, funcionan de forma particular:

- **Participación (5 %).** Empezáis el curso con el **5 % completo**: la
  participación se da por ganada. Solo se recorta si se observa **falta de
  participación en el seguimiento del proyecto**, y se valora en **ese mismo
  momento**, no como una evaluación aparte.
- **Evaluación por pares (5 %).** Es una valoración **intra-grupo y anónima**.
  Cada persona reparte **5 puntos entre sus compañeros de equipo** (no a sí
  misma). Los puntos que recibe cada estudiante se dividen por el **máximo que
  podía recibir**, de modo que la nota queda **normalizada** y el tamaño del
  equipo no influye. Un miembro que el grupo considere que no ha contribuido
  adecuadamente puede recibir 0 con independencia de la nota grupal.

Los detalles de cada componente están en los documentos de la carpeta
[entregas/](entregas/):

- **Entregas** — dos entregas documentales: la definición del proyecto
  ([entrega-1.md](entregas/entrega-1.md)) y la arquitectura y decisiones de
  implementación ([entrega-2.md](entregas/entrega-2.md)). En ellas se evalúa el
  registro del razonamiento técnico, no el volumen de documentación.
- **Presentación final** — la defensa pública del proyecto ante el tribunal
  ([entrega-3.md](entregas/entrega-3.md)).
- **Seguimiento del proyecto** — evaluación continua del tablero de tareas en las
  sesiones interactivas ([criterios-seguimiento.md](entregas/criterios-seguimiento.md)).
- **Valoración del tutor** — criterios con los que el tutor evalúa vuestro
  trabajo ([criterios-tutor.md](entregas/criterios-tutor.md)).

## Asignación de casos de uso

Los proyectos son **retos reales propuestos por las entidades colaboradoras**.
La asignación sigue este proceso:

1. **Publicación de los casos de uso** el **martes 15 de septiembre** en el
   Campus Virtual, con el detalle de cada reto y la entidad que lo propone,
   para que podáis analizarlos antes de elegir. Hay casos de uso **de
   continuación** (proyectos ya en curso) y casos de uso **nuevos** que
   arrancan de cero este curso.
2. **Formación de equipos** de **3 a 4 personas**, autoorganizados.
3. **Expresión de preferencias** de cada equipo sobre los casos de uso
   disponibles.
4. **Asignación**: si no hay conflicto entre equipos, la asignación es directa
   según las preferencias. Si varios equipos coinciden en un mismo caso, la
   entidad decide mediante una entrevista con los equipos interesados; el
   conflicto lo resuelve la entidad, no el equipo docente.

## Estructura del repositorio

| Carpeta / fichero | Contenido |
|---|---|
| `README.md` | Este documento, presentación de la asignatura. |
| `temario/` | Temario de la asignatura y presentaciones de cada tema del aula. |
| `evaluación/` | Instrucciones y criterios de las entregas, el seguimiento y la presentación final. |
| `entregas/` | Directorio donde realizar las entregas. |
