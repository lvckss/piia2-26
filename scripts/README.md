# Datos CARDD locales

Plan v1 y AC-001–AC-005: [Issue #64](https://github.com/lvckss/piia2-26/issues/64#issuecomment-6448595256).

Desde la raíz del repositorio, `download_cardd.py` coloca el paquete en:

```text
entregas/cu-19-interpretacion-danos/app/bd/
├── rawdata/
│   ├── image_info.xlsx
│   ├── instances_train.json
│   ├── instances_test.json
│   └── instances_val.json
└── clean_data/
    ├── train/{fullsize,thumbnails}/
    ├── test/{fullsize,thumbnails}/
    └── val/{fullsize,thumbnails}/
```

Estas carpetas, el estado de instalación y los temporales están ignorados por
Git. Se versionan el script, los tests y el SHA-256 del paquete; las imágenes
permanecen en cada copia local. No hay que añadirlas con `git add -f`.

## Descargar desde Google Drive

Con [Just](https://just.systems/) y Python 3.11+ con `venv`, el atajo desde
la raíz o cualquier subcarpeta del repositorio es:

```bash
just cardd
```

Prepara automáticamente `.venv-cardd`, instala la dependencia fijada y ejecuta
el descargador con el enlace del paquete v1. Puedes proporcionar otra URL con
`CARDD_URL`; se conserva el SHA-256 esperado. El entorno y los datos están
ignorados por Git. Las alternativas manuales y offline siguen disponibles debajo.

Necesitas Python 3.11 o posterior. Prepara una vez un entorno con la dependencia
de Drive (no requiere Bun, PostgreSQL ni las dependencias de ML):

```bash
python3 -m venv .venv-cardd
.venv-cardd/bin/python -m pip install -r scripts/requirements-cardd.txt
```

El [paquete v1 está en Google Drive](https://drive.google.com/file/d/1TXnFJUyNsxciAz4pxKtwD8lJ1uWzcdBK/view?usp=sharing)
como un único archivo `cardd-dataset-v1.tar.gz`.
El script usa `gdown --fuzzy --no-cookies`: no inicia sesión ni utiliza cookies
del navegador. El enlace debe permitir descargar sin autenticación. Si el archivo
es privado para cuentas concretas, descárgalo con tu cuenta desde el navegador y
utiliza el modo `--archive` descrito debajo; no hace falta cambiar sus permisos.

Para descargar la versión cuyo SHA-256 está registrado en el repo, ejecuta:

```bash
.venv-cardd/bin/python scripts/download_cardd.py \
  --url 'https://drive.google.com/file/d/1TXnFJUyNsxciAz4pxKtwD8lJ1uWzcdBK/view?usp=sharing'
```

También puedes configurar `CARDD_URL` y ejecutar el mismo comando sin `--url`.
Usa un enlace de archivo; los enlaces de carpeta no se admiten.
Para URLs HTTP(S) directas basta `python3`, sin instalar `gdown`.

Referencia de la dependencia y sus opciones: [gdown v5.2.0](https://github.com/wkentaro/gdown/tree/v5.2.0).

## Usar el paquete ya descargado

```bash
python3 scripts/download_cardd.py --archive /ruta/cardd-dataset-v1.tar.gz
```

El paquete v1 ocupa 9.397.037.140 bytes (aproximadamente 8,75 GiB). Reserva espacio
para el paquete y su contenido extraído (unos 18 GiB en total). Contiene las
4.000 imágenes CARDD, los metadatos originales y 3.999 miniaturas. La miniatura
ausente procede del material original; el script no la genera.

El SHA-256 esperado está fijado en [cardd-dataset.json](cardd-dataset.json):

```text
3276d0e8852d6e31124f437a7455e2c0e59265058dcee47b0c21d872149f8422
```

Para instalar otra versión explícita del paquete puedes indicar `--sha256 HASH`
o `CARDD_SHA256`. Obtén el hash del responsable del paquete por un canal fiable;
el script no acepta automáticamente como válido el hash del archivo descargado.

## Comprobaciones y recuperación

Antes de instalar, comprueba SHA-256, rutas y tipos de entradas del tar.gz, el
Excel presente y no vacío, los tres JSON COCO y las imágenes que referencian en
`clean_data/<split>/fullsize/`. Solo admite archivos normales y directorios bajo
`rawdata/` y `clean_data/`; rechaza enlaces, entradas duplicadas y rutas externas.
Extrae en un directorio temporal y publica las carpetas tras validarlas.

Una segunda ejecución comprueba la versión, existencia y tamaño de cada archivo
del registro local `.cardd-install.json`; si coinciden, termina sin volver a
descargar. Esta comprobación local no recalcula hashes individuales de imágenes:
una modificación que conserve el tamaño no se detecta. El SHA-256 completo se
comprueba al instalar el archivo.

Si hay carpetas preexistentes sin registro, otra versión o archivos ausentes o
modificados, el script informa del conflicto y conserva los datos. Mueve tus
carpetas y el marcador a una ubicación de respaldo o elige otro destino:

```bash
python3 scripts/download_cardd.py --archive /ruta/cardd-dataset-v1.tar.gz \
  --destination /otra/ruta/bd
```

Si la descarga falla por permisos, conexión o límites de Drive, no se instala.
Corrige el acceso y repite o usa un archivo local. Los temporales se limpian al
terminar o interrumpir normalmente; una terminación forzada puede dejar
`.cardd-stage-*` y `.cardd-lock`. Solo retíralos después de comprobar que no hay
otra ejecución activa. No se reanudan descargas interrumpidas.

## Base de datos y pruebas

Este comando prepara archivos; **no crea tablas ni inserta registros en
PostgreSQL**. El esquema está en `app/bd/schema.sql` y el importador heredado en
`app/bd/scripts/import_cardd_to_db.py` (rutas relativas a `app/bd/` y variable
`DATABASE_URL`). Cargar PostgreSQL se realiza por separado.

Las pruebas usan paquetes sintéticos pequeños, un servidor HTTP local y un
sustituto controlado de `gdown`. No requieren el dataset ni acceso a Drive:

```bash
python3 -m unittest discover -s scripts/tests -v
```

La prueba de descarga real desde Drive necesita el enlace del paquete subido;
las pruebas del adaptador de Drive no acreditan esa descarga remota.
