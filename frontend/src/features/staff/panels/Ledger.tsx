import { useEffect, useMemo, useState } from "react";

import { Panel, type Makerspace, useStaffGet } from "./shared";

type LedgerSource = "request" | "self_checkout" | "direct_handout";

type LedgerRow = {
  source: LedgerSource;
  item_name: string;
  units: Array<{ asset_tag: string; serial_number: string }>;
  container: { label: string } | null;
  target_label: string | null;
  holder: string;
  quantity: number;
  since: string | null;
  due: string | null;
  makerspace_id: number;
  reference_id: number;
  status: string;
};

type LedgerResponse = {
  count: number;
  results: LedgerRow[];
};

type SortKey = "item_name" | "holder" | "quantity" | "since" | "due" | "source" | "makerspace_id";
type SortDirection = "asc" | "desc";

const sourceLabels: Record<LedgerSource, string> = {
  request: "Request",
  self_checkout: "Self-checkout",
  direct_handout: "Direct",
};

// Color-code each loan card by where it came from, reusing the vibrant panel palette.
const sourcePanel: Record<LedgerSource, string> = {
  request: "panel-blue",
  self_checkout: "panel-mint",
  direct_handout: "panel-coral",
};

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "due", label: "Due date" },
  { key: "since", label: "Out since" },
  { key: "item_name", label: "Item" },
  { key: "holder", label: "Holder" },
  { key: "quantity", label: "Quantity" },
  { key: "source", label: "Source" },
];

const LEDGER_PAGE_SIZE = 50;

export function Ledger({ makerspace, isSuperadmin }: { makerspace: Makerspace; isSuperadmin: boolean }) {
  const [allMakerspaces, setAllMakerspaces] = useState(false);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; direction: SortDirection }>({
    key: "due",
    direction: "asc",
  });
  const aggregate = isSuperadmin && allMakerspaces;
  const ledgerPath = aggregate ? "/admin/ledger" : `/admin/makerspace/${makerspace.id}/ledger`;
  const ledger = useStaffGet<LedgerResponse>(
    ["ledger", aggregate ? "all" : makerspace.id, page, LEDGER_PAGE_SIZE],
    `${ledgerPath}?page=${page}&page_size=${LEDGER_PAGE_SIZE}`,
  );

  useEffect(() => {
    setPage(1);
  }, [aggregate, makerspace.id]);

  const rows = ledger.data?.results ?? [];
  const now = Date.now();
  const visibleRows = useMemo(() => {
    const normalizedFilter = filter.trim().toLowerCase();
    const filtered = normalizedFilter
      ? rows.filter((row) =>
          `${row.holder} ${row.item_name} ${row.container?.label ?? ""}`.toLowerCase().includes(normalizedFilter),
        )
      : rows;

    return [...filtered].sort((a, b) => compareRows(a, b, sort.key, sort.direction));
  }, [filter, rows, sort.direction, sort.key]);
  const itemCount = visibleRows.reduce((total, row) => total + row.quantity, 0);
  const totalRows = ledger.data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalRows / LEDGER_PAGE_SIZE));

  return (
    <Panel title="Ledger">
      <div className="grid gap-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-display text-2xl font-semibold text-ink">{itemCount} items out</p>
            <p className="text-sm text-muted">
              {aggregate ? "Across all makerspaces" : makerspace.name}
              {ledger.data ? ` - ${ledger.data.count} records` : ""}
            </p>
          </div>
          {isSuperadmin ? (
            <label className="inline-flex items-center gap-2 text-sm font-medium text-ink">
              <input
                type="checkbox"
                checked={allMakerspaces}
                onChange={(event) => {
                  setAllMakerspaces(event.target.checked);
                  setPage(1);
                }}
              />
              All makerspaces
            </label>
          ) : null}
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <input
            className="desk-input pill sm:flex-1"
            type="search"
            placeholder="Filter by holder or item"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          />
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-semibold uppercase tracking-wide text-muted">Sort</span>
            <select
              className="desk-input pill"
              value={sort.key}
              onChange={(event) => setSort((current) => ({ ...current, key: event.target.value as SortKey }))}
            >
              {SORT_OPTIONS.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="desk-button"
              onClick={() =>
                setSort((current) => ({ ...current, direction: current.direction === "asc" ? "desc" : "asc" }))
              }
            >
              {sort.direction === "asc" ? "Asc ↑" : "Desc ↓"}
            </button>
          </div>
        </div>

        {ledger.isLoading ? <p className="text-sm text-muted">Loading ledger...</p> : null}
        {ledger.error ? <p className="text-sm text-danger">{ledger.error.message}</p> : null}
        {!ledger.isLoading && !ledger.error && !visibleRows.length ? (
          <p className="rounded-2xl border-2 border-ink bg-bg p-4 text-sm text-muted shadow-brutal-sm">
            No items are currently out.
          </p>
        ) : null}

        {visibleRows.length ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {visibleRows.map((row) => (
              <LedgerCard
                key={`${row.source}-${row.reference_id}-${row.makerspace_id}-${row.item_name}`}
                row={row}
                overdue={isOverdue(row.due, now)}
                showMakerspace={aggregate}
              />
            ))}
          </div>
        ) : null}

        {ledger.data && totalRows > LEDGER_PAGE_SIZE ? (
          <div className="flex flex-wrap items-center justify-end gap-2 text-sm text-muted">
            <button className="desk-button" type="button" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>
              Previous
            </button>
            <span>Page {page} of {totalPages}</span>
            <button className="desk-button" type="button" disabled={page >= totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))}>
              Next
            </button>
          </div>
        ) : null}
      </div>
    </Panel>
  );
}

