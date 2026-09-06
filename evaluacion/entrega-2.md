# Entrega 2 — Arquitectura de la solución y decisiones de implementación

En esta entrega dais el salto de *qué* construir a *cómo* lo vais a construir.
Dejáis por escrito la **arquitectura de la solución** —qué piezas la componen y
cómo se relacionan— y las **decisiones de implementación** que habéis tomado por
el camino. Documentar la arquitectura y las decisiones permite que el equipo, y
también un asistente de IA, sepa cómo encaja todo y por qué se hizo así sin
reconstruir el razonamiento en cada sesión.

## Cómo trabajar y cómo entregar

La entrega se hace por flujo de *fork* y *pull request* sobre el repositorio
de la asignatura:

1. **Haced un fork** del repositorio de la asignatura a vuestra propia cuenta.
2. En vuestro fork, dentro de la carpeta `entregas/`, **cread una carpeta para
   vuestro caso de uso** con el nombre `cu-xx-nombre-corto`, donde `xx` es el
   número de caso de uso asignado y `nombre-corto` un identificador breve en
   `kebab-case` (por ejemplo, `cu-03-deteccion-fraude`).
3. Dentro de esa carpeta va **todo el material de vuestra entrega**: el
   `ARCHITECTURE.md`, los ADRs, el `README.md` y las specs.
4. Cuando esté lista, **abrid un pull request** desde vuestro fork hacia el
   repositorio de la asignatura. Ese pull request es la entrega.

## Fecha de entrega

La entrega debe estar lista el **lunes, 16 de noviembre de 2026** (antes de las
23:59). Después de esa hora, el pull request no se considera presentado.

## Qué tenéis que entregar

Dentro de vuestra carpeta `entregas/cu-xx-nombre-corto/`, la estructura debe
incluir al menos:

```
entregas/
  cu-xx-nombre-corto/
    README.md                 ← descripción de vuestro proyecto
    ARCHITECTURE.md           ← arquitectura de la solución
    specs/                    ← especificaciones funcionales
      <funcionalidad-1>.md    ← una funcionalidad
      <funcionalidad-2>.md    ← otra funcionalidad
    decisions/
      <decision-1>.md         ← un ADR
      <decision-2>.md         ← otro ADR
```

- **1 `ARCHITECTURE.md`** con la arquitectura de la solución: un diagrama y la
  descripción de sus componentes y el flujo entre ellos.
- **Al menos 2 ADRs** en `decisions/`, cada uno documentando una decisión de
  implementación del proyecto.
- El **`README.md`** debe enlazar al `ARCHITECTURE.md` y, si procede, a los ADRs.
- **Incluir specs funcionales**: fichas que definan qué construir, por qué y con
  qué criterios de aceptación verificables.

Los nombres de fichero van en `kebab-case` (minúsculas y guiones), con una
decisión o funcionalidad por fichero.

> **La forma es vuestra.** Mientras se cubran los elementos mínimos descritos
> más abajo, tenéis libertad para estructurar el `ARCHITECTURE.md` y los ADRs
> como mejor encaje con vuestro proyecto.

## El ARCHITECTURE.md

El `ARCHITECTURE.md` es el mapa de vuestra solución: el documento que muestra
las piezas que la componen y cómo se conectan, para que alguien que llega nuevo
entienda cómo funciona el sistema por dentro sin leerse todo el código. Como
mínimo debe incluir:

