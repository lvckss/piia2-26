import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'

import {
  QueryClient,
  QueryClientProvider,
} from '@tanstack/react-query'

import { RouterProvider, createRouter } from '@tanstack/react-router'

import { routeTree } from './routeTree.gen.ts'

import { ThemeProvider } from '@/components/theme-provider.tsx'

const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider defaultTheme="light" storageKey="vite-ui-theme">
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
)