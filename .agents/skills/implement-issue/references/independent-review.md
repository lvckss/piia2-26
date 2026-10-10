# Revisión independiente dentro de implement-issue

Leer este archivo al ejecutar la fase 3b. Es soporte privado de esta skill, no un
protocolo público ni un orquestador por Issues. El implementador conserva la
evaluación de hallazgos, las correcciones y las operaciones GitHub.

## Runtime y aislamiento

Codex: ejecutar [review_candidate.py](../scripts/review_candidate.py), stdlib y
`codex exec`, sin dependencias. Se ensayaron procesos separados en CLI 0.162.0;
esta integración debe aportar nueva evidencia de su versión instalada. El helper
congela archivos comprometidos explícitamente seleccionados, exige árbol limpio
y cobertura de todos los paths cambiados desde la base. Identifica HEAD, tree,
hashes por archivo y agregado. No copia archivos ignorados. Excluir secretos del scope y del contexto.
Seleccionar también dependencias/contratos relevantes; un scope que omite contexto
necesario no acredita revisión aunque todos sus hashes coincidan.

Reviewer tiene solo lectura; QA escribe tests/artefactos en su copia, con fuentes
y manifiesto en solo lectura. Ambos reciben perfiles nativos sin red de comandos,
approval `never`, historial nuevo y logs de pares inaccesibles. El proceso CLI
recoge el resultado fuera del sandbox de sus herramientas: no atribuir esa
escritura del lanzador al reviewer. Hay sondas previas y dentro de cada sesión:
original absoluto, canario relativo y symlink; reviewer no crea archivos, QA sí.
Un fallo de aislamiento detiene el circuito. No usar permisos peligrosos, blanket
write sobre /tmp, retry ciego ni un fallback de roles simulados.

El launcher puede requerir salir del sandbox exterior para que Codex construya
el suyo. Usar la autorización vigente y los permisos del runtime; si no puede
hacerlo, informar el impedimento. Nunca quitar el sandbox de los workers.
El perfil permite lecturas generales para herramientas locales: no acredita
confidencialidad de todo el filesystem. No entregar secretos como contexto.

Claude: el wrapper existente carga el mismo canon. Su CLI no estuvo disponible
en el ensayo, por lo que su delegación/aislamiento nativos no están acreditados.
Puede invocar este soporte Codex si Codex está instalado y el runtime lo permite;
en ese caso identificar parent Claude/workers Codex, no llamarlo prueba nativa
Claude. Solo usar delegación nativa distinta si sus permisos, independencia,
resultados y métricas se verifican realmente; en otro caso dejar la fase pendiente.

## Invocación y contexto pequeño

Congelar en un commit local de la rama feature los cambios comprendidos antes de
revisarlos; no publicar la PR aún. Usar commits semánticos sin amend/force. El
helper no crea commits, corrige ni escribe en el checkout. Preparar un JSON
temporal fuera del repo con `plan` (permalink/versión y AC pertinentes), `files`
(paths Git exactos, incluidos cambios y dependencias), `checks` (comandos locales
requeridos separados), contratos/restricciones concisos y riesgo. No incluir chat,
conclusiones del otro rol ni todo el historial. Máximo de contexto explícito:
24.000 caracteres; prompt <=48.000. El diff/delta se entrega como archivo
de solo lectura del snapshot, no se duplica íntegro en el prompt. Si no cabe, acotar o dividir revisión
sin perder cobertura, no truncar silenciosamente. Se rechazan symlinks/submodules, archivos eliminados
y `.codex/` como scope activo para evitar carga de configuración no examinada;
estos cambios requieren revisar como datos aislados y acreditar la cobertura por
otra vía segura, no omitirlos ni declarar la entrega completa.

```sh
python .agents/skills/implement-issue/scripts/review_candidate.py \
  --repo "$PWD" --base <sha-base> --context /tmp/<contexto>.json \
  --out /tmp/<salida-nueva> --depth brief --model <modelo-disponible>
```