- **Diagrama de arquitectura**: una representación visual de los componentes y
  sus conexiones. Podéis hacerlo de varias formas, a vuestra elección:
  - **ASCII art** directamente en el Markdown (por ejemplo, con
    [asciiflow.com](https://asciiflow.com)), lo que tiene la ventaja de versionarse como texto.
  - **Una imagen** (`.png` o `.svg`) generada con [Excalidraw](https://excalidraw.com),
    [draw.io](https://draw.io) o la herramienta que prefiráis, incrustada en el Markdown.
  - **Un diagrama [Mermaid](https://mermaid.js.org)** en un bloque de código, que GitHub
    renderiza automáticamente.
- **Descripción de los componentes**: qué es cada pieza del diagrama y de qué se
  responsabiliza (por ejemplo: ingesta de datos, almacenamiento, modelo,
  API/servicio, interfaz de usuario, orquestación...).
- **Flujo entre componentes**: cómo circula la información a través del sistema,
  de principio a fin (por ejemplo, desde que entra un dato hasta que se produce
  un resultado), explicando quién llama a quién y qué se intercambia.

El diagrama y el texto deben ser **coherentes entre sí** y coherentes con las
funcionalidades descritas en las specs de la Entrega 1: la arquitectura es la
que soporta esas funcionalidades.

## Los ADRs

Un ADR (de *Architecture Decision Record*) es un documento breve que deja
constancia de **una decisión** relevante del proyecto: qué se decidió, por qué,
qué otras opciones se barajaron y qué información es útil para llevarla a la
práctica. Sirve para que, meses después, cualquiera —incluido vuestro yo futuro
o un asistente de IA— entienda **por qué** el proyecto es como es y no tenga que
rehacer el análisis ni repetir errores ya descartados.

Las decisiones que documentéis deben ser **decisiones de implementación reales
de vuestro proyecto**. Por ejemplo: el tipo de modelo a usar, la función de
evaluación o métrica elegida, las librerías o *frameworks* principales, el
formato de almacenamiento de los datos, la estrategia de despliegue, etc.

Como mínimo, cada ADR incluye:

- **Decisión**: qué se ha decidido, enunciado de forma clara y directa (por
  ejemplo, "usaremos un modelo *gradient boosting* con XGBoost").
- **Motivación**: por qué se ha tomado esa decisión —el problema o la necesidad
  que resuelve y las razones que la justifican en vuestro contexto.
- **Alternativas**: qué otras opciones se plantearon y por qué se descartaron.
  Nombrar lo que **no** se eligió, y el motivo, es tan valioso como la propia
  decisión.
- **Referencias**: información útil para aplicar la decisión —fragmentos de
  código de ejemplo, URLs de documentación, comparativas, *benchmarks* o
  cualquier material que ayude a quien tenga que trabajar con ella.

Cada ADR va en su propio fichero dentro de `decisions/`, con un nombre en
`kebab-case` que resuma la decisión (por ejemplo,
`decisions/modelo-clasificacion.md` o `decisions/metrica-evaluacion.md`).

## Criterios de evaluación

La nota refleja **en qué grado** la entrega demuestra rigor, precisión y capacidad
de justificación en tres áreas: la claridad de la arquitectura, la solidez de las
decisiones y la coherencia global. **Todos los criterios pesan por igual**.

| Criterio | Bien hecho | Mejoras necesarias |
|---|---|---|
| **Diagrama de arquitectura** | El diagrama es legible, identifica explícitamente los componentes principales, muestra las conexiones entre ellos, y permite a un lector nuevo entender de qué se compone el sistema. Está enlazado desde el README. | El diagrama es confuso, incompleto, o tan abstracto que no comunica qué piezas tiene el sistema; falta claridad sobre qué es cada componente o cómo se conectan. |
| **Descripción de componentes y flujo** | Se explica con precisión de qué se responsabiliza cada componente del diagrama, qué datos recibe y qué produce. El flujo end-to-end (entrada → procesamiento → resultado) es trazable y coherente con las funcionalidades del proyecto. | La descripción es genérica o incompleta: no queda claro qué hace cada pieza, o no se ve cómo el flujo soporta las funcionalidades especificadas. |
| **Decisiones fundamentadas** | Cada ADR articula claramente **qué** se decidió, **por qué** (en el contexto específico del proyecto), y **qué alternativas** se consideraron y por qué no se eligieron. Las decisiones no son óbvias o triviales. | Las decisiones son superficiales, obvias ("usaremos Python porque sí"), o carecen de alternativas consideradas; la justificación no es específica del proyecto. |
| **Calidad de referencias y evidencia** | Cada ADR aporta información práctica para aplicar la decisión: fragmentos de código, URLs de documentación oficial, comparativas de herramientas, ejemplos concretos, o hallazgos de benchmarks que respaldan la elección. | Faltan referencias; la decisión se enuncia sin apoyo de evidencia ni recursos concretos para implementarla. |
| **Coherencia arquitectura ↔ proyecto** | La arquitectura es claramente la que soporta las funcionalidades del proyecto; cada decisión de implementación tiene sentido en el contexto de lo que se va a construir; no hay elementos desconectados ni decisiones que entren en conflicto. | La arquitectura parece desconectada del proyecto; hay decisiones que no se justifican en el contexto concreto o que se contradicen con las funcionalidades esperadas. |
