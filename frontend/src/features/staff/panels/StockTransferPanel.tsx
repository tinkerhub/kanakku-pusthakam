import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";
import { JsonRows, Panel, type Makerspace, type Product, useStaffGet } from "./shared";

type Container = {
  id: number;
  label: string;
  location: string;
};

export function StockTransferPanel({ makerspace }: { makerspace: Makerspace }) {
  const queryClient = useQueryClient();
  const products = useStaffGet<{ results: Product[] }>(["inventory", makerspace.id], `/admin/makerspace/${makerspace.id}/inventory`);
  const transfers = useStaffGet<{ results: unknown[] }>(["transfers", makerspace.id], `/admin/makerspace/${makerspace.id}/stock-transfers`);
  const containers = useStaffGet<{ results: Container[] }>(["containers", makerspace.id], `/admin/makerspace/${makerspace.id}/containers`);
  const [productId, setProductId] = useState("");
  const [destinationId, setDestinationId] = useState("");
  const [reason, setReason] = useState("Operational transfer");
  const create = useMutation({
    mutationFn: () =>
      staffRequest(`/admin/makerspace/${makerspace.id}/stock-transfers`, {
        method: "POST",
        body: JSON.stringify({
          destination_container_id: destinationId ? Number(destinationId) : null,
          reason,
          lines: [{ product_id: Number(productId), quantity: 1 }],
        }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["transfers", makerspace.id] }),
  });
  return (
    <Panel title="Stock transfers">
      <div className="grid gap-2 md:grid-cols-[1fr_1fr_1fr_auto]">
        <select className="desk-input" value={productId} onChange={(event) => setProductId(event.target.value)}>
          <option value="">Product</option>
          {products.data?.results?.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}
        </select>
        <select className="desk-input" value={destinationId} onChange={(event) => setDestinationId(event.target.value)}>
          <option value="">Destination</option>
          {containers.data?.results?.map((container) => <option key={container.id} value={container.id}>{container.label}</option>)}
        </select>
        <input className="desk-input" value={reason} onChange={(event) => setReason(event.target.value)} />
        <button disabled={!productId || create.isPending} onClick={() => create.mutate()}>Create</button>
      </div>
      <JsonRows data={transfers.data?.results ?? []} />
    </Panel>
  );
}
