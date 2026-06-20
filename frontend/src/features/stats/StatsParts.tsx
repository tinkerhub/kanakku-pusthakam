import type React from "react";

import { cyclePalette, PANEL_CLASS, SHADOW_CLASS } from "../../lib/palette";

type ChartRow = { label: string; value: number };

export function StatTile({
  index = 0,
  label,
  value,
}: {
  index?: number;
  label: string;
  value: number | string;
  tone?: "default" | "accent";
}) {
  const palette = cyclePalette(index);

  return (
    <div
      className={`rounded-lg border border-ink p-3 ${PANEL_CLASS[palette]} ${SHADOW_CLASS[palette]}`}
    >
      <p className="break-words font-display text-4xl font-bold leading-none text-ink">
        {value}
      </p>
      <p className="mt-2 font-mono text-xs font-semibold uppercase tracking-wide">
        {label}
      </p>
    </div>
  );
}

export function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="desk-panel overflow-hidden bg-bg">
      <div className="border-b border-ink bg-panel px-4 py-3">
        <h2 className="font-display text-lg font-semibold text-ink">{title}</h2>
      </div>
      <div className="space-y-4 p-4">{children}</div>
    </section>
  );
}

export function CompactList({
  rows,
  empty,
}: {
  rows: { label: string; value: string }[];
  empty: string;
}) {
  if (!rows.length) {
    return <p className="mt-3 text-sm text-muted">{empty}</p>;
  }

  return (
    <ul className="mt-3 divide-y divide-ink border-y border-ink text-sm">
      {rows.map((row) => (
        <li
          className="flex min-w-0 items-start gap-3 py-2"
          key={`${row.label}-${row.value}`}
        >
          <span className="min-w-0 flex-1 truncate text-ink" title={row.label}>
            {row.label}
          </span>
          <span className="shrink-0 text-right text-xs text-muted">{row.value}</span>
        </li>
      ))}
    </ul>
  );
}

export function BarChart({
  rows,
  valueLabel,
}: {
  rows: ChartRow[];
  valueLabel: string;
}) {
  const maxValue = Math.max(...rows.map((row) => row.value), 0);
  if (!rows.length || maxValue <= 0) {
    return <p className="text-sm text-muted">No chart data.</p>;
  }

  return (
    <div className="space-y-2">
      {rows.map((row) => {
        const width = `${Math.max((row.value / maxValue) * 100, 4)}%`;
        return (
          <div
            className="grid grid-cols-[minmax(0,1fr)_minmax(4rem,2fr)_auto] items-center gap-2 text-sm sm:grid-cols-[minmax(7rem,11rem)_1fr_auto]"
            key={row.label}
          >
            <span className="truncate text-ink" title={row.label}>
              {row.label}
            </span>
            <div className="h-3 overflow-hidden rounded-full border border-ink bg-panel">
              <div className="h-full rounded-full bg-accent" style={{ width }} />
            </div>
            <span className="min-w-14 text-right text-xs text-muted">
              {formatNumber(row.value)} {valueLabel}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function formatNumber(value: number) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value);
}

export function formatDate(value: string) {
  return new Date(value).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
