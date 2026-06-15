import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import QrScanner from "../../../components/ui/QrScanner";
import { staffRequest } from "../../../lib/api";
import { Panel, type Makerspace } from "./shared";

type ResolveTarget =
  | { type: "product"; id: number; name: string }
  | { type: "asset"; id: number; asset_tag: string; product: string; status: string }
  | { type: "box"; id: number; label: string; code: string };
type Resolved = { qr: { id: number; payload: string; status: string }; target: ResolveTarget; allowed_actions: string[] };
type BoxContents = {
  products: { id: number; name: string; available_quantity: number }[];
  assets: { id: number; asset_tag: string; product: string; status: string }[];
};

// The staff scanner page existed as an orphan route with dead action badges. This wires
// the staff-reachable allowed_actions the backend returns: revoke (MANAGE_QR) and box
// contents. checkout/return/direct_handout need a borrower identifier, so we point staff
// to the Direct handout / self-checkout flows instead of faking them here.
export function ScannerPanel(_props: { makerspace: Makerspace }) {
  const [payload, setPayload] = useState("");
  const [showScanner, setShowScanner] = useState(false);
  const [resolved, setResolved] = useState<Resolved | null>(null);
  const [contents, setContents] = useState<BoxContents | null>(null);

  const resolve = useMutation({
    mutationFn: (value: string) =>
      staffRequest<Resolved>("/admin/qr/resolve", { method: "POST", body: JSON.stringify({ payload: value.trim() }) }),
    onSuccess: (data) => {
      setResolved(data);
      setContents(null);
    },
  });
  const revoke = useMutation({
    mutationFn: (qrId: number) => staffRequest(`/admin/qr/${qrId}/revoke`, { method: "POST", body: JSON.stringify({}) }),
    onSuccess: () => resolved && resolve.mutate(resolved.qr.payload),
  });
  const loadContents = useMutation({
    mutationFn: (boxId: number) => staffRequest<BoxContents>(`/admin/containers/${boxId}/contents`),
    onSuccess: setContents,
  });

  const doResolve = (value: string) => {
    if (value.trim()) resolve.mutate(value);
  };
  const target = resolved?.target;
  const actions = resolved?.allowed_actions ?? [];
  const resolveError = resolve.error instanceof Error ? resolve.error.message : undefined;
  const revokeError = revoke.error instanceof Error ? revoke.error.message : undefined;

  return (
    <Panel title="Scanner">
      <p className="mb-3 text-sm text-muted">Scan or paste a QR payload to resolve a box, product, or asset and act on it.</p>
      <div className="flex flex-wrap gap-2">
        <input
          className="desk-input flex-1 font-mono"
          placeholder="QR payload"
          value={payload}
          onChange={(event) => setPayload(event.target.value)}
          onKeyDown={(event) => { if (event.key === "Enter") doResolve(payload); }}
        />
        <button className="desk-button" type="button" disabled={!payload.trim() || resolve.isPending} onClick={() => doResolve(payload)}>
          {resolve.isPending ? "Resolving..." : "Resolve"}
        </button>
        <button className="desk-button" type="button" onClick={() => setShowScanner(true)}>Scan camera</button>
      </div>
      {resolveError ? <p className="mt-2 text-sm text-danger">{resolveError}</p> : null}

      {resolved && target ? (
        <div className="mt-4 rounded-md border border-line bg-surface p-3">
          <p className="text-sm font-semibold text-ink">
            {target.type === "box" ? `Box: ${target.label} (${target.code})`
              : target.type === "product" ? `Product: ${target.name}`
              : `Asset: ${target.asset_tag} — ${target.product} (${target.status})`}
          </p>
          <p className="mt-1 text-xs text-muted">QR #{resolved.qr.id} · {resolved.qr.status}</p>
          <div className="desk-actions mt-3 flex flex-wrap gap-2 text-sm">
            {actions.includes("contents") && target.type === "box" ? (
              <button type="button" disabled={loadContents.isPending} onClick={() => loadContents.mutate(target.id)}>View contents</button>
            ) : null}
            {actions.includes("revoke") ? (
              <button type="button" className="text-danger" disabled={revoke.isPending} onClick={() => revoke.mutate(resolved.qr.id)}>
                {revoke.isPending ? "Revoking..." : "Revoke QR"}
              </button>
            ) : null}
          </div>
          {actions.some((action) => ["checkout", "return", "direct_handout"].includes(action)) ? (
            <p className="mt-2 text-xs text-muted">
              This item supports {actions.filter((a) => ["checkout", "return", "direct_handout"].includes(a)).join(" / ")} —
              use the Direct handout tab (or the public self-checkout page) which collect the borrower identity.
            </p>
          ) : null}
          {revokeError ? <p className="mt-2 text-sm text-danger">{revokeError}</p> : null}
          {contents ? (
            <div className="mt-3 rounded-md border border-line bg-bg p-2 text-xs text-muted">
              <p className="font-semibold text-ink">Contents</p>
              {contents.products.map((product) => <p key={`p-${product.id}`}>{product.name} — {product.available_quantity} available</p>)}
              {contents.assets.map((asset) => <p key={`a-${asset.id}`}>{asset.asset_tag} ({asset.status})</p>)}
              {!contents.products.length && !contents.assets.length ? <p>Empty.</p> : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {showScanner ? <QrScanner onScan={(value) => { setPayload(value); setShowScanner(false); doResolve(value); }} onClose={() => setShowScanner(false)} /> : null}
    </Panel>
  );
}
