export const VIBRANT = ["blue", "yellow", "mint", "coral"] as const;
export type Vibrant = (typeof VIBRANT)[number] | "pink";
/** Cycle hero/marketing cards through the 4 pastels by index. */
export function cyclePalette(index: number): (typeof VIBRANT)[number] {
  return VIBRANT[((index % VIBRANT.length) + VIBRANT.length) % VIBRANT.length];
}
/** The makerspace directory cards cycle blue → yellow → pink. */
export const DIRECTORY_VIBRANT = ["blue", "yellow", "pink"] as const;
export function cycleDirectory(index: number): Vibrant {
  const n = DIRECTORY_VIBRANT.length;
  return DIRECTORY_VIBRANT[((index % n) + n) % n];
}
export const PANEL_CLASS: Record<Vibrant, string> = {
  blue: "panel-blue", yellow: "panel-yellow", mint: "panel-mint", coral: "panel-coral",
  pink: "panel-pink",
};
export const SHADOW_CLASS: Record<Vibrant, string> = {
  blue: "shadow-hardsoft-blue", yellow: "shadow-hardsoft-yellow",
  mint: "shadow-hardsoft-mint", coral: "shadow-hardsoft-coral",
  pink: "shadow-hardsoft-pink",
};
