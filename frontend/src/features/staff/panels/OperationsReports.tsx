import { downloadStaffFile } from "../../../lib/api";
import { Panel, type Makerspace, useStaffGet } from "./shared";

export function OperationsReports({ makerspace }: { makerspace: Makerspace }) {
  const summary = useStaffGet<Record<string, number>>(["analytics", makerspace.id], `/admin/makerspace/${makerspace.id}/analytics/summary`);
  const reports = ["taken-items", "active-loans", "returns", "damaged-missing"];
  return (
    <Panel title="Reports">
      <div className="grid gap-3 sm:grid-cols-4">
        {Object.entries(summary.data ?? {}).map(([key, value]) => (
          <div key={key} className="rounded-md border border-line bg-surface p-3">
            <p className="text-2xl font-bold text-ink">{value}</p>
            <p className="text-xs text-muted">{key.replace(/_/g, " ")}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {reports.map((report) => (
          <button
            key={report}
            className="desk-button"
            onClick={() => downloadStaffFile(`/admin/makerspace/${makerspace.id}/reports/${report}/export?format=csv`, `${report}.csv`)}
          >
            {report} CSV
          </button>
        ))}
      </div>
    </Panel>
  );
}
