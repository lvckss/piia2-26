import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { AlertCircle, ArrowRight, Check, Download, FileText, ImagePlus, LoaderCircle, RotateCcw, Trash2, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { toDatasetUrl } from '@/lib/dataset-url'
import type { ImageWithLabels } from '@server/models/Image'
import { ContextoForm } from './ContextoForm'
import { DatasetSelector } from './DatasetSelector'
import { descargarMarkdown, ErrorPeritaje, peritajeApi, validarImagen, type Ejecucion, type PeticionInforme } from './api'
import { DamageViewer } from './DamageViewer'
import './peritaje.css'

const pasos = ['Imagen', 'Análisis', 'Siniestro', 'Informe']
const etapas: Record<Ejecucion['etapa'], string> = { entrada: 'Preparando la imagen', piia1: 'Detectando daños', agente1: 'Analizando daños y categoría del vehículo', agente2: 'Calculando presupuesto y consultando fuentes', agente3: 'Redactando el informe', verificacion: 'Comprobando las cifras del informe' }
type Imagen = { file: File; url: string; datasetId?: number }
const message = (e: unknown) => e instanceof Error ? e.message : 'No se pudo completar la operación.'

export function PeritajePage() {
  const catalogue = useQuery({ queryKey: ['peritaje-catalogos'], queryFn: ({ signal }) => peritajeApi.catalogos(signal), retry: false })
  const documents = catalogue.data?.fuente_detecciones === 'documentos'
  const [imagen, setImagen] = useState<Imagen | null>(null)
  const [execution, setExecution] = useState<Ejecucion | null>(null)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const [paused, setPaused] = useState(false)
  const [liberando, setLiberando] = useState(false)
  const [avisoCasos, setAvisoCasos] = useState('')
  const polling = useRef<AbortController | null>(null)
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
    if (!execution || !active || paused || liberando) return
    const controller = new AbortController()
    polling.current = controller
    const timer = window.setTimeout(() => {
      peritajeApi.consultar(execution.ejecucion_id, controller.signal).then(next => { if (!controller.signal.aborted) setExecution(next) }).catch(e => {
        if (controller.signal.aborted) return
        if (e instanceof ErrorPeritaje && e.status === 404) {
          setExecution({ ...execution, estado: 'error', resultado: null, error: { codigo: 'EJECUCION_NO_DISPONIBLE', etapa: 'entrada', mensaje: e.message, reintentable: false } })
        } else {
          setError(message(e)); setPaused(true)
        }
      })
    }, 500)
    return () => { clearTimeout(timer); controller.abort() }
  }, [execution, active, paused, liberando])

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

  async function liberarCasos() {
    if (lock.current || pending || liberando) return
    lock.current = true; polling.current?.abort(); setLiberando(true); setAvisoCasos('')
    try {
      const result = await peritajeApi.liberarCasos()
      setError('')
      if (execution && result.descartados.includes(execution.ejecucion_id)) {
        selection.current++; imageRequest.current?.abort(); setExecution(null); setImagen(null); setPaused(false); keys.current.clear()
      }
      const released = result.descartados.length
      setAvisoCasos(`${released === 1 ? 'Se ha liberado 1 caso.' : `Se han liberado ${released} casos.`}${result.en_curso ? ` ${result.en_curso === 1 ? 'Queda 1 análisis' : `Quedan ${result.en_curso} análisis`} en curso; podrás descartarlo al terminar.` : ''}`)
    } catch (e) { setAvisoCasos(message(e)) }
    finally { lock.current = false; setLiberando(false) }
  }

  return <main className={`peritaje h-full overflow-auto bg-muted/20 ${!completed ? 'peritaje-panel' : ''}`}>
    <div className="peritaje-content mx-auto flex max-w-[1500px] flex-col gap-5 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h1 className="flex items-center gap-2 text-xl font-semibold"><FileText className="size-5" /> Peritaje</h1><p className="mt-1 text-sm text-muted-foreground">Selecciona una imagen, revisa el análisis y genera el informe del siniestro.</p></div>
        {execution && <Button variant="outline" onClick={nuevo} disabled={active || pending}><RotateCcw className="size-4" /> Nuevo peritaje</Button>}
        {imagen && !execution && <span className="flex items-center gap-2 rounded-md border bg-card px-3 py-2 text-xs"><Check className="size-3.5" /> {imagen.file.name}</span>}
      </div>
      <ol aria-label="Pasos del peritaje" className="grid grid-cols-4 rounded-lg border bg-card p-3">
        {pasos.map((paso, index) => <li key={paso} aria-current={index === stage ? 'step' : undefined} className={`flex items-center justify-center gap-2 text-xs sm:text-sm ${index > stage ? 'text-muted-foreground' : 'font-medium'}`}><span className={`flex size-6 shrink-0 items-center justify-center rounded-full border text-xs ${index === stage ? 'border-primary bg-primary text-primary-foreground' : index < stage ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : ''}`}>{index < stage ? <Check className="size-3" /> : index + 1}</span>{paso}</li>)}
      </ol>
      {shownError && <div role="alert" className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm"><AlertCircle className="mt-0.5 size-4 shrink-0 text-destructive" /><div><p>{shownError}</p>{execution?.estado === 'error' && <p className="mt-1 text-xs text-muted-foreground">El caso se ha detenido. No se ha publicado ningún informe final.</p>}{paused && <Button variant="outline" className="mt-3" onClick={consultar} disabled={pending}>Volver a consultar progreso</Button>}</div></div>}
      {!execution && catalogue.isPending && <p className="text-sm text-muted-foreground">Cargando imágenes y catálogos…</p>}
      {!execution && catalogue.isError && <div role="alert" className="rounded-lg border p-4 text-sm"><p>{catalogue.error.message}</p><Button variant="outline" className="mt-2" onClick={() => catalogue.refetch()}>Volver a cargar catálogos</Button></div>}
      {completed && execution.resultado ? <Informe execution={execution} /> : <div className="peritaje-layout grid items-start gap-5 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
        <div className="peritaje-columna flex flex-col gap-4">
          {!execution && catalogue.data && <DatasetSelector disabled={pending} selectedId={imagen?.datasetId} onSelect={chooseDataset} exportedImages={documents ? catalogue.data.imagenes_exportadas : undefined} />}
          {!execution && catalogue.data && !documents && <section className="rounded-lg border bg-card p-4"><h2 className="flex items-center gap-2 font-semibold"><Upload className="size-4" /> O subir una imagen</h2><label className="mt-3 block cursor-pointer rounded-md border border-dashed p-4 text-sm"><span className="mb-2 flex items-center gap-2 text-muted-foreground"><ImagePlus className="size-4" /> JPEG o PNG · hasta 10 MiB y 20 millones de píxeles</span><input aria-label="Subir imagen JPEG o PNG" className="block w-full text-xs file:mr-3 file:rounded-md file:border file:bg-background file:px-3 file:py-1.5 file:font-medium" type="file" accept="image/jpeg,image/png" disabled={Boolean(execution)} onChange={e => { const file = e.target.files?.[0]; if (file) void chooseFile(file); e.target.value = '' }} /></label></section>}
          {imagen && execution && <DamageViewer key={execution.ejecucion_id} imagen={imagen} execution={execution} documents={documents} />}
        </div>
        <div className="peritaje-columna flex flex-col gap-4">
          {!execution && <section className="rounded-lg border bg-card p-5"><h2 className="font-semibold">Analizar la imagen</h2><p className="mt-2 text-sm leading-relaxed text-muted-foreground">{documents ? 'Se lee el documento de detecciones y la visión analiza sus daños y propone la categoría del vehículo.' : 'El detector localiza los daños y la visión propone su descripción y la categoría del vehículo.'} Después podrás completar el siniestro antes de calcular el presupuesto.</p><Button className="mt-5" onClick={analizar} disabled={!imagen || pending || !catalogue.data}>{pending ? <LoaderCircle className="size-4 animate-spin" /> : <ArrowRight className="size-4" />} Analizar imagen</Button><p className="mt-3 text-xs text-muted-foreground">Esta acción consulta los modelos configurados. Navegar y seleccionar imágenes no los ejecuta.</p></section>}
          {imagen && !execution && <DamageViewer imagen={imagen} documents={documents} />}
          {active && <section aria-live="polite" className="rounded-lg border bg-card p-5"><h2 className="flex items-center gap-2 font-semibold">{!paused && <LoaderCircle className="size-4 animate-spin" />}{paused ? 'Consulta del progreso interrumpida' : etapas[execution.etapa]}</h2><p className="mt-2 text-sm text-muted-foreground">{paused ? 'Puedes consultar el estado sin volver a enviar el trabajo.' : 'La operación sigue en curso. No necesitas volver a enviarla.'}</p></section>}
          {execution?.estado === 'esperando_datos' && execution.analisis && <ContextoForm analisis={execution.analisis} disabled={pending} onSubmit={generar} />}
          {!imagen && !execution && <div className="rounded-lg border border-dashed p-8 text-center text-muted-foreground"><ImagePlus className="mx-auto size-8 opacity-50" /><p className="mt-3 text-sm">La vista previa aparecerá al seleccionar una imagen.</p></div>}
        </div>
      </div>}
      <footer className="peritaje-pie flex flex-col justify-between gap-3 text-xs text-muted-foreground sm:flex-row sm:items-end">
        <div className="space-y-1">
          {documents && <p>Las detecciones de estas imágenes ya están calculadas. SAM3 no se ejecuta en este equipo.</p>}
          <p>Datos sintéticos de prototipo. Las cifras son orientativas y requieren revisión; no sustituyen una valoración pericial.</p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2 self-end">
          {avisoCasos && <p role="status" className="max-w-80 text-right">{avisoCasos}</p>}
          <Button type="button" variant="outline" disabled={pending || liberando} onClick={liberarCasos}>{liberando ? <LoaderCircle className="size-3.5 animate-spin" /> : <Trash2 className="size-3.5" />} Liberar casos</Button>
        </div>
      </footer>
    </div>
  </main>
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
