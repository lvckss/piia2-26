import { createFileRoute } from '@tanstack/react-router'
import { PeritajePage } from '@/features/peritaje/PeritajePage'

export const Route = createFileRoute('/peritaje')({ component: PeritajePage })
