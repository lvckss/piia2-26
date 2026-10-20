# Prueba de viabilidad ADK + OpenAI (#33)

Experimento autónomo con una función de juguete. No integra los tres agentes del
producto ni decide su arquitectura. Plan y criterios:
[plan v1 de #33](https://github.com/lvckss/piia2-26/issues/33#issuecomment-6289598174).

Se utiliza `gpt-6.1-sol` con effort `high`, mediante `LiteLlm` de ADK Python y
el bridge nativo de LiteLLM `openai/responses/`. OpenAI exige Responses API para
tool calling con este modelo; no basta enviar tools a Chat Completions.

- [Modelo y requisitos de OpenAI](https://developers.openai.com/api/docs/models/gpt-6.1-sol).
- [Conector de ADK Python](https://adk.dev/agents/models/litellm/).
- [Bridge nativo de LiteLLM](https://docs.litellm.ai/docs/providers/openai/responses_api#tool-search-via-chat-completions-bridge).

## Reproducir

Desde la raíz del repositorio, con Python 3.12:

```sh
python -m venv /tmp/piia2-33-venv
/tmp/piia2-33-venv/bin/python -m pip install -r entregas/cu-19-interpretacion-danos/app/agentes/orquestador/requirements-adk-smoke.txt
/tmp/piia2-33-venv/bin/python -m pip check
```

Las versiones son las usadas en el experimento; no se instalan dependencias
globales. LiteLLM 1.106.0 importa MCP al entrar en el bridge con tools de función,
aunque no se usen tools MCP. Sin esa dependencia se reprodujo
`ModuleNotFoundError: No module named 'mcp'`; por eso se incluye explícitamente.
No se inicia ningún servidor MCP ni proxy.

Pruebas deterministas, con clave ficticia y respuestas HTTP simuladas:

```sh
timeout --kill-after=2s 90s /tmp/piia2-33-venv/bin/python -m unittest discover \
  -s entregas/cu-19-interpretacion-danos/app/agentes/orquestador \
  -p test_probar_adk_openai.py -v
```

No acreditan compatibilidad con el proveedor. El test del recorrido atraviesa
ADK y LiteLLM y comprueba las peticiones serializadas: endpoint Responses,
modelo, effort, límite de salida y tool. Los controles negativos verifican que
un HTTP 429 no se reintenta y que no se envía una tercera petición si el modelo
sigue pidiendo la tool. También rechazan resultados alterados, ambiguos,
incompletos y sin ejecución real de la función.

Configurar únicamente `OPENAI_API_KEY` en
`entregas/cu-19-interpretacion-danos/.env`, excluido de Git, con permisos `0600`.
También puede facilitarse mediante la variable de entorno si no existe el archivo.
No pegar claves en comandos, chats o documentación. El script lee solo esa
variable del archivo; no lo ejecuta ni carga sus otros valores.

La siguiente orden **sí consume API** y debe ejecutarse una sola vez por tentativa:

```sh
timeout --kill-after=2s 120s /tmp/piia2-33-venv/bin/python \
  entregas/cu-19-interpretacion-danos/app/agentes/orquestador/probar_adk_openai.py \
  --ejecutar
```

Se registran llamada y respuesta de la tool mediante eventos públicos de ADK y
el contador de ejecución de esta función de juguete. La respuesta final debe ser
JSON con el mismo importe decimal `1233.55`, directamente o dentro del envoltorio
`{"result": "...JSON..."}` que ADK usa para retornos string. Se admite un único
envoltorio, se rechazan claves duplicadas y el importe se comprueba igualmente.
El prompt no proporciona ese importe.
Mencionar el número sin ejecutar la función no acredita la prueba.

Máximo dos llamadas al modelo y 4096 tokens de salida por llamada, sin retries
automáticos. Esto acota la tentativa, no representa un presupuesto monetario
enforced por el proveedor. El `timeout` exterior limita también atascos de
dependencias o de cancelación que un timeout asíncrono no pueda interrumpir.
Exit code distinto de cero, timeout o ausencia de informe válido son fallos o
verificación incompleta; nunca éxito. No se cambia de modelo como fallback.

## Evidencia de desarrollo y límites

- TDD: 10 tests iniciales fallaron por comportamiento ausente (21 errores
  `NotImplementedError`); después pasaron los 10. Se añadieron los controles del
  CLI y del recorrido nativo, hasta 15 tests.
- La instalación y los tests requieren las dependencias y los datos auxiliares
  de tokenización que el SDK utilice. Las sondas con red restringida se atascaron;
  no se contabilizan como verificaciones satisfactorias. La ejecución completa
  de 15 tests bajo el perfil de red utilizado para la prueba real pasó en 12,102 s.
- Tras capturar el envoltorio de ADK en el segundo intento, se reprodujo su
  rechazo como una regresión Red y se corrigió solo la comparación del resultado.
  La suite final de **17 tests pasa en 11,795 s**, incluyendo el envoltorio
  correcto y sus casos negativos. El código que llama al modelo y ejecuta la
  tool permanece idéntico al de la captura real.
- El ejemplo trabaja en memoria y no evalúa RAG, visión, los contratos del
  producto ni la coordinación de tres agentes. Un resultado favorable solo
  aporta evidencia para planificar #34.
- Un error de autenticación, cuota, permisos o disponibilidad del modelo deja
  la integración sin acreditar; no demuestra por sí solo que ADK sea incompatible.

## Resultados observados (2026-10-20)

### Intento 1: autenticación rechazada

Única tentativa real: **no concluyente**, bloqueada por autenticación.
OpenAI devolvió `AuthenticationError`, código `invalid_api_key`, antes de ejecutar
la tool. Lucas confirmó que la clave corresponde a OpenAI directamente; no se
ha cambiado el endpoint ni intentado otro proveedor o modelo.

| Comprobación de #33 | Resultado |
|---|---|
| Instalación/importación y registro de la función como tool | Sí, con las dependencias fijadas y el registro observado también en la tentativa real. |
| Modelo real de OpenAI con ADK | No acreditado: el proveedor rechazó la credencial. |
| Llamada real de la tool y conservación de cifras | No ejecutada: contador 0, sin llamada, resultado ni respuesta final. |

Duración: 11,426 s dentro del script y 13,481 s del proceso exterior.
No se recibieron datos de tokens ni coste; no se contabilizan como cero.
No hubo segundo intento. [Evidencia saneada y hash del script](evidencia-33.json).

En ese momento AC-002 quedó pendiente y la PR en borrador, con #33 bloqueada.
Después se detectó un espacio interior en el valor del `.env`; se retiró solo
ese espacio. No se sustituyó el resto de la clave ni se repitió automáticamente.

### Intento 2: recorrido real completado y comprobación local corregida

Lucas autorizó expresamente otra tentativa con «prueba ahora». OpenAI aceptó
la clave corregida; ADK llamó una vez a `importe_prueba` y el modelo devolvió
exactamente su resultado público: `{"result": "{\"total\": 1233.55}"}`.

El proceso original salió con código 1 porque el comprobador exigía `total`
en la raíz e ignoraba ese envoltorio de ADK. Se conserva íntegro ese resultado;
no se transforma su exit code en 0. Se reprodujo el falso negativo con un test,
se corrigió la comparación y se revalidó **localmente la misma captura**, sin
una tercera tentativa ni llamadas adicionales. La función de ejecución y el
CLI no cambiaron; sus hashes y el del comprobador quedan en la evidencia.

| Comprobación de #33 | Resultado final |
|---|---|
| Instalación y registro de tool | Sí, ADK y conector nativos. |
| Modelo real OpenAI | Sí, `gpt-6.1-sol`, effort `high`, mediante Responses API. |
| Tool y cifras intactas | Sí: una ejecución, llamada y respuesta enlazadas, importe decimal `1233.55` preservado; captura aceptada por el comprobador corregido. |

Métricas del **intento 2**: 18,038 s dentro del script y 20,440 s del proceso
exterior; 2 respuestas de modelo con uso reportado, 222 tokens de entrada,
155 de salida y 377 totales; caché 0. El adaptador incluye los tokens de
razonamiento en la salida reportada: no se suman otra vez. El runtime no ofrece
un importe monetario; no se inventa un coste. El intento 1 conserva sus métricas
como no disponibles. Contador histórico: **2 tentativas reales**, la segunda
autorizada manualmente; sin retries automáticos.

[Captura original del intento 2 y revalidación local](evidencia-33-intento-2.json).
No se afirma que el CLI corregido haya tenido una tercera ejecución real.

**Veredicto:** la viabilidad mínima ADK + OpenAI de #33 queda acreditada y
permite continuar la planificación de #34 con ADK como opción viable. No prueba
todavía coordinación de tres agentes, recuperación, RAG ni calidad del informe,
ni constituye aceptación de una arquitectura de producto. La PR se entrega para
revisión y merge humanos; la Issue no se cierra automáticamente.
