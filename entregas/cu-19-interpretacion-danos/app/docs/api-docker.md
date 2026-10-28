# api y docker

## qué cubre

este documento describe:

- la fastapi dentro de `ml/api`
- cómo se arranca
- cómo se usa
- cómo está dockerizada hoy

referencias principales:

- [ml/api/README.md](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/api/README.md)
- [docker/README.md](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/docker/README.md)
- [docker/ml-api/README.md](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/docker/ml-api/README.md)

## fastapi

### objetivo

`ml/api` es la capa http del motor de inferencia de `ml/StrategyPipeline`.

la separación buscada es:

```text
StrategyPipeline -> lógica de ml
ml/api           -> servicio http
docker/ml-api    -> empaquetado y despliegue aislado
```

### punto de entrada

la aplicación arranca desde:

- [ml/api/main.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/api/main.py)

ahí se hace:

- creación de `FastAPI()`
- registro de middlewares
- carga del predictor en startup
- inclusión de routers

### estructura interna

```text
ml/api/
  main.py
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

lectura rápida:

- `core/` resuelve configuración y startup
- `routes/` define endpoints
- `services/` contiene la lógica de orquestación de request/respuesta
- `schemas/` define el contrato público

## endpoints

### `GET /health`

sirve para ver:

- si la api está viva
- qué strategy está cargada
- si el modelo se llegó a montar
- si la verificación roi está activada

referencia:

- [health.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/api/routes/health.py)

### `POST /v1/damage-assessment`

endpoint principal de inferencia.

entrada:

- `file` por `multipart/form-data`
- `include_visualization` opcional por query

salida:

- lista `vehicle_damage_assessment`
- visualización opcional en base64

referencias:

- [damage_assessment.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/api/routes/damage_assessment.py)
- [response.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/api/schemas/response.py)

## strategies soportadas

la api soporta:

- `baseline`
- `sahi`
- `geometric_ensemble`

la strategy se elige al arrancar con:

```bash
ML_API_STRATEGY
```

limitación actual:

- una instancia de la api carga una sola strategy por proceso
- no está implementado todavía el cambio de strategy por request

## arranque local

el flujo local actual usa el entorno `sam3`.

ejemplos:

```bash
ML_API_STRATEGY=baseline \
conda run --no-capture-output -n sam3 \
uvicorn ml.api.main:app --host 127.0.0.1 --port 8001 --reload
```

```bash
ML_API_STRATEGY=sahi \
conda run --no-capture-output -n sam3 \
uvicorn ml.api.main:app --host 127.0.0.1 --port 8001 --reload
```

```bash
ML_API_STRATEGY=geometric_ensemble \
conda run --no-capture-output -n sam3 \
uvicorn ml.api.main:app --host 127.0.0.1 --port 8001 --reload
```

## uso de la api

health:

```bash
curl http://127.0.0.1:8001/health
```

inferencia:

```bash
curl -X POST "http://127.0.0.1:8001/v1/damage-assessment" \
  -F "file=@bd/rawdata/images/000135.jpg"
```

con visualización:

```bash
curl -X POST "http://127.0.0.1:8001/v1/damage-assessment?include_visualization=true" \
  -F "file=@bd/rawdata/images/000135.jpg"
```

## configuración por entorno

las variables importantes viven en:

- [settings.py](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/ml/api/core/settings.py)

las más relevantes:

- `ML_API_STRATEGY`
- `ML_API_MODEL_PATH`
- `ML_API_DEVICE`
- `ML_API_ENABLE_ROI_VERIFICATION`
- `ML_API_INCLUDE_VISUALIZATION`
- `ML_API_VISUALIZATION_FORMAT`
- `ML_API_SCORE_THRESHOLD`
- `ML_API_MASK_THRESHOLD`
- `ML_API_PROMPT_BATCH_SIZE`

además, para que docker no dependiera del layout local, la api ahora admite:

- `ML_API_FLAT_TIRE_CACHE_PATH`
- `ML_API_BROKEN_LAMP_CACHE_PATH`
- `SAM3_MODEL_PATH` como alias heredado

## docker

### objetivo

la carpeta `docker/` existe para aislar la api de ml del resto del proyecto.

ahora mismo no se dockeriza todo el stack. lo que está empaquetado es la fastapi de ml.

### estructura

```text
docker/
  README.md
  ml-api/
    Dockerfile
    docker-compose.yml
    docker-compose.gpu.yml
    build.sh
    run.sh
    entrypoint.sh
    requirements.txt
```

### arranque con compose

```bash
docker compose -f docker/ml-api/docker-compose.yml up --build
```

con gpu:

```bash
docker compose \
  -f docker/ml-api/docker-compose.yml \
  -f docker/ml-api/docker-compose.gpu.yml \
  up --build
```

### arranque con scripts

si el host no tiene el plugin `docker compose`, hay fallback:

```bash
sh docker/ml-api/build.sh
sh docker/ml-api/run.sh
```

### layout dentro del contenedor

dentro del contenedor:

- código: `/app/ml`
- modelo: `/models/facebook_sam3`
- cache hf: `/cache/huggingface`

el modelo se monta desde el host, no se descarga en build.

## relación con el backend bun

hay un punto importante de integración:

- el backend bun tiene servicios pensados para hablar con una api SAM3 externa
- pero hoy la fastapi nueva y ese puente no están alineados del todo

en concreto:

- [server/services/sam3Service.ts](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/server/services/sam3Service.ts) apunta por defecto a `http://127.0.0.1:8001`
- ese servicio espera un endpoint `/infer`
- la fastapi nueva expone `/v1/damage-assessment`
- además `sam3Route` no está montada en [server/app.ts](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/server/app.ts)

conclusión práctica:

- la fastapi está funcional como servicio aislado
- el acoplamiento `server -> fastapi` todavía requiere adaptación si quieres integrarlo directamente en la webapp actual

## estado actual resumido

- la api de `ml` ya existe y está operativa como servicio independiente
- el despliegue en docker ya está montado a nivel de archivos y comandos
- la capa web de `server/` todavía no consume esa api nueva de punta a punta
