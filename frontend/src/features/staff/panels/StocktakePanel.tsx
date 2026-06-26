import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";
import { Panel, type Makerspace, useStaffGet } from "./shared";
import { invalidateInventoryViews } from "../queryInvalidation";

type StocktakeRow = { id: number; status: string; notes: string; container: number | null };
type StocktakeLine = {
  id: number;
  product: number | null;
  asset: number | null;
  container: number | null;
  expected_quantity: number;
  counted_quantity: number;
  variance_quantity: number;
  condition: string;
  notes: string;
};
type StocktakeDetail = StocktakeRow & { lines: StocktakeLine[] };
type ProductOption = { id: number; name: string; tracking_mode: string };
type ContainerOption = { id: number; label: string; location?: string };

const CONDITIONS = ["available", "damaged", "lost", "unknown"];

export function StocktakePanel({ makerspace, isSuperadmin = false }: { makerspace: Makerspace; isSuperadmin?: boolean }) {
  const queryClient = useQueryClient();
  const [openId, setOpenId] = useState<number | null>(null);
  const [createNotes, setCreateNotes] = useState("Cycle count");
  const [createContainerId, setCreateContainerId] = useState("");
  const containersEnabled = makerspace.enabled_modules?.includes("containers") ?? false;
  const stocktakes = useStaffGet<{ results: StocktakeRow[] }>(["stocktakes", makerspace.id], `/admin/makerspace/${makerspace.id}/stocktakes`);
  const containers = useStaffGet<{ results: ContainerOption[] }>(
    ["stocktake-containers", makerspace.id],
    `/admin/makerspace/${makerspace.id}/containers?page_size=1000`,
    containersEnabled,
  );
  const create = useMutation({
    mutationFn: () =>
      staffRequest(`/admin/makerspace/${makerspace.id}/stocktakes`, {
        method: "POST",
        body: JSON.stringify({
          notes: createNotes,
          container_id: createContainerId ? Number(createContainerId) : null,
        }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["stocktakes", makerspace.id] }),
  });
  const action = useMutation({
    mutationFn: (path: string) => staffRequest(path, { method: "POST", body: JSON.stringify({}) }),
    onSuccess: (_data, path) => {
      queryClient.invalidateQueries({ queryKey: ["stocktakes", makerspace.id] });
      if (path.endsWith("/apply-adjustments")) {
        invalidateInventoryViews(queryClient, makerspace.id);
        queryClient.invalidateQueries({ queryKey: ["needs-fix-shelf", makerspace.id] });
      }
    },
  });
  const createError = create.error instanceof Error ? create.error.message : undefined;
  const actionError = action.error instanceof Error ? action.error.message : undefined;
  const containerName = (id: number | null) => containers.data?.results.find((container) => container.id === id)?.label ?? (id ? `Container #${id}` : "All containers");

  return (
    <Panel title="Stocktake">
      <div className="grid gap-2 md:grid-cols-[1fr_1fr_auto] md:items-end">
        <label className="grid gap-1 text-xs text-muted">
          <span>Session notes</span>
          <input className="desk-input" value={createNotes} onChange={(event) => setCreateNotes(event.target.value)} />
        </label>
        {containersEnabled ? (
          <label className="grid gap-1 text-xs text-muted">
            <span>Container</span>
            <select className="desk-input" value={createContainerId} onChange={(event) => setCreateContainerId(event.target.value)}>
              <option value="">All containers</option>
              {containers.data?.results.map((container) => <option key={container.id} value={container.id}>{container.label}</option>)}
            </select>
          </label>
        ) : <div />}
        <button className="desk-button" disabled={create.isPending} onClick={() => create.mutate()}>
          {create.isPending ? "Starting..." : "Start stocktake"}
        </button>
      </div>
      {createError ? <p className="mt-2 text-sm text-danger">{createError}</p> : null}
      {actionError ? <p className="mt-2 text-sm text-danger">{actionError}</p> : null}
      <div className="mt-3 grid gap-2">
        {stocktakes.data?.results?.map((row) => (
          <div key={row.id} className="rounded-md border border-line bg-surface p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <strong>#{row.id}</strong>
              <span className="rounded-md border border-line bg-bg px-2 py-0.5 text-xs text-muted">{row.status}</span>
              {canCount(row.status) ? (
                <button className="desk-button" type="button" onClick={() => setOpenId((id) => (id === row.id ? null : row.id))}>{openId === row.id ? "Hide counts" : "Count items"}</button>
              ) : null}
              {row.status === "counting" ? (
                <button className="desk-button" type="button" disabled={action.isPending} onClick={() => action.mutate(`/admin/stocktakes/${row.id}/complete`)}>Complete</button>
              ) : null}
              {isSuperadmin && row.status === "completed" ? (
                <button className="desk-button" type="button" disabled={action.isPending} onClick={() => action.mutate(`/admin/stocktakes/${row.id}/approve`)}>Approve</button>
              ) : null}
              {isSuperadmin && row.status === "approved" ? (
                <button className="desk-button" type="button" disabled={action.isPending} onClick={() => action.mutate(`/admin/stocktakes/${row.id}/apply-adjustments`)}>Apply</button>
              ) : null}
            </div>
            <p className="mt-1 text-muted">{row.notes}{row.container ? ` - ${containerName(row.container)}` : ""}</p>
            {openId === row.id ? <CountSection makerspace={makerspace} stocktakeId={row.id} containersEnabled={containersEnabled} /> : null}
          </div>
        ))}
      </div>
    </Panel>
  );
}

function CountSection({ makerspace, stocktakeId, containersEnabled }: { makerspace: Makerspace; stocktakeId: number; containersEnabled: boolean }) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"product" | "asset">("product");
  const [productId, setProductId] = useState("");
  const [assetId, setAssetId] = useState("");
  const [containerId, setContainerId] = useState("");
  const [counted, setCounted] = useState("0");
  const [condition, setCondition] = useState("available");
  const [notes, setNotes] = useState("");
  const detail = useStaffGet<StocktakeDetail>(["stocktake-detail", stocktakeId], `/admin/stocktakes/${stocktakeId}`);
  const products = useStaffGet<{ results: ProductOption[] }>(["inventory-all", makerspace.id], `/admin/makerspace/${makerspace.id}/inventory?page_size=1000`);
  const containers = useStaffGet<{ results: ContainerOption[] }>(
    ["stocktake-containers", makerspace.id],
    `/admin/makerspace/${makerspace.id}/containers?page_size=1000`,
    containersEnabled,
  );
  const productName = (id: number | null) => products.data?.results.find((product) => product.id === id)?.name ?? (id ? `#${id}` : "-");
  const containerName = (id: number | null) => containers.data?.results.find((container) => container.id === id)?.label ?? (id ? `Container #${id}` : "-");
  // A container-scoped stocktake requires every count line to carry that container_id.
  // Force it (and lock the line selector) so the first record doesn't fail; otherwise
  // free choice. Deriving it (vs. seeding state) survives the post-record reset.
  const sessionContainer = detail.data?.container ?? null;
  const effectiveContainerId = sessionContainer != null ? String(sessionContainer) : containerId;

  const record = useMutation({
    mutationFn: () => {
      const payload = {
        ...(mode === "asset" ? { asset_id: Number(assetId) } : { product_id: Number(productId) }),
        ...(effectiveContainerId ? { container_id: Number(effectiveContainerId) } : {}),
        counted_quantity: Number(counted) || 0,
        condition,
        notes,
      };
      return staffRequest(`/admin/stocktakes/${stocktakeId}/count-lines`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: () => {
      setProductId("");
      setAssetId("");
      setContainerId("");
      setCounted("0");
      setNotes("");
      queryClient.invalidateQueries({ queryKey: ["stocktake-detail", stocktakeId] });
      queryClient.invalidateQueries({ queryKey: ["stocktakes", makerspace.id] });
    },
  });
  const recordError = record.error instanceof Error ? record.error.message : undefined;
  const lines = detail.data?.lines ?? [];
  const canSave = mode === "asset" ? Boolean(assetId) : Boolean(productId);
  const selectedProduct = products.data?.results.find((product) => product.id === Number(productId));

  return (
    <div className="mt-3 rounded-md border border-line bg-bg p-3">
      <div className="grid gap-2 md:grid-cols-[120px_1fr_1fr_120px_140px] md:items-end">
        <label className="grid gap-1 text-xs text-muted">
          <span>Count type</span>
          <select className="desk-input" value={mode} onChange={(event) => { setMode(event.target.value as "product" | "asset"); setAssetId(""); setCounted("0"); }}>
            <option value="product">Product</option>
            <option value="asset">Asset</option>
          </select>
        </label>
        {mode === "asset" ? (
          <label className="grid gap-1 text-xs text-muted">
            <span>Asset ID</span>
            <input className="desk-input" type="number" min="1" value={assetId} onChange={(event) => setAssetId(event.target.value)} />
          </label>
        ) : (
          <label className="grid gap-1 text-xs text-muted">
            <span>Product</span>
            <select className="desk-input" value={productId} disabled={products.isLoading} onChange={(event) => setProductId(event.target.value)}>
              <option value="">Select product</option>
              {products.data?.results.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}
            </select>
          </label>
        )}
        {containersEnabled ? (
          <label className="grid gap-1 text-xs text-muted">
            <span>Line container</span>
            <select className="desk-input" value={effectiveContainerId} disabled={sessionContainer != null} onChange={(event) => setContainerId(event.target.value)}>
              <option value="">No container</option>
              {containers.data?.results.map((container) => <option key={container.id} value={container.id}>{container.label}</option>)}
            </select>
          </label>
        ) : <div />}
        <label className="grid gap-1 text-xs text-muted">
          <span>Counted</span>
          <input className="desk-input" type="number" min="0" max={mode === "asset" ? 1 : undefined} value={counted} onChange={(event) => setCounted(event.target.value)} />
        </label>
        <label className="grid gap-1 text-xs text-muted">
          <span>Condition</span>
          <select className="desk-input" value={condition} onChange={(event) => setCondition(event.target.value)}>
            {CONDITIONS.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
        {mode === "asset" ? <span>Asset counts must be 0 or 1.</span> : null}
        {selectedProduct ? <span>Selected: {selectedProduct.name} ({selectedProduct.tracking_mode})</span> : null}
        <button className="desk-button" type="button" onClick={() => setCounted("0")}>0</button>
        <button className="desk-button" type="button" onClick={() => setCounted("1")}>1</button>
        {mode === "product" ? <button className="desk-button" type="button" onClick={() => setCounted((value) => String(Math.max(0, Number(value || 0) + 1)))}>+1</button> : null}
      </div>
      <label className="mt-2 grid gap-1 text-xs text-muted">
        <span>Line notes</span>
        <input className="desk-input" value={notes} onChange={(event) => setNotes(event.target.value)} />
      </label>
      <div className="desk-actions mt-2 flex justify-end">
        <button className="desk-button" disabled={!canSave || record.isPending} onClick={() => record.mutate()}>{record.isPending ? "Saving..." : "Record count"}</button>
      </div>
      {recordError ? <p className="mt-2 text-sm text-danger">{recordError}</p> : null}
      <div className="mt-3 grid min-w-0 gap-1">
        {lines.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-[720px] text-left text-xs">
              <thead className="text-muted">
                <tr><th className="py-1">Item</th><th>Container</th><th>Expected</th><th>Counted</th><th>Variance</th><th>Condition</th><th>Notes</th></tr>
              </thead>
              <tbody>
                {lines.map((line) => (
                  <tr key={line.id} className="border-t border-line">
                    <td className="py-1"><span className="block max-w-48 break-words">{line.asset ? `Asset #${line.asset}` : productName(line.product)}</span></td>
                    <td>{containerName(line.container)}</td>
                    <td>{line.expected_quantity}</td>
                    <td>{line.counted_quantity}</td>
                    <td className={line.variance_quantity === 0 ? "text-muted" : "text-danger"}>{line.variance_quantity}</td>
                    <td>{line.condition}</td>
                    <td><span className="block max-w-56 break-words">{line.notes || "-"}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="text-xs text-muted">No counts recorded yet.</p>}
      </div>
    </div>
  );
}

function canCount(status: string) {
  return status === "draft" || status === "counting";
}
