import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";
import { Panel, type Makerspace } from "./shared";

export function QrTools({ makerspace }: { makerspace: Makerspace }) {
  const [batchTitle, setBatchTitle] = useState("QR labels");
  const mutation = useMutation({
    mutationFn: () =>
      staffRequest("/admin/qr/containers", {
        method: "POST",
        body: JSON.stringify({ makerspace_id: makerspace.id, label: prompt("Box label") ?? "" }),
      }),
  });
  const batch = useMutation({
    mutationFn: () =>
      staffRequest(`/admin/makerspace/${makerspace.id}/qr-print-batches`, {
        method: "POST",
        body: JSON.stringify({ title: batchTitle }),
      }),
  });
  return (
    <Panel title="QR tools">
      <div className="flex flex-wrap gap-2">
        <button onClick={() => mutation.mutate()}>Create container QR</button>
        <input className="desk-input" value={batchTitle} onChange={(event) => setBatchTitle(event.target.value)} />
        <button onClick={() => batch.mutate()}>Create print batch</button>
      </div>
      {mutation.data ? <pre className="mt-3 rounded-md border border-line bg-bg p-3 text-xs text-muted">{JSON.stringify(mutation.data, null, 2)}</pre> : null}
      {batch.data ? <pre className="mt-3 rounded-md border border-line bg-bg p-3 text-xs text-muted">{JSON.stringify(batch.data, null, 2)}</pre> : null}
    </Panel>
  );
}
