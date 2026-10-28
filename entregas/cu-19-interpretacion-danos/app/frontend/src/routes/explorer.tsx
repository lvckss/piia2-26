import { useState } from "react";
import { ExplorerImageGrid } from "@/features/explorer/ExplorerImageGrid";
import { FilterSidebar } from "@/features/explorer/FilterSidebar";
import { createFileRoute } from "@tanstack/react-router";
import {
  DEFAULT_FILTERS,
  type FilterState,
} from "@/types/explorer-filters";

export const Route = createFileRoute("/explorer")({
  component: RouteComponent,
});

function RouteComponent() {
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);

  return (
    <div className="grid h-full min-h-0 w-full grid-cols-[20rem_minmax(0,1fr)] overflow-hidden">
      <aside className="h-full min-h-0 border-r bg-sidebar">
        <FilterSidebar
          filters={filters}
          onChange={setFilters}
          onReset={() => setFilters(DEFAULT_FILTERS)}
        />
      </aside>

      <main className="min-h-0 min-w-0 overflow-hidden">
        <ExplorerImageGrid filters={filters} />
      </main>
    </div>
  );
}