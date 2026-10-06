# Lifecycle de desarrollo

Esta foundation documenta el proceso y proporciona templates. Los pasos y sus
comprobaciones se realizan manualmente. Las invariantes están en [AGENTS.md](../AGENTS.md).

```text
GitHub Issue → Spec → ADR → Test Plan → Planning PR → Ready
             → TDD → Implementation PR → CI / traceability / review → Done
```

| Fase | Resultado y condición para avanzar |
|---|---|
| GitHub Issue | Problema y alcance registrados con el template de Issue. Es requisito antes de cualquier código productivo. |
| Spec | Comportamiento y AC verificables con IDs estables, enlazados a la Issue. Usar el template en `docs/templates/` y guardar en `entregas/<caso>/specs/`. |
| ADR | Decisión propuesta en `docs/adr/`, enlazada a la Issue y a las Specs que cubre. |
| Test Plan | Casos, datos, entorno y comandos previstos para cada AC; puede ser una sección de la Spec o un documento versionado enlazado. |
| Planning PR | PR de documentación que revisa Spec, ADR y Test Plan. El revisor acepta explícitamente el ADR; registrar esa aceptación e integrar la PR antes de implementar. |
| Ready | Issue enlazada, Spec revisada, ADR aceptado, Test Plan que cubre todos los AC, Planning PR integrada y sin pendientes que bloqueen implementación. Registrar manualmente esta comprobación en la Issue. |
| TDD | En una nueva feature branch desde `main` con la planificación integrada, ejecutar Red → Green → Refactor por comportamiento y registrar evidencia. |
| Implementation PR | PR distinta que enlaza Issue, Spec, ADR, Test Plan y Planning PR, con tests trazables y evidencia de verificación. |
| CI / traceability / review | Revisar resultados de verificación, cobertura de AC y diff. La CI queda para una fase posterior; en esta foundation se aportan comandos y resultados manuales. |
| Done | Todos los AC verificados, evidencia revisada e Implementation PR aprobada e integrada por el equipo; cerrar entonces la Issue. |

La Planning PR debe referenciar la Issue sin cerrarla (`Refs #N`). La
Implementation PR puede usar `Closes #N`: la Issue permanece abierta durante
la implementación. Ready y Done son condiciones del proceso, sin integración
con GitHub Projects ni etiquetas automáticas.

Para la trazabilidad manual, usar siempre la ruta de la Spec junto al ID del
AC. El Test Plan relaciona AC y casos; los tests incluyen esa referencia; la
Implementation PR relaciona tests y evidencia. Para TDD, registrar el comando
y el fallo esperado en Red, el resultado en Green y la comprobación posterior
a Refactor. Indicar cualquier verificación pendiente con su motivo.

Los cambios exclusivamente documentales usan una PR documental y evidencia
de revisión de contenido, enlaces y diff. No requieren un ciclo TDD funcional
ni una Implementation PR adicional. Las specs y ejemplos existentes se
conservan; para nuevas implementaciones se completan según estas reglas.

No se incorporan en esta fase GitHub Projects, skills externas, GitHub Actions,
automatización TDD, scripts de trazabilidad ni branch protection.

Templates: [Spec](templates/spec-template.md), [ADR](adr/template.md),
[GitHub Issue](../.github/ISSUE_TEMPLATE/work-item.md) y
[Pull Request](../.github/pull_request_template.md).
