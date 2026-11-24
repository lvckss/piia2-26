import { useState } from 'react'
import { ImageIcon, LoaderCircle, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useInfiniteImages } from '@/features/explorer/api/use-infinite-images'
import { toDatasetUrl } from '@/lib/dataset-url'
import type { ImageWithLabels } from '@server/models/Image'
import type { DamageCategory, Split } from '@/types/explorer-filters'

type Props = { disabled: boolean; selectedId?: number; onSelect: (image: ImageWithLabels) => void }
export function DatasetSelector({ disabled, selectedId, onSelect }: Props) {
  const [split, setSplit] = useState('')
  const [damage, setDamage] = useState('')
  const [search, setSearch] = useState('')
  const query = useInfiniteImages({ split: split ? [split as Split] : [], damageCategories: damage ? [damage as DamageCategory] : [] })
  const images = query.data?.pages.flatMap(p => p.items).filter(i => i.file_name.toLowerCase().includes(search.toLowerCase())) ?? []
  return <section className="rounded-lg border bg-card" aria-label="Imágenes del dataset">
    <div className="border-b p-4">
      <h2 className="flex items-center gap-2 font-semibold"><ImageIcon className="size-4" /> Seleccionar del dataset</h2>
      <p className="mt-1 text-sm text-muted-foreground">Elige una imagen original. Seleccionarla todavía no inicia el análisis.</p>
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        <label className="text-xs text-muted-foreground">Partición del dataset
          <select className="peritaje-input mt-1" aria-label="Partición del dataset" value={split} onChange={e => setSplit(e.target.value)} disabled={disabled}>
            <option value="">Todas las particiones</option><option value="train">Entrenamiento</option><option value="val">Validación</option><option value="test">Prueba</option>
          </select>
        </label>
        <label className="text-xs text-muted-foreground">Tipo de daño
          <select className="peritaje-input mt-1" aria-label="Tipo de daño" value={damage} onChange={e => setDamage(e.target.value)} disabled={disabled}>
            <option value="">Todos los daños</option>{[['dent', 'Abolladura'], ['scratch', 'Arañazo'], ['crack', 'Grieta'], ['glass shatter', 'Cristal roto'], ['lamp broken', 'Faro roto'], ['tire flat', 'Neumático pinchado']].map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </select>
        </label>
      </div>
      <label className="mt-2 flex items-center gap-2 rounded-md border px-3"><Search className="size-4 text-muted-foreground" />
        <input aria-label="Buscar por nombre en las imágenes cargadas" className="h-9 w-full bg-transparent text-sm outline-none" placeholder="Buscar en las imágenes cargadas…" value={search} onChange={e => setSearch(e.target.value)} disabled={disabled} />
      </label>
    </div>
    <div className="max-h-[28rem] overflow-auto p-3">
      {query.isPending && <p className="p-6 text-center text-sm text-muted-foreground">Cargando imágenes…</p>}
      {query.isError && <div className="p-4 text-sm"><p>No se pudieron cargar las imágenes del dataset.</p><Button variant="outline" className="mt-2" onClick={() => query.refetch()}>Volver a cargar imágenes</Button></div>}
      {!query.isPending && !query.isError && images.length === 0 && <p className="p-6 text-center text-sm text-muted-foreground">No hay imágenes con estos filtros. Puedes cambiar los filtros o subir una imagen.</p>}
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-3">
        {images.map(image => <button key={image.id} type="button" disabled={disabled} aria-pressed={selectedId === image.id} aria-label={`Seleccionar imagen ${image.file_name}`} onClick={() => onSelect(image)} className={`overflow-hidden rounded-lg border bg-card text-left transition hover:border-foreground/40 hover:shadow-sm focus-visible:outline-2 focus-visible:outline-ring disabled:opacity-50 ${selectedId === image.id ? 'border-primary ring-1 ring-primary' : ''}`}>
          <img src={toDatasetUrl(image.ruta_thumbnail || image.ruta_imagen)} alt={image.file_name} loading="lazy" className="aspect-video w-full bg-muted object-cover" />
          <div className="p-2"><p className="truncate text-xs font-medium">{image.file_name}</p><p className="mt-1 text-[11px] text-muted-foreground">{image.split} · {image.labels.length} tipos de daño anotados</p></div>
        </button>)}
      </div>
      {query.hasNextPage && <Button variant="outline" className="mt-4 w-full" disabled={disabled || query.isFetchingNextPage} onClick={() => query.fetchNextPage()}>{query.isFetchingNextPage && <LoaderCircle className="size-4 animate-spin" />} Cargar más imágenes</Button>}
    </div>
  </section>
}
