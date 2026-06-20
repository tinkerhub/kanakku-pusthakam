import { PANEL_CLASS, SHADOW_CLASS, cyclePalette } from "../../../lib/palette";
import { type Makerspace, useStaffGet } from "./shared";

type ListResponse<T> = {
  count?: number;
  results: T[];
};

type LedgerRow = {
  quantity: number;
};

type Summary = {
  products: number;
  assets: number;
  active_loans: number;
  available_quantity: number;
  issued_quantity: number;
  damaged_quantity: number;
  missing_quantity: number;
};

type ShelfItem = {
  needs_fix_quantity: number;
};

type AuditLogEntry = {
  id: number;
  actor: number | null;
  action: string;
  target_type: string;
  target_id: string | number | null;
  created_at: string;
};

type StatTileModel = {
  label: string;
  value: number;
  detail: string;
  loading: boolean;
  error: Error | null;
};

export function CommandCenter({
  makerspace,
  canReviewHardware,
  canSeePrinting,
  canViewAudit,
  canViewInventory,
  canViewLedger,
  canViewNeedsFix,
}: {
  makerspace: Makerspace;
  canReviewHardware: boolean;
  canSeePrinting: boolean;
  canViewAudit: boolean;
  canViewInventory: boolean;
  canViewLedger: boolean;
  canViewNeedsFix: boolean;
}) {
  const ledger = useStaffGet<ListResponse<LedgerRow>>(
    ["command-center", "ledger", makerspace.id],
    `/admin/makerspace/${makerspace.id}/ledger`,
    canViewLedger,
  );
  const pendingHardware = useStaffGet<ListResponse<unknown>>(
    ["command-center", "pending-hardware", makerspace.id],
    `/admin/makerspace/${makerspace.id}/pending-requests`,
    canReviewHardware,
  );
  const pendingPrints = useStaffGet<ListResponse<unknown>>(
    ["command-center", "pending-prints", makerspace.id],
    `/printing/manage/requests/?makerspace=${makerspace.id}&status=pending`,
    canSeePrinting,
  );
  const summary = useStaffGet<Summary>(
    ["command-center", "summary", makerspace.id],
    `/admin/makerspace/${makerspace.id}/analytics/summary`,
    canViewInventory,
  );
  const needsFix = useStaffGet<ListResponse<ShelfItem>>(
    ["command-center", "needs-fix", makerspace.id],
    `/admin/inventory/needs-fix?makerspace=${makerspace.id}`,
    canViewNeedsFix,
  );
  const audit = useStaffGet<ListResponse<AuditLogEntry>>(
    ["command-center", "audit", makerspace.id],
    `/admin/audit-logs?makerspace=${makerspace.id}`,
    canViewAudit,
  );

  const activeLoanRecords = ledger.data?.count ?? ledger.data?.results.length ?? 0;
  const activeLoanItems =
    ledger.data?.results.reduce((total, row) => total + row.quantity, 0) ?? 0;
  const needsFixUnits =
    needsFix.data?.results.reduce((total, row) => total + row.needs_fix_quantity, 0) ?? 0;
  const activity = audit.data?.results.slice(0, 6) ?? [];

  const tiles: StatTileModel[] = [
    canViewLedger
      ? {
          label: "Active loans",
          value: activeLoanRecords,
          detail: `${activeLoanItems} item${activeLoanItems === 1 ? "" : "s"} out`,
          loading: ledger.isLoading,
          error: ledger.error,
        }
      : null,
    canReviewHardware
      ? {
          label: "Pending hardware requests",
          value: listCount(pendingHardware.data),
          detail: "Awaiting review",
          loading: pendingHardware.isLoading,
          error: pendingHardware.error,
        }
      : null,
    canSeePrinting
      ? {
          label: "Pending prints",
          value: listCount(pendingPrints.data),
          detail: "Awaiting print review",
          loading: pendingPrints.isLoading,
          error: pendingPrints.error,
        }
      : null,
    canViewInventory
      ? {
          label: "Items in inventory",
          value: summary.data?.products ?? 0,
          detail: `${summary.data?.available_quantity ?? 0} available units`,
          loading: summary.isLoading,
          error: summary.error,
        }
      : null,
    canViewNeedsFix
      ? {
          label: "To-be-fixed",
          value: listCount(needsFix.data),
          detail: `${needsFixUnits} unit${needsFixUnits === 1 ? "" : "s"} on shelf`,
          loading: needsFix.isLoading,
          error: needsFix.error,
        }
      : null,
  ].filter((tile): tile is StatTileModel => tile !== null);

  return (
    <div className="space-y-5">
      <section className="desk-panel overflow-hidden">
        <div className="border-b border-line px-4 py-4">
          <p className="font-mono text-xs font-semibold uppercase text-accent">
            {makerspace.public_code ?? makerspace.slug}
          </p>
          <h2 className="mt-1 font-display text-3xl font-bold uppercase text-ink">
            Command Center
          </h2>
        </div>
        <div className="desk-panel-body p-4">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {tiles.map((tile, index) => (
              <StatTile
                key={tile.label}
                index={index}
                label={tile.label}
                value={tile.value}
                detail={tile.detail}
                loading={tile.loading}
                error={tile.error}
              />
            ))}
          </div>
        </div>
      </section>

      {canViewAudit ? (
        <section className="desk-panel overflow-hidden">
          <div className="border-b border-line px-4 py-3">
            <h2 className="font-display text-lg font-bold uppercase text-ink">
              Live Activity
            </h2>
          </div>
          <div className="desk-panel-body p-4">
            {audit.isLoading ? <p className="text-sm text-muted">Loading activity...</p> : null}
            {audit.error ? <p className="text-sm text-danger">{audit.error.message}</p> : null}
            {!audit.isLoading && !audit.error && !activity.length ? (
              <p className="rounded-md border border-line bg-surface p-3 text-sm text-muted">
                No recent activity for this makerspace.
              </p>
            ) : null}
            <div className="grid gap-2">
              {activity.map((entry) => (
                <article
                  key={entry.id}
                  className="rounded-lg border border-line bg-surface px-3 py-2 text-sm"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold text-ink">{humanize(entry.action)}</span>
                    <time className="font-mono text-xs uppercase text-muted">
                      {formatLocalDateTime(entry.created_at)}
                    </time>
                  </div>
                  <p className="mt-1 break-words text-xs text-muted">
                    {entry.target_type}:{entry.target_id ?? "-"}
                    {entry.actor ? ` by staff #${entry.actor}` : ""}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function StatTile({
  index,
  label,
  value,
  detail,
  loading,
  error,
}: {
  index: number;
  label: string;
  value: number;
  detail: string;
  loading: boolean;
  error: Error | null;
}) {
  const palette = cyclePalette(index);
  return (
    <article
      className={`${PANEL_CLASS[palette]} ${SHADOW_CLASS[palette]} min-h-36 rounded-2xl border border-ink p-4 transition-transform hover:-translate-y-0.5 hover:scale-[1.02]`}
    >
      <p className="font-mono text-xs font-semibold uppercase">{label}</p>
      <p className="mt-3 font-display text-5xl font-bold leading-none">
        {loading ? "..." : value}
      </p>
      <p className="mt-2 text-sm font-semibold">{detail}</p>
      {error ? <p className="mt-3 text-xs font-semibold text-danger">{error.message}</p> : null}
    </article>
  );
}

function listCount<T>(data?: ListResponse<T>) {
  return data?.count ?? data?.results.length ?? 0;
}

function humanize(value: string) {
  return value.replace(/[._-]/g, " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

function formatLocalDateTime(value: string) {
  return new Date(value).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
