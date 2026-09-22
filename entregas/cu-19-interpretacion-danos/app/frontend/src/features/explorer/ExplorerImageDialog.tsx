import * as React from "react";
import { useImageByID } from "./api/use-image-by-id";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
    Car,
    Layers,
    Maximize2,
    ImageIcon,
    AlertTriangle,
    Info,
    Eye,
    EyeOff,
    Download
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";

type ExplorerImageDialogProps = {
    imageId: number | null;
    open: boolean;
    onOpenChange: (open: boolean) => void;
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

const DAMAGE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
    dent: { bg: "bg-blue-500/15", border: "border-blue-500/50", text: "text-blue-600 dark:text-blue-400" },
    scratch: { bg: "bg-amber-500/15", border: "border-amber-500/50", text: "text-amber-600 dark:text-amber-400" },
    crack: { bg: "bg-rose-500/15", border: "border-rose-500/50", text: "text-rose-600 dark:text-rose-400" },
    "glass shatter": { bg: "bg-cyan-500/15", border: "border-cyan-500/50", text: "text-cyan-600 dark:text-cyan-400" },
    glass_shatter: { bg: "bg-cyan-500/15", border: "border-cyan-500/50", text: "text-cyan-600 dark:text-cyan-400" },
    "tire flat": { bg: "bg-violet-500/15", border: "border-violet-500/50", text: "text-violet-600 dark:text-violet-400" },
    tire_flat: { bg: "bg-violet-500/15", border: "border-violet-500/50", text: "text-violet-600 dark:text-violet-400" },
    "lamp broken": { bg: "bg-orange-500/15", border: "border-orange-500/50", text: "text-orange-600 dark:text-orange-400" },
    lamp_broken: { bg: "bg-orange-500/15", border: "border-orange-500/50", text: "text-orange-600 dark:text-orange-400" },
};

const DAMAGE_HEX_COLORS: Record<string, string> = {
    dent: "#3b82f6",
    scratch: "#f59e0b",
    crack: "#f43f5e",
    "glass shatter": "#06b6d4",
    glass_shatter: "#06b6d4",
    "tire flat": "#8b5cf6",
    tire_flat: "#8b5cf6",
    "lamp broken": "#f97316",
    lamp_broken: "#f97316",
};

// HELPERS DE POSICIONAMIENTO DE LABELS

type LabelPosition = {
    x: number;
    y: number;
};

type DragState = {
    instanceId: number;
    pointerId: number;
    startPointerX: number;
    startPointerY: number;
    startLabelX: number;
    startLabelY: number;
};

function clamp(value: number, min: number, max: number) {
    return Math.min(Math.max(value, min), max);
}

function getDamageLabel(label: string) {
    return DAMAGE_LABELS[label] ?? label;
}

function getDamageColors(label: string) {
    return DAMAGE_COLORS[label] ?? {
        bg: "bg-slate-500/15",
        border: "border-slate-500/50",
        text: "text-slate-600 dark:text-slate-400",
    };
}