`brief`: 2–4 sondas útiles y revisión dirigida; `standard`: comportamiento y
regresiones adyacentes; `deep`: contratos y fallos de mayor riesgo, siempre
acotados. Documentación trivial puede usar `--roles reviewer` con
`roles_justification` en contexto explicando QA no aplicable. No usar una
exención por mero tamaño del diff ni omitir QA frente a incertidumbre funcional.
Timeout predeterminado 240 s por intento, configurable y registrado.

Salida: `summary.json`, candidata, informes por rol, eventos reales, stderr,
comandos/sondas y métricas. Exit 0 = revisiones completas sin hallazgos; 1 =
hallazgos que requieren adjudicación; 2 = circuito incompleto. Exit 0 tampoco
sustituye los AC/DoD ni el criterio del implementador. El gate contrasta informe
y eventos de ejecución; no acepta checks descritos sin ejecución real correcta,
versión equivocada, turnos fallidos, timeout, fuente alterada o QA sin exploración.
El contrato canónico exige exploración real, reproducible y ligada al candidato,
sin imponer lenguaje o runner. Este helper inicial solo acredita el ciclo estándar
de `unittest.TestCase` e `IsolatedAsyncioTestCase`. QA indica archivos nuevos en
`exploratory_tests` (paths relativos exactos); el launcher verifica su procedencia
y hashes, y ejecuta una vez [qa_unittest.py](../scripts/qa_unittest.py) con Python
local y el mismo perfil nativo QA. Sus tests deben ser importables por archivo y
usar imports absolutos desde la copia. No se ejecuta el bloque `__main__` ni se
interpreta/reproduce el comando exploratorio para acreditar tests.

El runner carga mediante `TestLoader` y ejecuta una `TestSuite` estándar con un
`TestResult` propio: registra `startTest`, `addSuccess` y `stopTest`. La clase y
el método deben estar definidos en el archivo nuevo; comprobarlo usa la API
pública `inspect.getsourcefile`, únicamente para procedencia. Clases importadas,
métodos heredados/alias de archivos existentes y procedencia ambigua no obtienen
crédito. No hay tracing, inspección de frames ni acceso a internos de unittest.
Un caso obtiene crédito solo si registra exactamente un inicio, éxito y cierre,
en una ejecución completa, con tests intactos y recibo ligado al candidato.
`completed` indica que la ejecución controlada retornó normalmente, sin errores
del runner, interrupción ni petición pública de parada (`TestResult.shouldStop`).
No exige callbacks de todos los casos cargados: los skips de fixtures pueden
dejarlos sin iniciar. Estos casos siguen visibles con sus contadores y diagnósticos
de skip, como cobertura no ejecutada; nunca reciben crédito ni invalidan por sí
solos el caso exitoso de otra clase o módulo.
Skips, expected failures, unexpected successes, errores y casos incompletos no
acreditan éxito. No se distingue por la pila preparación/cuerpo: fallos y errores
se conservan como evidencia, sin atribuirles ejecución satisfactoria.

Todos los fallos/errores/expected failures/unexpected successes recogidos por el runner se entregan
automáticamente como `runner_findings`, con ID, repro y diagnóstico, incluso ante
interrupción o si el agente informó `clear`. Son pendientes de adjudicación,
`untriaged`, no defectos automáticamente aceptados; requieren corrección o descarte
con evidencia antes de la siguiente revisión. Un caso exitoso no oculta los demás
fallos. Una ejecución sin éxito nuevo queda incompleta y conserva sus hallazgos;
estos no provocan reintentos técnicos ciegos para sustituir una corrección.

