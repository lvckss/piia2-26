import { z } from 'zod'

const option = z.object({ id: z.string(), nombre: z.string() })
const exportedImage = z.object({
  id: z.number().int().positive(), id_externo: z.number().int(), file_name: z.string(),
  split: z.enum(['train', 'val', 'test']), ruta_imagen: z.string(), ruta_thumbnail: z.string().nullable().optional(),
  width: z.number().int().positive(), height: z.number().int().positive(),
  numero_instancias: z.number().int().default(0), numero_categorias: z.number().int().default(0), labels: z.array(z.string()).default([]),
})
export const catalogosSchema = z.object({
  vehiculos: z.array(option), polizas: z.array(option), regiones: z.array(option),
  tipos_taller: z.array(option), acabados: z.array(option), tipos_pieza: z.array(option),
  fuente_detecciones: z.enum(['api', 'documentos']).default('api'),
  imagenes_exportadas: z.array(exportedImage).optional(),
}).superRefine((catalogue, ctx) => {
  if (catalogue.fuente_detecciones === 'documentos' && !catalogue.imagenes_exportadas)
    ctx.addIssue({ code: 'custom', message: 'Falta el lote de documentos.' })
})
export type Catalogos = z.infer<typeof catalogosSchema>
const errorSchema = z.object({
  codigo: z.string(), mensaje: z.string(), etapa: z.string().optional(), reintentable: z.boolean().optional(),
})
const analisisSchema = z.object({
  image_id: z.union([z.string(), z.number()]),
  resumen_filtro_previo: z.record(z.string(), z.unknown()).optional(),
  vehiculo: z.object({ categoria: z.string(), vehiculo_id_referencia: z.string().nullable() }),
  findings: z.array(z.object({
    finding_id: z.string(), category: z.string(), confidence_tier: z.string(),
    vision_verdict: z.string(), score: z.number(), pieza_id: z.string().nullable(),
    severidad: z.string().nullable(), vision_description: z.string(),
  })),
})
const ragSchema = z.object({
  estado: z.enum(['recuperadas', 'parcial', 'sin_resultados', 'error', 'no_aplica']),
  consultas: z.array(z.object({
    tema: z.string(), estado: z.string(),
    incidencias: z.array(z.object({ mensaje: z.string() }).passthrough()).optional(),
  }).passthrough()).optional(),
}).passthrough()
export const ejecucionSchema = z.object({
  ejecucion_id: z.string().min(1),
  estado: z.enum(['analizando', 'esperando_datos', 'generando_informe', 'completada', 'error']),
  etapa: z.enum(['entrada', 'piia1', 'agente1', 'agente2', 'agente3', 'verificacion']),
  analisis: analisisSchema.nullable(),
  resultado: z.object({
    markdown: z.string(),
    agente2: z.object({ diagnostico_rag: ragSchema }).passthrough(),
  }).nullable(),
  error: errorSchema.nullable(),
}).superRefine((e, ctx) => {
  if (e.estado === 'completada' && (!e.resultado || e.error)) ctx.addIssue({ code: 'custom', message: 'Informe incompleto.' })
  if (e.estado === 'esperando_datos' && !e.analisis) ctx.addIssue({ code: 'custom', message: 'Falta el análisis.' })
  if (e.estado === 'error' && !e.error) ctx.addIssue({ code: 'custom', message: 'Falta la causa del error.' })
  if (e.estado !== 'completada' && e.resultado) ctx.addIssue({ code: 'custom', message: 'Resultado sin verificar.' })
})
export type Ejecucion = z.infer<typeof ejecucionSchema>
export type Analisis = NonNullable<Ejecucion['analisis']>
export type PeticionInforme = {
  contexto: {
    vehiculo_id: string; region: string; tipo_taller: string; acabado: string; tipo_pieza: string;
    rol: 'propio' | 'tercero_perjudicado'; edad_anios: number; km: number; poliza_id?: string;
  };
  seleccion_vehiculo?: { tipo: 'referencia_confirmada' | 'seleccion_usuario'; vehiculo_id: string };
}

