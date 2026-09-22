# docker de la api ml

esta carpeta contiene el empaquetado docker de `ml/api`.

la idea es tener la api de inferencia aislada del resto del proyecto, con su propio contenedor y sin depender de arrancarla a mano con conda.

## qué hay aquí

```text
docker/ml-api/
  Dockerfile
  docker-compose.yml
  docker-compose.gpu.yml
  entrypoint.sh
  requirements.txt
  README.md
```

## qué levanta

el servicio que arranca este contenedor es:

```text
uvicorn ml.api.main:app
```

expone:

- `GET /health`
- `POST /v1/damage-assessment`

por defecto publica el puerto `8001`, igual que la integración actual del backend.

## rutas esperadas dentro del contenedor

el contenedor copia `ml/` a `/app/ml`.

la api resuelve sus rutas así:

- código ml: `/app/ml`
- modelo sam3: `/models/facebook_sam3`
- caches tip-adapter: `/app/ml/config/tip_adapter/...`

por eso el `docker-compose.yml` monta la carpeta de modelos del host en
`/models`.

## requisitos previos

antes de levantarlo, necesitas:

- docker
- docker compose
- la carpeta de modelos. Por defecto se busca en `models/` en la raíz del
  repositorio; también puedes indicar una ruta absoluta con `PROJECT_MODELS_DIR`.

en esta estructura real del proyecto:

```text
piia2-26/
  models/
    facebook_sam3/
  entregas/
    cu-19-interpretacion-danos/
      app/
        docker/
          ml-api/
```

## arranque base

desde la raíz `app/`:

```bash
docker compose -f docker/ml-api/docker-compose.yml up --build
```

o desde cualquier sitio, usando la ruta absoluta del repo si quieres.

si en tu máquina no tienes el plugin `docker compose`, también puedes usar los scripts de esta carpeta:

```bash
sh docker/ml-api/build.sh
sh docker/ml-api/run.sh
```

cuando el servicio esté arriba:

```bash
curl http://127.0.0.1:8001/health
```

## usar baseline, sahi o ensemble

la strategy se elige con `ML_API_STRATEGY`.

### baseline

```bash
ML_API_STRATEGY=baseline \
docker compose -f docker/ml-api/docker-compose.yml up --build
```

o con script:

```bash
ML_API_STRATEGY=baseline sh docker/ml-api/run.sh
```

### sahi

```bash
ML_API_STRATEGY=sahi \
docker compose -f docker/ml-api/docker-compose.yml up --build
```

o con script:

```bash
ML_API_STRATEGY=sahi sh docker/ml-api/run.sh
```

### geometric ensemble

```bash
ML_API_STRATEGY=geometric_ensemble \
docker compose -f docker/ml-api/docker-compose.yml up --build
```

o con script:

```bash
ML_API_STRATEGY=geometric_ensemble sh docker/ml-api/run.sh
```

## activar gpu

por defecto el compose base no fuerza gpu.

si tu máquina tiene nvidia container toolkit y quieres pedir gpu al contenedor:

```bash
docker compose \
  -f docker/ml-api/docker-compose.yml \
  -f docker/ml-api/docker-compose.gpu.yml \
  up --build
```

ese override hace dos cosas:

- añade `gpus: all`
- fija `ML_API_DEVICE=cuda`

## variables más importantes

puedes pasarlas inline al comando o desde tu shell.

| variable | para qué sirve | default en compose |
| --- | --- | --- |
| `ML_API_STRATEGY` | strategy cargada por la api | `baseline` |
| `ML_API_MODEL_PATH` | ruta del modelo dentro del contenedor | `/models/facebook_sam3` |
| `ML_API_ENABLE_ROI_VERIFICATION` | activa tip-adapter | `false` |
| `ML_API_INCLUDE_VISUALIZATION` | devuelve imagen anotada en base64 | `false` |
| `ML_API_VISUALIZATION_FORMAT` | formato de la imagen anotada | `PNG` |
| `ML_API_SCORE_THRESHOLD` | umbral de score | `0.6` |
| `ML_API_MASK_THRESHOLD` | umbral de máscara | `0.5` |
| `ML_API_PROMPT_BATCH_SIZE` | batch de prompts para baseline | `6` |
| `ML_API_DEVICE` | dispositivo de inferencia | no fijado en compose base |
| `ML_API_RELOAD` | añade `--reload` al uvicorn | `false` |

## ejemplos de arranque

baseline con visualización:

```bash
ML_API_STRATEGY=baseline \
ML_API_INCLUDE_VISUALIZATION=true \
docker compose -f docker/ml-api/docker-compose.yml up --build
```

sahi con verificación roi:

```bash
ML_API_STRATEGY=sahi \
ML_API_ENABLE_ROI_VERIFICATION=true \
docker compose -f docker/ml-api/docker-compose.yml up --build
```

baseline con gpu:

```bash
ML_API_STRATEGY=baseline \
docker compose \
  -f docker/ml-api/docker-compose.yml \
  -f docker/ml-api/docker-compose.gpu.yml \
  up --build
```

## probar inferencia

ejemplo con una imagen local del dataset:

```bash
curl -X POST "http://127.0.0.1:8001/v1/damage-assessment?include_visualization=true" \
  -F "file=@bd/rawdata/images/000135.jpg"
```

## parar y limpiar

parar el servicio:

```bash
docker compose -f docker/ml-api/docker-compose.yml down
```

parar y borrar también el volumen de cache de hugging face:

```bash
docker compose -f docker/ml-api/docker-compose.yml down -v
```

si usas `docker run`, el contenedor va con `--rm`, así que se borra al parar. el volumen `ml_api_hf_cache` sí se queda y, si quieres limpiarlo, lo puedes borrar con:

```bash
docker volume rm ml_api_hf_cache
```

## notas importantes

- el contenedor monta `../../../../models:/models:ro`, así que si tu carpeta host de modelos cambia, tendrás que ajustar el compose.
- si activas roi verification y no existe cache local de hugging face, el contenedor puede descargar pesos de clip en el primer arranque.
- el `healthcheck` puede tardar un poco en ponerse en verde porque sam3 se carga al arrancar.
- este setup está pensado para la api de `ml`, no para notebooks ni para el frontend.

## por qué he tocado también `settings.py`

para dockerizar esto bien, la api necesitaba aceptar rutas por variables de entorno.

ahora soporta:

- `ML_API_MODEL_PATH`
- `ML_API_FLAT_TIRE_CACHE_PATH`
- `ML_API_BROKEN_LAMP_CACHE_PATH`

además mantiene compatibilidad con `SAM3_MODEL_PATH` como alias del modelo.
