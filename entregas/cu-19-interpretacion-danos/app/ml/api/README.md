# api de evaluación de daños

## qué es

esta carpeta contiene la capa http de fastapi para exponer el motor de inferencia que vive en `ml/StrategyPipeline`.

la idea es separar responsabilidades:

- `ml/StrategyPipeline` es la lógica de ml
- `ml/api` es el servicio http que recibe una imagen y devuelve un json con daños detectados

la api trabaja con una imagen subida por `multipart/form-data`, ejecuta una strategy del pipeline y devuelve:

- daños detectados
- `bbox` en formato `xywh`
- área de cada daño
- score
- opcionalmente, una imagen anotada en base64

## estructura

```text
ml/api/
  main.py
  README.md
  core/
    paths.py
    settings.py
    startup.py
  routes/
    health.py
    damage_assessment.py
  schemas/
    response.py
  services/
    predictor.py
    sample_builder.py
    response_mapper.py
    visualization.py
```

## flujo interno

el flujo de una request es este:

```text
cliente http
  -> route de fastapi
  -> sample_builder
  -> predictor
  -> strategy de StrategyPipeline
  -> response_mapper
  -> response json
```

si se pide visualización:

```text
resultado de inferencia
  -> visualization.py
  -> imagen anotada en base64
  -> response json
```

## strategies soportadas

la api soporta estas strategies:

- `baseline`
- `sahi`
- `geometric_ensemble`

### limitación actual

ahora mismo la api carga una sola strategy por proceso.

eso significa que eliges la strategy al arrancar con `ML_API_STRATEGY` y todas las requests de ese proceso usan esa strategy.

no está implementado todavía elegir `baseline` o `sahi` por request dentro del mismo proceso.

## requisitos

esta api necesita:

- el entorno de conda `sam3`
- el modelo sam3 en `models/facebook_sam3`
- opcionalmente, caches de tip-adapter si activas verificación roi

## rutas que usa la api

las rutas base se resuelven en `ml/api/core/paths.py`.

por defecto se espera esto:

- modelo sam3: `models/facebook_sam3`
- cache flat tire: `ml/config/tip_adapter/flat_tire/cropped_embeddings_001/cache.pt`
- cache broken lamp: `ml/config/tip_adapter/broken_lamp/cropped_embeddings_001/cache.pt`

## cómo arrancar

siempre arranca la api desde `app/` y usando el entorno `sam3`.

### baseline

```bash
cd /home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app
ML_API_STRATEGY=baseline conda run --no-capture-output -n sam3 \
  uvicorn ml.api.main:app --host 127.0.0.1 --port 8001 --reload
```

### sahi

```bash
cd /home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app
ML_API_STRATEGY=sahi conda run --no-capture-output -n sam3 \
  uvicorn ml.api.main:app --host 127.0.0.1 --port 8001 --reload
```

### geometric ensemble

```bash
cd /home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app
ML_API_STRATEGY=geometric_ensemble conda run --no-capture-output -n sam3 \
  uvicorn ml.api.main:app --host 127.0.0.1 --port 8001 --reload
```

### levantar las tres a la vez

si quieres comparar strategies en paralelo, usa puertos distintos:

```bash
ML_API_STRATEGY=baseline conda run --no-capture-output -n sam3 \
  uvicorn ml.api.main:app --host 127.0.0.1 --port 8001

ML_API_STRATEGY=sahi conda run --no-capture-output -n sam3 \
  uvicorn ml.api.main:app --host 127.0.0.1 --port 8002

ML_API_STRATEGY=geometric_ensemble conda run --no-capture-output -n sam3 \
  uvicorn ml.api.main:app --host 127.0.0.1 --port 8003
```

## endpoints

### `GET /health`

sirve para comprobar:

- que el servicio está vivo
- qué strategy está cargada
- si el modelo está cargado
- si la verificación roi está activada

ejemplo:

```bash
curl http://127.0.0.1:8001/health
```

respuesta típica:

```json
{
  "status": "ok",
  "app_name": "Vehicle Damage Assessment API",
  "strategy_name": "baseline",
  "model_path": "/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/models/facebook_sam3",
  "model_loaded": true,
  "roi_verification_enabled": false
}
```

### `POST /v1/damage-assessment`

endpoint principal de inferencia.

#### entrada

- `file`: imagen por `multipart/form-data`
- `include_visualization`: query param opcional

#### ejemplo sin visualización

```bash
curl -X POST "http://127.0.0.1:8001/v1/damage-assessment" \
  -F "file=@bd/rawdata/images/000135.jpg"
```

#### ejemplo con visualización

```bash
curl -X POST "http://127.0.0.1:8001/v1/damage-assessment?include_visualization=true" \
  -F "file=@bd/rawdata/images/000135.jpg"
```

#### respuesta típica

```json
{
  "vehicle_damage_assessment": [
    {
      "damage_class": "scratch",
      "bbox": {
        "x": 120.0,
        "y": 84.0,
        "width": 230.0,
        "height": 75.0
      },
      "area": 17250.0,
      "score": 0.91
    }
  ],
  "visualization": {
    "mime_type": "image/png",
    "image_base64": "iVBORw0KGgoAAA..."
  }
}
```

## contrato de respuesta

### `vehicle_damage_assessment`

siempre es una lista porque una imagen puede contener:

