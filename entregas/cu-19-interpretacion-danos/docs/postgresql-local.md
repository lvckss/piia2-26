# PostgreSQL compartida: explorador y RAG

El [Compose del caso](../compose.yaml) aloja una sola PostgreSQL para las tablas
del explorador y las futuras tablas del RAG. Este incremento de #32 prepara la
base: **todavía no indexa documentos ni genera embeddings**. #34 incorporará el
resto de los servicios al mismo archivo.

Se utiliza PostgreSQL 18 y pgvector 0.8.7, con la imagen fijada por digest. El
volumen `cu19_postgres_data` se monta en `/var/lib/postgresql`, la ubicación de
la imagen de PostgreSQL 18. Las credenciales locales viven en `.env.postgres`,
ignorada por Git; el arranque no llama a OpenAI.

## Si ya tienes la base del explorador en localhost

Necesitas Docker Engine con Compose v2, Python 3.11+ y los clientes `psql`,
`pg_dump` y `pg_restore` de PostgreSQL 18. El cliente `pg_dump` no debe ser de
una versión mayor inferior a la del servidor de origen. Para este procedimiento
se ha comprobado PostgreSQL 18.6 en ambos extremos. La conexión actual debe
estar en `app/.env` como una sola línea `DATABASE_URL=...`.

Desde la raíz del caso:

```bash
just db-configure       # genera una contraseña privada; conserva config existente
just db-up              # PostgreSQL accesible en 127.0.0.1:5433
just db-migration-plan  # simulación: no conecta ni cambia datos
just db-migrate         # copia, verifica y actualiza app/.env
```

La copia se hace con `pg_dump` en formato custom y `pg_restore` en una sola
transacción. Se rechaza un destino que ya tenga tablas, secuencias u otros
objetos de usuario; no hay `--clean`, borrado de tablas ni sobrescritura de una
base poblada. Se conservan las tablas, sus filas, IDs, restricciones, índices y
posiciones de secuencias. La restauración utiliza el propietario configurado
en Docker; no copia roles ni permisos globales de otras bases del servidor.

El script contrasta los recuentos y SHA-256 de las filas ordenadas, las columnas,
las restricciones, los índices y las secuencias. Comprueba que el origen no haya
cambiado durante la operación y que funcione la distancia coseno de pgvector.
**No escribas en la base de origen mientras copias.** Si detecta cambios o falla
una comprobación, conserva la conexión original y el respaldo para investigar.

La comparación normaliza únicamente una representación equivalente que
PostgreSQL puede reescribir al restaurar: el cast de un array de constantes
`varchar` a `text[]`, frente al cast individual de sus elementos. El resto de
la restricción, incluidos los valores permitidos, se sigue comparando.

Si la restauración terminó pero falló la verificación, se puede volver a
comprobar esa copia sin restaurar sobre ella. Con `app/.env` aún apuntando al
origen y la ruta real del respaldo:

```bash
python3 scripts/migrate_postgres.py --execute \
  --verify-backup backups/postgres/<fecha-UTC> --update-app-env
```

Este modo no escribe en las tablas: compara otra vez ambas bases y exige que
el archivo de conexión coincida con el respaldo antes de permitir el cambio.

Solo después de verificar cambia `DATABASE_URL` en `app/.env`. Reinicia un
backend que ya estuviera en ejecución para que lea la conexión nueva. Si el
shell tiene su propia `DATABASE_URL`, elimina esa exportación o actualízala:
el entorno del proceso tiene prioridad sobre `.env`.

El origen de localhost:5432 se conserva y sigue disponible; el contenedor usa
5433 para permitir comparar ambas copias. **No hay sincronización posterior**:
una vez cambiado el backend, sus nuevas escrituras van a Docker.

Cada operación deja en `backups/postgres/<fecha-UTC>/`, fuera de Git:

- `database.dump`: respaldo completo de esa base, sin roles globales.
- `app.env.before`: configuración anterior, incluida su conexión privada.
- `verification.json`: recuentos, huellas y versiones comprobadas.

