# Pestaña Peritaje

Issue [#34](https://github.com/lvckss/piia2-26/issues/34). Plan: [Spec 34 v1.7](../../specs/34-orquestacion-web.md) y [complemento UI v1 / AC-015](https://github.com/lvckss/piia2-26/issues/34#issuecomment-7135966562). Arquitectura: [ADR 0007](../../docs/adr/0007-orquestacion-adk-web-efimera.md), aceptado mediante #60.

La pestaña **Peritaje**, en `/peritaje`, convive con Playground y Explorar dataset. Conserva componentes, tipografía y aspecto de la aplicación existente. Permite elegir una imagen original con los servicios y filtros del explorador o subir JPEG/PNG. Seleccionar y navegar no inicia inferencia.

El recorrido es: imagen → «Analizar imagen» → resultados de solo lectura → confirmar/elegir vehículo y completar el siniestro → «Generar informe» → Markdown visible y descargable. La categoría desconocida muestra V14 y las advertencias acordadas; el navegador no fabrica `vehiculo_origen`. La póliza solo se envía para rol propio. Los datos y presupuestos los produce el servidor.

## Estado de integración

Este incremento implementa el **cliente web** y sus pruebas de navegador. Consume `/api/catalogos` y `/api/peritajes` conforme al recorrido aceptado; el backend de orquestación y el Compose completo siguen pendientes en #34. Ante una API ausente o incompatible muestra un error; nunca sustituye la respuesta por detecciones o informes precalculados. Las pruebas guionizan HTTP exclusivamente desde Playwright, fuera del código de producto.

Los esquemas de `server/models/` necesarios para reutilizar el explorador se incluyen como código fuente: antes una regla de ignorado de pesos `models/` también los excluía del repositorio. Las carpetas de modelos, imágenes, credenciales y resultados locales siguen ignoradas.

## Ejecutar y comprobar

Desde `app/`, instalar dependencias con `bun install`; desde `app/frontend/`, ejecutar también `bun install`. Arrancar el backend con su configuración habitual y `bun run dev` desde `app/`; arrancar Vite con `bun run dev` desde `app/frontend/`. La UI usa los proxies `/api` y `/dataset` existentes.

Para instalar el navegador de pruebas desde `app/frontend/`:

```sh
bunx playwright install chromium --only-shell
```

Checks:

```sh
# Desde app/
bun run test:peritaje

# Desde app/frontend/
bun run build
bunx tsc -b
bunx eslint src/features/peritaje src/lib/dataset-url.ts src/routes/peritaje.tsx tests/peritaje playwright.config.ts
```

Puede usarse `PLAYWRIGHT_BROWSERS_PATH` para ubicar el navegador fuera del directorio por defecto. Playwright levanta Vite en `127.0.0.1:5174`. Sus respuestas son deterministas y no consultan ML/OpenAI, PostgreSQL ni los archivos de CarDD. Los resultados y trazas se guardan localmente y no se versionan.

Trazabilidad: los nombres de las pruebas indican los AC de la Spec o del complemento. Verifican acciones explícitas, filtros y original, límites de bytes/píxeles, confirmación/selección, tercero, 422 recuperable, claves y doble clic, polling y caso perdido, estados RAG, errores y contrato, descarga UTF-8, HTML inerte, descarte y navegación móvil/explorador.

## Contrato que consume el cliente

El cliente valida las respuestas con `src/features/peritaje/api.ts`. Catálogos: arrays `vehiculos`, `polizas`, `regiones`, `tipos_taller`, `acabados` y `tipos_pieza`, con opciones `{id, nombre}`. Son datos del servidor, no valores inventados por el formulario.

La fase A envía multipart `file`; ambos POST llevan `Idempotency-Key`. La fase B envía `{contexto, seleccion_vehiculo?}` y nunca envía findings, tiers ni procedencia libre. Para contexto corregido se crea otra clave; un reintento explícito del mismo contenido conserva la suya.

Las respuestas de ejecución contienen `ejecucion_id`, `estado`, `etapa`, `analisis`, `resultado`, `error`; los tres últimos son anulables según la fase. `analisis` conserva `image_id`, `vehiculo` y `findings` públicos del Agente 1. `resultado` contiene `markdown` y `agente2` con `diagnostico_rag`. Solo se muestra y descarga en `completada`, sin error, y se rechaza un GET que devuelva el ID de otro caso. Estos detalles de serialización concretan el contrato de la Spec para conectar el servidor pendiente; no acreditan que exista su implementación.

No hay historial ni reenvío automático de POST. Un fallo de polling exige consulta explícita y no reinicia el análisis. Descartar usa DELETE; si el servidor no confirma la limpieza, conserva el caso y muestra el error. La descarga conserva los mismos bytes UTF-8 del Markdown recibido; el renderizador deshabilita HTML crudo y no carga imágenes incluidas en el texto generado.

La integración real, la igualdad con los importes del Agente 2, el ciclo de vida del servidor, Compose y la lectura humana de 3–5 informes permanecen pendientes en sus slices. Los tests del cliente no acreditan la DoD completa de #34.
