# AC-024: filtro de cobertura por póliza y tema

Plan: [#54 v1.5, AC-024 y precisión de AC-008](https://github.com/lvckss/piia2-26/issues/54#issuecomment-7140196344).
Ejecución: [slice 12](https://github.com/lvckss/piia2-26/issues/54#issuecomment-7140217985).
Base: `main` `7cff307c3838b73e97064b3ae95ef33dfeadfac2`.
Resultado de la comparación: [benchmark antes/después](54-rag-pertinencia-benchmark.csv).

## Problema reproducido y cambio

Con `small`, el tema automático de cristales de 1281 recupera primero un
fragmento de homologación; la primera sección de la póliza queda en el puesto 7.
Para «cláusula aplicable» (1281 y 82), el primer resultado es el artículo 46
de la Ley de Contrato de Seguro sobre incendio; la primera sección de póliza
queda en el puesto 10. La exclusión pertinente tiene peor distancia que el
artículo ajeno: un umbral no separa estos resultados y reordenar el top-4 pierde
las cláusulas que ya quedaron fuera.

`RAG_POLICY_TOPIC_FILTER=1` limita antes del ranking los tres temas automáticos
de cobertura a las secciones 2/3 de la póliza seleccionada. Mantiene coseno,
desempate por ID, k máximo, cotejo literal y firma pública. No rellena con
legislación. Sin activar el mecanismo, o ante otro tema/póliza vacía, se
conserva el comportamiento anterior. No modifica índice, cálculos ni redactor.

## TDD y PostgreSQL aislada

Comandos desde la carpeta del caso, con las dependencias de `requirements-rag.txt`:

```sh
.venv-rag/bin/python app/agentes/agente_recuperacion/probar_rag.py --postgres
.venv-rag/bin/python app/agentes/agente_recuperacion/probar_indexado.py --postgres
```

Los tests crean y retiran una PostgreSQL Docker desechable. No usan la URL real
como `RAG_TEST_DATABASE_URL` ni pagan embeddings.

- Red, antes del cambio productivo: 25 tests, **38 fallos de comportamiento**,
  sin errores de importación. El artículo ajeno gana por distancia y el filtro
  aún no existe; también falla la devolución vacía sin pagar y el cotejo de un
  pasaje pertinente alterado.
- Green: **25/25 tests de búsqueda**, incluidas las integraciones. Cobertura de
  cuatro pólizas, tres temas, k=1/4/100, desempates, literalidad, secciones ausentes,
  desactivación y consultas no afectadas, póliza inválida y pasajes corruptos.

Regresión final ejecutada con Python 3.12 y los datos locales de la empresa:

| Comando / suite | Resultado |
|---|---|
| `probar_indexado.py --postgres` | 18/18, PostgreSQL desechable |
| `probar_costes.py` | 13/13 |
| `probar_agente2.py` | 10/10 |
| `probar_justificacion.py` | 14/14 (base sin #113; no hay dependencia de esa PR) |
| `probar_informe.py` | 38/38 |
| `probar_informes_reales.py` | 12/12 |
| `probar_evaluar_informes.py` | 13/13 |
| `probar_agente1_stub.py`, `probar_vision_stub.py`, `probar_vehiculo_stub.py` | OK; vehículo 10 pruebas |
| `probar_lote_stub.py` | OK, incluidas las 30 salidas versionadas; subprueba opcional de fotos/detecciones locales omitida por no estar disponibles en la copia aislada |
| `python scripts/verificar_entrega.py comprobar` | AC-001/002/004 OK |
| `git diff --check` | OK |

Las suites `probar_*.py` se ejecutan desde su directorio de componente. No se
ejecutó visión/redacción de pago ni se alteró la caché de calibración. La revisión
humana del texto de las nuevas justificaciones corresponde a la ejecución final.

## Evaluación controlada real

Corpus SHA-256: `f493d6494e41c24c43b127a37e1930d6e19e4fd0426520b190be7f129189cb5c`.
CSV de preguntas SHA-256: `4f9e629a317885f3c83559ca81b4d2ca476eb45aa0c6473b8a0adb4d97591369`.
Protocolo: `articles-policy-sections-char1500-overlap200-title-v1`.
Dos generaciones activas, 2.032 fragmentos y 11 documentos por modelo; small
1.536 dimensiones y large 3.072. Las generaciones exactas se comprueban contra
el baseline antes de evaluar.

El baseline pagado conserva los 30 textos de consulta (25 preguntas y cinco
temas automáticos), sus vectores, pasajes y fuentes. Dos llamadas, 725 tokens
por modelo, coste estimado total 0,00010875 USD con las tarifas configuradas en
el repositorio; no es una factura ni una actualización de tarifas. No se usa
el gold para recuperar: el producto se resuelve por su nombre en la pregunta,
como exige el protocolo de #32.

La reevaluación llama al **NormativaRetriever y agente2 reales**, con el filtro
apagado/encendido y el mismo corpus, consulta y vector. Los únicos elementos
simulados son el proveedor de embeddings (reproduce el vector ya pagado) y la
frontera de conexión del buscador en la composición (inyecta ese retriever).
PostgreSQL exige `default_transaction_read_only=on`. No hay API de embeddings
ni LLM, y el redactor de informes sigue siendo determinista.

| Comprobación | small | large |
|---|---:|---:|
| hit@4 antes | 25/25 | 25/25 |
| hit@4 después | 25/25 | 25/25 |
| Preguntas con pasajes y fuentes exactamente idénticos | 25/25 | 25/25 |
| Casos con todos los campos deterministas idénticos | 30/30 | 30/30 |
| Informes con cifras ajenas, antes/después | 0/0 | 0/0 |
| Casos 82 y 1281: solo secciones 2/3 de P-TERC-BASICO | 2/2 | 2/2 |

En 82 y 1281 desaparecen de la normativa los artículos de incendio y
homologación. La exclusión 3.4 está presente. `large` ya recuperaba su póliza
en esos temas; el filtro limita también sus secciones irrelevantes. Los
pasajes pueden repetirse entre temas: este cambio no modifica la agrupación
de citas del informe.

Las 25 preguntas usan formulaciones distintas de los temas automáticos y no
activan este filtro. Por eso su igualdad exacta acredita preservación, pero
no sustituye la evaluación de los casos de producción. No se afirma 25/25 de
**suficiencia**: la revisión humana de #32 sigue pendiente, especialmente las
preguntas 24 (identificación de la norma) y 25 (intervalo completo de artículos
RMI). Con pasajes idénticos se preservan también sus carencias previas. No se
declara satisfecha la DoD global de #32 ni una evaluación del texto del LLM.

### Reproducción sin gasto

Conservar fuera de git `resultados.json`, `vectores-small.json` y
`vectores-large.json` del baseline autorizado. En esta ejecución están en
`/tmp/piia2-rag-revision/`; la comparación completa, en `/tmp/piia2-54-replay/`.
Las rutas son locales y temporales: para repetir en otro equipo se necesitan
esos archivos y las mismas generaciones, o un nuevo baseline explícitamente
autorizado. No se versionan las bases, los vectores ni los documentos del paquete.

Con `DATABASE_URL` configurada para el índice que contiene esas generaciones:

```sh
.venv-rag/bin/python scripts/evaluar_pertinencia.py \
  --baseline /tmp/piia2-rag-revision \
  --destino /tmp/piia2-54-replay
```

Una consulta sin vector guardado o una generación distinta falla; no activa
llamadas de pago como fallback. Para el cambio de recuperación AC-008 mantiene
corpus/consultas/vectores; los pasajes son la salida que cambia. No se reutiliza
una respuesta cacheada del LLM con pasajes diferentes.

## Activación y límites

Tras integrar la PR, configurar `RAG_POLICY_TOPIC_FILTER=1` en el proceso que
ejecuta agente2 (entorno o `.env` del caso / `app/.env`), según el
[README del componente](../../app/agentes/agente_recuperacion/README.md).
La variable ausente o `0` conserva la recuperación previa. No requiere reindexar.

Solo actúa sobre tres textos exactos de temas y dos nombres de sección del
corpus actual. Un cambio futuro de esos textos/secciones requiere revisar el
mapa y volver a evaluar. No es un clasificador general de pertinencia ni un
control de contradicciones del LLM. Que Básico no tenga una cláusula de lunas
no se presenta como una exclusión literal de lunas.
