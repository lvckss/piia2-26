// filter-sidebar.tsx
import type { ElementType, ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
    ChevronDown,
    RotateCcw,
    Filter,
    Layers,
    Camera,
    Palette,
    Target,
    Grid3X3,
} from "lucide-react";

import type {
    FilterState,
    Split,
    DamageCategory,
    ShootingAngle,
    VehicleColor,
    CoverageState,
} from "@/types/explorer-filters";
import { DEFAULT_FILTERS } from "@/types/explorer-filters";

type Option<T extends string> = {
    value: T;
    label: string;
};

const SPLIT_OPTIONS: Option<Split>[] = [
    { value: "train", label: "Train" },
    { value: "val", label: "Validation" },
    { value: "test", label: "Test" },
];

const DAMAGE_OPTIONS: Option<DamageCategory>[] = [
    { value: "dent", label: "Abolladura" },
    { value: "scratch", label: "Arañazo" },
    { value: "crack", label: "Grieta" },
    { value: "glass shatter", label: "Cristal roto" },
    { value: "lamp broken", label: "Faro roto" },
    { value: "tire flat", label: "Neumático pinchado" },
];

const ANGLE_OPTIONS: Option<ShootingAngle>[] = [
    { value: "front", label: "Frontal" },
    { value: "rear", label: "Trasera" },
    { value: "side", label: "Lateral" },
    { value: "inside", label: "Interior" },
    { value: "NaN", label: "Desconocido" },
];

const COLOR_OPTIONS: Option<VehicleColor>[] = [
    { value: "white", label: "Blanco" },
    { value: "black", label: "Negro" },
    { value: "gray", label: "Gris" },
    { value: "silver", label: "Plateado" },
    { value: "blue", label: "Azul" },
    { value: "red", label: "Rojo" },
    { value: "green", label: "Verde" },
    { value: "yellow", label: "Amarillo" },
    { value: "brown", label: "Marrón" },
    { value: "other", label: "Otro" },
];

function FilterSection({
    title,
    icon: Icon,
    children,
    defaultOpen = true,
}: {
    title: string;
    icon: ElementType;
    children: ReactNode;
    defaultOpen?: boolean;
}) {
    return (
        <Collapsible defaultOpen={defaultOpen} className="group">
            <CollapsibleTrigger className="flex w-full items-center justify-between py-2 text-sm font-medium hover:cursor-pointer">
                <span className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-muted-foreground" />
                    {title}
                </span>

                <ChevronDown className="h-4 w-4 text-muted-foreground transition-transform group-data-[state=open]:rotate-180" />
            </CollapsibleTrigger>

            <CollapsibleContent className="pt-2 pb-4">
                {children}
            </CollapsibleContent>
        </Collapsible>
    );
}

function CheckboxGroup<T extends string>({
    options,
    selected,
    onChange,
    columns = 1,
}: {
    options: Option<T>[];
    selected: T[];
    onChange: (selected: T[]) => void;
    columns?: 1 | 2;
}) {
    const gridClass = columns === 2 ? "grid-cols-2" : "grid-cols-1";

    const toggleValue = (value: T, checked: boolean) => {
        if (checked) {
            onChange([...selected, value]);
            return;
        }

        onChange(selected.filter((item) => item !== value));
    };

    return (
        <div className={`grid gap-2 ${gridClass}`}>
            {options.map((option) => {
                const isChecked = selected.includes(option.value);
                return (
                    <label
                        key={option.value}
                        className="flex items-center gap-2 text-sm text-foreground hover:cursor-pointer"
                    >
                        <Checkbox
                            checked={isChecked}
                            onCheckedChange={(checked) => toggleValue(option.value, !!checked)}
                            className={
                                isChecked
                                    ? "hover:cursor-pointer"
                                    : "hover:bg-muted hover:cursor-pointer"
                            }
                        />
                        <span className="truncate">{option.label}</span>
                    </label>
                );
            })}
        </div>
    );
}

function CoverageToggle({
    value,
    onChange,
}: {
    value: CoverageState;
    onChange: (value: CoverageState) => void;
}) {
    const options: { value: CoverageState; label: string }[] = [
        { value: "ambos", label: "Ambos" },
        { value: "todo", label: "Todo" },
        { value: "parcial", label: "Parcial" },
    ];

    return (
        <div className="flex overflow-hidden rounded-md border">
            {options.map((option) => {
                const isActive = value === option.value;

                return (
                    <button
                        key={option.value}
                        type="button"
                        onClick={() => onChange(option.value)}
                        className={[
                            "flex-1 px-3 py-1.5 text-xs font-medium transition-colors hover:cursor-pointer",
                            isActive
                                ? "bg-primary text-primary-foreground"
                                : "bg-background text-foreground hover:bg-muted hover:text-foreground",
                        ].join(" ")}
                    >
                        {option.label}
                    </button>
                );
            })}
        </div>
    );
}

