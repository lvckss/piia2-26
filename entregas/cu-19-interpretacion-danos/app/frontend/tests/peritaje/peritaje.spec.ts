import { expect, test, type Page } from '@playwright/test'

// Spec 34 v1.7 AC-001/003/004/006–012 y AC-015 del complemento UI:
// https://github.com/lvckss/piia2-26/issues/34#issuecomment-7135966562
// Solo dobles HTTP en pruebas: el producto nunca importa estas respuestas.
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC', 'base64')
const markdown = '# Informe de peritaje — imagen 82\n\n## Resumen\n\nEstimación: **123,45 €**.\n\n<script>window.peritajeInseguro = true</script>\n\n| Concepto | Importe |\n|---|---|\n| Reparación | 123,45 € |\n'
const option = (id: string, nombre: string) => ({ id, nombre })
const catalogos = {
  vehiculos: [option('V02', 'SEAT León'), option('V05', 'Volkswagen Golf'), option('V14', 'Dacia Sandero')],
  polizas: [option('P-TR-FR300', 'Todo riesgo con franquicia'), option('P-TERC-BASICO', 'Terceros básico')],
  regiones: [option('Madrid', 'Madrid')],
  tipos_taller: [option('multimarca', 'Multimarca')],
  acabados: [option('metalizado', 'Metalizado'), option('solido', 'Sólido')],
  tipos_pieza: [option('oem', 'Original (OEM)')],
}

function estado(fase = 'esperando_datos', desconocido = false) {
  return {
    ejecucion_id: 'caso-82', estado: fase, etapa: fase === 'completada' ? 'verificacion' : 'agente1',
    analisis: {
      image_id: 82, resumen_filtro_previo: { total_detecciones: 3, analizadas: 1 },
      vehiculo: { categoria: desconocido ? 'desconocido' : 'C', vehiculo_id_referencia: desconocido ? null : 'V02' },
      findings: [{ finding_id: '82-1', category: 'dent', confidence_tier: 'confirmed', vision_verdict: 'confirmado', pieza_id: 'PARAG_DEL', severidad: 'moderado', score: 0.83, vision_description: 'Abolladura en el paragolpes delantero.' }],
    },
    resultado: fase === 'completada' ? {
      markdown, agente2: { diagnostico_rag: { estado: 'parcial', consultas: [{ tema: 'Daños propios', estado: 'sin_resultados', incidencias: [{ mensaje: 'Sin fuentes para este tema.' }] }] } },
    } : null,
    error: null,
  }
}

async function preparar(page: Page, opts: { desconocido?: boolean; contextoInvalido?: boolean; perdido?: boolean; fallo?: boolean; originalAusente?: boolean; catalogoAusente?: boolean } = {}) {
  const llamadas = { analisis: 0, informes: 0, lecturas: 0, borrados: 0, imagenes: [] as string[], cuerpos: [] as Record<string, unknown>[], claves: [] as string[], archivos: [] as Buffer[] }
  let generado = false
  await page.route('**/api/images**', async route => {
    llamadas.imagenes.push(route.request().url())
    await route.fulfill({ json: { items: [82, 381].map(id => ({ id, id_externo: id, file_name: `${String(id).padStart(6, '0')}.jpg`, ruta_imagen: `test/${id}.png`, ruta_thumbnail: `test/${id}.png`, width: 1, height: 1, split: 'test', labels: ['dent'] })), nextCursor: null } })
  })
  await page.route('**/dataset/**', route => opts.originalAusente ? route.fulfill({ status: 404 }) : route.fulfill({ contentType: 'image/png', body: PNG }))
  await page.route('**/api/catalogos', route => opts.catalogoAusente ? route.fulfill({ status: 503, json: { error: { mensaje: 'Catálogos no disponibles.' } } }) : route.fulfill({ json: catalogos }))
  await page.route('**/api/peritajes**', async route => {
    const req = route.request(), url = new URL(req.url())
    if (req.method() === 'DELETE') { llamadas.borrados++; return route.fulfill({ status: 204 }) }
    if (req.method() === 'POST' && url.pathname.endsWith('/informe')) {
      llamadas.informes++; llamadas.cuerpos.push(req.postDataJSON()); llamadas.claves.push(req.headers()['idempotency-key'])
      if (opts.contextoInvalido && llamadas.informes === 1) return route.fulfill({ status: 422, json: { error: { codigo: 'PERITAJE_ENTRADA_INVALIDA', etapa: 'entrada', mensaje: 'Kilómetros inválidos.', reintentable: false, campos: { km: 'Revisa los kilómetros.' } } } })
      generado = true
      return route.fulfill({ status: 202, json: estado('generando_informe', opts.desconocido) })
    }
    if (req.method() === 'POST') {
      llamadas.analisis++; llamadas.archivos.push(req.postDataBuffer()!); llamadas.claves.push(req.headers()['idempotency-key'])
      return route.fulfill({ status: 202, json: estado('analizando', opts.desconocido) })
    }
    llamadas.lecturas++
    if (opts.perdido) return route.fulfill({ status: 404, json: { error: { codigo: 'EJECUCION_NO_DISPONIBLE', mensaje: 'La ejecución ya no está disponible.', etapa: 'entrada', reintentable: false } } })
    if (generado && opts.fallo) return route.fulfill({ json: { ...estado('error'), error: { codigo: 'CIFRAS_INCONSISTENTES', etapa: 'verificacion', mensaje: 'El informe contiene cifras inconsistentes.', reintentable: false } } })
    return route.fulfill({ json: estado(generado ? 'completada' : 'esperando_datos', opts.desconocido) })
  })
  await page.goto('/peritaje')
  return llamadas
}