Los archivos se crean con permisos `0600` y el directorio de cada copia con
`0700`. No subas estos respaldos al repositorio ni los pegues en comentarios.

Para volver a usar el origen, conserva primero cualquier escritura nueva en
Docker y restaura manualmente la línea de conexión de `app.env.before`; reinicia
el backend. Volver al origen no traslada las escrituras hechas después del corte.

## Instalación nueva, sin base previa

```bash
just db-configure
just db-up
just db-init
```

`db-init` crea las tablas vacías con `app/bd/schema.sql`, en una transacción;
si ya existen, falla sin reemplazarlas. Después se usa el importador de CARDD
documentado en [la guía de datos](../scripts/README.md#base-de-datos-y-pruebas).
La descarga de archivos con `just cardd` sigue siendo un paso separado.

Configura `DATABASE_URL` en `app/.env` usando usuario, contraseña, puerto y base
de `.env.postgres`; codifica los caracteres reservados del usuario/contraseña
si construyes una URL. La migración de una base existente hace ese cambio
automáticamente. Las credenciales de este archivo se aplican al inicializar un
volumen vacío: editarlo después no cambia por sí solo la contraseña almacenada.

## Conexiones y uso habitual

| Cliente | Servidor | Puerto | Base |
|---|---|---|---|
| Backend o Python ejecutados en el host | `127.0.0.1` | `5433` por defecto | `cardd_webapp` por defecto |
| Futuros servicios del mismo Compose | `postgres` | `5432` | La misma base configurada |

El puerto se publica solo en la interfaz local. Se puede cambiar `POSTGRES_PORT`
en `.env.postgres` si hay conflicto. No uses `localhost` desde otro contenedor:
allí apunta a ese contenedor, no al servicio PostgreSQL.

```bash
just db-up
just db-psql
just backend
just db-stop
```

Dentro de `psql`:

```sql
\dt public.*
SELECT extversion FROM pg_extension WHERE extname = 'vector';
SELECT '[1,0,0]'::vector <=> '[0,1,0]'::vector; -- 1
```

El esquema `rag` está reservado para el componente de recuperación y no cambia
las tablas `public.imagenes`, `public.instancias` o `public.etiquetas`. El schema
de fragmentos/generaciones y el indexador se entregarán en los siguientes pasos
de #32. PostgreSQL no necesita un segundo servicio para los vectores.

`db-stop`, `docker compose down` sin `-v` y recrear el contenedor conservan el
volumen. **`down -v` elimina los datos**; no forma parte de los comandos normales
de este proyecto. Los scripts de `docker-entrypoint-initdb.d` se ejecutan solo
al crear un volumen vacío. Para una base que ya existía sin la extensión:

```bash
docker compose --env-file .env.postgres exec -T postgres \
  sh -c 'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < app/bd/docker/10-vector.sql
```

## Pruebas de integración

`scripts/tests/test_postgres.py` traza estas verificaciones a la spec 32,
AC-013 y preservación del explorador. Usa una PostgreSQL real con pgvector;
crea y elimina exclusivamente bases temporales `cu19_test_<uuid>`.

Con `POSTGRES_TEST_URL` configurada de forma privada para una PostgreSQL
**desechable** que tenga la extensión y el esquema `rag` preparados:

```bash
python3 -m unittest discover -s scripts/tests -p test_postgres.py -v
```

Sin esa variable las cuatro pruebas de integración se omiten y **no acreditan
verificación de PostgreSQL**; la prueba de normalización sí puede ejecutarse.
La comprobación con los datos reales y la persistencia al recrear el contenedor
se registran por separado en la evidencia de #32. No requieren acceso a OpenAI.

Referencias: [pgvector para Docker](https://github.com/pgvector/pgvector#docker),
[volumen e inicialización de PostgreSQL](https://hub.docker.com/_/postgres),
[pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html) y
[pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html).