function LedgerCard({ row, overdue, showMakerspace }: { row: LedgerRow; overdue: boolean; showMakerspace: boolean }) {
  return (
    <article
      className={`${sourcePanel[row.source]} brutal-border rounded-lg p-4 shadow-brutal-sm ${
        overdue ? "ring-2 ring-danger ring-offset-2 ring-offset-bg" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-display text-base font-semibold uppercase leading-tight break-words">{row.item_name}</h3>
        <span className="chip shrink-0 normal-case tracking-normal">{sourceLabels[row.source]}</span>
      </div>

      <UnitLines row={row} />

      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        <Field label="Holder" value={row.holder} />
        <Field label="Qty" value={String(row.quantity)} />
        <Field label="Out" value={formatDate(row.since)} />
        <Field label="Due" value={formatDate(row.due)} danger={overdue} />
        {showMakerspace ? <Field label="Space" value={`#${row.makerspace_id}`} /> : null}
      </dl>

      {overdue ? (
        <span className="status-box status-box-danger mt-3 inline-flex px-3 py-1 text-xs normal-case">Overdue</span>
      ) : null}
    </article>
  );
}

function Field({ label, value, danger = false }: { label: string; value: string; danger?: boolean }) {
  return (
    <>
      <dt className="font-mono text-xs font-semibold uppercase tracking-wide opacity-70">{label}</dt>
      <dd className={`break-words ${danger ? "font-semibold text-danger" : ""}`}>{value}</dd>
    </>
  );
}

function UnitLines({ row }: { row: LedgerRow }) {
  const containerLine = row.container ? (
    <div className="mt-1 break-words text-xs opacity-80">{"📦"} {row.container.label}</div>
  ) : null;

  if (row.units.length) {
    return (
      <>
        <div className="mt-1 flex flex-wrap gap-x-2 gap-y-0.5 font-mono text-xs opacity-80">
          {row.units.map((unit) => (
            <span className="break-words" key={`${unit.asset_tag}-${unit.serial_number || "no-serial"}`}>
              #{unit.asset_tag}
              {unit.serial_number ? ` · ${unit.serial_number}` : ""}
            </span>
          ))}
        </div>
        {containerLine}
      </>
    );
  }

  if (row.target_label) {
    return (
      <>
        <div className="mt-1 break-words text-xs opacity-80">{row.target_label}</div>
        {containerLine}
      </>
    );
  }

  return containerLine;
}

function compareRows(a: LedgerRow, b: LedgerRow, key: SortKey, direction: SortDirection) {
  const directionMultiplier = direction === "asc" ? 1 : -1;
  const left = sortableValue(a, key);
  const right = sortableValue(b, key);

  if (typeof left === "number" && typeof right === "number") {
    return (left - right) * directionMultiplier;
  }

  return String(left).localeCompare(String(right)) * directionMultiplier;
}

function sortableValue(row: LedgerRow, key: SortKey) {
  if (key === "since" || key === "due") {
    return row[key] ? new Date(row[key]).getTime() : Number.MAX_SAFE_INTEGER;
  }
  if (key === "source") return sourceLabels[row.source];
  return row[key];
}

function isOverdue(value: string | null, now: number) {
  return Boolean(value && new Date(value).getTime() < now);
}

function formatDate(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}
