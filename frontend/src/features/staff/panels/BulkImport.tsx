import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";
import { Panel, type Makerspace } from "./shared";

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
