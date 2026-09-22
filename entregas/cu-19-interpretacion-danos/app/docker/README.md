# docker

esta carpeta agrupa todo lo relacionado con contenedores del proyecto.

ahora mismo el objetivo principal es dockerizar la parte de `ml` para poder levantar la api de inferencia de forma aislada, sin depender de arrancarla a mano con conda en la máquina host.

## qué hay aquí

```text
docker/
  README.md
  ml-api/
    Dockerfile
    README.md
    build.sh
    run.sh
    docker-compose.yml
    docker-compose.gpu.yml
    entrypoint.sh
    requirements.txt
```

## qué está dockerizado ahora mismo

ahora mismo solo está dockerizada la api de `ml`:

- código fuente: `ml/api`
- motor de inferencia reutilizado: `ml/StrategyPipeline`
- servicio expuesto: fastapi + uvicorn

no se ha dockerizado aquí:

- el frontend
- el backend de `server/`
- notebooks
- utilidades de entrenamiento o exploración

## idea general

la separación es esta:

```text
ml/StrategyPipeline
  -> lógica de inferencia

ml/api
  -> capa http

docker/ml-api
  -> empaquetado y arranque aislado de esa api
```

el contenedor no mete el proyecto entero como aplicación monolítica. mete solo lo que necesita la api de ml para arrancar y servir inferencia.

## servicio disponible

el contenedor arranca:

```text
uvicorn ml.api.main:app
```

y expone:

- `GET /health`
- `POST /v1/damage-assessment`

por defecto el puerto publicado es:

```text
8001
```

eso encaja con la integración que ya existía en el backend, que esperaba la api python en ese puerto.

## estructura de `ml-api`

la subcarpeta importante es [ml-api/README.md](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/docker/ml-api/README.md), pero aquí te dejo el resumen operativo.

archivos clave:

- [Dockerfile](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/docker/ml-api/Dockerfile): construye la imagen
- [docker-compose.yml](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/docker/ml-api/docker-compose.yml): arranque base
- [docker-compose.gpu.yml](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/docker/ml-api/docker-compose.gpu.yml): override para gpu
- [build.sh](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/docker/ml-api/build.sh): build sin depender de compose
- [run.sh](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/docker/ml-api/run.sh): run sin depender de compose
- [requirements.txt](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/docker/ml-api/requirements.txt): dependencias python del contenedor
- [entrypoint.sh](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/docker/ml-api/entrypoint.sh): arranque real del proceso

## rutas importantes

dentro del contenedor:

- app root: `/app`
- código ml: `/app/ml`
- modelo sam3: `/models/facebook_sam3`
- cache de hugging face: `/cache/huggingface`

en el host, el compose monta la carpeta de modelos del proyecto en:

```text
/models
```

la ruta host real esperada por defecto es:

```text
../../../../models
```

vista desde:

```text
app/docker/ml-api/docker-compose.yml
```

eso resuelve a:

```text
/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/models
```

## por qué hubo que tocar la api

para que la api pudiera vivir bien dentro de un contenedor, hubo que desacoplar varias rutas del layout local de desarrollo.

ahora `ml/api/core/settings.py` acepta estas variables:

- `ML_API_MODEL_PATH`
- `ML_API_FLAT_TIRE_CACHE_PATH`
- `ML_API_BROKEN_LAMP_CACHE_PATH`

y además mantiene compatibilidad con:

- `SAM3_MODEL_PATH`

esto permite que dentro del contenedor el modelo viva en `/models/facebook_sam3` sin romper el flujo local fuera de docker.

## cómo arrancarlo

### opción 1: con compose

desde la raíz `app/`:

```bash
docker compose -f docker/ml-api/docker-compose.yml up --build
```

si quieres usar gpu:

```bash
docker compose \
  -f docker/ml-api/docker-compose.yml \
  -f docker/ml-api/docker-compose.gpu.yml \
  up --build
```

### opción 2: con scripts

esto es útil si tu host no tiene el plugin `docker compose`.

build:

```bash
sh docker/ml-api/build.sh
```

run:

```bash
sh docker/ml-api/run.sh
```

## strategies soportadas

la api dentro del contenedor sigue funcionando igual que fuera.

puedes elegir:

- `baseline`
- `sahi`
- `geometric_ensemble`

la variable es:

```bash
ML_API_STRATEGY
```

ejemplos:

```bash
ML_API_STRATEGY=baseline sh docker/ml-api/run.sh
```

