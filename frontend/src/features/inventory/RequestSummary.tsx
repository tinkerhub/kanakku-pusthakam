import type { PublicRequestStatus } from "../../types/inventory";

function formatStatus(status: string): string {
  return status.replace(/_/g, " ").toLowerCase();
}

export function RequestSummary({ request }: { request: PublicRequestStatus }) {
  return (
    <div className="rounded-md border border-line bg-surface p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted">Status</p>
          <p className="mt-1 text-base font-semibold capitalize text-ink">
            {formatStatus(request.status)}
          </p>
        </div>
      </div>
      {request.rejection_reason ? (
        <p className="mt-2 text-sm text-danger">{request.rejection_reason}</p>
      ) : null}
      {request.requested_for ? (
        <p className="mt-2 line-clamp-2 text-sm text-muted">
          {request.requested_for}
        </p>
      ) : null}
      <div className="mt-3 space-y-1">
        {request.items.map((item) => (
          <div
            className="flex justify-between gap-3 text-sm text-muted"
            key={`${request.public_token ?? request.created_at}-${item.product_name}`}
          >
            <span>{item.product_name}</span>
            <span>x{item.requested_quantity}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
