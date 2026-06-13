import { useState } from "react";

import { Panel, useStaffGet } from "./shared";

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
