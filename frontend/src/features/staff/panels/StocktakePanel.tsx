import { useMutation, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";
import { Panel, type Makerspace, useStaffGet } from "./shared";

export function StocktakePanel({ makerspace }: { makerspace: Makerspace }) {
  const queryClient = useQueryClient();
  const stocktakes = useStaffGet<{ results: { id: number; status: string; notes: string }[] }>(["stocktakes", makerspace.id], `/admin/makerspace/${makerspace.id}/stocktakes`);
  const create = useMutation({
    mutationFn: () =>
      staffRequest(`/admin/makerspace/${makerspace.id}/stocktakes`, {
        method: "POST",
        body: JSON.stringify({ notes: "Cycle count" }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["stocktakes", makerspace.id] }),
  });
  const action = useMutation({
    mutationFn: (path: string) => staffRequest(path, { method: "POST", body: JSON.stringify({}) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["stocktakes", makerspace.id] }),
  });
  return (
    <Panel title="Stocktake">
      <button onClick={() => create.mutate()}>Start stocktake</button>
      <div className="mt-3 grid gap-2">
        {stocktakes.data?.results?.map((row) => (
          <div key={row.id} className="rounded-md border border-line bg-surface p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <strong>#{row.id}</strong>
              <span className="rounded-md border border-line bg-bg px-2 py-0.5 text-xs text-muted">{row.status}</span>
              <button onClick={() => action.mutate(`/admin/stocktakes/${row.id}/complete`)}>Complete</button>
              <button onClick={() => action.mutate(`/admin/stocktakes/${row.id}/approve`)}>Approve</button>
              <button onClick={() => action.mutate(`/admin/stocktakes/${row.id}/apply-adjustments`)}>Apply</button>
            </div>
            <p className="mt-1 text-muted">{row.notes}</p>
          </div>
        ))}
      </div>
    </Panel>
  );
}
