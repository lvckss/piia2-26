import { afterAll, expect, test } from 'bun:test'
import app from '../app'
import sql from '../bd/bd'

// specs/34-orquestacion-web.md AC-001/011: backend real, sin ML ni proveedor.
afterAll(async () => { await sql.end({ timeout: 0 }) })
test('AC-001/011: la ruta de análisis existe y rechaza una entrada sin imagen como JSON', async () => {
  const response = await app.request('/api/peritajes', { method: 'POST', headers: { 'Idempotency-Key': 'sin-imagen' } })
  expect(response.status).toBe(400)
  expect(response.headers.get('content-type')).toContain('application/json')
  expect((await response.json()).error.codigo).toBe('PERITAJE_ENTRADA_INVALIDA')
})
test('AC-011: una ruta API desconocida no devuelve texto ni la página HTML', async () => {
  const response = await app.request('/api/ruta-desconocida')
  expect(response.status).toBe(404)
  expect(response.headers.get('content-type')).toContain('application/json')
})
