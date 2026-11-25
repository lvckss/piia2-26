"""HTTP interno para el flujo de Spec 34 v1.7 / ADR 0007 (un worker)."""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.datastructures import UploadFile

from workflow import FlowError, MAX_BYTES, Workflow


def create_app(workflow=None):
    if workflow is None:
        from pipeline import ProductionPipeline
        workflow = Workflow(ProductionPipeline(), ttl=float(os.environ.get("PERITAJE_TTL_SECONDS", "3600")), capacity=int(os.environ.get("PERITAJE_CAPACITY", "2")))

    @asynccontextmanager
    async def lifespan(_app):
        async def sweep():
            while True:
                await asyncio.sleep(30)
                await asyncio.to_thread(workflow.cleanup)
        task = asyncio.create_task(sweep())
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            await asyncio.to_thread(workflow.close)

    app = FastAPI(lifespan=lifespan)

    @app.exception_handler(FlowError)
    async def flow_error(_request, error):
        return JSONResponse({"error": error.public}, status_code=error.status)

    @app.exception_handler(Exception)
    async def unexpected(_request, _error):
        error = FlowError("CONTRATO_INVALIDO", "El servicio no pudo completar la petición.", status=500)
        return JSONResponse({"error": error.public}, status_code=500)

    @app.middleware("http")
    async def no_cache(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/catalogos")
    def catalogues():
        return workflow.catalogue()

    @app.post("/peritajes", status_code=202)
    async def create(request: Request):
        key = request.headers.get("Idempotency-Key")
        workflow._key(key)
        if not request.headers.get("Content-Type", "").startswith("multipart/form-data;"):
            raise FlowError("PERITAJE_ENTRADA_INVALIDA", "Sube una sola imagen JPEG o PNG.")
        try:
            async with request.form(max_files=1, max_fields=0, max_part_size=MAX_BYTES) as form:
                entries = list(form.multi_items())
                if len(entries) != 1 or entries[0][0] != "file" or not isinstance(entries[0][1], UploadFile):
                    raise FlowError("PERITAJE_ENTRADA_INVALIDA", "Sube una sola imagen JPEG o PNG.")
                file = entries[0][1]
                data = await file.read(MAX_BYTES + 1)
                return await asyncio.to_thread(workflow.create, data, file.content_type, key, file.filename)
        except FlowError:
            raise
        except Exception as exc:
            raise FlowError("PERITAJE_ENTRADA_INVALIDA", "No se pudo leer la imagen enviada.") from exc

    @app.get("/peritajes/{case_id}")
    def state(case_id: str):
        return workflow.get(case_id)

    @app.delete("/peritajes")
    def discard_retained():
        return workflow.discard_retained()

    @app.post("/peritajes/{case_id}/informe", status_code=202)
    async def report(case_id: str, request: Request):
        try:
            body = await request.json()
            # Rechaza NaN/Infinity, que json.loads admite por defecto.
            json.dumps(body, allow_nan=False)
        except (ValueError, TypeError) as exc:
            raise FlowError("PERITAJE_ENTRADA_INVALIDA", "El contexto debe ser un JSON válido.", status=422) from exc
        return await asyncio.to_thread(workflow.generate, case_id, body, request.headers.get("Idempotency-Key"))

    @app.get("/peritajes/{case_id}/informe.md")
    def download(case_id: str):
        return Response(workflow.download(case_id), media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="informe.md"'})

    @app.delete("/peritajes/{case_id}", status_code=204)
    def discard(case_id: str):
        workflow.delete(case_id)
        return Response(status_code=204)

    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_app(), host="127.0.0.1", port=int(os.environ.get("ORQUESTADOR_PORT", "8004")))
