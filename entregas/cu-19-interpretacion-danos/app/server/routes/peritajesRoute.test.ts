import { expect, test } from 'bun:test'
import { Hono } from 'hono'
import { createPeritajeRoutes } from './peritajesRoute'

// specs/34-orquestacion-web.md AC-001/010/011/012. Transporte sin proveedores.
test('AC-001/010: conserva el multipart y la clave sin reenviar cookies ni credenciales', async () => {
  let calls = 0
  const request = (async (url: string, options: RequestInit) => {
    calls++
    expect(url).toBe('http://orquestador/peritajes')
    const headers = new Headers(options.headers)
    expect(headers.get('Idempotency-Key')).toBe('same-key')
    expect(headers.get('cookie')).toBeNull()
    expect(headers.get('Authorization')).toBeNull()
    const parsed = await new Response(options.body, { headers }).formData()
    expect(await (parsed.get('file') as File).text()).toBe('imagen')
    return Response.json({ ejecucion_id: 'case', estado: 'analizando' }, { status: 202 })
  }) as typeof fetch
  const app = new Hono().route('/api', createPeritajeRoutes('http://orquestador', request))
  const body = new FormData(); body.append('file', new File(['imagen'], 'foto.png', { type: 'image/png' }))
  const response = await app.request('/api/peritajes', { method: 'POST', body, headers: { 'Idempotency-Key': 'same-key', cookie: 'private=value', Authorization: 'private' } })
  expect(response.status).toBe(202)
  expect(calls).toBe(1)
})

test('AC-011: servicio caído y respuesta incompatible producen errores JSON comprensibles', async () => {
  for (const request of [async () => { throw new Error('private host details') }, async () => new Response('Not Found', { status: 404 })]) {
    const app = new Hono().route('/api', createPeritajeRoutes('http://orquestador', request as typeof fetch))
    const response = await app.request('/api/catalogos')
    expect([502, 503]).toContain(response.status)
    const result = await response.json()
    expect(result.error.mensaje).toBeTruthy()
    expect(JSON.stringify(result)).not.toContain('private')
  }
})

test('AC-012: descarga los mismos bytes y permite descartar sin contenido JSON', async () => {
  const markdown = '# Informe\n\nImporte: 12,00 €\n'
  const request = (async (_url: string, options: RequestInit) => options.method === 'DELETE'
    ? new Response(null, { status: 204 })
    : new Response(markdown, { headers: { 'Content-Type': 'text/markdown; charset=utf-8', 'Content-Disposition': 'attachment; filename="informe.md"' } })) as typeof fetch
  const app = new Hono().route('/api', createPeritajeRoutes('http://orquestador', request))
  const response = await app.request('/api/peritajes/case/informe.md')
  expect(await response.text()).toBe(markdown)
  expect(response.headers.get('cache-control')).toBe('no-store')
  expect((await app.request('/api/peritajes/case', { method: 'DELETE' })).status).toBe(204)
})