function RangeFilter({
    label,
    value,
    min,
    max,
    step,
    minText,
    maxText,
    onChange,
}: {
    label?: string;
    value: [number, number];
    min: number;
    max: number;
    step: number;
    minText: string;
    maxText: string;
    onChange: (value: [number, number]) => void;
}) {
    return (
        <div className="space-y-2 px-2">
            {label ? <Label className="text-xs text-muted-foreground">{label}</Label> : null}

            <div className="flex justify-between text-xs text-muted-foreground">
                <span>{minText}</span>
                <span>{maxText}</span>
            </div>

            <Slider
                value={value}
                min={min}
                max={max}
                step={step}
                onValueChange={(next) => onChange(next as [number, number])}
            />
        </div>
    );
}

type FilterSidebarProps = {
    filters: FilterState;
    onChange: (next: FilterState) => void;
    onReset?: () => void;
};

export function FilterSidebar({
    filters,
    onChange,
    onReset,
}: FilterSidebarProps) {
    const updateFilter = <K extends keyof FilterState>(
        key: K,
        value: FilterState[K]
    ) => {
        onChange({ ...filters, [key]: value });
    };

    const resetFilters = () => {
        onChange(DEFAULT_FILTERS);
        onReset?.();
    };

    const updateFilters = (patch: Partial<FilterState>) => {
        onChange({ ...filters, ...patch });
    };

    return (
        <aside className="flex h-full min-h-0 flex-col bg-background text-sidebar-foreground">
            <div className="border-b p-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Filter className="h-4 w-4 text-primary" />
                        <h2 className="text-sm font-semibold">Filters</h2>
                    </div>

                    <Button
                        variant="outline"
                        size="sm"
                        onClick={resetFilters}
                        className="hover:cursor-pointer"
                    >
                        <RotateCcw className="mr-1 h-3 w-3" />
                        Reset
                    </Button>
                </div>
            </div>

            <ScrollArea className="min-h-0 flex-1 px-4">
                <div className="py-2">
                    <FilterSection title="Conjunto de datos" icon={Layers}>
                        <CheckboxGroup
                            options={SPLIT_OPTIONS}
                            selected={filters.split}
                            onChange={(value) => updateFilter("split", value)}
                        />
                    </FilterSection>

                    <Separator className="my-2" />

                    <FilterSection title="Categoría del daño (label)" icon={Target}>
                        <CheckboxGroup
                            options={DAMAGE_OPTIONS}
                            selected={filters.damageCategories}
                            onChange={(value) => updateFilter("damageCategories", value)}
                            columns={2}
                        />
                    </FilterSection>

                    <Separator className="my-2" />

                    <FilterSection title="Número de instancias" icon={Grid3X3}>
                        <div className="space-y-4">
                            <RangeFilter
                                value={[filters.minInstances, filters.maxInstances]}
                                min={0}
                                max={13}
                                step={1}
                                minText={`Mín: ${filters.minInstances}`}
                                maxText={`Máx: ${filters.maxInstances}`}
                                onChange={([min, max]) => {
                                    updateFilters({
                                        minInstances: min,
                                        maxInstances: max,
                                    });
                                }}
                            />

                            <RangeFilter
                                label="Número de categorías distintas"
                                value={[filters.minCategories, filters.maxCategories]}
                                min={0}
                                max={6}
                                step={1}
                                minText={`Mín: ${filters.minCategories}`}
                                maxText={`Máx: ${filters.maxCategories}`}
                                onChange={([min, max]) => {
                                    updateFilters({
                                        minCategories: min,
                                        maxCategories: max,
                                    });
                                }}
                            />
                        </div>
                    </FilterSection>

                    <Separator className="my-2" />

                    <FilterSection
                        title="Área que ocupa la instancia (%)"
                        icon={Grid3X3}
                        defaultOpen={false}
                    >
                        <RangeFilter
                            value={[filters.minArea, filters.maxArea]}
                            min={0}
                            max={100}
                            step={0.01}
                            minText={`Mín: ${filters.minArea.toFixed(2)}%`}
                            maxText={`Máx: ${filters.maxArea.toFixed(2)}%`}
                            onChange={([min, max]) => {
                                updateFilters({
                                    minArea: min,
                                    maxArea: max,
                                });
                            }}
                        />
                    </FilterSection>

                    <Separator className="my-2" />

                    <FilterSection title="Cobertura (cuanto se ve de coche)" icon={Target} defaultOpen={false}>
                        <CoverageToggle
                            value={filters.complete}
                            onChange={(value) => updateFilter("complete", value)}
                        />
                    </FilterSection>

                    <Separator className="my-2" />

                    <FilterSection title="Ángulo de la foto" icon={Camera}>
                        <CheckboxGroup
                            options={ANGLE_OPTIONS}
                            selected={filters.shootingAngle}
                            onChange={(value) => updateFilter("shootingAngle", value)}
                            columns={2}
                        />
                    </FilterSection>

                    <Separator className="my-2" />

                    <FilterSection
                        title="Color del vehículo"
                        icon={Palette}
                        defaultOpen={false}
                    >
                        <CheckboxGroup
                            options={COLOR_OPTIONS}
                            selected={filters.vehicleColor}
                            onChange={(value) => updateFilter("vehicleColor", value)}
                            columns={2}
                        />
                    </FilterSection>

                    <Separator className="my-2" />
                </div>
            </ScrollArea>
        </aside>
    );
}