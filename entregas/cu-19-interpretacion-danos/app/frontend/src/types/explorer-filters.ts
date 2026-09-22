export type TriState = "ambos" | "sí" | "no";
export type CoverageState = "ambos" | "todo" | "parcial";

export type Split = "train" | "val" | "test";

export type DamageCategory =
  | "dent"
  | "scratch"
  | "crack"
  | "glass shatter"
  | "lamp broken"
  | "tire flat";

export type ShootingAngle =
  | "front"
  | "inside"
  | "rear"
  | "side"
  | "NaN";

export type VehicleColor =
  | "white"
  | "black"
  | "gray"
  | "silver"
  | "blue"
  | "red"
  | "green"
  | "yellow"
  | "brown"
  | "other";

export type FilterState = {
  split: Split[];
  damageCategories: DamageCategory[];
  minInstances: number;
  maxInstances: number;
  minCategories: number;
  maxCategories: number;
  occluded: TriState;
  shootingAngle: ShootingAngle[];
  complete: CoverageState;
  vehicleColor: VehicleColor[];
  minArea: number;
  maxArea: number;
  onlyMultipleDamages: boolean;
  search: string;
};

export const DEFAULT_FILTERS: FilterState = {
  split: [],
  damageCategories: [],
  minInstances: 0,
  maxInstances: 13,
  minCategories: 0,
  maxCategories: 6,
  occluded: "ambos",
  shootingAngle: [],
  complete: "ambos",
  vehicleColor: [],
  minArea: 0,
  maxArea: 100,
  onlyMultipleDamages: false,
  search: "",
};