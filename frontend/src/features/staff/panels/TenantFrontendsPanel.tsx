import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";
import { Panel, type Makerspace, useStaffGet } from "./shared";

const FRONTEND_TYPES = [
  "public_portal",
  "staff_admin",
  "guest_handover",
  "scanner",
  "kiosk",
  "superadmin_console",
  "third_party",
];

type TenantFrontend = {
  id: number;
  token: string;
  hostname: string | null;
  frontend_type: string;
  allowed_origins: string[];
  enabled_modules: string[];
  is_primary: boolean;
  is_active: boolean;
};

type FrontendForm = {
  frontend_type: string;
  origin: string;
  enabled_modules: string;
  is_primary: boolean;
  is_active: boolean;
};

const lines = (value: string) => value.split("\n").map((line) => line.trim()).filter(Boolean);
const singleOrigin = (value: string) => {
  const origin = value.trim().replace(/\/+$/, "");
  return origin ? [origin] : [];
};
const hostnameFromOrigin = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) return null;
  try {
    return new URL(trimmed.includes("://") ? trimmed : `https://${trimmed}`).hostname;
  } catch {
    return trimmed;
  }
};
const originFromFrontend = (frontend: TenantFrontend) =>
  frontend.allowed_origins?.[0] ?? (frontend.hostname ? `https://${frontend.hostname}` : "");

// Frontend entries are scoped to this makerspace. The origin is only scheme and
// host; routes like /admin belong to the React app, not the backend allowlist.
export function TenantFrontendsPanel({ makerspace }: { makerspace: Makerspace }) {
  const queryClient = useQueryClient();
  const frontends = useStaffGet<{ results: TenantFrontend[] }>(
    ["frontends", makerspace.id],
    `/admin/makerspace/${makerspace.id}/frontends`,
  );
  const [form, setForm] = useState<FrontendForm>({
    frontend_type: "public_portal",
    origin: "",
    enabled_modules: "",
    is_primary: false,
    is_active: true,
  });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["frontends", makerspace.id] });

  const create = useMutation({
    mutationFn: () =>
      staffRequest(`/admin/makerspace/${makerspace.id}/frontends`, {
        method: "POST",
        body: JSON.stringify({
          frontend_type: form.frontend_type,
          hostname: hostnameFromOrigin(form.origin),
          allowed_origins: singleOrigin(form.origin),
          enabled_modules: lines(form.enabled_modules),
          is_primary: form.is_primary,
          is_active: form.is_active,
        }),
      }),
    onSuccess: () => {
      setForm({
        frontend_type: "public_portal",
        origin: "",
        enabled_modules: "",
        is_primary: false,
        is_active: true,
      });
      invalidate();
    },
  });
  const createError = create.error instanceof Error ? create.error.message : undefined;

  return (
    <Panel title="Frontend origins">
      {frontends.isLoading ? <p className="text-sm text-muted">Loading frontends...</p> : null}
      <div className="grid gap-2">
        {frontends.data?.results?.map((frontend) => (
          <FrontendRow key={frontend.id} frontend={frontend} onSaved={invalidate} />
        ))}
        {!frontends.isLoading && !frontends.data?.results?.length ? (
          <p className="text-sm text-muted">No frontend origins registered for this makerspace yet.</p>
        ) : null}
      </div>

      <form
        className="mt-4 grid gap-2 rounded-md border border-line bg-surface p-3"
        onSubmit={(event) => {
          event.preventDefault();
          create.mutate();
        }}
      >
        <h3 className="text-sm font-semibold text-ink">Register a frontend</h3>
        <div className="grid gap-2 md:grid-cols-2">
          <select
            className="desk-input"
            value={form.frontend_type}
            onChange={(event) => setForm({ ...form, frontend_type: event.target.value })}
          >
            {FRONTEND_TYPES.map((type) => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
          <input
            className="desk-input"
            placeholder="https://alphamakerspace.com"
            value={form.origin}
            onChange={(event) => setForm({ ...form, origin: event.target.value })}
          />
        </div>
        <textarea
          className="desk-input font-mono text-xs"
          placeholder="Enabled modules, one per line (optional)"
          value={form.enabled_modules}
          onChange={(event) => setForm({ ...form, enabled_modules: event.target.value })}
        />
        <div className="flex flex-wrap gap-4 text-sm text-muted">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={form.is_primary}
              onChange={(event) => setForm({ ...form, is_primary: event.target.checked })}
            />
            Primary
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
            />
            Active
          </label>
        </div>
        {createError ? <p className="text-sm text-danger">{createError}</p> : null}
        <button
          className="desk-button-primary"
          type="submit"
          disabled={create.isPending || !form.origin.trim()}
        >
          {create.isPending ? "Registering..." : "Register frontend"}
        </button>
      </form>
    </Panel>
  );
}

function FrontendRow({ frontend, onSaved }: { frontend: TenantFrontend; onSaved: () => void }) {
  const [editing, setEditing] = useState(false);
  const [origin, setOrigin] = useState(originFromFrontend(frontend));
  const [isActive, setIsActive] = useState(frontend.is_active);
  const [isPrimary, setIsPrimary] = useState(frontend.is_primary);

  const save = useMutation({
    mutationFn: () =>
      staffRequest(`/admin/frontends/${frontend.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          hostname: hostnameFromOrigin(origin),
          allowed_origins: singleOrigin(origin),
          is_active: isActive,
          is_primary: isPrimary,
        }),
      }),
    onSuccess: () => {
      setEditing(false);
      onSaved();
    },
  });
  const saveError = save.error instanceof Error ? save.error.message : undefined;

  return (
    <div className="rounded-md border border-line bg-surface p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <strong className="text-ink">{frontend.frontend_type}</strong>
        <span className="text-xs text-muted">{originFromFrontend(frontend) || "no origin"}</span>
        {frontend.is_primary ? <span className="rounded-md bg-accent/15 px-2 py-0.5 text-xs text-accent">Primary</span> : null}
        <span className={`rounded-md px-2 py-0.5 text-xs ${frontend.is_active ? "bg-success/15 text-success" : "bg-warn/15 text-warn"}`}>
          {frontend.is_active ? "Active" : "Inactive"}
        </span>
        <button type="button" className="ml-auto" onClick={() => setEditing((value) => !value)}>
          {editing ? "Cancel" : "Edit"}
        </button>
      </div>
      <p className="mt-1 break-all text-xs text-muted">Token: {frontend.token}</p>
      {editing ? (
        <div className="mt-3 grid gap-2">
          <input
            className="desk-input"
            placeholder="https://alphamakerspace.com"
            value={origin}
            onChange={(event) => setOrigin(event.target.value)}
          />
          <div className="flex flex-wrap gap-4 text-xs text-muted">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={isPrimary} onChange={(event) => setIsPrimary(event.target.checked)} />
              Primary
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={isActive} onChange={(event) => setIsActive(event.target.checked)} />
              Active
            </label>
          </div>
          {saveError ? <p className="text-sm text-danger">{saveError}</p> : null}
          <button className="desk-button" type="button" disabled={save.isPending || !origin.trim()} onClick={() => save.mutate()}>
            {save.isPending ? "Saving..." : "Save"}
          </button>
        </div>
      ) : null}
    </div>
  );
}
