import { Fragment, useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { Ejecucion } from './api'

const labels: Record<string, string> = { dent: 'Abolladura', scratch: 'Arañazo', crack: 'Grieta', glass_shatter: 'Cristal roto', lamp_broken: 'Faro roto', tire_flat: 'Neumático pinchado' }
const labelFor = (category: string) => labels[category.replaceAll(' ', '_')] ?? category
const motionQuery = '(prefers-reduced-motion: reduce)'
function subscribeMotion(listener: () => void) {
  const media = window.matchMedia(motionQuery)
  media.addEventListener('change', listener)
  return () => media.removeEventListener('change', listener)
}

type Props = { imagen: { file: File; url: string }; execution?: Ejecucion; documents: boolean }
export function DamageViewer({ imagen, execution, documents }: Props) {
  const frame = useRef<HTMLDivElement>(null)
  const [bounds, setBounds] = useState({ width: 0, height: 0 })
  const [natural, setNatural] = useState({ width: 0, height: 0 })
  const [selected, setSelected] = useState(0)
  const [reveal, setReveal] = useState({ key: '', count: 0 })
  const reducedMotion = useSyncExternalStore(subscribeMotion, () => window.matchMedia(motionQuery).matches, () => false)
  const findings = execution?.estado === 'analizando' ? undefined : execution?.analisis?.findings
  const preview = execution?.detecciones
  const boxes = findings ? findings.flatMap(finding => {
    const bbox = finding.bbox_xywh ?? preview?.findings.find(p => p.finding_id === finding.finding_id)?.bbox_xywh
    return bbox ? [{ finding_id: finding.finding_id, category: finding.category, score: finding.score, bbox_xywh: bbox }] : []
  }) : preview?.findings ?? []
  const count = boxes.length
  const key = `${execution?.ejecucion_id ?? ''}:${boxes.map(f => f.finding_id).join('|')}`
  const animate = execution?.estado === 'analizando' && !reducedMotion
  const visible = animate ? (reveal.key === key ? reveal.count : 0) : count
  const index = Math.max(0, Math.min(selected, Math.max(0, (findings?.length ?? 0) - 1)))
  const current = findings?.[index]

  useEffect(() => {
    const element = frame.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      setBounds(previous => previous.width === width && previous.height === height ? previous : { width, height })
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!animate || !count) return
    let shown = 0
    const timer = window.setInterval(() => {
      shown++
      setReveal({ key, count: shown })
      if (shown >= count) window.clearInterval(timer)
    }, 300)
    return () => window.clearInterval(timer)
  }, [animate, count, key])

  const width = preview?.image_width ?? natural.width
  const height = preview?.image_height ?? natural.height
  const scale = width && height ? Math.min(bounds.width / width, bounds.height / height) : 0
  const offsetX = (bounds.width - width * scale) / 2
  const offsetY = (bounds.height - height * scale) / 2
  const verdict = current?.vision_verdict === 'rechazado' ? 'No confirmado' : current?.confidence_tier === 'confirmed' ? 'Confirmado' : 'Requiere revisión'

  return <>
    <section className="peritaje-vista-previa overflow-hidden rounded-lg border bg-card">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b p-3"><p className="truncate text-sm font-medium">{imagen.file.name}</p><span className="shrink-0 text-xs text-muted-foreground">{(imagen.file.size / 1024).toFixed(1)} KiB</span></div>
      <div ref={frame} className="peritaje-imagen-marco relative min-h-0 bg-muted/40">
        <img src={imagen.url} alt={`Vista previa de ${imagen.file.name}`} className="block max-h-[25rem] w-full object-contain" onLoad={event => setNatural({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })} />
        {scale > 0 && <div role="group" aria-label="Cajas de detección" className="pointer-events-none absolute inset-0 overflow-hidden">
          {boxes.slice(0, visible).map((box, position) => {
            const [x, y, w, h] = box.bbox_xywh
            const finding = findings?.find(f => f.finding_id === box.finding_id)
            const active = Boolean(current && current.finding_id === box.finding_id)
            const tone = !finding ? 'candidata' : finding.vision_verdict === 'rechazado' ? 'rechazada' : finding.confidence_tier === 'confirmed' ? 'confirmada' : 'pendiente'
            const text = `${position + 1} · ${labelFor(box.category)}`
            const tagWidth = Math.min(text.length * 6.5 + 14, width * scale)
            return <Fragment key={box.finding_id}>
              <button type="button" data-finding-id={box.finding_id} data-tone={tone} aria-pressed={active} aria-label={`Seleccionar daño ${position + 1}: ${labelFor(box.category)}`} disabled={!findings} onClick={() => setSelected(findings?.findIndex(f => f.finding_id === box.finding_id) ?? 0)} className={`peritaje-caja pointer-events-auto absolute ${active ? 'peritaje-caja-activa' : ''}`} style={{ left: offsetX + x * scale, top: offsetY + y * scale, width: w * scale, height: h * scale }} />
              <span aria-hidden="true" data-tone={tone} className={`peritaje-etiqueta absolute truncate rounded px-1.5 py-0.5 text-[11px] font-medium ${active ? 'z-20' : 'z-10'}`} style={{ left: Math.max(offsetX, Math.min(offsetX + x * scale, offsetX + width * scale - tagWidth)), top: Math.max(offsetY, offsetY + y * scale - 21), maxWidth: tagWidth }}>{text}</span>
            </Fragment>
          })}
        </div>}
      </div>
      <p className="shrink-0 p-3 text-xs text-muted-foreground">{execution ? documents ? 'Cajas provisionales del documento. La visión comprueba estas detecciones antes de presupuestar.' : 'La visión comprueba estas detecciones antes de presupuestar.' : 'Imagen original seleccionada. El análisis se ejecuta al pulsar el botón.'}</p>
    </section>

    {execution && !findings && <div className="shrink-0 rounded-lg border bg-card p-4 text-sm" aria-live="polite"><p className="font-medium">{documents ? 'Detecciones del documento' : 'Detecciones disponibles'}</p><p className="mt-1 text-xs text-muted-foreground">{preview ? `${Math.min(visible, count)} de ${count} cajas disponibles. ${execution.estado === 'error' ? 'El análisis se ha detenido.' : 'La visión está revisando la imagen.'}` : 'Preparando las detecciones de la imagen…'}</p></div>}

    {findings && <section aria-label="Daños analizados" className="peritaje-danos shrink-0 overflow-hidden rounded-lg border bg-card">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b px-4 py-3">
        <div><h2 className="font-semibold">Daños analizados</h2><p className="mt-0.5 text-xs text-muted-foreground" aria-live="polite">{findings.length ? `Daño ${index + 1} de ${findings.length}` : '0 hallazgos'}</p></div>
        {findings.length > 0 && <div className="flex gap-1"><Button type="button" variant="outline" size="icon" aria-label="Daño anterior" disabled={index === 0} onClick={() => setSelected(index - 1)}><ChevronLeft /></Button><Button type="button" variant="outline" size="icon" aria-label="Daño siguiente" disabled={index === findings.length - 1} onClick={() => setSelected(index + 1)}><ChevronRight /></Button></div>}
      </div>
      {current ? <div className="peritaje-dano-detalle space-y-2 p-4 text-sm">
        <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-medium">{labelFor(current.category)}</h3><span className={`rounded border px-2 py-0.5 text-xs ${current.vision_verdict === 'rechazado' ? 'bg-muted text-muted-foreground' : current.confidence_tier === 'confirmed' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-amber-200 bg-amber-50 text-amber-900'}`}>{verdict}</span></div>
        <p className="break-words text-muted-foreground">{current.vision_description || 'Sin descripción disponible.'}</p>
        <p className="break-all text-xs text-muted-foreground">Puntuación del detector: {(current.score * 100).toFixed(0)} % · {current.finding_id}</p>
      </div> : <p className="p-4 text-sm text-muted-foreground">No se han encontrado daños para analizar.</p>}
    </section>}
  </>
}