async function seleccionar(page: Page) {
  await page.getByRole('button', { name: 'Seleccionar imagen 000082.jpg', exact: true }).click()
  await expect(page.getByRole('img', { name: 'Vista previa de 000082.jpg' })).toBeVisible()
}
async function analizar(page: Page) {
  await seleccionar(page)
  await page.getByRole('button', { name: 'Analizar imagen', exact: true }).click()
  await expect(page.getByText('Abolladura en el paragolpes delantero.')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Vehículo y siniestro', exact: true })).toBeVisible()
}
async function contexto(page: Page, tercero = false) {
  const confirmar = page.getByRole('button', { name: 'Confirmar vehículo propuesto' })
  if (await confirmar.count()) await confirmar.click()
  const budget = page.getByRole('button', { name: /Datos para el presupuesto/ })
  if (await budget.getAttribute('aria-expanded') !== 'true') await budget.click()
  await page.getByLabel('Antigüedad (años)').fill('3')
  await page.getByLabel('Kilómetros', { exact: true }).fill('42000')
  await page.getByLabel('Región').selectOption('Madrid')
  await page.getByLabel('Tipo de taller').selectOption('multimarca')
  await page.getByLabel('Acabado de pintura').selectOption('metalizado')
  await page.getByLabel('Tipo de pieza').selectOption('oem')
  await page.getByLabel('Rol en el siniestro').selectOption(tercero ? 'tercero_perjudicado' : 'propio')
  if (!tercero) await page.getByLabel('Póliza').selectOption('P-TR-FR300')
}

test('AC-001/015: nueva pestaña, selección y filtros sin inferencia', async ({ page }) => {
  const l = await preparar(page)
  await expect(page.getByRole('link', { name: 'Peritaje', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Explorar dataset' })).toBeVisible()
  await page.getByLabel('Partición del dataset').selectOption('test')
  await seleccionar(page)
  expect(l.imagenes.some(u => new URL(u).searchParams.get('split') === 'test')).toBeTruthy()
  expect(l.analisis).toBe(0)
  await page.getByRole('button', { name: 'Analizar imagen', exact: true }).evaluate((b: HTMLButtonElement) => { b.click(); b.click() })
  await expect(page.getByText('Abolladura en el paragolpes delantero.')).toBeVisible()
  expect(l.analisis).toBe(1)
  expect(l.archivos[0].includes(PNG)).toBeTruthy()
  expect(l.claves[0]).toBeTruthy()
})

test('AC-001: subida válida espera al botón; texto, vacío y exceso de tamaño se rechazan', async ({ page }) => {
  const l = await preparar(page)
  const input = page.getByLabel('Subir imagen JPEG o PNG')
  await input.setInputFiles({ name: 'foto.png', mimeType: 'image/png', buffer: PNG })
  await expect(page.getByRole('img', { name: 'Vista previa de foto.png' })).toBeVisible()
  expect(l.analisis).toBe(0)
  await input.setInputFiles({ name: 'texto.txt', mimeType: 'text/plain', buffer: Buffer.from('texto') })
  await expect(page.getByRole('alert')).toContainText('JPEG o PNG')
  await input.setInputFiles({ name: 'vacia.png', mimeType: 'image/png', buffer: Buffer.alloc(0) })
  await expect(page.getByRole('alert')).toContainText('vacío')
  await input.setInputFiles({ name: 'enorme.png', mimeType: 'image/png', buffer: Buffer.alloc(10 * 1024 * 1024 + 1) })
  await expect(page.getByRole('alert')).toContainText('10 MiB')
  await input.setInputFiles({ name: 'corrupta.png', mimeType: 'image/png', buffer: Buffer.from('no es una imagen') })
  await expect(page.getByRole('alert')).toContainText('decodificar')
  expect(l.analisis).toBe(0)
  await expect(page.getByRole('button', { name: 'Analizar imagen', exact: true })).toBeDisabled()
})

test('AC-003/004/006/012: formulario válido, hallazgos intactos y descarga literal segura', async ({ page }) => {
  const l = await preparar(page)
  await analizar(page)
  await expect(page.getByRole('button', { name: 'Generar informe', exact: true })).toBeDisabled()
  await contexto(page)
  await page.getByRole('button', { name: 'Generar informe', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Informe de peritaje — imagen 82' })).toBeVisible()
  expect(l.analisis).toBe(1); expect(l.informes).toBe(1)
  expect(l.cuerpos[0]).toEqual({ contexto: { vehiculo_id: 'V02', region: 'Madrid', tipo_taller: 'multimarca', acabado: 'metalizado', tipo_pieza: 'oem', rol: 'propio', edad_anios: 3, km: 42000, poliza_id: 'P-TR-FR300' }, seleccion_vehiculo: { tipo: 'referencia_confirmada', vehiculo_id: 'V02' } })
  expect(await page.evaluate(() => (window as unknown as Record<string, unknown>).peritajeInseguro)).toBeUndefined()
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Descargar Markdown' }).click()])
  expect(download.suggestedFilename()).toBe('peritaje-caso-82.md')
  const stream = await download.createReadStream(), chunks: Buffer[] = []
  for await (const chunk of stream!) chunks.push(chunk)
  expect(Buffer.concat(chunks).toString('utf8')).toBe(markdown)
  await page.getByRole('button', { name: 'Nuevo peritaje', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Seleccionar imagen 000082.jpg', exact: true })).toBeVisible()
  expect(l.borrados).toBe(1)
})

test('AC-004: error 422 permite corregir sin repetir visión', async ({ page }) => {
  const l = await preparar(page, { contextoInvalido: true })
  await analizar(page); await contexto(page)
  await page.getByRole('button', { name: 'Generar informe', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Kilómetros inválidos')
  await expect(page.getByLabel('Kilómetros', { exact: true })).toHaveValue('42000')
  await page.getByLabel('Kilómetros', { exact: true }).fill('40000')
  await page.getByRole('button', { name: 'Generar informe', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Descargar Markdown' })).toBeVisible()
  expect(l.analisis).toBe(1); expect(l.informes).toBe(2)
  expect(l.claves[1]).not.toBe(l.claves[2])
})

test('AC-003/008: desconocido muestra V14 sin fabricar procedencia', async ({ page }) => {
  const l = await preparar(page, { desconocido: true })
  await analizar(page)
  await expect(page.getByText('Vehículo no identificado en la imagen:', { exact: false })).toBeVisible()
  await expect(page.getByText('La pérdida total no es fiable para el vehículo real.', { exact: false })).toBeVisible()
  await contexto(page)
  await page.getByRole('button', { name: 'Generar informe', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Descargar Markdown' })).toBeVisible()
  expect(l.cuerpos[0]).not.toHaveProperty('seleccion_vehiculo')
  expect(l.cuerpos[0].contexto).toHaveProperty('vehiculo_id', 'V14')
  expect(l.cuerpos[0].contexto).not.toHaveProperty('vehiculo_origen')
})

test('AC-003/004: selección manual y tercero omiten póliza', async ({ page }) => {
  const l = await preparar(page)
  await analizar(page); await contexto(page, true)
  await page.getByRole('combobox', { name: 'Vehículo', exact: true }).selectOption('V05')
  await page.getByRole('button', { name: 'Generar informe', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Descargar Markdown' })).toBeVisible()
  expect(l.cuerpos[0]).toHaveProperty('seleccion_vehiculo', { tipo: 'seleccion_usuario', vehiculo_id: 'V05' })
  expect(l.cuerpos[0].contexto).not.toHaveProperty('poliza_id')
})

test('AC-007: RAG parcial conserva aviso y motivo por tema', async ({ page }) => {
  await preparar(page); await analizar(page); await contexto(page)
  await page.getByRole('button', { name: 'Generar informe', exact: true }).click()
  await expect(page.getByText('Informe preliminar', { exact: true })).toBeVisible()
  await expect(page.getByText('Sin fuentes para este tema.')).toBeVisible()
})

test('AC-010/011: caso perdido detiene polling sin reenvío automático', async ({ page }) => {
  const l = await preparar(page, { perdido: true })
  await seleccionar(page)
  await page.getByRole('button', { name: 'Analizar imagen', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('ya no está disponible')
  await page.waitForTimeout(1200)
  expect(l.analisis).toBe(1); expect(l.lecturas).toBe(1)
  await expect(page.getByRole('button', { name: 'Descargar Markdown' })).toHaveCount(0)
})

test('AC-009/011: fallo de cifras nunca publica ni permite descargar', async ({ page }) => {
  await preparar(page, { fallo: true }); await analizar(page); await contexto(page)
  await page.getByRole('button', { name: 'Generar informe', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('cifras inconsistentes')
  await expect(page.getByRole('button', { name: 'Descargar Markdown' })).toHaveCount(0)
})

test('AC-015: original ausente no inicia análisis', async ({ page }) => {
  const l = await preparar(page, { originalAusente: true })
  await page.getByRole('button', { name: 'Seleccionar imagen 000082.jpg', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('imagen original')
  await expect(page.getByRole('button', { name: 'Analizar imagen', exact: true })).toBeDisabled()
  expect(l.analisis).toBe(0)
})

test('AC-001: límites exactos de bytes y píxeles, sin reescalado ni inferencia', async ({ page }) => {
  const l = await preparar(page)
  const input = page.getByLabel('Subir imagen JPEG o PNG')
  const exacta = Buffer.alloc(10 * 1024 * 1024); PNG.copy(exacta)
  await input.setInputFiles({ name: 'limite-bytes.png', mimeType: 'image/png', buffer: exacta })
  await expect(page.getByRole('img', { name: 'Vista previa de limite-bytes.png' })).toBeVisible()
  for (const width of [5000, 5001]) {
    const bytes = await page.evaluate(async width => {
      const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = 4000
      const blob = await new Promise<Blob>(resolve => canvas.toBlob(b => resolve(b!), 'image/png'))
      const bytes = Array.from(new Uint8Array(await blob.arrayBuffer())); canvas.width = 0; return bytes
    }, width)
    await input.setInputFiles({ name: `pixeles-${width}.png`, mimeType: 'image/png', buffer: Buffer.from(bytes) })
    if (width === 5000) await expect(page.getByRole('img', { name: 'Vista previa de pixeles-5000.png' })).toBeVisible()
    else await expect(page.getByRole('alert')).toContainText('20 millones de píxeles')
  }
  expect(l.analisis).toBe(0)
})

test('AC-010/011: error de transporte no reenvía POST y el reintento explícito conserva la clave', async ({ page }) => {
  const l = await preparar(page)
  const claves: string[] = []
  await page.route('**/api/peritajes', async route => {
    claves.push(route.request().headers()['idempotency-key'])
    if (claves.length === 1) await route.abort('failed')
    else await route.fulfill({ status: 202, json: estado('analizando') })
  })
  await seleccionar(page)
  await page.getByRole('button', { name: 'Analizar imagen', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('No se pudo conectar')
  await page.waitForTimeout(600)
  expect(claves).toHaveLength(1)
  await page.getByRole('button', { name: 'Analizar imagen', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Vehículo y siniestro', exact: true })).toBeVisible()
  expect(claves).toHaveLength(2); expect(claves[0]).toBe(claves[1]); expect(l.informes).toBe(0)
})

test('AC-010/011: polling fallido se reanuda solo al pedirlo, sin reiniciar el análisis', async ({ page }) => {
  const l = await preparar(page)
  let consultas = 0
  await page.route('**/api/peritajes/caso-82', route => {
    consultas++
    return consultas === 1 ? route.fulfill({ status: 503, json: { error: { codigo: 'SERVICIO_ERROR', mensaje: 'Consulta interrumpida.' } } }) : route.fulfill({ json: estado() })
  })
  await seleccionar(page)
  await page.getByRole('button', { name: 'Analizar imagen', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Consulta interrumpida')
  await page.waitForTimeout(1000); expect(consultas).toBe(1)
  await page.getByRole('button', { name: 'Volver a consultar progreso' }).click()
  await expect(page.getByRole('heading', { name: 'Vehículo y siniestro', exact: true })).toBeVisible()
  expect(consultas).toBe(2); expect(l.analisis).toBe(1)
})

test('AC-011: respuesta de otro caso se rechaza sin mostrar sus datos', async ({ page }) => {
  await preparar(page)
  await page.route('**/api/peritajes/caso-82', route => route.fulfill({ json: { ...estado('completada'), ejecucion_id: 'otro-caso' } }))
  await seleccionar(page)
  await page.getByRole('button', { name: 'Analizar imagen', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('incompatible')
  await expect(page.getByRole('button', { name: 'Descargar Markdown' })).toHaveCount(0)
})

test('AC-004: catálogo ausente bloquea el presupuesto sin inventar opciones', async ({ page }) => {
  const l = await preparar(page, { catalogoAusente: true })
  await expect(page.getByRole('alert')).toContainText('no está disponible')
  await expect(page.getByRole('button', { name: 'Analizar imagen', exact: true })).toBeDisabled()
  expect(l.informes).toBe(0); expect(l.analisis).toBe(0)
})

test('Preservación y AC-015: el explorador mantiene su ruta y el móvil no desborda', async ({ page }) => {
  await preparar(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole('button', { name: 'Seleccionar imagen 000082.jpg', exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await page.getByRole('link', { name: 'Explorar dataset' }).click()
  await expect(page).toHaveURL(/\/explorer$/)
  await expect(page.getByRole('button', { name: 'Analizar imagen', exact: true })).toHaveCount(0)
})

// Complemento UI v2: https://github.com/lvckss/piia2-26/issues/34#issuecomment-7138654855
test('AC-017: modo documentos limita el selector al lote y no ofrece subidas nuevas', async ({ page }) => {
  const l = await preparar(page)
  await page.route('**/api/catalogos', route => route.fulfill({ json: { ...catalogos, fuente_detecciones: 'documentos', imagenes_exportadas: [{ id: 82, id_externo: 82, file_name: '000082.jpg', ruta_imagen: 'test/82.png', ruta_thumbnail: 'test/82.png', width: 1, height: 1, split: 'test', labels: ['dent'] }] } }))
  await page.reload()
  await expect(page.getByText('Las detecciones de estas imágenes ya están calculadas. SAM3 no se ejecuta en este equipo.', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Seleccionar imagen 000082.jpg', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Seleccionar imagen 000381.jpg', exact: true })).toHaveCount(0)
  await expect(page.getByLabel('Subir imagen JPEG o PNG')).toHaveCount(0)
  await seleccionar(page)
  expect(l.analisis).toBe(0)
  await page.getByLabel('Buscar por nombre en las imágenes cargadas').fill('000009')
  await expect(page.getByRole('button', { name: /Seleccionar imagen / })).toHaveCount(0)
})

test('AC-015/017: inicio fijo en escritorio, scroll del listado y aviso pequeño al pie', async ({ page }) => {
  const l = await preparar(page)
  await page.route('**/api/catalogos', route => route.fulfill({ json: {
    ...catalogos, fuente_detecciones: 'documentos', imagenes_exportadas: Array.from({ length: 60 }, (_, index) => ({
      id: 82 + index, id_externo: 82 + index, file_name: `${String(82 + index).padStart(6, '0')}.jpg`,
      ruta_imagen: `test/${82 + index}.png`, ruta_thumbnail: `test/${82 + index}.png`, width: 1, height: 1, split: 'test', labels: ['dent'],
    })),
  } }))
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.reload()
  await seleccionar(page)
  const main = page.getByRole('main')
  await expect.poll(() => main.evaluate(element => element.scrollHeight - element.clientHeight)).toBeLessThanOrEqual(1)
  const note = page.locator('footer').getByText('Las detecciones de estas imágenes ya están calculadas. SAM3 no se ejecuta en este equipo.', { exact: true })
  await expect(note).toBeVisible()
  expect(await note.evaluate(element => parseFloat(getComputedStyle(element).fontSize))).toBeLessThanOrEqual(12)
  expect((await note.boundingBox())!.y + (await note.boundingBox())!.height).toBeLessThanOrEqual(800)
  const first = page.getByRole('button', { name: 'Seleccionar imagen 000082.jpg', exact: true })
  const position = await first.boundingBox()
  await page.mouse.move(position!.x + 20, position!.y + 20)
  await page.mouse.wheel(0, 600)
  await expect.poll(() => first.evaluate(element => {
    let parent = element.parentElement
    while (parent && parent.tagName !== 'MAIN') {
      if (parent.scrollTop > 0) return true
      parent = parent.parentElement
    }
    return false
  })).toBe(true)
  expect(await main.evaluate(element => element.scrollTop)).toBe(0)
  expect(l.analisis).toBe(0)
})

test('AC-003/004: presupuesto plegado con valores de demo, disclaimer y vehículo confirmado visible', async ({ page }) => {
  const l = await preparar(page)
  await analizar(page)
  const budget = page.getByRole('button', { name: /Datos para el presupuesto/ })
  await expect(budget).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByLabel('Antigüedad (años)')).toBeHidden()
  await expect(page.getByText('En un sistema integrado con la aseguradora, estos datos se cargarían desde la información del cliente y su póliza, sin introducirlos manualmente. Esta demo utiliza valores de ejemplo que puedes modificar.', { exact: true })).toBeVisible()
  await expect(page.getByRole('combobox', { name: 'Vehículo', exact: true })).toHaveValue('')
  await page.getByRole('button', { name: 'Confirmar vehículo propuesto' }).click()
  await expect(page.getByRole('combobox', { name: 'Vehículo', exact: true })).toHaveValue('V02')
  await page.getByRole('button', { name: 'Generar informe', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Descargar Markdown' })).toBeVisible()
  expect(l.cuerpos[0]).toEqual({ contexto: { vehiculo_id: 'V02', region: 'Madrid', tipo_taller: 'multimarca', acabado: 'solido', tipo_pieza: 'oem', rol: 'propio', edad_anios: 3, km: 42000, poliza_id: 'P-TERC-BASICO' }, seleccion_vehiculo: { tipo: 'referencia_confirmada', vehiculo_id: 'V02' } })
  expect(l.analisis).toBe(1)
})

test('AC-003/004: editar y plegar conserva datos; volver a confirmar sincroniza vehículo y origen', async ({ page }) => {
  const l = await preparar(page)
  await analizar(page)
  const vehicle = page.getByRole('combobox', { name: 'Vehículo', exact: true })
  await vehicle.selectOption('V05')
  const budget = page.getByRole('button', { name: /Datos para el presupuesto/ })
  await budget.click()
  await expect(page.getByLabel('Antigüedad (años)')).toHaveValue('3')
  await expect(page.getByLabel('Póliza')).toHaveValue('P-TERC-BASICO')
  await page.getByLabel('Kilómetros', { exact: true }).fill('56000')
  await budget.click(); await budget.click()
  await expect(page.getByLabel('Kilómetros', { exact: true })).toHaveValue('56000')
  await page.getByRole('button', { name: 'Confirmar vehículo propuesto' }).click()
  await expect(vehicle).toHaveValue('V02')
  await page.getByRole('button', { name: 'Generar informe', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Descargar Markdown' })).toBeVisible()
  expect(l.cuerpos[0]).toHaveProperty('seleccion_vehiculo', { tipo: 'referencia_confirmada', vehiculo_id: 'V02' })
  expect(l.cuerpos[0].contexto).toHaveProperty('km', 56000)
  expect(l.analisis).toBe(1)
})

test('AC-004: un valor de demo ausente del catálogo se deja pendiente, sin sustituirlo', async ({ page }) => {
  const l = await preparar(page)
  await page.route('**/api/catalogos', route => route.fulfill({ json: { ...catalogos, acabados: [option('metalizado', 'Metalizado')] } }))
  await page.reload(); await analizar(page)
  await page.getByRole('button', { name: 'Confirmar vehículo propuesto' }).click()
  await expect(page.getByRole('button', { name: 'Generar informe', exact: true })).toBeDisabled()
  await page.getByRole('button', { name: /Datos para el presupuesto/ }).click()
  await expect(page.getByLabel('Acabado de pintura')).toHaveValue('')
  await page.getByLabel('Acabado de pintura').selectOption('metalizado')
  await page.getByRole('button', { name: 'Generar informe', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Descargar Markdown' })).toBeVisible()
  expect(l.cuerpos[0].contexto).toHaveProperty('acabado', 'metalizado')
})
