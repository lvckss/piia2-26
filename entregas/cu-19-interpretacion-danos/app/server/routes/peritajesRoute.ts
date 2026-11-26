import { Hono, type Context } from 'hono'
import { bodyLimit } from 'hono/body-limit'

// Spec 34 v1.7, AC-001/004/010/011/012. Hono solo transporta el contrato:
// Python conserva el estado, valida el contexto y ejecuta los agentes.
export function createPeritajeRoutes(
  upstream = process.env.ORQUESTADOR_URL ?? 'http://127.0.0.1:8004',
  request: typeof fetch = fetch,
) {
  const error = (c: Context, status: 400 | 413 | 502 | 503 | 504, codigo: string, mensaje: string) =>
    c.json({ error: { codigo, etapa: 'entrada', mensaje, reintentable: status >= 500 } }, status)
  const limit = bodyLimit({ maxSize: 10 * 1024 * 1024 + 128 * 1024, onError: c => error(c, 413, 'PERITAJE_ENTRADA_INVALIDA', 'La imagen supera el límite de 10 MiB.') })
  const proxy = async (c: Context) => {
    const path = c.req.path.replace(/^\/api/, '')
    const method = c.req.method
    const headers = new Headers()
    if (method === 'POST') {
      const key = c.req.header('Idempotency-Key')
      if (!key || key.length > 200) return error(c, 400, 'PERITAJE_ENTRADA_INVALIDA', 'Falta una clave de petición válida.')
      headers.set('Idempotency-Key', key)
      const type = c.req.header('Content-Type') ?? ''
      if (path === '/peritajes' && !type.startsWith('multipart/form-data;'))
        return error(c, 400, 'PERITAJE_ENTRADA_INVALIDA', 'Sube una sola imagen JPEG o PNG.')
      if (path.endsWith('/informe') && !type.startsWith('application/json'))
        return error(c, 400, 'PERITAJE_ENTRADA_INVALIDA', 'El contexto del siniestro debe enviarse como JSON.')
      headers.set('Content-Type', type)
    }
    try {
      const response = await request(`${upstream.replace(/\/$/, '')}${path}`, {
        method, headers, body: method === 'POST' ? await c.req.arrayBuffer() : undefined,
        signal: AbortSignal.timeout(15_000), redirect: 'error',
      })
      const contentType = response.headers.get('content-type') ?? ''
      if (method === 'DELETE' && response.status === 204)
        return new Response(null, { status: 204, headers: { 'Cache-Control': 'no-store' } })
      const download = method === 'GET' && path.endsWith('/informe.md') && response.ok
      if (!contentType.includes(download ? 'text/markdown' : 'application/json'))
        return error(c, 502, 'CONTRATO_INVALIDO', 'El servicio de análisis devolvió una respuesta incompatible.')
      const outgoing = new Headers({ 'Content-Type': contentType, 'Cache-Control': 'no-store' })
      const disposition = response.headers.get('content-disposition')
      if (download && disposition) outgoing.set('Content-Disposition', disposition)
      return new Response(response.body, { status: response.status, headers: outgoing })
    } catch (cause) {
      if (cause instanceof DOMException && ['TimeoutError', 'AbortError'].includes(cause.name))
        return error(c, 504, 'TIMEOUT', 'Se agotó el tiempo de conexión con el servicio de análisis.')
      return error(c, 503, 'ORQUESTADOR_NO_DISPONIBLE', 'El servicio de análisis no está disponible. Comprueba que esté iniciado.')
    }
  }
  return new Hono()
    .get('/catalogos', proxy)
    .post('/peritajes', limit, proxy)
    .delete('/peritajes', proxy)
    .get('/peritajes/:id{[A-Za-z0-9_-]+}', proxy)
    .delete('/peritajes/:id{[A-Za-z0-9_-]+}', proxy)
    .post('/peritajes/:id{[A-Za-z0-9_-]+}/informe', limit, proxy)
    .get('/peritajes/:id{[A-Za-z0-9_-]+}/informe.md', proxy)
}