```bash
ML_API_STRATEGY=sahi sh docker/ml-api/run.sh
```

```bash
ML_API_STRATEGY=geometric_ensemble sh docker/ml-api/run.sh
```

si usas compose:

```bash
ML_API_STRATEGY=baseline docker compose -f docker/ml-api/docker-compose.yml up --build
```

## variables de entorno más importantes

las más útiles para operar la api son:

| variable | para qué sirve |
| --- | --- |
| `ML_API_STRATEGY` | strategy cargada al arrancar |
| `ML_API_MODEL_PATH` | ruta del modelo dentro del contenedor |
| `ML_API_DEVICE` | fuerza `cpu` o `cuda` |
| `ML_API_ENABLE_ROI_VERIFICATION` | activa tip-adapter |
| `ML_API_INCLUDE_VISUALIZATION` | devuelve la imagen anotada en base64 |
| `ML_API_VISUALIZATION_FORMAT` | `PNG` o `JPEG` |
| `ML_API_SCORE_THRESHOLD` | umbral de score |
| `ML_API_MASK_THRESHOLD` | umbral de máscara |
| `ML_API_PROMPT_BATCH_SIZE` | batch de prompts para baseline |
| `ML_API_RELOAD` | activa `uvicorn --reload` |

## prueba rápida

health:

```bash
curl http://127.0.0.1:8001/health
```

inferencia:

```bash
curl -X POST "http://127.0.0.1:8001/v1/damage-assessment?include_visualization=true" \
  -F "file=@bd/rawdata/images/000135.jpg"
```

## gpu

el contenedor base no fuerza gpu.

si quieres inferencia con cuda, necesitas:

- docker con soporte nvidia
- nvidia container toolkit
- usar el override [docker-compose.gpu.yml](/home/lvcks/Documents/TERCERO/PROYECTO_INTEGRADOR/WEBAPP/app/docker/ml-api/docker-compose.gpu.yml) o pasar `ML_API_DEVICE=cuda`

ojo con esto:

- pedir `ML_API_DEVICE=cuda` sin runtime gpu funcional te va a romper el arranque o la inferencia
- en cpu debería arrancar igual, pero será bastante más lento

## cache y descargas

hay dos tipos de artefactos externos:

1. modelo sam3
   - no se descarga en build
   - se monta desde la carpeta host `models/`

2. pesos de hugging face
   - pueden descargarse en el primer arranque si faltan en cache
   - se guardan en el volumen `ml_api_hf_cache`

esto afecta especialmente a:

- sam3 vía `transformers`
- clip si activas roi verification

## límites actuales

- una instancia de la api carga una sola strategy por proceso
- este docker está pensado para servir inferencia, no para notebooks
- no está montado todavía un stack completo `frontend + server + ml-api` con compose unificado
- la build puede tardar bastante porque las dependencias de ml pesan

## troubleshooting

### el contenedor no encuentra el modelo

revisa:

- que exista `models/facebook_sam3` en el host
- que el volumen del compose apunte a la carpeta correcta
- que `ML_API_MODEL_PATH` dentro del contenedor sea `/models/facebook_sam3`

### `docker compose` no existe

usa:

```bash
sh docker/ml-api/build.sh
sh docker/ml-api/run.sh
```

### el arranque tarda mucho

es normal en el primer boot si:

- no hay cache de hugging face
- el modelo pesa bastante
- estás tirando de cpu

### la build falla descargando paquetes

eso no suele ser un fallo de la configuración del proyecto, sino de red o de mirrors durante `apt` o `pip`.

el `Dockerfile` ya lleva reintentos y timeout ampliado en la fase de `pip`, pero si la red está mal, puede seguir fallando.

## validación hecha

de lo que hay aquí, se ha comprobado:

- sintaxis de `settings.py`
- sintaxis de `entrypoint.sh`
- parseo yaml de los compose
- resolución real de la ruta host a `models/`
- una build real de docker hasta fase de instalación de dependencias python

lo que no he podido validar de punta a punta en esta máquina es un `docker compose up` completo porque aquí no está disponible el plugin `docker compose`.

## siguiente paso razonable

si quieres seguir por esta línea, lo natural ahora es una de estas dos cosas:

1. crear un `docker-compose` raíz que una `server` y `ml-api`
2. crear una variante `dev` de `ml-api` con bind mount de `ml/` y recarga para iterar más rápido
