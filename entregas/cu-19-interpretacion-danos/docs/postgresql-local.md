# PostgreSQL del proyecto, siempre en Docker

El backend del explorador y el futuro RAG comparten una sola PostgreSQL con
pgvector. Se ejecuta desde el [Compose del caso](../compose.yaml), con un volumen
persistente; no necesita una instalación PostgreSQL en el host.

## Primera vez

Necesitas Docker con Compose, Just y Python 3.11+. Desde la carpeta del caso:

```bash
just db-init
```

Este comando crea `.env.postgres` con una contraseña aleatoria privada,
arranca PostgreSQL en Docker, prepara las tablas vacías del explorador y la
extensión vector, y configura `DATABASE_URL` en `app/.env` para el backend local.
Conserva las demás variables de la aplicación y respalda una conexión anterior
en `app/.env.before-docker` cuando cambia. Todos esos archivos son locales e
ignorados por Git.

Los scripts de inicialización SQL se ejecutan **solo al crear un volumen vacío**.
Si la base ya existe, repetir `db-init` conserva sus tablas, datos y contraseña.
Una instalación nueva crea tablas vacías; cargar CARDD usa el importador
existente descrito en [la guía de datos](../scripts/README.md#base-de-datos-y-pruebas).

## Siguientes arranques

```bash
just db-up
just backend
```

`db-up` arranca el servicio y espera a que esté disponible. No vuelve a cargar
el esquema, importar datos ni generar embeddings. Si el backend ya estaba en
marcha cuando se configuró la conexión, reinícialo. Evita una `DATABASE_URL`
exportada antigua en el shell: tiene prioridad sobre el `.env` que lee Bun.

Para abrir una consola o detener la base conservando sus datos:

```bash
just db-psql
just db-stop
```

## Conexión y persistencia

| Cliente | Servidor | Puerto por defecto |
|---|---|---|
| Backend o Python en tu equipo | `127.0.0.1` | `5433` |
| Futuros servicios del mismo Compose | `postgres` | `5432` |

Ambos usan la misma base `cardd_webapp`. Las credenciales están en
`.env.postgres`; el puerto solo se publica en la interfaz local. Para otro puerto
en la primera preparación: `POSTGRES_PORT=5434 just db-init`. Después utiliza
el valor guardado en `.env.postgres`. Cambiar una contraseña en ese archivo
no modifica por sí solo la almacenada en un volumen ya inicializado.

Se fija PostgreSQL 18 / pgvector 0.8.7 por digest de imagen. El volumen
`cu19_postgres_data` se monta en `/var/lib/postgresql`, como requiere la imagen
de PostgreSQL 18. Detener o recrear el contenedor conserva el volumen.
`docker compose down` sin `-v` también lo conserva; **`down -v` elimina los datos**
y no forma parte del uso habitual.

El esquema `rag` está preparado para las futuras tablas de recuperación; las
tablas del explorador siguen en `public`. Todavía no hay indexado ni búsqueda:
este incremento prepara PostgreSQL dentro de #32. #34 integrará el resto de
servicios en este mismo Compose.

Los respaldos de una migración puntual pueden conservarse en `backups/postgres/`,
ignorada por Git. El uso habitual se realiza desde Docker; no sincroniza datos
con una PostgreSQL del host ni incorpora una herramienta de migración.

## Verificación reproducible

La prueba de AC-013 usa una copia de la carpeta en una ruta con espacios, un
proyecto Compose aislado y un puerto libre. Comprueba el primer `db-init`, la
configuración de conexión del backend, pgvector, la repetición sin perder datos y `db-up` después
de detener/recrear el contenedor. Elimina únicamente sus recursos de prueba.

```bash
RUN_POSTGRES_INTEGRATION=1 python3 -m unittest discover \
  -s scripts/tests -p test_postgres_init.py -v
```

Sin esa variable la prueba se omite y no acredita verificación de PostgreSQL.
No necesita clientes PostgreSQL en el host ni acceso a OpenAI.

Referencias: [pgvector para Docker](https://github.com/pgvector/pgvector#docker)
y [volumen e inicialización de PostgreSQL](https://hub.docker.com/_/postgres).
