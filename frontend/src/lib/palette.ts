export const VIBRANT = ["blue", "yellow", "mint", "coral"] as const;
export type Vibrant = (typeof VIBRANT)[number];
/** Cycle hero/marketing cards through the 4 pastels by index. */
export function cyclePalette(index: number): Vibrant {
  return VIBRANT[((index % VIBRANT.length) + VIBRANT.length) % VIBRANT.length];
}
export const PANEL_CLASS: Record<Vibrant, string> = {
  blue: "panel-blue", yellow: "panel-yellow", mint: "panel-mint", coral: "panel-coral",
};
export const SHADOW_CLASS: Record<Vibrant, string> = {
  blue: "shadow-hardsoft-blue", yellow: "shadow-hardsoft-yellow",
  mint: "shadow-hardsoft-mint", coral: "shadow-hardsoft-coral",
};
