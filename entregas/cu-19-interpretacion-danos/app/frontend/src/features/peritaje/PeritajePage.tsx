import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { AlertCircle, ArrowRight, Check, Download, FileText, ImagePlus, LoaderCircle, RotateCcw, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { toDatasetUrl } from '@/lib/dataset-url'
import type { ImageWithLabels } from '@server/models/Image'
import { ContextoForm } from './ContextoForm'
import { DatasetSelector } from './DatasetSelector'
import { descargarMarkdown, ErrorPeritaje, peritajeApi, validarImagen, type Analisis, type Ejecucion, type PeticionInforme } from './api'
import './peritaje.css'

const pasos = ['Imagen', 'Análisis', 'Siniestro', 'Informe']
const etapas: Record<Ejecucion['etapa'], string> = { entrada: 'Preparando la imagen', piia1: 'Detectando daños', agente1: 'Analizando daños y categoría del vehículo', agente2: 'Calculando presupuesto y consultando fuentes', agente3: 'Redactando el informe', verificacion: 'Comprobando las cifras del informe' }
const danos: Record<string, string> = { dent: 'Abolladura', scratch: 'Arañazo', crack: 'Grieta', glass_shatter: 'Cristal roto', lamp_broken: 'Faro roto', tire_flat: 'Neumático pinchado' }
type Imagen = { file: File; url: string; datasetId?: number }
const message = (e: unknown) => e instanceof Error ? e.message : 'No se pudo completar la operación.'

export function PeritajePage() {
  const [imagen, setImagen] = useState<Imagen | null>(null)
  const [execution, setExecution] = useState<Ejecucion | null>(null)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const [paused, setPaused] = useState(false)
  const lock = useRef(false)
  const selection = useRef(0)
  const imageRequest = useRef<AbortController | null>(null)
  const keys = useRef(new Map<string, string>())
  const active = execution?.estado === 'analizando' || execution?.estado === 'generando_informe'
  const completed = execution?.estado === 'completada'
  const stage = completed || execution?.estado === 'generando_informe' ? 3 : execution?.estado === 'esperando_datos' ? 2 : execution ? 1 : 0
  const shownError = error || (execution?.estado === 'error' ? execution.error?.mensaje ?? 'La ejecución ha fallado.' : '')

  useEffect(() => () => { if (imagen) URL.revokeObjectURL(imagen.url) }, [imagen])
  useEffect(() => () => { imageRequest.current?.abort(); selection.current++ }, [])
  useEffect(() => {
    if (!execution || !active || paused) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      peritajeApi.consultar(execution.ejecucion_id, controller.signal).then(setExecution).catch(e => {
        if (controller.signal.aborted) return
        if (e instanceof ErrorPeritaje && e.status === 404) {
          setExecution({ ...execution, estado: 'error', resultado: null, error: { codigo: 'EJECUCION_NO_DISPONIBLE', etapa: 'entrada', mensaje: e.message, reintentable: false } })
        } else {
          setError(message(e)); setPaused(true)
        }
      })
    }, 500)
    return () => { clearTimeout(timer); controller.abort() }
  }, [execution, active, paused])

  function keyFor(content: string) {
    const existing = keys.current.get(content)
    if (existing) return existing
    const key = crypto.randomUUID(); keys.current.set(content, key); return key
  }
  async function chooseFile(file: File) {
    if (execution || lock.current) return
    const token = ++selection.current
    imageRequest.current?.abort(); setImagen(null); setError(''); setPending(true)
    try {
      await validarImagen(file)
      if (selection.current !== token) return
      keys.current.clear(); setImagen({ file, url: URL.createObjectURL(file) })
    } catch (e) { if (selection.current === token) setError(message(e)) }
    finally { if (selection.current === token) setPending(false) }
  }
  async function chooseDataset(image: ImageWithLabels) {
    if (execution || lock.current) return
    const token = ++selection.current
    imageRequest.current?.abort()
    const controller = new AbortController(); imageRequest.current = controller
    setImagen(null); setError(''); setPending(true)
    try {
      const response = await fetch(toDatasetUrl(image.ruta_imagen), { signal: controller.signal })
      if (!response.ok) throw new Error('No se pudo cargar la imagen original del dataset.')
      const blob = await response.blob()
      const file = new File([blob], image.file_name, { type: blob.type })
      await validarImagen(file)
      if (selection.current !== token) return
      keys.current.clear(); setImagen({ file, url: URL.createObjectURL(file), datasetId: image.id })
    } catch (e) { if (!controller.signal.aborted && selection.current === token) setError(message(e)) }
    finally { if (selection.current === token) setPending(false) }
  }
  async function analizar() {
    if (!imagen || execution || lock.current || pending) return
    lock.current = true; setPending(true); setError('')
    try { setExecution(await peritajeApi.analizar(imagen.file, keyFor('analisis'))); setPaused(false) }
    catch (e) { setError(message(e)) }
    finally { lock.current = false; setPending(false) }
  }
  async function generar(body: PeticionInforme) {
    if (!execution || execution.estado !== 'esperando_datos' || lock.current) return
    lock.current = true; setPending(true); setError('')
    try { setExecution(await peritajeApi.informe(execution.ejecucion_id, body, keyFor(`informe:${JSON.stringify(body)}`))); setPaused(false) }
    catch (e) { setError(message(e)) }
    finally { lock.current = false; setPending(false) }
  }
  async function consultar() {
    if (!execution || lock.current) return
    lock.current = true; setPending(true)
    try { setExecution(await peritajeApi.consultar(execution.ejecucion_id)); setPaused(false); setError('') }
    catch (e) { setError(message(e)) }
    finally { lock.current = false; setPending(false) }
  }
  async function nuevo() {
    if (active || lock.current) return
    lock.current = true; setPending(true); setError('')
    try {
      if (execution) await peritajeApi.descartar(execution.ejecucion_id)
      selection.current++; imageRequest.current?.abort(); setExecution(null); setImagen(null); setPaused(false); keys.current.clear()
    } catch (e) { setError(message(e)) }
    finally { lock.current = false; setPending(false) }
  }

  return <main className="peritaje h-full overflow-auto bg-muted/20">
    <div className="mx-auto max-w-[1500px] space-y-5 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h1 className="flex items-center gap-2 text-xl font-semibold"><FileText className="size-5" /> Peritaje</h1><p className="mt-1 text-sm text-muted-foreground">Selecciona una imagen, revisa el análisis y genera el informe del siniestro.</p></div>
        {execution && <Button variant="outline" onClick={nuevo} disabled={active || pending}><RotateCcw className="size-4" /> Nuevo peritaje</Button>}
        {imagen && !execution && <span className="flex items-center gap-2 rounded-md border bg-card px-3 py-2 text-xs"><Check className="size-3.5" /> {imagen.file.name}</span>}
      </div>
      <ol aria-label="Pasos del peritaje" className="grid grid-cols-4 rounded-lg border bg-card p-3">
        {pasos.map((paso, index) => <li key={paso} aria-current={index === stage ? 'step' : undefined} className={`flex items-center justify-center gap-2 text-xs sm:text-sm ${index > stage ? 'text-muted-foreground' : 'font-medium'}`}><span className={`flex size-6 shrink-0 items-center justify-center rounded-full border text-xs ${index === stage ? 'border-primary bg-primary text-primary-foreground' : index < stage ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : ''}`}>{index < stage ? <Check className="size-3" /> : index + 1}</span>{paso}</li>)}
      </ol>
      {shownError && <div role="alert" className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm"><AlertCircle className="mt-0.5 size-4 shrink-0 text-destructive" /><div><p>{shownError}</p>{execution?.estado === 'error' && <p className="mt-1 text-xs text-muted-foreground">El caso se ha detenido. No se ha publicado ningún informe final.</p>}{paused && <Button variant="outline" className="mt-3" onClick={consultar} disabled={pending}>Volver a consultar progreso</Button>}</div></div>}
      {completed && execution.resultado ? <Informe execution={execution} /> : <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          {!execution && <DatasetSelector disabled={pending} selectedId={imagen?.datasetId} onSelect={chooseDataset} />}
          {!execution && <section className="rounded-lg border bg-card p-4"><h2 className="flex items-center gap-2 font-semibold"><Upload className="size-4" /> O subir una imagen</h2><label className="mt-3 block cursor-pointer rounded-md border border-dashed p-4 text-sm"><span className="mb-2 flex items-center gap-2 text-muted-foreground"><ImagePlus className="size-4" /> JPEG o PNG · hasta 10 MiB y 20 millones de píxeles</span><input aria-label="Subir imagen JPEG o PNG" className="block w-full text-xs file:mr-3 file:rounded-md file:border file:bg-background file:px-3 file:py-1.5 file:font-medium" type="file" accept="image/jpeg,image/png" disabled={Boolean(execution)} onChange={e => { const file = e.target.files?.[0]; if (file) void chooseFile(file); e.target.value = '' }} /></label></section>}
          {imagen && execution && <VistaPrevia imagen={imagen} analizada />}
        </div>
        <div className="space-y-4">
          {!execution && <section className="rounded-lg border bg-card p-5"><h2 className="font-semibold">Analizar la imagen</h2><p className="mt-2 text-sm leading-relaxed text-muted-foreground">El detector localiza los daños y la visión propone su descripción y la categoría del vehículo. Después podrás completar el siniestro antes de calcular el presupuesto.</p><Button className="mt-5" onClick={analizar} disabled={!imagen || pending}>{pending ? <LoaderCircle className="size-4 animate-spin" /> : <ArrowRight className="size-4" />} Analizar imagen</Button><p className="mt-3 text-xs text-muted-foreground">Esta acción consulta los modelos configurados. Navegar y seleccionar imágenes no los ejecuta.</p></section>}
          {imagen && !execution && <VistaPrevia imagen={imagen} />}
          {active && <section aria-live="polite" className="rounded-lg border bg-card p-5"><h2 className="flex items-center gap-2 font-semibold">{!paused && <LoaderCircle className="size-4 animate-spin" />}{paused ? 'Consulta del progreso interrumpida' : etapas[execution.etapa]}</h2><p className="mt-2 text-sm text-muted-foreground">{paused ? 'Puedes consultar el estado sin volver a enviar el trabajo.' : 'La operación sigue en curso. No necesitas volver a enviarla.'}</p></section>}
          {execution?.estado === 'esperando_datos' && execution.analisis && <ContextoForm analisis={execution.analisis} disabled={pending} onSubmit={generar} />}
          {!imagen && !execution && <div className="rounded-lg border border-dashed p-8 text-center text-muted-foreground"><ImagePlus className="mx-auto size-8 opacity-50" /><p className="mt-3 text-sm">La vista previa aparecerá al seleccionar una imagen.</p></div>}
        </div>
      </div>}
      {execution?.analisis && !completed && <Hallazgos analisis={execution.analisis} />}
      <p className="text-xs text-muted-foreground">Datos sintéticos de prototipo. Las cifras son orientativas y requieren revisión; no sustituyen una valoración pericial.</p>
    </div>
  </main>
}

