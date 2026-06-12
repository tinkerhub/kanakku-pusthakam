import { useState } from "react";
import type React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";

export type Makerspace = {
  id: number;
  name: string;
  public_code: string;
  slug: string;
  telegram_group_chat_id: string;
};
type Product = {
  id: number;
  name: string;
  total_quantity: number;
  available_quantity: number;
  issued_quantity: number;
  damaged_quantity: number;
  lost_quantity: number;
  public_self_checkout_enabled: boolean;
};
type RequestItem = {
  id: number;
  product_id: number;
  product_name: string;
  requested_quantity: number;
  issued_quantity: number;
  returned_quantity: number;
  damaged_quantity: number;
  missing_quantity: number;
};
type HardwareRequest = {
  id: number;
  status: string;
  requester_username: string;
  requested_for: string;
  items: RequestItem[];
  assigned_box?: { code: string; label: string };
};

export function useStaffGet<T>(key: unknown[], path: string, enabled = true) {
  return useQuery({
    queryKey: key,
    queryFn: () => staffRequest<T>(path),
    enabled,
  });
}

export function Queues({ makerspace, guestOnly }: { makerspace: Makerspace; guestOnly: boolean }) {
  const queryClient = useQueryClient();
  const pending = useStaffGet<{ results: HardwareRequest[] }>(
    ["pending", makerspace.id],
    `/admin/makerspace/${makerspace.id}/pending-requests`,
    !guestOnly,
  );
  const accepted = useStaffGet<{ results: HardwareRequest[] }>(
    ["accepted", makerspace.id],
    `/admin/makerspace/${makerspace.id}/accepted-requests`,
  );
  const active = useStaffGet<{ results: HardwareRequest[] }>(
    ["active", makerspace.id],
    `/admin/makerspace/${makerspace.id}/active-loans`,
  );
  const action = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: object }) =>
      staffRequest(path, { method: "POST", body: JSON.stringify(body ?? {}) }),
    onSuccess: () => queryClient.invalidateQueries(),
  });
  return (
    <div className="grid gap-4">
      {!guestOnly ? (
        <Panel title="Pending review">
          <RequestList
            rows={pending.data?.results ?? []}
            actions={(row) => (
              <>
                <button onClick={() => action.mutate({ path: `/admin/requests/${row.id}/accept` })}>Accept</button>
                <button onClick={() => action.mutate({ path: `/admin/requests/${row.id}/reject`, body: { reason: "Rejected in admin app." } })}>Reject</button>
              </>
            )}
          />
        </Panel>
      ) : null}
      <Panel title="Handover queue">
        <RequestList
          rows={accepted.data?.results ?? []}
          actions={(row) => (
            <>
              <button onClick={() => action.mutate({ path: `/admin/requests/${row.id}/assign-box`, body: { box_code: prompt("Box QR code") ?? "" } })}>Assign box</button>
              <button onClick={() => action.mutate({ path: `/admin/requests/${row.id}/issue`, body: { evidence_id: Number(prompt("Issue evidence id")), remark: "Issued from staff app." } })}>Issue</button>
            </>
          )}
        />
      </Panel>
      {!guestOnly ? (
        <Panel title="Active loans">
          <RequestList
            rows={active.data?.results ?? []}
            actions={(row) => (
              <button onClick={() => action.mutate({ path: `/admin/requests/${row.id}/return`, body: returnPayload(row) })}>Return</button>
            )}
          />
        </Panel>
      ) : null}
    </div>
  );
}

function returnPayload(row: HardwareRequest) {
  return {
    evidence_id: Number(prompt("Return evidence id")),
    box_code: prompt("Returned box QR code") ?? row.assigned_box?.code ?? "",
    remark: prompt("Return remark") ?? "",
    resolutions: row.items.map((item) => ({
      item_id: item.id,
      returned: item.issued_quantity - item.returned_quantity - item.damaged_quantity - item.missing_quantity,
      damaged: 0,
      missing: 0,
    })),
  };
}

function RequestList({ rows, actions }: { rows: HardwareRequest[]; actions: (row: HardwareRequest) => React.ReactNode }) {
  if (!rows.length) return <p className="text-sm text-ink/60">No requests.</p>;
  return (
    <div className="overflow-hidden rounded-md border border-line">
      {rows.map((row) => (
        <article key={row.id} className="border-b border-line bg-surface/50 p-3 last:border-b-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold text-ink">#{row.id} {row.requester_username}</h3>
            <span className="rounded-md border border-line bg-bg px-2 py-0.5 text-xs text-muted">{row.status}</span>
            <div className="desk-actions ml-auto flex flex-wrap gap-2 text-sm">
              {actions(row)}
            </div>
          </div>
          <p className="mt-2 text-sm text-muted">{row.requested_for || "No note"}</p>
          <p className="mt-2 text-xs text-ink/60">
            {row.items.map((item) => `${item.product_name} x${item.requested_quantity}`).join(", ")}
          </p>
        </article>
      ))}
    </div>
  );
}

