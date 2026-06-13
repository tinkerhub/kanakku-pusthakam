import { Panel, useStaffGet } from "./shared";

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