Soporte deliberadamente acotado: no `load_tests`, suites personalizadas ni overrides
de `run`, `__call__` o `id`, métodos generadores ni métodos async en `TestCase`
sin `IsolatedAsyncioTestCase`; tampoco afirmar garantías frente a manipulación
deliberada del framework por los tests. Decoradores/procedencia no confirmable y
otros runners no reciben acreditación automática. Ejecución directa, por módulo
y discovery pueden aportar evidencia exploratoria, pero ni esas formas, imports,
patrones, assertions top-level ni exit 0 sustituyen el recibo controlado.
Timeout, recibo ausente/incompleto o archivo alterado bloquean la entrega.
Mantener tests deterministas, locales y sin efectos externos; logs/request/recibo
del runner tienen prefijo separado del agente, con duración y exit propios.
No reetiquetar un check requerido como QA ni aceptar evidencia del modelo como
certificado del runner. Esta adaptación aprobada preserva AC-001–AC-008 del plan;
la evidencia histórica no acredita automáticamente un candidato refactorizado.
El timeout termina el grupo completo, incluidos descendientes resistentes a SIGTERM.

## Corrección, revalidación y coste

Agrupar duplicados y hallazgos con una misma causa antes de corregir. Reproducir
en el entorno del implementador; distinguir defecto, problema previo, entorno y
falso positivo. Registrar IDs, candidata, decisión y evidencia. Las sugerencias no
son órdenes: preservar contrato/alcance y aplicar los gates normales de cambio.
No convertir `info`, low severity o un comando con exit 0 en descarte automático.
Un hallazgo relevante aceptado y pendiente bloquea entrega.

Tras corregir y verificar tests/evals, crear commit/candidata nueva y revalidar.
Preparar un array temporal de decisiones: objetos con `role`, `finding` (ID),
`candidate` (hash anterior), `decision` (`fixed`/`rejected`) y `evidence` (repro,
resultado y referencia). No marcar `fixed` sin comprobar la corrección. Invocar
con `--previous /tmp/<salida-anterior> --decisions /tmp/<decisiones>.json`.
Cada rol recibe solo su informe anterior (incluidos sus `runner_findings`), sus decisiones y el delta; no el chat
del autor ni el informe de su par. Examinar delta, regresiones y efectos posibles;
ampliar si cambia riesgo/contrato, sin repetir exploración descartada sin evidencia.
Si el scope crece, cubrir también el contenido nuevo, no solo el delta.

Máximo inicial orientativo: dos lotes de corrección, un retry técnico por rol en
el circuito. El helper conserva intentos y acota esos contadores; una revisión
previa incompleta no justifica incrementalidad. Tras un fallo, corregir su causa
y completar el rol que falta antes de continuar. Con `--previous`, un rol
incompleto y presupuesto disponible se vuelve a ejecutar con cobertura completa,
sin usar su informe para justificar incrementalidad; el reintento queda consumido. Alcanzar límites informa/escala
y deja la entrega pendiente; no aflojar garantías para terminar. No reiniciar los
contadores creando otra salida ni ocultar un fallo anterior. Extender un presupuesto
requiere motivo explícito y límites nuevos, sin autorización implícita de scope.

Guardar usage del runtime por intento: input/output/cached tokens (cached es parte
de input, no sumarlo otra vez), duración, retry, hallazgos aceptados útiles tras
adjudicación. Ausente = null/no disponible; no estimar tokens, precio o descuentos.
La revalidación añade las contribuciones útiles fijadas con evidencia a las
métricas anteriores. Un defecto duplicado entre roles cuenta como un defecto,
aunque ambos hayan aportado evidencia. Incorporar un resumen compacto y referencias
duraderas a Issue/PR; no publicar logs crudos con datos privados ni miles de líneas.
Los resultados en /tmp pueden desaparecer: conservar evidencia pertinente antes
de interrumpir y no presentar el archivo temporal como registro durable.

Antes de presentar PR comprobar que HEAD publicado coincide con la candidata
verificada y que no hay cambios posteriores sin revisión. Si hubo cambios, revisar
su delta y volver a verificar. Aprobación humana y merge manual permanecen intactos.