export function Inventory({ makerspace }: { makerspace: Makerspace }) {
  const queryClient = useQueryClient();
  const products = useStaffGet<{ results: Product[] }>(
    ["inventory", makerspace.id],
    `/admin/makerspace/${makerspace.id}/inventory`,
  );
  const toggle = useMutation({
    mutationFn: (product: Product) =>
      staffRequest(`/admin/inventory/${product.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          public_self_checkout_enabled: !product.public_self_checkout_enabled,
        }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["inventory", makerspace.id] }),
  });
  return (
    <Panel title="Inventory">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="bg-surface text-xs uppercase tracking-wide text-muted"><tr className="border-b border-line"><th className="px-3 py-2">Name</th><th>Total</th><th>Available</th><th>Issued</th><th>Damaged</th><th>Lost</th><th>Public QR</th></tr></thead>
          <tbody>
            {products.data?.results?.map((product) => (
              <tr key={product.id} className="border-b border-line last:border-b-0">
                <td className="px-3 py-2 font-medium text-ink">{product.name}</td>
                <td>{product.total_quantity}</td>
                <td>{product.available_quantity}</td>
                <td>{product.issued_quantity}</td>
                <td>{product.damaged_quantity}</td>
                <td>{product.lost_quantity}</td>
                <td>
                  <button onClick={() => toggle.mutate(product)}>
                    {product.public_self_checkout_enabled ? "Allowed" : "Off"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

export function BulkImport({ makerspace }: { makerspace: Makerspace }) {
  const [text, setText] = useState('[{"name":"New Kit","total_quantity":"1","available_quantity":"1"}]');
  const mutation = useMutation({
    mutationFn: (apply: boolean) =>
      staffRequest(`/admin/makerspace/${makerspace.id}/inventory/import/${apply ? "apply" : "preview"}`, {
        method: "POST",
        body: JSON.stringify({ rows: JSON.parse(text) }),
      }),
  });
  return (
    <Panel title="Bulk import">
      <textarea className="desk-input h-40 w-full font-mono text-sm" value={text} onChange={(e) => setText(e.target.value)} />
      <div className="mt-3 flex gap-2">
        <button onClick={() => mutation.mutate(false)}>Preview</button>
        <button onClick={() => mutation.mutate(true)}>Apply</button>
      </div>
      {mutation.data ? <pre className="mt-3 max-h-80 overflow-auto rounded-md border border-line bg-bg p-3 text-xs text-muted">{JSON.stringify(mutation.data, null, 2)}</pre> : null}
    </Panel>
  );
}

export function QrTools({ makerspace }: { makerspace: Makerspace }) {
  const mutation = useMutation({
    mutationFn: () =>
      staffRequest("/admin/qr/boxes", {
        method: "POST",
        body: JSON.stringify({ makerspace_id: makerspace.id, label: prompt("Box label") ?? "" }),
      }),
  });
  return (
    <Panel title="QR tools">
      <button onClick={() => mutation.mutate()}>Create box QR</button>
      {mutation.data ? <pre className="mt-3 rounded-md border border-line bg-bg p-3 text-xs text-muted">{JSON.stringify(mutation.data, null, 2)}</pre> : null}
    </Panel>
  );
}

export function Users() {
  const spaceManagers = useStaffGet<{ results: unknown[] }>(
    ["space-managers"],
    "/admin/users/space-managers",
  );
  const inventoryManagers = useStaffGet<{ results: unknown[] }>(
    ["inventory-managers"],
    "/admin/users/inventory-managers",
  );
  const guests = useStaffGet<{ results: unknown[] }>(["guests"], "/admin/users/guest-admins");
  const printManagers = useStaffGet<{ results: unknown[] }>(
    ["print-managers"],
    "/admin/users/print-managers",
  );
  return (
    <Panel title="Users">
      <div className="grid gap-3 sm:grid-cols-4">
        <div className="rounded-md border border-line bg-surface p-3">
          <p className="text-2xl font-bold text-ink">{spaceManagers.data?.results?.length ?? 0}</p>
          <p className="text-xs text-muted">Space managers</p>
        </div>
        <div className="rounded-md border border-line bg-surface p-3">
          <p className="text-2xl font-bold text-ink">{inventoryManagers.data?.results?.length ?? 0}</p>
          <p className="text-xs text-muted">Inventory managers</p>
        </div>
        <div className="rounded-md border border-line bg-surface p-3">
          <p className="text-2xl font-bold text-ink">{guests.data?.results?.length ?? 0}</p>
          <p className="text-xs text-muted">Guest admins</p>
        </div>
        <div className="rounded-md border border-line bg-surface p-3">
          <p className="text-2xl font-bold text-ink">{printManagers.data?.results?.length ?? 0}</p>
          <p className="text-xs text-muted">Print managers</p>
        </div>
      </div>
    </Panel>
  );
}

export function AuditLog() {
  const [targetType, setTargetType] = useState("");
  const [targetId, setTargetId] = useState("");
  const params = new URLSearchParams();
  if (targetType) params.set("target_type", targetType);
  if (targetId) params.set("target_id", targetId);
  const query = params.toString();
  const logs = useStaffGet<{ results: { id: number; action: string; target_type: string; target_id: string; created_at: string }[] }>(
    ["audit", query],
    `/admin/audit-logs${query ? `?${query}` : ""}`,
  );
  return (
    <Panel title="Audit logs">
      <div className="mb-3 grid gap-2 sm:grid-cols-2">
        <input className="desk-input" placeholder="target type, e.g. inventory.inventoryproduct" value={targetType} onChange={(e) => setTargetType(e.target.value)} />
        <input className="desk-input" placeholder="target id" value={targetId} onChange={(e) => setTargetId(e.target.value)} />
      </div>
      <div className="grid gap-2 text-sm">
        {logs.data?.results?.map((log) => (
          <div key={log.id} className="rounded-md border border-line bg-surface p-2">
            <span className="font-semibold">{log.action}</span>
            <span className="ml-2 text-muted">{log.target_type}:{log.target_id}</span>
            <span className="ml-2 text-muted">{new Date(log.created_at).toLocaleString()}</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

export function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="desk-panel overflow-hidden">
      <div className="border-b border-line px-4 py-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">{title}</h2>
      </div>
      <div className="desk-panel-body p-4">
        {children}
      </div>
    </section>
  );
}
