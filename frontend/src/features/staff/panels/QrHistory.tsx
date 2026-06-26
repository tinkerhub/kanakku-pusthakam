import { useState } from "react";

import { useStaffGet } from "./shared";

type QrHistoryTarget =
  | { productId: number; assetId?: never }
  | { productId?: never; assetId: number };

type QrHistoryEntry = {
  id: string;
  source: string;
  context: string;
  actor: number | null;
  created_at: string;
};

type QrHistoryResponse = {
  product?: number;
  asset?: number;
  scans: QrHistoryEntry[];
};

export function QrHistory({
  title,
  productId,
  assetId,
  className = "grid w-full gap-2 border-t border-line pt-3",
}: QrHistoryTarget & { title?: string; className?: string }) {
  const [open, setOpen] = useState(false);
  const isAsset = assetId !== undefined;
  const targetId = isAsset ? assetId : productId;
  const path = isAsset ? `/admin/assets/${targetId}/qr-history` : `/admin/inventory/${targetId}/qr-history`;
  const history = useStaffGet<QrHistoryResponse>(
    [isAsset ? "asset-qr-history" : "product-qr-history", targetId],
    path,
    open,
  );
  const rows = history.data?.scans ?? [];

  return (
    <div className={className}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">{title ?? (isAsset ? "Asset QR history" : "Product QR history")}</h3>
        <button className="desk-button" type="button" onClick={() => setOpen((value) => !value)}>
          {open ? "Hide" : "History"}
        </button>
      </div>
      {open && history.isLoading ? <p className="text-sm text-muted">Loading QR history...</p> : null}
      {open && history.error ? <p className="text-sm text-danger">{history.error.message}</p> : null}
      {open && !history.isLoading && !history.error && !rows.length ? <p className="text-sm text-muted">No QR scans recorded.</p> : null}
      {open && rows.length ? (
        <div className="overflow-x-auto">
          <table className="min-w-[520px] text-left text-xs">
            <thead className="text-muted">
              <tr>
                <th className="py-1 pr-3">Context</th>
                <th className="py-1 pr-3">Source</th>
                <th className="py-1 pr-3">Actor</th>
                <th className="py-1">Scanned</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((scan) => (
                <tr key={scan.id} className="border-t border-line">
                  <td className="py-1 pr-3 text-ink">{humanize(scan.context || "scan")}</td>
                  <td className="py-1 pr-3 text-muted">{humanize(scan.source || "qr_scan")}</td>
                  <td className="py-1 pr-3 text-muted">{scan.actor ? `User #${scan.actor}` : "System"}</td>
                  <td className="py-1 text-muted">{formatDate(scan.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function humanize(value: string) {
  return value.replace(/_/g, " ").replace(/^\w/, (match) => match.toUpperCase());
}

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
