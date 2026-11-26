// Misma resolución de rutas para el explorador y el selector de peritaje.
export function toDatasetUrl(rawPath?: string | null) {
  if (!rawPath) return ''
  const cleaned = rawPath.replace(/\\/g, '/').replace(/^\.?\//, '').replace(/^.*\/bd\/clean_data\//, '').replace(/^.*\/clean_data\//, '')
  return `/dataset/${cleaned.split('/').map(encodeURIComponent).join('/')}`
}
