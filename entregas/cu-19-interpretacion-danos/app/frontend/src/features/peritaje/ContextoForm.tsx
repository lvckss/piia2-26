import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertCircle, CarFront, Check, ChevronDown, FileText, LoaderCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { AVISO_V14, peritajeApi, type Analisis, type Catalogos, type PeticionInforme } from './api'

type Props = { analisis: Analisis; disabled: boolean; onSubmit: (body: PeticionInforme) => void }
type Choice = PeticionInforme['seleccion_vehiculo']
type Fields = Record<'edad' | 'km' | 'region' | 'taller' | 'acabado' | 'pieza' | 'rol' | 'poliza', string>
export function ContextoForm({ analisis, disabled, onSubmit }: Props) {
  const query = useQuery({ queryKey: ['peritaje-catalogos'], queryFn: ({ signal }) => peritajeApi.catalogos(signal), retry: false })
  const [selection, setSelection] = useState<Choice>()
  const [editedFields, setEditedFields] = useState<Partial<Fields>>({})
  const available = (options: Catalogos['vehiculos'] | undefined, preferred: string) => options?.some(o => o.id === preferred) ? preferred : ''
  const fields: Fields = {
    edad: '3', km: '42000', region: available(query.data?.regiones, 'Madrid'),
    taller: available(query.data?.tipos_taller, 'multimarca'), acabado: available(query.data?.acabados, 'solido'),
    pieza: available(query.data?.tipos_pieza, 'oem'), rol: 'propio', poliza: available(query.data?.polizas, 'P-TERC-BASICO'),
    ...editedFields,
  }
  const unknown = analisis.vehiculo.categoria === 'desconocido'
  const vehicleId = selection?.vehiculo_id ?? (unknown ? 'V14' : '')
  const referenceId = analisis.vehiculo.vehiculo_id_referencia
  const proposed = query.data?.vehiculos.find(v => v.id === referenceId)
  const numbersValid = fields.edad.trim() !== '' && fields.km.trim() !== '' && Number.isFinite(Number(fields.edad)) && Number.isFinite(Number(fields.km)) && Number(fields.edad) >= 0 && Number(fields.km) >= 0
  const valid = Boolean(query.data && query.data.vehiculos.some(v => v.id === vehicleId) && numbersValid
    && available(query.data.regiones, fields.region) && available(query.data.tipos_taller, fields.taller)
    && available(query.data.acabados, fields.acabado) && available(query.data.tipos_pieza, fields.pieza)
    && (fields.rol === 'tercero_perjudicado' || available(query.data.polizas, fields.poliza)))
  const update = (key: keyof Fields, value: string) => setEditedFields(f => ({ ...f, [key]: value }))
  const policyName = query.data?.polizas.find(p => p.id === fields.poliza)?.nombre
  const summary = `${fields.edad || '—'} años · ${fields.km ? Number(fields.km).toLocaleString('es-ES') : '—'} km · ${fields.region || 'Región pendiente'} · ${fields.rol === 'tercero_perjudicado' ? 'Tercero perjudicado' : policyName || 'Póliza pendiente'}`
  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!valid || disabled) return
    const body: PeticionInforme = { contexto: {
      vehiculo_id: vehicleId, region: fields.region, tipo_taller: fields.taller, acabado: fields.acabado, tipo_pieza: fields.pieza,
      rol: fields.rol as 'propio' | 'tercero_perjudicado', edad_anios: Number(fields.edad), km: Number(fields.km),
      ...(fields.rol === 'propio' ? { poliza_id: fields.poliza } : {}),
    }, ...(selection ? { seleccion_vehiculo: selection } : {}) }
    onSubmit(body)
  }
  function select(key: keyof typeof fields, label: string, options: Catalogos['vehiculos'] | undefined) {
    return <label className="text-sm">{label}<select className="peritaje-input mt-1.5" value={fields[key]} onChange={e => update(key, e.target.value)} required disabled={disabled || !query.data}><option value="">Seleccionar…</option>{options?.map(o => <option key={o.id} value={o.id}>{o.nombre}</option>)}</select></label>
  }
  return <form onSubmit={submit} className="rounded-lg border bg-card">
    <div className="border-b p-4"><h2 className="flex items-center gap-2 font-semibold"><CarFront className="size-4" /> Vehículo y siniestro</h2><p className="mt-1 text-sm text-muted-foreground">Confirma el vehículo de cálculo y completa los datos que no aporta la imagen.</p></div>
    <div className="space-y-5 p-4">
      {query.isPending && <p className="text-sm text-muted-foreground">Cargando catálogos…</p>}
      {query.isError && <div role="alert" className="rounded-md border border-destructive/30 p-3 text-sm"><p>{query.error.message}</p><Button type="button" variant="outline" className="mt-2" onClick={() => query.refetch()}>Volver a cargar catálogos</Button></div>}
      <div className="rounded-md border bg-muted/30 p-3">
        <p className="text-xs font-medium text-muted-foreground">{unknown ? 'Categoría no reconocida' : `Categoría propuesta: ${analisis.vehiculo.categoria}`}</p>
        <p className="mt-1 font-medium">{unknown ? 'Dacia Sandero · referencia V14' : proposed?.nombre ?? referenceId}</p>
        {!unknown && <Button type="button" variant={selection?.tipo === 'referencia_confirmada' ? 'secondary' : 'outline'} className="mt-3" disabled={disabled || !proposed} onClick={() => setSelection({ tipo: 'referencia_confirmada', vehiculo_id: referenceId! })}>{selection?.tipo === 'referencia_confirmada' && <Check className="size-4" />} Confirmar vehículo propuesto</Button>}
        <p className="mt-2 text-xs text-muted-foreground">Es una referencia para calcular, no la identificación del modelo fotografiado.</p>
      </div>
      <label className="block text-sm">Vehículo<select className="peritaje-input mt-1.5" disabled={disabled || !query.data} value={selection?.vehiculo_id ?? ''} onChange={e => setSelection(e.target.value ? { tipo: 'seleccion_usuario', vehiculo_id: e.target.value } : undefined)}><option value="">{unknown ? 'Usar referencia V14 por defecto' : 'Seleccionar vehículo…'}</option>{query.data?.vehiculos.map(v => <option key={v.id} value={v.id}>{v.nombre}</option>)}</select></label>
      {unknown && !selection && <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950"><p className="flex items-start gap-2"><AlertCircle className="mt-0.5 size-4 shrink-0" /><span>{AVISO_V14}</span></p><p className="mt-2 text-xs">V14 es una referencia fija; no garantiza el mínimo exacto de cada reparación. El valor venal y la indemnización se calculan con ese coche. La pérdida total no es fiable para el vehículo real.</p></div>}
      <Collapsible className="rounded-md border">
        <CollapsibleTrigger asChild>
          <button type="button" disabled={disabled} className="group flex w-full items-center justify-between gap-3 rounded-md p-4 text-left outline-none hover:bg-muted/40 focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50">
            <span><span className="block text-xs font-semibold uppercase tracking-wide">Datos para el presupuesto</span><span className="mt-1 block text-xs text-muted-foreground">{summary}</span></span>
            <ChevronDown aria-hidden="true" className="size-4 shrink-0 transition-transform group-data-[state=open]:rotate-180" />
          </button>
        </CollapsibleTrigger>
        <p className="px-4 pb-4 text-xs leading-relaxed text-muted-foreground">En un sistema integrado con la aseguradora, estos datos se cargarían desde la información del cliente y su póliza, sin introducirlos manualmente. Esta demo utiliza valores de ejemplo que puedes modificar.</p>
        <CollapsibleContent>
          <fieldset disabled={disabled} className="grid gap-4 border-t p-4 sm:grid-cols-2">
            <legend className="sr-only">Datos para el presupuesto</legend>
            <label className="text-sm">Antigüedad (años)<input className="peritaje-input mt-1.5" type="number" min="0" step="any" required placeholder="Ej. 3" value={fields.edad} onChange={e => update('edad', e.target.value)} /></label>
            <label className="text-sm">Kilómetros<input className="peritaje-input mt-1.5" type="number" min="0" step="any" required placeholder="Ej. 42000" value={fields.km} onChange={e => update('km', e.target.value)} /></label>
            {select('region', 'Región', query.data?.regiones)}{select('taller', 'Tipo de taller', query.data?.tipos_taller)}
            {select('acabado', 'Acabado de pintura', query.data?.acabados)}{select('pieza', 'Tipo de pieza', query.data?.tipos_pieza)}
            <label className="text-sm">Rol en el siniestro<select className="peritaje-input mt-1.5" value={fields.rol} onChange={e => update('rol', e.target.value)}><option value="propio">Vehículo propio</option><option value="tercero_perjudicado">Tercero perjudicado</option></select></label>
            {fields.rol === 'propio' && select('poliza', 'Póliza', query.data?.polizas)}
          </fieldset>
        </CollapsibleContent>
      </Collapsible>
      <div className="border-t pt-4"><Button type="submit" className="w-full sm:w-auto" disabled={!valid || disabled}>{disabled ? <LoaderCircle className="size-4 animate-spin" /> : <FileText className="size-4" />} Generar informe</Button><p className="mt-2 text-xs text-muted-foreground">Generar el informe no vuelve a analizar la imagen.</p></div>
    </div>
  </form>
}
