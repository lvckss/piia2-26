import * as React from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { Image, ImageWithLabels } from "@server/models/Image";
import { useInfiniteImages } from "./api/use-infinite-images";
import { ExplorerImageDialog } from "./ExplorerImageDialog";

import {
  Camera,
  VectorSquare,
  Layers3,
  Palette,
  Maximize2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import type { ImagesFiltersInput } from "@server/models/ImageFilters";

type ExplorerImageGridProps = {
  filters: ImagesFiltersInput;
};

const ANGLE_LABELS: Record<string, string> = {
  front: "Frontal",
  inside: "Interior",
  rear: "Trasera",
  side: "Lateral",
  NaN: "Desconocido",
};

const COLOR_LABELS: Record<string, string> = {
  white: "Blanco",
  black: "Negro",
  gray: "Gris",
  silver: "Plateado",
  blue: "Azul",
  red: "Rojo",
  green: "Verde",
  yellow: "Amarillo",
  brown: "Marrón",
  other: "Otro",
};

const COVERAGE_LABELS: Record<string, string> = {
  complete: "Todo",
  completa: "Todo",
  full: "Todo",
  total: "Todo",
  partial: "Parcial",
  parcial: "Parcial",
};

const DAMAGE_LABELS: Record<string, string> = {
  dent: "Abolladura",
  scratch: "Arañazo",
  crack: "Grieta",
  "glass shatter": "Cristal roto",
  glass_shatter: "Cristal roto",
  "tire flat": "Neumático pinchado",
  tire_flat: "Neumático pinchado",
  "lamp broken": "Faro roto",
  lamp_broken: "Faro roto",
};

const LABEL_BADGE_CLASSES: Record<string, string> = {
  dent: "bg-blue-100 text-blue-800 border border-blue-200",
  scratch: "bg-amber-100 text-amber-800 border border-amber-200",
  crack: "bg-rose-100 text-rose-800 border border-rose-200",
  "glass shatter": "bg-cyan-100 text-cyan-800 border border-cyan-200",
  glass_shatter: "bg-cyan-100 text-cyan-800 border border-cyan-200",
  "tire flat": "bg-violet-100 text-violet-800 border border-violet-200",
  tire_flat: "bg-violet-100 text-violet-800 border border-violet-200",
  "lamp broken": "bg-orange-100 text-orange-800 border border-orange-200",
  lamp_broken: "bg-orange-100 text-orange-800 border border-orange-200",
};

const GRID_PADDING = 24;
const GRID_GAP = 12;

const CARD_WIDTH = 300;
const CARD_MEDIA_HEIGHT = Math.round((CARD_WIDTH * 9) / 16);
const CARD_BODY_HEIGHT = 132;
const CARD_HEIGHT = CARD_MEDIA_HEIGHT + CARD_BODY_HEIGHT;
const ROW_HEIGHT = CARD_HEIGHT + GRID_GAP;

function humanizeText(value?: string | null) {
  if (!value) return null;

  return value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function getAngleLabel(value?: string | null) {
  if (!value) return null;
  return ANGLE_LABELS[value] ?? humanizeText(value);
}

function getColorLabel(value?: string | null) {
  if (!value) return null;
  return COLOR_LABELS[value] ?? humanizeText(value);
}

function getCoverageLabel(value?: string | null) {
  if (!value) return null;
  return COVERAGE_LABELS[value.toLowerCase()] ?? humanizeText(value);
}

function getDamageLabel(label: string) {
  return DAMAGE_LABELS[label] ?? humanizeText(label) ?? label;
}

function getDamageBadgeClass(label: string) {
  return (
    LABEL_BADGE_CLASSES[label] ??
    "bg-muted text-muted-foreground border border-border"
  );
}

function toDatasetUrl(rawPath?: string | null) {
  if (!rawPath) return "";

  const cleaned = rawPath
    .replace(/\\/g, "/")
    .replace(/^\.?\//, "")
    .replace(/^.*\/bd\/clean_data\//, "")
    .replace(/^.*\/clean_data\//, "");

  return `/dataset/${cleaned
    .split("/")
    .map(encodeURIComponent)
    .join("/")}`;
}

function splitBadgeClass(split: Image["split"]) {
  switch (split) {
    case "train":
      return "bg-emerald-600 text-white";
    case "val":
      return "bg-amber-500 text-white";
    case "test":
      return "bg-sky-600 text-white";
    default:
      return "bg-muted text-foreground";
  }
}

function coverageBadgeClass(cobertura?: string | null) {
  const value = cobertura?.toLowerCase() ?? "";

  if (
    value.includes("complete") ||
    value.includes("completa") ||
    value.includes("full") ||
    value.includes("total")
  ) {
    return "bg-emerald-600/90 text-white";
  }

  if (
    value.includes("partial") ||
    value.includes("parcial") ||
    value.includes("occluded") ||
    value.includes("oculta")
  ) {
    return "bg-amber-500/90 text-white";
  }

  return "bg-background/90 text-foreground";
}

function MiniBadge({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-medium ${className}`}
    >
      {children}
    </span>
  );
}

function getColumnCount(availableWidth: number) {
  if (availableWidth <= 0) return 1;

  return Math.max(
    1,
    Math.floor((availableWidth + GRID_GAP) / (CARD_WIDTH + GRID_GAP))
  );
}

const ImageCard = React.memo(function ImageCard({
  image,
  onClick,
}: {
  image: ImageWithLabels;
  onClick: () => void;
}) {
  const imageSrc = React.useMemo(
    () => toDatasetUrl(image.ruta_thumbnail ?? image.ruta_imagen),
    [image.ruta_thumbnail, image.ruta_imagen]
  );

  const angleLabel = getAngleLabel(image.angulo_fotografia);
  const coverageLabel = getCoverageLabel(image.cobertura);
  const vehicleColor = getColorLabel(image.color_vehiculo);

  return (
    <button
      type="button"
      onClick={onClick}
      className="block text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-ring hover:cursor-pointer"
      style={{ width: CARD_WIDTH, height: CARD_HEIGHT }}
    >
      <article className="group flex h-full w-full flex-col overflow-hidden rounded-xl border border-border bg-card transition-all hover:border-accent hover:shadow-md">
        <div
          className="relative overflow-hidden bg-muted"
          style={{ height: CARD_MEDIA_HEIGHT }}
        >
          <img
            src={imageSrc}
            alt={image.file_name}
            loading="lazy"
            decoding="async"
            fetchPriority="low"
            width={CARD_WIDTH}
            height={CARD_MEDIA_HEIGHT}
            className="h-full w-full object-cover transition-transform duration-200 group-hover:scale-[1.03]"
          />

          <div className="absolute inset-0 bg-black/0 transition-colors duration-200 group-hover:bg-black/10" />

          <div className="absolute left-2 top-2 flex gap-1">
            <MiniBadge className={`${splitBadgeClass(image.split)} uppercase`}>
              {image.split}
            </MiniBadge>
          </div>

          <div className="absolute right-2 top-2">
            <MiniBadge className="bg-background/90 text-foreground shadow-sm">
              <VectorSquare className="h-3 w-3" />
              {image.numero_instancias}
            </MiniBadge>
          </div>

          <div className="absolute bottom-2 left-2 flex max-w-[70%] gap-1 overflow-hidden">
            {angleLabel ? (
              <MiniBadge className="bg-background/90 text-muted-foreground shadow-sm">
                <Camera className="h-3 w-3" />
                {angleLabel}
              </MiniBadge>
            ) : null}
          </div>

          <div className="absolute bottom-2 right-2 flex gap-1">
            {coverageLabel ? (
              <MiniBadge className={coverageBadgeClass(image.cobertura)}>
                {image.cobertura?.toLowerCase().includes("complete") ||
                image.cobertura?.toLowerCase().includes("completa") ||
                image.cobertura?.toLowerCase().includes("full") ||
                image.cobertura?.toLowerCase().includes("total") ? (
                  <CheckCircle2 className="h-3 w-3" />
                ) : (
                  <AlertCircle className="h-3 w-3" />
                )}
                {coverageLabel}
              </MiniBadge>
            ) : null}
          </div>
        </div>

        <div
          className="flex flex-1 flex-col justify-between px-4 pt-3 pb-2"
          style={{ height: CARD_BODY_HEIGHT }}
        >
          <div className="min-w-0 space-y-1">
            <div className="flex items-start gap-2">
              <p className="min-w-0 flex-1 truncate text-sm font-medium leading-5 text-foreground">
                {image.file_name}
              </p>

              {image.labels.length > 0 ? (
                <div className="flex max-w-[45%] flex-wrap justify-end gap-1 overflow-hidden">
                  {image.labels.map((label) => (
                    <MiniBadge
                      key={`${image.id}-${label}`}
                      className={getDamageBadgeClass(label)}
                    >
                      {getDamageLabel(label)}
                    </MiniBadge>
                  ))}
                </div>
              ) : null}
            </div>

            <p className="truncate text-[11px] font-mono text-muted-foreground">
              ID {image.id} · ext {image.id_externo}
            </p>
          </div>

          <div className="flex gap-1.5 overflow-hidden">
            <MiniBadge className="bg-secondary text-secondary-foreground">
              <Layers3 className="h-3 w-3" />
              {image.numero_categorias} categorías
            </MiniBadge>

            <MiniBadge className="bg-secondary text-secondary-foreground">
              <VectorSquare className="h-3 w-3" />
              {image.numero_instancias} instancias
            </MiniBadge>

            <MiniBadge className="bg-secondary text-secondary-foreground">
              <Maximize2 className="h-3 w-3" />
              {image.width}×{image.height}
            </MiniBadge>

            {vehicleColor ? (
              <MiniBadge className="bg-secondary text-secondary-foreground">
                <Palette className="h-3 w-3" />
                {vehicleColor}
              </MiniBadge>
            ) : null}
          </div>
        </div>
      </article>
    </button>
  );
});

export function ExplorerImageGrid({ filters }: ExplorerImageGridProps) {
  const [selectedImageId, setSelectedImageId] = React.useState<number | null>(null);
  const [dialogOpen, setDialogOpen] = React.useState(false);

  const openImageDialog = React.useCallback((imageId: number) => {
    setSelectedImageId(imageId);
    setDialogOpen(true);
  }, []);

  const {
    data,
    isPending,
    isError,
    error,
    hasNextPage,
    fetchNextPage,
    isFetchingNextPage,
    isFetching,
  } = useInfiniteImages(filters);

  const scrollRef = React.useRef<HTMLDivElement | null>(null);
  const resizeObserverRef = React.useRef<ResizeObserver | null>(null);
  const [availableWidth, setAvailableWidth] = React.useState(0);

  const images = React.useMemo(
    () => data?.pages.flatMap((page) => page.items) ?? [],
    [data]
  );

  const setMeasureElement = React.useCallback((node: HTMLDivElement | null) => {
    resizeObserverRef.current?.disconnect();
    resizeObserverRef.current = null;

    if (!node) return;

    const update = () => {
      const nextWidth = node.clientWidth;
      setAvailableWidth((prev) => (prev !== nextWidth ? nextWidth : prev));
    };

    update();

    const observer = new ResizeObserver(() => update());
    observer.observe(node);
    resizeObserverRef.current = observer;
  }, []);

  React.useEffect(() => {
    return () => {
      resizeObserverRef.current?.disconnect();
    };
  }, []);

  const columns = React.useMemo(
    () => getColumnCount(availableWidth),
    [availableWidth]
  );

  const rowCount = React.useMemo(
    () => Math.ceil(images.length / columns),
    [images.length, columns]
  );

  const gridWidth = React.useMemo(
    () => columns * CARD_WIDTH + (columns - 1) * GRID_GAP,
    [columns]
  );

  const rowVirtualizer = useVirtualizer({
    count: rowCount,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 8,
  });

  const virtualRows = rowVirtualizer.getVirtualItems();

  React.useEffect(() => {
    rowVirtualizer.measure();
  }, [columns, rowCount, rowVirtualizer]);

  React.useEffect(() => {
    const lastRow = virtualRows[virtualRows.length - 1];
    if (!lastRow) return;

    const isNearEnd = lastRow.index >= rowCount - 3;

    if (isNearEnd && hasNextPage && !isFetching && !isFetchingNextPage) {
      void fetchNextPage();
    }
  }, [
    virtualRows,
    rowCount,
    hasNextPage,
    isFetching,
    isFetchingNextPage,
    fetchNextPage,
  ]);

  if (isPending) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Cargando imágenes...
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-destructive">
        {(error as Error).message}
      </div>
    );
  }

  if (images.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        No hay imágenes.
      </div>
    );
  }

  return (
    <>
      <div ref={scrollRef} className="h-full min-h-0 w-full overflow-auto">
        <div style={{ padding: GRID_PADDING }}>
          <div
            ref={setMeasureElement}
            className="relative w-full"
            style={{ height: rowVirtualizer.getTotalSize() }}
          >
            {virtualRows.map((virtualRow) => {
              const startIndex = virtualRow.index * columns;
              const endIndex = startIndex + columns;
              const rowImages = images.slice(startIndex, endIndex);

              return (
                <div
                  key={virtualRow.key}
                  className="absolute left-0 top-0 w-full"
                  style={{
                    transform: `translateY(${virtualRow.start}px)`,
                    height: CARD_HEIGHT,
                  }}
                >
                  <div
                    className="mx-auto grid"
                    style={{
                      gridTemplateColumns: `repeat(${columns}, ${CARD_WIDTH}px)`,
                      gap: `${GRID_GAP}px`,
                      width: `${gridWidth}px`,
                    }}
                  >
                    {rowImages.map((image) => (
                      <ImageCard
                        key={image.id}
                        image={image}
                        onClick={() => openImageDialog(image.id)}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>

          {isFetchingNextPage ? (
            <div className="py-4 text-center text-sm text-muted-foreground">
              Cargando más...
            </div>
          ) : null}
        </div>
      </div>

      <ExplorerImageDialog
        imageId={selectedImageId}
        open={dialogOpen}
        onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) {
            setSelectedImageId(null);
          }
        }}
      />
    </>
  );
}