- cero daños
- un daño
- varios daños

cada item incluye:

- `damage_class`: clase de daño
- `bbox`: caja en formato `xywh`
- `area`: área de la máscara
- `score`: confianza del modelo

### `visualization`

es opcional.

si está presente:

- `mime_type` indica el tipo de imagen
- `image_base64` contiene la imagen anotada

esta visualización está pensada para:

- demos
- debug rápido
- integración simple con frontend

no es el dato estructurado principal.

## variables de entorno

estas son las variables más importantes:

| variable | para qué sirve | valor por defecto |
| --- | --- | --- |
| `ML_API_HOST` | host del servicio | `127.0.0.1` |
| `ML_API_PORT` | puerto del servicio | `8001` |
| `ML_API_STRATEGY` | strategy a cargar | `baseline` |
| `ML_API_DEVICE` | dispositivo para inferencia | `None` |
| `ML_API_SCORE_THRESHOLD` | umbral mínimo de score | `0.6` |
| `ML_API_MASK_THRESHOLD` | umbral de máscara | `0.5` |
| `ML_API_PROMPT_BATCH_SIZE` | batch de prompts para baseline | `6` |
| `ML_API_INCLUDE_VISUALIZATION` | si la visualización va por defecto | `false` |
| `ML_API_VISUALIZATION_FORMAT` | formato de la imagen anotada | `PNG` |
| `ML_API_ENABLE_ROI_VERIFICATION` | activa tip-adapter para roi | `false` |
| `ML_API_CORS_ALLOW_ORIGINS` | orígenes cors separados por comas | lista local de desarrollo |

### ejemplos útiles

activar visualización por defecto:

```bash
ML_API_INCLUDE_VISUALIZATION=true
```

usar jpeg para la imagen anotada:

```bash
ML_API_VISUALIZATION_FORMAT=JPEG
```

activar verificación roi:

```bash
ML_API_ENABLE_ROI_VERIFICATION=true
```

combinar varias:

```bash
ML_API_STRATEGY=baseline \
ML_API_ENABLE_ROI_VERIFICATION=true \
ML_API_INCLUDE_VISUALIZATION=true \
conda run --no-capture-output -n sam3 \
uvicorn ml.api.main:app --host 127.0.0.1 --port 8001 --reload
```

## comportamiento en startup

al arrancar:

- fastapi ejecuta el `lifespan`
- `startup.py` comprueba que el modelo existe
- construye la strategy elegida
- envuelve la strategy en `VehicleDamagePredictor`
- guarda el predictor en `app.state.predictor`

eso evita cargar el modelo en cada request.

## conversión de imagen

la request no entra directamente al pipeline.

antes se hace esto:

- se leen los bytes del fichero
- se decodifica con pillow
- se normaliza a `RGB`
- se convierte en un `ImageSample`

esto lo hace `services/sample_builder.py`.

## visualización

si `include_visualization=true`:

- se pintan máscaras con transparencia
- se dibujan `bbox`
- se dibuja `label + score`
- la imagen final se serializa a `PNG` o `JPEG`
- después se codifica en base64

esto lo hace `services/visualization.py`.

## integración con el resto del proyecto

esta api está pensada para vivir dentro del repo, pero como servicio separado del backend principal.

el patrón recomendado es:

```text
frontend
  -> server
  -> ml/api
```

así:

- el frontend no depende de detalles del servicio ml
- el backend puede reenviar la imagen
- la strategy real puede cambiar sin tocar el frontend

## errores comunes

### `curl: (26) Failed to open/read local data from file/application`

esto no es un error de fastapi.

significa que `curl` no encuentra el fichero local que intentas subir.

ejemplo correcto:

```bash
curl -X POST "http://127.0.0.1:8001/v1/damage-assessment" \
  -F "file=@bd/rawdata/images/000135.jpg"
```

### `503 El predictor todavía no está cargado`

la api aún no ha terminado de arrancar o falló el startup.

revisa:

- si el entorno `sam3` está activo
- si el modelo existe
- si `uvicorn` mostró una excepción en startup

### `415 El fichero enviado no es una imagen soportada`

el `content-type` no parece imagen.

envía un `jpg`, `jpeg` o `png` real.

### `400 No se pudo decodificar la imagen enviada`

los bytes existen, pero pillow no puede abrir la imagen.

normalmente significa:

- fichero corrupto
- extensión engañosa
- contenido no válido

## desarrollo y documentación interactiva

si arrancas la api con uvicorn, tienes:

- swagger ui en `http://127.0.0.1:8001/docs`
- redoc en `http://127.0.0.1:8001/redoc`

## notas de diseño

- `bbox` se devuelve en `xywh` porque es el formato natural del pipeline
- `vehicle_damage_assessment` es una lista, no un objeto único
- la imagen en base64 es opcional porque infla bastante la respuesta
- la api no usa `CarddLoader`; construye un `ImageSample` al vuelo
- la lógica de inferencia no vive en las rutas; vive en servicios y en `StrategyPipeline`

## siguiente mejora razonable

si quieres una sola api capaz de usar varias strategies por request, la mejora correcta es:

- cargar varios predictors en startup
- guardarlos en `app.state.predictors`
- aceptar un parámetro `strategy` en la request
- seleccionar el predictor adecuado sin reconstruir modelos en caliente

ahora mismo eso no está implementado.
