# Entrega 3 — Presentación final del proyecto

En esta última entrega no documentáis el proyecto: lo **contáis**. Preparáis la
**presentación final** con la que defenderéis vuestro trabajo ante el resto de
la clase y el profesorado. Es el momento de comunicar, en pocos minutos y de
forma convincente, qué problema abordasteis, cómo lo resolvisteis y qué
habéis conseguido.

A diferencia de las entregas anteriores, aquí **el contenido y el formato son
libres**: cada equipo decide cómo estructurar y diseñar su presentación. Lo que
se fija son unos mínimos de contenido, la duración y las condiciones de entrega.

## Dónde y cómo se presenta

La presentación se realiza de forma **presencial en el Salón de Actos de la
ETSE**. Proyectaréis desde el **ordenador de presentación del propio salón**,
así que vuestro fichero debe estar en un **formato compatible** con ese equipo.
Para evitar sorpresas:

- Entregad la presentación en un formato estándar y portable (por ejemplo,
  **PDF**, que se abre en cualquier equipo sin depender de fuentes ni software
  concreto). Si usáis PowerPoint, Keynote, Google Slides u otra herramienta,
  **exportad también una versión PDF** como salvaguarda.
- Si vuestra presentación incluye vídeo, audio o una demo en vivo, **comprobad
  con antelación** que funcionará en el equipo del salón y llevad una
  alternativa (por ejemplo, un vídeo grabado de la demo) por si algo falla.
- Incrustad las fuentes o usad tipografías estándar para que el diseño no se
  rompa en otro equipo.

## Cómo entregar

La entrega se hace por flujo de *fork* y *pull request* sobre el repositorio
de la asignatura, igual que las entregas anteriores:

1. **Haced un fork** del repositorio de la asignatura a vuestra propia cuenta.
2. En vuestro fork, dentro de la carpeta `entregas/`, usad **la misma carpeta de
   vuestro caso de uso** que en las entregas previas: `cu-xx-nombre-corto`,
   donde `xx` es el número de caso de uso asignado y `nombre-corto` un
   identificador breve en `kebab-case`.
3. Dentro de esa carpeta, cread una subcarpeta `presentacion/` con **el fichero
   de la presentación** (y los recursos que necesite, como el vídeo de la demo).
4. Cuando esté lista, **abrid un pull request** desde vuestro fork hacia el
   repositorio de la asignatura. Ese pull request es la entrega.

La estructura queda así:

```
entregas/
  cu-xx-nombre-corto/
    presentacion/
      presentacion.pdf        ← la presentación (formato portable)
      demo.mp4                 ← opcional: vídeo de respaldo de la demo
```

## Fecha de presentación y entrega

Las presentaciones se realizarán **durante la semana del 14 de diciembre de 2026**.
Cada equipo elige la **fecha exacta de su presentación** dentro de esa semana,
sujeto a disponibilidad del Salón de Actos y coordinación con los demás equipos.

Debéis entregar una **versión de la presentación con al menos dos días de
antelación** a la fecha de vuestra presentación. Esa versión es la que cuenta
como entrega en plazo.

Podéis **seguir actualizándola hasta el mismo día de la presentación**: los
cambios posteriores a la entrega en plazo son bienvenidos y no penalizan,
siempre que la versión inicial se haya subido a tiempo. La idea es que nadie
llegue al día de la presentación sin nada entregado, pero que tengáis margen
para pulir los últimos detalles.

## Qué tiene que contener la presentación

La presentación tiene una **duración máxima de 10 minutos**. Ajustad el número
de diapositivas y el nivel de detalle a ese tiempo: es preferible contar bien
tres cosas que atropellar diez. Como mínimo, debe incluir:

- **Motivación del proyecto**: qué problema resuelve y por qué es interesante.
  Que el público entienda, sin conocer el proyecto de antes, por qué merece la
  pena lo que habéis hecho.
- **Solución propuesta**: cómo lo habéis abordado. Una visión clara de la
  aproximación y de las piezas principales de la solución, sin necesidad de
  entrar en todo el detalle técnico.
- **Muestra del resultado**: la evidencia de lo que habéis conseguido. Según el
  tipo de proyecto:
  - En proyectos de **ámbito más científico**, presentad la **evaluación con
    métricas**: qué medisteis, con qué datos y qué resultados obtuvisteis
    (por ejemplo, la métrica de vuestro modelo sobre el conjunto de test).
  - En proyectos de **ámbito más producto**, presentad una **demo**: una
    muestra del sistema funcionando que deje ver qué hace y cómo se usa.

> **La forma es vuestra.** Mientras se cubran estos mínimos de contenido, se
> respete la duración y el formato sea compatible con el equipo del salón,
> tenéis total libertad para diseñar y estructurar la presentación como mejor
> represente vuestro trabajo.

## Criterios de evaluación

La presentación será **evaluada por un tribunal profesional externo** a la
asignatura, ante el cual defenderéis vuestro trabajo. La nota refleja **en qué
grado** la presentación comunica con claridad y rigor el trabajo realizado y en
qué grado el equipo lo defiende ante el tribunal, en cinco áreas. **Todos los
criterios pesan por igual**.

| Criterio | Bien hecho | Mejoras necesarias |
|---|---|---|
| **Contextualización y motivación** | La presentación explica con claridad qué problema aborda el proyecto, por qué es relevante resolverlo y en qué entorno se aplica la solución. El público entiende, sin conocimiento previo, por qué el trabajo merece la pena. | La motivación es vaga o se da por supuesta; no queda claro qué problema se resuelve, por qué es relevante ni dónde se aplica la solución. |
| **Justificación y adecuación de la solución** | La aproximación y las piezas principales de la solución se explican de forma clara, y las decisiones técnicas se sustentan con argumentos sólidos y coherentes con el problema identificado. | La solución se describe de forma confusa o superficial; las decisiones técnicas no se justifican o no encajan con el problema planteado. |
| **Análisis y demostración del resultado** | Se muestra evidencia concreta de lo conseguido —métricas de evaluación o una demo funcional—, con un análisis de calidad de los resultados y una identificación honesta de las limitaciones de la solución. | No hay evidencia real del resultado, o la que se presenta no se analiza; no se reconocen las limitaciones ni se valora si el proyecto cumple lo propuesto. |
| **Adecuación de respuestas ante el tribunal** | Las respuestas a las preguntas del tribunal demuestran rigor, conocimiento del trabajo y actitud crítica, abordando las cuestiones con solvencia y honestidad. | Las respuestas son imprecisas, evasivas o revelan desconocimiento del propio trabajo; no se afrontan las preguntas con actitud crítica. |
| **Claridad de la exposición** | La presentación está bien estructurada, es visualmente clara y profesional, y se ajusta a los 10 minutos, con un ritmo que permite seguirla sin atropellamientos ni tiempos muertos. | La presentación se excede o se queda muy corta en el tiempo, va desordenada, o el soporte visual y la comunicación oral dificultan seguir el hilo. |
