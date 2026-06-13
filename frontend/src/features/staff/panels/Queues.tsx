import type React from "react";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";
import { Panel, type Makerspace, useStaffGet } from "./shared";

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
  return_due_at: string | null;
  return_reminder_sent_at: string | null;
  items: RequestItem[];
  assigned_box?: { code: string; label: string };
};

export function Queues({ makerspace, guestOnly }: { makerspace: Makerspace; guestOnly: boolean }) {
  const queryClient = useQueryClient();
  const policy = useStaffGet<{ id: number; default_loan_days: number }>(
    ["return-policy", makerspace.id],
    `/admin/makerspace/${makerspace.id}/return-policy`,
    !guestOnly,
  );
  const [defaultLoanDays, setDefaultLoanDays] = useState("7");
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
  const savePolicy = useMutation({
    mutationFn: () =>
      staffRequest(`/admin/makerspace/${makerspace.id}/return-policy`, {
        method: "PATCH",
        body: JSON.stringify({ default_loan_days: Number(defaultLoanDays) || 7 }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["return-policy", makerspace.id] }),
  });
  useEffect(() => {
    if (policy.data) {
      setDefaultLoanDays(String(policy.data.default_loan_days));
    }
  }, [policy.data]);
  const setDue = (row: HardwareRequest) => {
    const value = prompt(
      "Return due date/time",
      row.return_due_at ? localDateTimeValue(row.return_due_at) : localDateTimeValue(defaultDueDate(Number(defaultLoanDays) || 7).toISOString()),
    );
    if (value === null) return;
    action.mutate({
      path: `/admin/requests/${row.id}/return-due`,
      body: { return_due_at: value ? new Date(value).toISOString() : null },
    });
  };
  return (
    <div className="grid gap-4">
      {!guestOnly ? (
        <Panel title="Return policy">
          <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
            <input
              className="desk-input"
              type="number"
              min="1"
              value={defaultLoanDays}
              onChange={(event) => setDefaultLoanDays(event.target.value)}
            />
            <button disabled={savePolicy.isPending} onClick={() => savePolicy.mutate()}>
              Save default days
            </button>
          </div>
          <p className="mt-2 text-sm text-muted">
            Default return time is used when a request is issued. Current default: {policy.data?.default_loan_days ?? 7} days.
          </p>
        </Panel>
      ) : null}
      {!guestOnly ? (
        <Panel title="Pending review">
          <RequestList
            rows={pending.data?.results ?? []}
            actions={(row) => (
              <>
                <button onClick={() => action.mutate({ path: `/admin/requests/${row.id}/accept` })}>Accept</button>
                <button onClick={() => action.mutate({ path: `/admin/requests/${row.id}/reject`, body: { reason: "Rejected in admin app." } })}>Reject</button>
                <button onClick={() => setDue(row)}>Set due</button>
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
              <button onClick={() => setDue(row)}>Set due</button>
            </>
          )}
        />
      </Panel>
      {!guestOnly ? (
        <Panel title="Active loans">
          <RequestList
            rows={active.data?.results ?? []}
            actions={(row) => (
              <>
                <button onClick={() => setDue(row)}>Set due</button>
                <button onClick={() => action.mutate({ path: `/admin/requests/${row.id}/return`, body: returnPayload(row) })}>Return</button>
              </>
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
          <p className="mt-1 text-xs text-muted">
            {row.return_due_at ? `Due ${new Date(row.return_due_at).toLocaleString()}` : "No return due time set"}
            {row.return_reminder_sent_at ? ` · reminder sent ${new Date(row.return_reminder_sent_at).toLocaleString()}` : ""}
          </p>
          <p className="mt-2 text-xs text-ink/60">
            {row.items.map((item) => `${item.product_name} x${item.requested_quantity}`).join(", ")}
          </p>
        </article>
      ))}
    </div>
  );
}

function defaultDueDate(days: number) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date;
}

function localDateTimeValue(value: string) {
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}
