import { createRootRoute, Link, Outlet } from '@tanstack/react-router'
//import { TanStackRouterDevtools } from '@tanstack/react-router-devtools'
export const Route = createRootRoute({
  component: RootComponent,
})

function RootComponent() {
  return (
    <div className="grid h-dvh grid-rows-[auto_minmax(0,1fr)] overflow-hidden">
      <header className="border-b">
        <div className="flex gap-2 p-2">
          <Link to="/" className="[&.active]:font-bold">
            Playground
          </Link>
          {' | '}
          <Link to="/explorer" className="[&.active]:font-bold">
            Explorar dataset
          </Link>
        </div>
      </header>

      <div className="min-h-0 overflow-hidden">
        <Outlet />
      </div>
    </div>
  )
}