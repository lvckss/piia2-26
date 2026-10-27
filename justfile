# Plan v2, AC-006–AC-008:
# https://github.com/lvckss/piia2-26/issues/64#issuecomment-6449486337
app := 'entregas/cu-19-interpretacion-danos/app'
cardd_url := env('CARDD_URL', 'https://drive.google.com/file/d/1TXnFJUyNsxciAz4pxKtwD8lJ1uWzcdBK/view?usp=sharing')

# Mostrar los comandos disponibles.
default:
    @just --list

# Arrancar React + Vite (dependencias Bun instaladas previamente).
frontend:
    cd {{ quote(app + '/frontend') }} && bun run dev

# Arrancar Bun + Hono (requiere DATABASE_URL y PostgreSQL disponible).
backend:
    cd {{ quote(app) }} && bun run dev

# Preparar el entorno Python y descargar/verificar CARDD sin activar el venv.
cardd:
    @test -x .venv-cardd/bin/python || python3 -m venv .venv-cardd
    @.venv-cardd/bin/python -m pip install --disable-pip-version-check --quiet -r scripts/requirements-cardd.txt
    @.venv-cardd/bin/python scripts/download_cardd.py --url {{ quote(cardd_url) }}
