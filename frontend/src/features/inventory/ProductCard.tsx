import { Link } from "react-router-dom";

import { cyclePalette, PANEL_CLASS, SHADOW_CLASS } from "../../lib/palette";
import type { Availability, Product } from "../../types/inventory";

type ProductCardProps = {
  product: Product;
  index: number;
  detailPath: string;
  quantity: number;
  onDecrement: () => void;
  onIncrement: () => void;
};

function isUnavailable(product: Product): boolean {
  return product.availability?.label === "Unavailable";
}

function statusChip(availability: Availability): { text: string; cls: string } | null {
  if (availability === null) {
    return null;
  }
  const label = availability.label ?? "Available";
  const count =
    availability.mode === "exact_count" && availability.count != null
      ? availability.count
      : null;

  if (label === "Unavailable") {
    return { text: "Unavailable", cls: "chip bg-[#ffdad6] text-[#93000a]" };
  }
  if (label === "Limited") {
    return {
      text: count != null ? `Limited (${count})` : "Limited",
      cls: "chip bg-[#fcdf46] text-[#3d3400]",
    };
  }
  return {
    text: count != null ? `Available (${count})` : "Available",
    cls: "chip chip-available",
  };
}

export function ProductCard({
  product,
  index,
  detailPath,
  quantity,
  onDecrement,
  onIncrement,
}: ProductCardProps) {
  const disabled = isUnavailable(product);
  const chip = statusChip(product.availability);
  const idLabel = `ID: ${String(product.id).padStart(4, "0")}`;
  const palette = cyclePalette(index);

  return (
    <article className={`group flex h-full flex-col overflow-hidden rounded-lg border border-ink bg-panel transition-all duration-150 hover:-translate-y-1 hover:scale-[1.02] ${SHADOW_CLASS[palette]}`}>
      <div className={`border-b border-ink px-3 py-2 font-mono text-xs font-semibold uppercase tracking-wide ${PANEL_CLASS[palette]}`}>
        Catalog item
      </div>
      <div className="relative h-44 overflow-hidden border-b border-ink bg-surface">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.name}
            loading="lazy"
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="blueprint-bg grid h-full w-full place-items-center">
            <span className="font-display text-4xl font-bold uppercase text-ink/15">
              {product.name.slice(0, 2)}
            </span>
          </div>
        )}
        {chip ? (
          <span className={`absolute right-2 top-2 max-w-[calc(100%-1rem)] ${chip.cls}`}>{chip.text}</span>
        ) : null}
      </div>

      <div className="flex flex-1 flex-col p-4">
        <h2 className="break-words font-display text-lg font-semibold uppercase leading-tight text-ink">
          {product.name}
        </h2>
        <div className="mt-2 flex flex-wrap gap-2">
          <span className="chip">{idLabel}</span>
        </div>
        <p className="mt-2 line-clamp-2 text-sm leading-6 text-muted">
          {product.description || "No description provided."}
        </p>
        {product.category_name ? (
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="chip">{product.category_name}</span>
          </div>
        ) : null}

        <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-4">
          <div className="flex items-center rounded-full border border-ink bg-bg">
            <button
              aria-label={`Remove ${product.name}`}
              className="h-9 w-9 rounded-l-full font-mono text-lg font-semibold text-ink transition hover:bg-surface hover:text-ink disabled:cursor-not-allowed disabled:text-muted"
              disabled={quantity === 0}
              type="button"
              onClick={onDecrement}
            >
              -
            </button>
            <span className="grid h-9 min-w-10 place-items-center border-x border-ink px-2 font-mono text-sm font-semibold text-ink">
              {quantity}
            </span>
            <button
              aria-label={`Add ${product.name}`}
              className="h-9 w-9 rounded-r-full font-mono text-lg font-semibold text-ink transition hover:bg-surface hover:text-ink disabled:cursor-not-allowed disabled:text-muted"
              disabled={disabled}
              type="button"
              onClick={onIncrement}
            >
              +
            </button>
          </div>
          <Link
            className="min-w-0 break-words font-mono text-xs font-semibold uppercase tracking-tight text-secondary underline-offset-4 hover:underline"
            to={detailPath}
          >
            Details &rarr;
          </Link>
        </div>
      </div>
    </article>
  );
}
