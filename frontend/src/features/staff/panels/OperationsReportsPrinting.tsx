import { useState } from "react";

import { BarChart, DataState, PieChart, ReportTable, StatCards } from "./OperationsReportsParts";
import { Panel, type Makerspace, useStaffGet } from "./shared";

export type PrintingReport = {
  totals: Record<string, number>;
  payments: {
    paid_amount: string;
    paid_count: number;
    outstanding_amount: string;
    outstanding_count: number;
  };
  printer_hours: {
    printer_id: number;
    printer_name: string;
    printer_model?: string;
    completed_requests: number;
    hours: number;
    makerspace_id?: number;
  }[];
  printer_outcomes: {
    printer_id: number;
    printer_name: string;
    printer_model?: string;
    completed: number;
    failed: number;
    grams_used: number;
    makerspace_id?: number;
  }[];
  filament_used: {
    spool_id: number;
    material: string;
    color: string;
    grams_used: number;
    remaining_grams: number;
    makerspace_id?: number;
  }[];
  filament_by_brand: { brand: string; grams_used: number; spools: number }[];
  top_requesters: {
    requester_id: number;
    requester: string;
    grams: number;
    requests: number;
    items: number;
    makerspace_id?: number;
  }[];
  total_grams_used: number;
  filament_estimated_by_period: {
    by_month: { period: string; grams: number }[];
    by_day: { period: string; grams: number }[];
    by_hour: { period: string; grams: number }[];
  };
};

type PeriodKey = "month" | "day" | "hour";

const periods: { key: PeriodKey; label: string; dataKey: keyof PrintingReport["filament_estimated_by_period"] }[] = [
  { key: "month", label: "Month", dataKey: "by_month" },
  { key: "day", label: "Day", dataKey: "by_day" },
  { key: "hour", label: "Hour", dataKey: "by_hour" },
];

// Print-status pie slices, in a stable display order.
const statusPie: { key: keyof PrintingReport["totals"]; label: string }[] = [
  { key: "completed", label: "Completed" },
  { key: "collected", label: "Collected" },
  { key: "printing", label: "Printing" },
  { key: "pending", label: "Pending" },
  { key: "accepted", label: "Accepted" },
  { key: "failed", label: "Failed" },
  { key: "rejected", label: "Rejected" },
];

function printerDisplayName(row: { printer_name: string; printer_model?: string }) {
  return row.printer_model ? `${row.printer_name} (${row.printer_model})` : row.printer_name;
}

