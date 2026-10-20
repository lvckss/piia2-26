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
JSON con el mismo importe decimal `1233.55`. El prompt no proporciona ese importe.
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
- El ejemplo trabaja en memoria y no evalúa RAG, visión, los contratos del
  producto ni la coordinación de tres agentes. Un resultado favorable solo
  aporta evidencia para planificar #34.
- Un error de autenticación, cuota, permisos o disponibilidad del modelo deja
  la integración sin acreditar; no demuestra por sí solo que ADK sea incompatible.

## Resultado observado (2026-10-20)

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

AC-002 sigue pendiente y no se recomienda todavía adoptar ni descartar ADK.
Siguiente acción: sustituir localmente la credencial por una válida y autorizar
expresamente una nueva tentativa, conservando el intento anterior. La PR queda
en borrador y la Issue bloqueada; no se declara terminada ni se hace merge.
