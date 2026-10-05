# Integración con Google ADK (guía para Lucas)

Esta guía es autónoma. Antes, lee `specs/piia2-arquitectura-multiagente.md`
(sistema completo, contrato JSON, decisiones tomadas con la empresa).

## Objetivo

Una ejecución de punta a punta: **foto + datos del siniestro → informe en
markdown**, pasando por los tres agentes. La empresa trabaja con Google ADK y lo
recomienda (nos pidieron elegir un framework y dijeron que ADK iría bien).
Pero **no está comprobado que funcione bien con nuestro modelo (OpenAI)**, y eso
es lo primero que hay que averiguar, porque decide el plan de todo el sistema.

## Paso 0 — prueba mínima de viabilidad (haz esto primero; pocas horas)

Comprueba, con un agente de juguete, estas tres cosas:

1. **Instalar `google-adk` y registrar una función Python normal como tool**,
   como en el ejemplo de la empresa (`piia2_paquete_datos/scripts/ejemplo_tool.py`:
   funciones normales con anotaciones de tipo y docstring pasadas en
   `tools=[...]` de un `Agent`; los datos estructurados viajan como cadenas JSON).
   Ese ejemplo **no está probado** por la empresa.
2. **Que el agente use un modelo de OpenAI.** ADK está pensado para Gemini; para
   otros modelos hay un adaptador (creemos que es `LiteLlm`, pero **compruébalo
   en la documentación de la versión que instales**). El modelo y la clave van
   en `OPENAI_MODEL` y `OPENAI_API_KEY` (variables de entorno; nunca en el repo).
3. **Que llame a la tool, reciba su resultado y lo devuelva con las cifras
   intactas.** Una tool que devuelve `{"total": 1233.55}` y un agente que lo
   cuenta sin cambiar el número.

**Criterio de decisión:**
- Si funciona sin pelearte mucho: sigue con ADK (Paso 1).
- Si da problemas serios: **plan B**, un orquestador en Python normal
  (`pipeline.py`) que llama a las mismas funciones en orden. Antes de
  descartar ADK, pregunta a la empresa si es obligatorio y qué cuenta como
  «agente»: el enunciado pide un sistema *multiagente*, y conviene saber si
  basta con funciones coordinadas o hacen falta agentes con LLM que se
  coordinen. Lucía puede preguntarlo.

Pase lo que pase, **comunícalo pronto** al equipo: es el mayor riesgo del
proyecto y cuanto antes se sepa, antes se ajusta.

## Qué hay que juntar

Todo son funciones Python normales, ya probadas sin red. No hay que
reescribirlas, solo registrarlas o llamarlas:

| Agente | Función | Dónde | Quién |
|---|---|---|---|
| 1 — visión | `analizar_imagen(...)` | `agente_multimodal/agente1.py` | Lucía |
| 2 — costes y cobertura | `estimar_siniestro(...)` | `agente_recuperacion/costes_y_cobertura.py` | Víctor |
| 2 — normativa (RAG) | `buscar_normativa(...)` y `agente2(...)` | `agente_recuperacion/normativa_rag.py` | tú |
| 3 — informe | `generar_informe(...)` | `agente_redactor/informe.py` | Víctor |

Las entradas y salidas de cada una están en el contrato
(`piia2-arquitectura-multiagente.md`) y hay ejemplos en
`app/agentes/ejemplos_contrato/`.

## Reglas de diseño

1. **Las cifras nunca pasan por el LLM.** Un modelo puede reescribir un número
   sin avisar. Las tools devuelven datos estructurados, el informe lo
   genera código (`generar_informe`) y se guarda en un fichero, y al final se
   ejecuta `comprobar_cifras(informe, agente2)` (de la guía del informe) para
   asegurar que ningún importe es inventado.
2. **`analizar_imagen` ya llama a OpenAI por dentro** (`vision.py`, con cache
   y contador de tokens). Si la registras como tool de un agente, el agente de
   ADK solo orquesta: no dupliques la llamada al modelo de visión.
3. **Orquestación mínima que se pueda defender como multiagente:** un agente
   coordinador que llama a los tres en orden, o tres agentes con un
   coordinador (sub-agentes). Elige lo más simple que permita ADK y cumpla lo
   que la empresa entienda por multiagente.
4. **Pruebas sin gastar:** `agente_multimodal/probar_vision_stub.py` trae un
   `ClienteFalso` de OpenAI; úsalo para probar el cableado sin llamar a la API.
   Las ejecuciones reales cuestan: la cache de `vision.py` evita repetir
   llamadas idénticas.

Trabaja en una carpeta nueva `entregas/cu-19-interpretacion-danos/app/agentes/orquestador/`.

## Paso 1 — un recorrido completo con una imagen real

- **Entrada:** un JSON de `piia2_detecciones/baseline_500/` (detecciones de
  PIIA-1), su foto en `CarDD_release/CarDD_COCO/<split>2017/` y un contexto de
  siniestro (`ejemplos_contrato/contexto_siniestro.json` o uno propio).
- **Salida:** un `informe.md` por imagen y un JSON con lo que produjo cada
  agente.
- Comprueba a mano que el informe se entiende y que las cifras coinciden con
  las del Agente 2.

## Paso 2 — varias imágenes y tabla de resultados

Repite con 3-5 imágenes distintas (alguna con daños fáciles, como un
parabrisas roto o un faro, y alguna difícil) y recoge para la defensa: qué
salió bien, qué no, cuánto costó cada ejecución en tokens, y los casos límite.

## Qué NO tienes que hacer

- No reescribas los agentes: registra o llama a lo que ya hay.
- No dejes que el LLM escriba o recalcule importes.
- No subas a git el paquete de la empresa, la base `chroma_db/` ni la clave.
- Git: nadie hace commits directos en `main`; rama + PR que mergea el equipo.

## Definición de terminado

- [ ] Prueba mínima de ADK hecha, con la decisión (ADK o plan B) comunicada al equipo.
- [ ] Una imagen real recorre los tres agentes hasta un `informe.md`.
- [ ] `comprobar_cifras` pasa sobre ese informe.
- [ ] Probado con 3-5 imágenes, con una tabla de resultados y de coste.
- [ ] Todo en una rama con su PR.