export function PrintingReportSection({ makerspace, aggregate, rangeParam = "" }: { makerspace: Makerspace; aggregate: boolean; rangeParam?: string }) {
  const [period, setPeriod] = useState<PeriodKey>("month");
  const scopeKey = aggregate ? "all" : makerspace.id;
  // printing routes are mounted under /api/v1/printing/ (not /api/v1/admin/).
  const printingBase = aggregate
    ? "/printing/admin/printing/reports"
    : `/printing/admin/makerspace/${makerspace.id}/printing/reports`;
  const printingPath = rangeParam ? `${printingBase}?${rangeParam}` : printingBase;
  const printing = useStaffGet<PrintingReport>(["operations-report", "printing", scopeKey, rangeParam], printingPath);

  const activePeriod = periods.find((item) => item.key === period) ?? periods[0];
  const filamentRows = printing.data?.filament_estimated_by_period[activePeriod.dataKey] ?? [];
  const statusRows = statusPie
    .map((item) => ({ label: item.label, value: printing.data?.totals[item.key] ?? 0 }))
    .filter((row) => row.value > 0);
  const brandRows = (printing.data?.filament_by_brand ?? [])
    .slice(0, 8)
    .map((row) => ({ label: row.brand, value: row.grams_used }));

  return (
    <Panel title="3D printing">
      <DataState loading={printing.isLoading} error={printing.error} empty={!printing.data}>
        <div className="space-y-5">
          <StatCards
            stats={[
              ["Total requests", printing.data?.totals.total_requests],
              ["Completed", printing.data?.totals.completed],
              ["Collected", printing.data?.totals.collected],
              ["Printing", printing.data?.totals.printing],
              ["Pending", printing.data?.totals.pending],
              ["Accepted", printing.data?.totals.accepted],
              ["Failed", printing.data?.totals.failed],
              ["Rejected", printing.data?.totals.rejected],
              ["Spool grams used", printing.data?.total_grams_used],
            ]}
          />

          <div>
            <h3 className="mb-2 text-sm font-semibold text-ink">Payments</h3>
            <StatCards
              stats={[
                [`Collected (${printing.data?.payments.paid_count ?? 0})`, printing.data?.payments.paid_amount ?? "0"],
                [`Outstanding (${printing.data?.payments.outstanding_count ?? 0})`, printing.data?.payments.outstanding_amount ?? "0"],
              ]}
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <div className="rounded-2xl border border-ink bg-bg p-3">
              <h3 className="mb-3 text-sm font-semibold text-ink">Requests by status</h3>
              <PieChart rows={statusRows} valueLabel="" />
            </div>
            <div className="rounded-2xl border border-ink bg-bg p-3">
              <h3 className="mb-3 text-sm font-semibold text-ink">Filament share by brand</h3>
              <PieChart rows={brandRows} valueLabel="g" />
            </div>
          </div>

          <div>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-ink">Estimated filament</h3>
              <div className="flex rounded-full border border-ink bg-bg p-1">
                {periods.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    className={`rounded-full px-3 py-1 text-xs font-semibold ${period === item.key ? "bg-accent text-on-accent" : "text-muted"}`}
                    onClick={() => setPeriod(item.key)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
            <BarChart rows={filamentRows.map((row) => ({ label: row.period, value: row.grams }))} valueLabel="g" />
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <div>
              <h3 className="mb-2 text-sm font-semibold text-ink">Printer hours</h3>
              <ReportTable
                data={{
                  rows: [
                    aggregate
                      ? ["makerspace_id", "printer", "completed_requests", "hours"]
                      : ["printer", "completed_requests", "hours"],
                    ...(printing.data?.printer_hours ?? []).map((row) =>
                      aggregate
                        ? [row.makerspace_id ?? "", printerDisplayName(row), row.completed_requests, row.hours]
                        : [printerDisplayName(row), row.completed_requests, row.hours],
                    ),
                  ],
                }}
              />
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold text-ink">Printer outcomes (success / fail / grams)</h3>
              <ReportTable
                data={{
                  rows: [
                    aggregate
                      ? ["makerspace_id", "printer", "completed", "failed", "grams_used"]
                      : ["printer", "completed", "failed", "grams_used"],
                    ...(printing.data?.printer_outcomes ?? []).map((row) =>
                      aggregate
                        ? [row.makerspace_id ?? "", printerDisplayName(row), row.completed, row.failed, row.grams_used]
                        : [printerDisplayName(row), row.completed, row.failed, row.grams_used],
                    ),
                  ],
                }}
              />
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold text-ink">Filament used</h3>
              <ReportTable
                data={{
                  rows: [
                    aggregate
                      ? ["makerspace_id", "material", "color", "grams_used", "remaining_grams"]
                      : ["material", "color", "grams_used", "remaining_grams"],
                    ...(printing.data?.filament_used ?? []).map((row) =>
                      aggregate
                        ? [row.makerspace_id ?? "", row.material, row.color, row.grams_used, row.remaining_grams]
                        : [row.material, row.color, row.grams_used, row.remaining_grams],
                    ),
                  ],
                }}
              />
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold text-ink">Filament by brand</h3>
              <BarChart
                rows={(printing.data?.filament_by_brand ?? []).slice(0, 8).map((row) => ({ label: row.brand, value: row.grams_used }))}
                valueLabel="g"
              />
              <ReportTable
                data={{
                  rows: [
                    ["brand", "grams_used", "spools"],
                    ...(printing.data?.filament_by_brand ?? []).map((row) => [row.brand, row.grams_used, row.spools]),
                  ],
                }}
              />
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold text-ink">Top requesters (by filament)</h3>
              {aggregate ? (
                // The aggregate list is ordered per makerspace, so a single top-8 bar chart
                // would only show the first makerspace. The per-makerspace table below is
                // the source of truth in aggregate mode.
                <p className="mb-2 text-xs text-muted">Per-makerspace ranking shown in the table below.</p>
              ) : (
                <BarChart
                  rows={(printing.data?.top_requesters ?? []).slice(0, 8).map((row) => ({ label: row.requester, value: row.grams }))}
                  valueLabel="g"
                />
              )}
              <ReportTable
                data={{
                  rows: [
                    aggregate
                      ? ["makerspace_id", "requester", "grams", "requests", "items"]
                      : ["requester", "grams", "requests", "items"],
                    ...(printing.data?.top_requesters ?? []).map((row) =>
                      aggregate
                        ? [row.makerspace_id ?? "", row.requester, row.grams, row.requests, row.items]
                        : [row.requester, row.grams, row.requests, row.items],
                    ),
                  ],
                }}
              />
            </div>
          </div>
        </div>
      </DataState>
    </Panel>
  );
}