export class ErrorPeritaje extends Error {
  status: number
  codigo: string
  constructor(message: string, status = 0, codigo = 'CONEXION_ERROR') {
    super(message); this.status = status; this.codigo = codigo
  }
}

async function request(path: string, init?: RequestInit): Promise<unknown> {
  let response: Response
  try { response = await fetch(path, init) }
  catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    throw new ErrorPeritaje('No se pudo conectar con el servicio. No se ha reenviado la petición automáticamente.')
  }
  let body: unknown
  try { body = await response.json() }
  catch { throw new ErrorPeritaje('El servicio no devolvió una respuesta de peritaje válida.', response.status, 'CONTRATO_INVALIDO') }
  if (!response.ok) {
    const parsed = z.object({ error: errorSchema }).safeParse(body)
    throw new ErrorPeritaje(parsed.success ? parsed.data.error.mensaje : `El servicio no está disponible (${response.status}).`, response.status, parsed.success ? parsed.data.error.codigo : 'SERVICIO_ERROR')
  }
  return body
}
async function execution(path: string, init?: RequestInit, id?: string) {
  const parsed = ejecucionSchema.safeParse(await request(path, init))
  if (!parsed.success || (id && parsed.data.ejecucion_id !== id)) throw new ErrorPeritaje('El servicio devolvió un estado de ejecución incompatible.', 0, 'CONTRATO_INVALIDO')
  return parsed.data
}
const pathFor = (id: string) => `/api/peritajes/${encodeURIComponent(id)}`
export const peritajeApi = {
  async catalogos(signal?: AbortSignal) {
    const result = catalogosSchema.safeParse(await request('/api/catalogos', { signal }))
    if (!result.success) throw new ErrorPeritaje('Los catálogos recibidos no tienen el formato esperado.', 0, 'CONTRATO_INVALIDO')
    return result.data
  },
  analizar(file: File, clave: string) {
    const body = new FormData(); body.append('file', file)
    return execution('/api/peritajes', { method: 'POST', headers: { 'Idempotency-Key': clave }, body })
  },
  consultar(id: string, signal?: AbortSignal) { return execution(pathFor(id), { signal }, id) },
  informe(id: string, body: PeticionInforme, clave: string) {
    return execution(`${pathFor(id)}/informe`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': clave }, body: JSON.stringify(body) }, id)
  },
  async descartar(id: string) {
    let response: Response
    try { response = await fetch(pathFor(id), { method: 'DELETE' }) }
    catch { throw new ErrorPeritaje('No se pudo descartar el caso. Vuelve a intentarlo para liberar sus archivos temporales.') }
    if (response.status !== 204 && response.status !== 404) throw new ErrorPeritaje('No se pudo descartar el caso. Puede que todavía esté trabajando.', response.status)
  },
}

export const AVISO_V14 = 'Vehículo no identificado en la imagen: el presupuesto usa el vehículo de menor coste del catálogo. Es una estimación a la baja: si el taller encuentra un importe mayor, avisará a la aseguradora para revisarlo.'
export async function validarImagen(file: File): Promise<void> {
  if (!['image/jpeg', 'image/png'].includes(file.type)) throw new Error('Selecciona una imagen JPEG o PNG.')
  if (file.size === 0) throw new Error('El archivo está vacío.')
  if (file.size > 10 * 1024 * 1024) throw new Error('La imagen supera el límite de 10 MiB.')
  let bitmap: ImageBitmap
  try { bitmap = await createImageBitmap(file) }
  catch { throw new Error('No se pudo decodificar la imagen. Selecciona otro archivo JPEG o PNG.') }
  const pixels = bitmap.width * bitmap.height; bitmap.close()
  if (pixels > 20_000_000) throw new Error('La imagen supera el límite de 20 millones de píxeles.')
}

export function descargarMarkdown(markdown: string, id: string) {
  const url = URL.createObjectURL(new Blob([markdown], { type: 'text/markdown;charset=utf-8' }))
  const a = document.createElement('a'); a.href = url; a.download = `peritaje-${id.replace(/[^a-zA-Z0-9_-]/g, '_')}.md`
  a.click(); window.setTimeout(() => URL.revokeObjectURL(url), 0)
}