function VistaPrevia({ imagen, analizada = false }: { imagen: Imagen; analizada?: boolean }) {
  return <section className="overflow-hidden rounded-lg border bg-card"><div className="flex items-center justify-between gap-2 border-b p-3"><p className="truncate text-sm font-medium">{imagen.file.name}</p><span className="shrink-0 text-xs text-muted-foreground">{(imagen.file.size / 1024).toFixed(1)} KiB</span></div><img src={imagen.url} alt={`Vista previa de ${imagen.file.name}`} className="max-h-[25rem] w-full bg-muted/40 object-contain" /><p className="p-3 text-xs text-muted-foreground">{analizada ? 'Imagen utilizada para este análisis.' : 'Imagen original seleccionada. El análisis se ejecuta al pulsar el botón.'}</p></section>
}

function Hallazgos({ analisis }: { analisis: Analisis }) {
  return <section className="overflow-hidden rounded-lg border bg-card"><div className="border-b p-4"><h2 className="font-semibold">Daños analizados <span className="ml-1 text-xs font-normal text-muted-foreground">{analisis.findings.length} hallazgos</span></h2><p className="mt-1 text-xs text-muted-foreground">Resultados de solo lectura. Los pendientes y los no confirmados conservan su estado.</p></div>
    {analisis.findings.length === 0 ? <p className="p-5 text-sm text-muted-foreground">No se han encontrado daños para analizar.</p> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-muted/40 text-xs text-muted-foreground"><tr>{['Hallazgo', 'Daño', 'Estado', 'Confianza', 'Descripción'].map(h => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}</tr></thead><tbody className="divide-y">{analisis.findings.map(f => <tr key={f.finding_id}><td className="whitespace-nowrap px-4 py-3 text-xs">{f.finding_id}</td><td className="whitespace-nowrap px-4 py-3">{danos[f.category.replaceAll(' ', '_')] ?? f.category}</td><td className="px-4 py-3"><span className={`whitespace-nowrap rounded border px-2 py-0.5 text-xs ${f.vision_verdict === 'rechazado' ? 'border-border bg-muted text-muted-foreground' : f.confidence_tier === 'confirmed' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-amber-200 bg-amber-50 text-amber-900'}`}>{f.vision_verdict === 'rechazado' ? 'No confirmado' : f.confidence_tier === 'confirmed' ? 'Confirmado' : 'Requiere revisión'}</span></td><td className="px-4 py-3 tabular-nums">{(f.score * 100).toFixed(0)} %</td><td className="min-w-64 px-4 py-3 text-muted-foreground">{f.vision_description}</td></tr>)}</tbody></table></div>}
  </section>
}

function Informe({ execution }: { execution: Ejecucion }) {
  const result = execution.resultado!
  const rag = result.agente2.diagnostico_rag
  const preliminary = ['parcial', 'sin_resultados', 'error'].includes(rag.estado)
  return <section className="rounded-lg border bg-card">
    <div className="flex flex-wrap items-center justify-between gap-3 border-b p-4"><div><h2 className="font-semibold">Informe generado</h2><p className="mt-1 text-xs text-muted-foreground">El archivo descargado conserva el contenido mostrado.</p></div><Button onClick={() => descargarMarkdown(result.markdown, execution.ejecucion_id)}><Download className="size-4" /> Descargar Markdown</Button></div>
    {preliminary && <aside className="m-4 rounded-md border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950"><p className="font-semibold">Informe preliminar</p><p className="mt-1">Faltan fuentes para respaldar algunos temas. Revisa las advertencias y las citas disponibles del informe.</p>{rag.consultas?.filter(q => q.estado !== 'recuperadas').map((q, i) => <div key={`${q.tema}-${i}`} className="mt-2"><p className="font-medium">{q.tema}</p>{q.incidencias?.length ? q.incidencias.map((inc, j) => <p key={j}>{inc.mensaje}</p>) : <p>Sin fuentes suficientes para este tema.</p>}</div>)}</aside>}
    <article className="peritaje-markdown p-5 md:p-8"><ReactMarkdown skipHtml remarkPlugins={[remarkGfm]} components={{ img: ({ alt }) => <span>{alt}</span>, a: ({ children, href }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a> }}>{result.markdown}</ReactMarkdown></article>
  </section>
}
