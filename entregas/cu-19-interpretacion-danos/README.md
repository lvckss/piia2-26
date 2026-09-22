# CU-19 — Interpretación de daños en vehículos

## Qué es el proyecto

Este proyecto continúa el trabajo realizado en PIIA1 sobre segmentación de daños
en vehículos. Su objetivo es construir una prueba de concepto capaz de recibir
una imagen de un vehículo y producir una interpretación estructurada de los
daños visibles: tipo de daño, localización, región afectada y evidencia visual
que permita revisar el resultado.

La solución combinará el pipeline de visión basado en SAM3 desarrollado durante
la etapa anterior con componentes de interpretación multimodal. El resultado se
orienta a asistir a una persona técnica durante la inspección, no a sustituir su
criterio profesional.

## Motivación

La inspección manual de imágenes de vehículos requiere tiempo y puede variar
entre personas. El proyecto busca estudiar hasta qué punto una solución de IA
puede convertir una imagen y sus segmentaciones en información consistente,
trazable y útil para apoyar ese proceso.

Al finalizar el proyecto se pretende disponer de una demostración reproducible,
con una interfaz sencilla y un protocolo de evaluación que permita conocer no
solo los aciertos del sistema, sino también sus errores y limitaciones.

## Alcance

El proyecto incluye:

- recepción y validación de imágenes de vehículos;
- detección o segmentación de daños mediante el pipeline de visión existente;
- asociación de cada daño con su región o parte visible del vehículo;
- generación de una interpretación estructurada y revisable;
- visualización de máscaras, regiones y resultados sobre la imagen original;
- evaluación cuantitativa y análisis de errores sobre conjuntos de datos
  versionados;
- registro de la configuración, métricas y procedencia de cada resultado.

Quedan fuera del alcance inicial:

- una tasación económica vinculante;
- la aprobación o rechazo automático de reparaciones o indemnizaciones;
- la identificación de propietarios, matrículas o personas;
- una aplicación preparada para uso comercial sin supervisión humana;
- garantizar resultados fiables en imágenes o tipos de daño no representados
  en los datos de evaluación.

## Equipo

| Integrante | Rol inicial | Contacto |
|---|---|---|
| Lucía Luis Castaño | Desarrollo e investigación de IA | lucia.luis.castano@rai.usc.gal |
| Víctor Hidalgo Carreira | Desarrollo e investigación de IA | victor.hidalgo@rai.usc.gal |
| Lucas García Ruiz | Desarrollo e investigación de IA | lucas.garcia0@rai.usc.es |

Los roles son iniciales y podrán concretarse conforme se repartan las
responsabilidades de producto, datos, modelos e integración.

## Estructura

```text
cu-19-interpretacion-danos/
├── README.md
├── specs/
│   ├── interpretacion-danos-imagen.md
│   └── evaluacion-trazabilidad.md
└── app/
    ├── frontend/
    ├── server/
    ├── ml/
    ├── bd/
    └── docker/
```

- `README.md`: presenta el problema, la motivación, el alcance y el equipo.
- `specs/interpretacion-danos-imagen.md`: define el flujo funcional que
  transforma una imagen en una interpretación estructurada.
- `specs/evaluacion-trazabilidad.md`: define cómo se evaluarán, compararán y
  rastrearán los resultados del sistema.
- `app/`: contiene el código fuente de la aplicación heredada de PIIA1,
  organizado por capas. Su propio [README](app/README.md) explica cómo se
  ejecutan el frontend, el backend y el pipeline ML.
