# Entrega 1 — Definición del proyecto (README + specs)

En esta primera entrega dejáis por escrito de qué va vuestro proyecto y qué
funcionalidades lo componen. Todavía no construís el proyecto:
el objetivo es tener definido el caso de uso y, en formato *spec*, la definición
funcional de cada funcionalidad. Documentar antes de programar permite que el
equipo, y también un asistente de IA, sepa qué hay que hacer sin reconstruir el
contexto en cada sesión.

## Cómo trabajar y cómo entregar

La entrega se hace por flujo de *fork* y *pull request* sobre el repositorio
de la asignatura:

1. **Haced un fork** del repositorio de la asignatura a vuestra propia cuenta.
2. En vuestro fork, dentro de la carpeta `entregas/`, **cread una carpeta para
   vuestro caso de uso** con el nombre `cu-xx-nombre-corto`, donde `xx` es el
   número de caso de uso asignado y `nombre-corto` un identificador breve en
   `kebab-case` (por ejemplo, `cu-03-deteccion-fraude`).
3. Dentro de esa carpeta va **todo el material de vuestra entrega**: el
   `README.md` y las specs.
4. Cuando esté lista, **abrid un pull request** desde vuestro fork hacia el
   repositorio de la asignatura. Ese pull request es la entrega.

## Fecha de entrega

La entrega debe estar lista el **lunes, 19 de octubre de 2026** (antes de las
23:59). Después de esa hora, el pull request no se considera presentado.

## Qué tenéis que entregar

Dentro de vuestra carpeta `entregas/cu-xx-nombre-corto/`, al menos esta
estructura:

```
entregas/
  cu-xx-nombre-corto/
    README.md                 ← qué es el proyecto
    specs/
      <funcionalidad-1>.md   ← una funcionalidad
      <funcionalidad-2>.md   ← otra funcionalidad
```

- **1 `README.md`** que responda "de qué va el proyecto".
- **Al menos 2 specs** en `specs/`, cada una con la definición funcional de una
  funcionalidad y sus criterios de aceptación.

Los nombres de fichero van en `kebab-case` (minúsculas y guiones), con una
funcionalidad por fichero.

> **La forma es vuestra.** Mientras se cubran los elementos mínimos descritos
> más abajo, tenéis libertad para estructurar el README y las specs como mejor
> encaje con vuestro proyecto.

## El README

El README es la puerta de entrada al proyecto: el documento que da la visión
de conjunto de qué es, para qué sirve y cómo se organiza. Debe permitir que
alguien que llega nuevo entienda el proyecto sin preguntaros nada. Como mínimo:

- **Qué es**: un párrafo que diga qué es el proyecto y qué problema resuelve.
- **Motivación**: por qué habéis escogido este proyecto y qué queréis conseguir
  al terminarlo.
- **Alcance**: qué entra en el proyecto y qué queda explícitamente fuera.
- **Equipo**: quién sois, con el rol y el correo de contacto de cada persona.
- **Estructura**: explica qué contiene cada carpeta y fichero de tu repositorio
  (dónde está el README, dónde están las specs, qué hay dentro de cada una).

## Las specs

Una spec (de *specification*) es el documento donde se especifica **qué
construir, por qué y con qué criterios**. No se queda en nombrar la
funcionalidad: captura la **intención** que hay detrás —el problema real que
resuelve y el resultado que se busca— y baja al detalle de qué debe hacer, sus
restricciones y sus criterios de aceptación.

Una buena spec **explica qué queremos y por qué**, y concreta lo suficiente para
que otra persona —o un asistente de IA— construya la funcionalidad sin adivinar.
Sirve de **brújula**: cuando durante la implementación surge una duda, la spec
es lo que permite decidir sin reabrir la conversación. Como mínimo, cada spec
incluye:

- **Qué construir**: la funcionalidad a desarrollar descrita con precisión, incluyendo qué
  hace y dónde encaja en el sistema.
- **Por qué**: la intención detrás de la funcionalidad, el problema que resuelve
  y el resultado que se persigue. Es lo que da sentido a las decisiones y actúa
  de brújula ante las dudas.
- **Restricciones**: límites y condiciones que la funcionalidad debe respetar
  (rendimiento, validaciones, casos límite, dependencias, supuestos).
- **Criterios de aceptación**: condiciones **verificables** que permiten decir
  que la funcionalidad cumple lo especificado. Redactadlas de forma observable
  y precisa. Por ejemplo, "el modelo alcanza ≥0.80 de F1 en el set de test"
  resulta comprobable, mientras que "el modelo funciona bien" queda abierto a
  interpretación.

## Criterios de evaluación

La nota refleja **en qué grado** la entrega demuestra rigor, claridad y capacidad
de especificación en dos áreas: la definición del proyecto y la precisión de las
funcionalidades. **Todos los criterios pesan por igual**.

| Criterio | Bien hecho | Mejoras necesarias |
|---|---|---|
| **Claridad del proyecto** | El README comunica de forma inequívoca qué es el proyecto, qué problema resuelve, por qué es interesante y a quién va dirigido. Un lector nuevo entiende sin ambigüedad la misión del proyecto. | El proyecto es vago o genérico; no queda claro qué es exactamente, qué problema resuelve específicamente, o por qué es relevante. |
| **Definición del alcance** | El README delimita con precisión qué entra en el proyecto y, igual de importante, qué queda explícitamente fuera. El lector entiende los límites del problema a resolver. | El alcance es difuso o incompleto; no se sabe dónde termina el proyecto o qué está fuera de él; hay elementos ambiguos. |
| **Intención y precisión de las specs** | Cada spec articula claramente **qué** hay que construir (descripción precisa de la funcionalidad, no solo su nombre) y **por qué** (el problema que resuelve, el beneficio esperado). Las restricciones y supuestos están explícitos. | Las specs son superficiales o solo nombran funcionalidades sin explicar qué hacen realmente ni por qué importan; faltan restricciones o supuestos. |
| **Verificabilidad de criterios de aceptación** | Los criterios de aceptación de cada spec son **observables y comprobables**: alguien que no es del equipo puede verificar si la funcionalidad cumple o no. Evitan términos vagos como "bien", "suficientemente", "adecuadamente". | Los criterios son subjetivos, circulares o no verificables ("el modelo debe ser bueno", "debe funcionar correctamente"); no permiten una evaluación objetiva. |
| **Coherencia interna** | Las funcionalidades de las specs se derivan lógicamente del alcance definido en el README; cada una tiene sentido en el contexto del proyecto; no hay funcionalidades aisladas o que se contradigan; el equipo y el caso de uso forman un todo coherente. | Las specs parecen desconectadas entre sí o del proyecto; hay funcionalidades que no encajan con el alcance; el proyecto parece una colección de ideas sin hilo conductor. |
