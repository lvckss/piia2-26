# Spec: <nombre de la funcionalidad>

<!-- Copiar a entregas/<caso>/specs/<nombre-kebab-case>.md.
     Sustituir placeholders y eliminar instrucciones antes de revisión. -->

- GitHub Issue: <URL>
- Estado: Borrador / Revisada (elegir uno)
- ADRs que cubren la implementación: <rutas y estado; deben estar Aceptados antes de implementar>
- Planning PR: <URL; completar al abrirla>

## Qué construir

<Comportamiento esperado, entradas y salidas, y dónde encaja en el sistema.>

## Por qué

<Problema, usuarios afectados y resultado que se persigue.>

## Alcance

- Incluido: <comportamientos cubiertos por esta Spec>
- Fuera de alcance: <límites explícitos>

## Restricciones y supuestos

<Validaciones, casos límite, errores, dependencias, compatibilidad y rendimiento.
Para IA: datos/partición, protocolo, métricas y umbrales verificables.>

## Acceptance Criteria

<!-- Un resultado observable por fila. Mantener los IDs estables; no renumerar
     ni reutilizar un ID retirado. Evitar criterios como “funciona bien”. -->

| ID | Dado / Cuando | Resultado esperado y condición de éxito |
|---|---|---|
| AC-001 | <entrada o precondición y acción> | <resultado observable, umbral o tolerancia> |
| AC-002 | <entrada inválida o caso límite y acción> | <error o comportamiento verificable> |

## Test Plan

<!-- Plan manual dentro de la Spec o enlace a un documento versionado.
     Cubrir todos los AC antes de Ready. Los tests se escriben durante TDD. -->

| Referencia (ruta de Spec + AC) | Caso de prueba y nivel | Datos / entorno | Comando o pasos previstos |
|---|---|---|---|
| <ruta de esta Spec>#AC-001 | <caso; unitario/integración/end-to-end> | <fixture o dataset y versión> | <comando o pasos reproducibles> |
| <ruta de esta Spec>#AC-002 | <caso negativo> | <entrada inválida> | <comando o pasos reproducibles> |

## Pendientes para Ready

<Preguntas y dependencias que bloquean implementación. Resolverlas en la
Planning PR; “ninguno” solo cuando se hayan resuelto.>
