import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import { Panel, type Makerspace, useStaffGet } from "./StaffPanels";

type DirectLoan = {
  id: number;
  public_token: string;
  status: string;
  target_label: string;
  due_at: string | null;
  items: { product_name: string; quantity: number }[];
};

export function DirectLoans({ makerspace }: { makerspace: Makerspace }) {
  const queryClient = useQueryClient();
  const [identifier, setIdentifier] = useState("");
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [qrPayloads, setQrPayloads] = useState("");
  const [dueAt, setDueAt] = useState("");
  const loans = useStaffGet<{ results: DirectLoan[] }>(
    ["direct-loans", makerspace.id],
    `/admin/makerspace/${makerspace.id}/direct-loans`,
  );
  const issue = useMutation({
    mutationFn: () =>
      staffRequest(`/admin/makerspace/${makerspace.id}/direct-loans`, {
        method: "POST",
        body: JSON.stringify({
          identifier,
          due_at: dueAt ? new Date(dueAt).toISOString() : null,
          qr_payloads: qrPayloads
            .split("\n")
            .map((value) => value.trim())
            .filter(Boolean),
          items: productId
            ? [{ product_id: Number(productId), quantity: Number(quantity) }]
            : [],
        }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["direct-loans", makerspace.id] }),
  });
  const returnLoan = useMutation({
    mutationFn: (loanId: number) =>
      staffRequest(`/admin/direct-loans/${loanId}/return`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["direct-loans", makerspace.id] }),
  });

  return (
    <div className="grid gap-4">
      <Panel title="Direct handout">
        <div className="grid gap-3 md:grid-cols-2">
          <input className="desk-input" placeholder="Check-In username, email, phone, or ID" value={identifier} onChange={(e) => setIdentifier(e.target.value)} />
          <input className="desk-input" type="datetime-local" value={dueAt} onChange={(e) => setDueAt(e.target.value)} />
          <input className="desk-input" placeholder="Product ID for manual item" value={productId} onChange={(e) => setProductId(e.target.value)} />
          <input className="desk-input" placeholder="Quantity" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
        </div>
        <textarea
          className="desk-input mt-3 h-24 w-full font-mono text-sm"
          placeholder="Optional QR payloads, one per line"
          value={qrPayloads}
          onChange={(e) => setQrPayloads(e.target.value)}
        />
        <button className="desk-button-primary mt-3" onClick={() => issue.mutate()}>
          Issue direct handout
        </button>
        {issue.error ? <p className="mt-3 text-sm text-danger">{issue.error.message}</p> : null}
      </Panel>

      <Panel title="Direct handout loans">
        <div className="grid gap-2">
          {loans.data?.results?.map((loan) => (
            <article key={loan.id} className="rounded-md border border-line bg-surface p-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-ink">{loan.target_label}</h3>
                  <p className="text-xs text-muted">{loan.status}{loan.due_at ? ` · due ${new Date(loan.due_at).toLocaleString()}` : ""}</p>
                </div>
                {loan.status === "checked_out" ? (
                  <button className="desk-button" onClick={() => returnLoan.mutate(loan.id)}>
                    Return
                  </button>
                ) : null}
              </div>
              <p className="mt-2 text-xs text-muted">
                {loan.items.map((item) => `${item.product_name} x${item.quantity}`).join(", ")}
              </p>
            </article>
          ))}
        </div>
      </Panel>
    </div>
  );
}