function getDamageHexColor(label: string) {
    return DAMAGE_HEX_COLORS[label] ?? "#64748b";
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

function getSegmentationPolygons(segmentation: unknown): number[][] {
    if (!Array.isArray(segmentation)) return [];
    if (segmentation.length === 0) return [];

    if (segmentation.every((v) => typeof v === "number")) {
        return [segmentation as number[]];
    }

    return segmentation.filter(
        (polygon): polygon is number[] =>
            Array.isArray(polygon) &&
            polygon.length >= 6 &&
            polygon.every((v) => typeof v === "number")
    );
}

function polygonToPoints(coords: number[]) {
    const points: string[] = [];

    for (let i = 0; i < coords.length - 1; i += 2) {
        points.push(`${coords[i]},${coords[i + 1]}`);
    }

    return points.join(" ");
}

function formatArea(area: number) {
    if (area >= 1000000) {
        return `${(area / 1000000).toFixed(2)}M px²`;
    }
    if (area >= 1000) {
        return `${(area / 1000).toFixed(1)}K px²`;
    }
    return `${area.toFixed(0)} px²`;
}

export function ExplorerImageDialog({
    imageId,
    open,
    onOpenChange,
}: ExplorerImageDialogProps) {
    const { data: image, isPending, isError, error } = useImageByID(imageId, open);
    const [hoveredInstance, setHoveredInstance] = React.useState<number | null>(null);
    const [showOverlay, setShowOverlay] = React.useState(true);

    const imageSrc = React.useMemo(() => {
        if (!image) return "";
        return toDatasetUrl(image.ruta_imagen);
    }, [image]);

    const damageStats = React.useMemo(() => {
        if (!image) return {};
        const stats: Record<string, number> = {};
        image.instances.forEach((instance) => {
            const label = instance.categoria_nombre;
            stats[label] = (stats[label] || 0) + 1;
        });
        return stats;
    }, [image]);

    const svgRef = React.useRef<SVGSVGElement | null>(null);

    // POSICIONAMIENTO DE LABELS
    const [labelPositions, setLabelPositions] = React.useState<Record<number, LabelPosition>>({});
    const [dragState, setDragState] = React.useState<DragState | null>(null);

    const getSvgPoint = React.useCallback((clientX: number, clientY: number) => {
        const svg = svgRef.current;
        if (!svg) return null;

        const pt = svg.createSVGPoint();
        pt.x = clientX;
        pt.y = clientY;

        const ctm = svg.getScreenCTM();
        if (!ctm) return null;

        return pt.matrixTransform(ctm.inverse());
    }, []);

    React.useEffect(() => {
        if (!open) {
            setLabelPositions({});
            setDragState(null);
            return;
        }

        setLabelPositions({});
        setDragState(null);
    }, [image?.id, open]);

    React.useEffect(() => {
        if (!dragState || !image) return;

        const activeDrag = dragState;
        const currentImage = image;

        function handlePointerMove(event: PointerEvent) {
            if (event.pointerId !== activeDrag.pointerId) return;

            const point = getSvgPoint(event.clientX, event.clientY);
            if (!point) return;

            const instance = currentImage.instances.find(
                (x) => x.id === activeDrag.instanceId
            );
            if (!instance) return;

            const label = getDamageLabel(instance.categoria_nombre);
            const labelWidth = Math.max(70, label.length * 8 + 20);
            const labelHeight = 22;

            const deltaX = point.x - activeDrag.startPointerX;
            const deltaY = point.y - activeDrag.startPointerY;

            const nextX = clamp(
                activeDrag.startLabelX + deltaX,
                0,
                Math.max(0, currentImage.width - labelWidth)
            );

            const nextY = clamp(
                activeDrag.startLabelY + deltaY,
                0,
                Math.max(0, currentImage.height - labelHeight)
            );

            setLabelPositions((prev) => ({
                ...prev,
                [activeDrag.instanceId]: { x: nextX, y: nextY },
            }));
        }

        function handlePointerEnd(event: PointerEvent) {
            if (event.pointerId !== activeDrag.pointerId) return;
            setDragState(null);
        }

        window.addEventListener("pointermove", handlePointerMove);
        window.addEventListener("pointerup", handlePointerEnd);
        window.addEventListener("pointercancel", handlePointerEnd);

        return () => {
            window.removeEventListener("pointermove", handlePointerMove);
            window.removeEventListener("pointerup", handlePointerEnd);
            window.removeEventListener("pointercancel", handlePointerEnd);
        };
    }, [dragState, image, getSvgPoint]);

    const handleDownloadImage = React.useCallback(async () => {
        if (!imageSrc || !image) return;

        try {
            const response = await fetch(imageSrc);
            if (!response.ok) {
                throw new Error("No se pudo descargar la imagen");
            }

            const blob = await response.blob();
            const objectUrl = window.URL.createObjectURL(blob);

            const link = document.createElement("a");
            link.href = objectUrl;
            link.download = image.file_name || `image-${image.id}.jpg`;

            document.body.appendChild(link);
            link.click();
            link.remove();

            window.URL.revokeObjectURL(objectUrl);
        } catch {
            // fallback
            window.open(imageSrc, "_blank");
        }
    }, [imageSrc, image]);

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="h-[90vh] w-[96vw] gap-0 overflow-hidden p-0 sm:max-w-[min(96vw,1400px)] [&>button]:cursor-pointer">
                {isPending ? (
                    <div className="flex h-full flex-col items-center justify-center gap-4">
                        <div className="relative">
                            <div className="h-16 w-16 rounded-full border-4 border-muted" />
                            <div className="absolute inset-0 h-16 w-16 animate-spin rounded-full border-4 border-transparent border-t-primary" />
                        </div>
                        <p className="text-sm text-muted-foreground animate-pulse">
                            Cargando imagen...
                        </p>
                    </div>
                ) : null}

                {isError ? (
                    <div className="flex h-full flex-col items-center justify-center gap-4">
                        <div className="rounded-full bg-destructive/10 p-4">
                            <AlertTriangle className="h-8 w-8 text-destructive" />
                        </div>
                        <div className="text-center">
                            <p className="font-medium text-destructive">Error al cargar</p>
                            <p className="text-sm text-muted-foreground">
                                {(error as Error).message}
                            </p>
                        </div>
                    </div>
                ) : null}

                {image ? (
                    <div className="grid h-full min-h-0 grid-cols-1 lg:grid-cols-[minmax(0,1fr)_380px]">
                        {/* Image Panel */}
                        <div className="relative min-h-0 overflow-hidden bg-muted/30">
                            <div className="absolute top-4 right-4 z-10 flex gap-2">
                                <Button
                                    variant="secondary"
                                    size="sm"
                                    className="h-8 gap-1.5 border border-black/20 bg-background/80 backdrop-blur-sm hover:cursor-pointer hover:bg-accent/80"
                                    onClick={() => setShowOverlay(!showOverlay)}
                                >
                                    {showOverlay ? (
                                        <>
                                            <EyeOff className="h-3.5 w-3.5" />
                                            <span className="hidden sm:inline">Ocultar</span>
                                        </>
                                    ) : (
                                        <>
                                            <Eye className="h-3.5 w-3.5" />
                                            <span className="hidden sm:inline">Mostrar</span>
                                        </>
                                    )}
                                </Button>

                                <Button
                                    variant="secondary"
                                    size="sm"
                                    className="h-8 gap-1.5 border border-black/20 bg-background/80 backdrop-blur-sm hover:cursor-pointer hover:bg-accent/80"
                                    onClick={handleDownloadImage}
                                >
                                    <Download className="h-3.5 w-3.5" />
                                    <span className="hidden sm:inline">Descargar</span>
                                </Button>

                                <Button
                                    variant="secondary"
                                    size="sm"
                                    className="h-8 gap-1.5 border border-black/20 bg-background/80 backdrop-blur-sm hover:cursor-pointer hover:bg-accent/80"
                                    onClick={() => window.open(imageSrc, "_blank")}
                                >
                                    <Maximize2 className="h-3.5 w-3.5" />
                                    <span className="hidden sm:inline">Ampliar</span>
                                </Button>
                            </div>

                            <div className="flex h-full items-center justify-center overflow-auto p-20 py-48">
                                <div className="relative inline-block overflow-hidden rounded-lg shadow-2xl ring-1 ring-black/10">
                                    <img
                                        src={imageSrc}
                                        alt={image.file_name}
                                        className="block max-h-full max-w-full object-contain"
                                    />

                                    {showOverlay && (
                                        <svg
                                            ref={svgRef}
                                            className="absolute inset-0 h-full w-full select-none transition-opacity duration-300"
                                            viewBox={`0 0 ${image.width} ${image.height}`}
                                            preserveAspectRatio="none"
                                        >

                                            {image.instances.map((instance) => {
                                                const color = getDamageHexColor(instance.categoria_nombre);
                                                const label = getDamageLabel(instance.categoria_nombre);
                                                const polygons = getSegmentationPolygons(instance.segmentacion);
                                                const isHovered = hoveredInstance === instance.id;

                                                const labelWidth = Math.max(70, label.length * 8 + 20);
                                                const defaultLabelX = clamp(instance.bbox_x, 0, Math.max(0, image.width - labelWidth));
                                                const defaultLabelY = clamp(instance.bbox_y - 26, 0, Math.max(0, image.height - 22));

                                                const currentLabelPosition = labelPositions[instance.id] ?? {
                                                    x: defaultLabelX,
                                                    y: defaultLabelY,
                                                };

                                                const labelX = currentLabelPosition.x;
                                                const labelY = currentLabelPosition.y;
                                                const textY = labelY + 14;
                                                const isDragging = dragState?.instanceId === instance.id;

                                                return (
                                                    <g
                                                        key={instance.id}
                                                        className="transition-all duration-200"
                                                        style={{
                                                            opacity: hoveredInstance === null || isHovered ? 1 : 0.3,
                                                        }}
                                                    >
                                                        {polygons.length > 0 ? (
                                                            polygons.map((polygon, index) => (
                                                                <polygon
                                                                    key={`${instance.id}-${index}`}
                                                                    points={polygonToPoints(polygon)}
                                                                    fill={isHovered ? `${color}44` : `${color}22`}
                                                                    stroke={color}
                                                                    strokeWidth={isHovered ? 3 : 2}
                                                                    vectorEffect="non-scaling-stroke"
                                                                    className="transition-all duration-200"
                                                                    pointerEvents="none"
                                                                />
                                                            ))
                                                        ) : (
                                                            <rect
                                                                x={instance.bbox_x}
                                                                y={instance.bbox_y}
                                                                width={instance.bbox_width}
                                                                height={instance.bbox_height}
                                                                fill={isHovered ? `${color}33` : `${color}18`}
                                                                stroke={color}
                                                                strokeWidth={isHovered ? 3 : 2}
                                                                strokeDasharray={isHovered ? "none" : "4 2"}
                                                                vectorEffect="non-scaling-stroke"
                                                                rx={4}
                                                                className="transition-all duration-200"
                                                                pointerEvents="none"
                                                            />
                                                        )}

                                                        <g
                                                            style={{
                                                                cursor: isDragging ? "grabbing" : "grab",
                                                                touchAction: "none",
                                                            }}
                                                            onPointerDown={(event) => {
                                                                event.preventDefault();
                                                                event.stopPropagation();

                                                                const point = getSvgPoint(event.clientX, event.clientY);
                                                                if (!point) return;

                                                                setHoveredInstance(instance.id);
                                                                setDragState({
                                                                    instanceId: instance.id,
                                                                    pointerId: event.pointerId,
                                                                    startPointerX: point.x,
                                                                    startPointerY: point.y,
                                                                    startLabelX: labelX,
                                                                    startLabelY: labelY,
                                                                });
                                                            }}
                                                            onPointerEnter={() => setHoveredInstance(instance.id)}
                                                            onPointerLeave={() => {
                                                                if (dragState?.instanceId !== instance.id) {
                                                                    setHoveredInstance((prev) => (prev === instance.id ? null : prev));
                                                                }
                                                            }}
                                                        >
                                                            <rect
                                                                x={labelX}
                                                                y={labelY}
                                                                width={labelWidth}
                                                                height={22}
                                                                rx={6}
                                                                ry={6}
                                                                fill={color}
                                                                className="drop-shadow-md"
                                                            />
                                                            <text
                                                                x={labelX + 10}
                                                                y={textY}
                                                                fill="white"
                                                                fontSize="12"
                                                                fontWeight="600"
                                                                fontFamily="system-ui, sans-serif"
                                                                pointerEvents="none"
                                                            >
                                                                {label}
                                                            </text>
                                                        </g>
                                                    </g>
                                                );
                                            })}
                                        </svg>
                                    )}
                                </div>
                            </div>

                            {/* Bottom info strip without dark gradient */}
                            <div className="absolute inset-x-0 bottom-0 border-t bg-background/95 p-4 backdrop-blur-sm">
                                <div className="mx-auto flex max-w-5xl flex-col gap-3">
                                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                                        <div className="rounded-lg border bg-background px-3 py-2 text-center">
                                            <ImageIcon className="mx-auto mb-1 h-4 w-4 text-muted-foreground" />
                                            <p className="text-[11px] text-muted-foreground">Resolución</p>
                                            <p className="text-sm font-semibold">
                                                {image.width}×{image.height}
                                            </p>
                                        </div>

                                        <div className="rounded-lg border bg-background px-3 py-2 text-center">
                                            <Layers className="mx-auto mb-1 h-4 w-4 text-muted-foreground" />
                                            <p className="text-[11px] text-muted-foreground">Instancias</p>
                                            <p className="text-sm font-semibold">
                                                {image.numero_instancias}
                                            </p>
                                        </div>

                                        <div className="rounded-lg border bg-background px-3 py-2 text-center">
                                            <p className="mb-1 text-[11px] text-muted-foreground">Split</p>
                                            <Badge variant="secondary" className="text-xs capitalize">
                                                {image.split}
                                            </Badge>
                                        </div>

                                        <div className="rounded-lg border bg-background px-3 py-2 text-center">
                                            <p className="mb-1 text-[11px] text-muted-foreground">Categorías</p>
                                            <p className="text-sm font-semibold">
                                                {image.numero_categorias}
                                            </p>
                                        </div>
                                    </div>

                                    <div className="flex flex-wrap justify-center gap-2">
                                        {Object.entries(damageStats).map(([label, count]) => (
                                            <Badge
                                                key={label}
                                                variant="outline"
                                                className="gap-1.5 border-black/20 bg-background text-xs font-medium text-foreground"
                                            >
                                                <span
                                                    className="h-2 w-2 rounded-full"
                                                    style={{ backgroundColor: getDamageHexColor(label) }}
                                                />
                                                {getDamageLabel(label)}
                                                <span className="ml-0.5 text-muted-foreground">×{count}</span>
                                            </Badge>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Details Panel */}
                        <div className="flex h-full min-h-0 flex-col border-l bg-background">
                            <div className="border-b bg-muted/30 p-5 shrink-0">
                                <DialogHeader className="space-y-3 text-left">
                                    <div className="flex items-start gap-3">
                                        <div className="min-w-0 flex-1">
                                            <DialogTitle className="truncate text-base font-semibold text-4xl py-2">
                                                {image.file_name}
                                            </DialogTitle>
                                            <DialogDescription className="mt-1 flex items-center gap-2 text-xs">
                                                <Badge variant="outline" className="font-mono text-xs">
                                                    ID {image.id}
                                                </Badge>
                                                <Badge variant="outline" className="font-mono text-xs">
                                                    ext {image.id_externo}
                                                </Badge>
                                            </DialogDescription>
                                        </div>
                                    </div>
                                </DialogHeader>
                            </div>

                            <div className="flex min-h-0 flex-1 flex-col px-5 py-5">
                                <div className="mb-3 flex items-center gap-2 shrink-0">
                                    <AlertTriangle className="h-4 w-4 text-muted-foreground" />
                                    <span className="text-sm font-medium">Daños detectados</span>
                                    <Badge variant="secondary" className="ml-auto text-xs">
                                        {image.instances.length}
                                    </Badge>
                                </div>

                                {image.instances.length === 0 ? (
                                    <div className="rounded-xl border border-dashed p-6 text-center">
                                        <div className="mx-auto mb-3 w-fit rounded-full bg-muted p-3">
                                            <Car className="h-6 w-6 text-muted-foreground" />
                                        </div>
                                        <p className="text-sm font-medium">Sin daños</p>
                                        <p className="mt-1 text-xs text-muted-foreground">
                                            Esta imagen no tiene instancias de daño detectadas.
                                        </p>
                                    </div>
                                ) : (
                                    <ScrollArea className="min-h-0 flex-1 pr-2">
                                        <div className="space-y-2 px-3 py-2">
                                            {image.instances.map((instance) => {
                                                const colors = getDamageColors(instance.categoria_nombre);
                                                const isHovered = hoveredInstance === instance.id;

                                                return (
                                                    <div
                                                        key={instance.id}
                                                        className={cn(
                                                            "group cursor-pointer rounded-xl border p-4 transition-all duration-200",
                                                            colors.bg,
                                                            colors.border,
                                                            isHovered && "ring-2 ring-offset-2 scale-[1.02]"
                                                        )}
                                                        style={
                                                            isHovered
                                                                ? ({
                                                                    ["--tw-ring-color" as any]: getDamageHexColor(
                                                                        instance.categoria_nombre
                                                                    ),
                                                                } as React.CSSProperties)
                                                                : undefined
                                                        }
                                                        onMouseEnter={() => setHoveredInstance(instance.id)}
                                                        onMouseLeave={() => setHoveredInstance(null)}
                                                    >
                                                        <div className="mb-3 flex items-center justify-between">
                                                            <div className="flex items-center gap-2.5">
                                                                <span
                                                                    className="h-3 w-3 rounded-full ring-2 ring-white shadow-sm"
                                                                    style={{
                                                                        backgroundColor: getDamageHexColor(
                                                                            instance.categoria_nombre
                                                                        ),
                                                                    }}
                                                                />
                                                                <span className={cn("text-sm font-semibold", colors.text)}>
                                                                    {getDamageLabel(instance.categoria_nombre)}
                                                                </span>
                                                            </div>

                                                            <Badge
                                                                variant="outline"
                                                                className="font-mono text-xs opacity-60"
                                                            >
                                                                #{instance.id}
                                                            </Badge>
                                                        </div>

                                                        <div className="grid grid-cols-2 gap-2 text-xs">
                                                            <div className="rounded-md bg-background/60 px-2.5 py-1.5">
                                                                <span className="text-muted-foreground">Área</span>
                                                                <p className="font-medium text-foreground">
                                                                    {formatArea(instance.area)}
                                                                </p>
                                                            </div>

                                                            <div className="rounded-md bg-background/60 px-2.5 py-1.5">
                                                                <span className="text-muted-foreground">Cobertura</span>
                                                                <p className="font-medium text-foreground">
                                                                    {instance.area_pct.toFixed(2)}%
                                                                </p>
                                                            </div>
                                                        </div>

                                                        <div className="mt-2 rounded-md bg-background/40 px-2.5 py-1.5 font-mono text-xs text-muted-foreground">
                                                            bbox: ({instance.bbox_x.toFixed(0)},{" "}
                                                            {instance.bbox_y.toFixed(0)}){" "}
                                                            {instance.bbox_width.toFixed(0)}×
                                                            {instance.bbox_height.toFixed(0)}
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </ScrollArea>
                                )}
                            </div>
                        </div>
                    </div>
                ) : null}
            </DialogContent>
        </Dialog>
    );
}