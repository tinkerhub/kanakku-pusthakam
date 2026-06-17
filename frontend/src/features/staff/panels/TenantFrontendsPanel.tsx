import { useEffect, useState } from "react";
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

type DeploymentMode = "central" | "single";

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
  const singleTenantFrontend = frontends.data?.results?.find(
    (frontend) => frontend.frontend_type === "staff_admin" && frontend.is_active,
  );
  const [deploymentMode, setDeploymentMode] = useState<DeploymentMode>("central");
  const [singleTenantOrigin, setSingleTenantOrigin] = useState("");
  const [form, setForm] = useState<FrontendForm>({
    frontend_type: "public_portal",
    origin: "",
    enabled_modules: "",
    is_primary: false,
    is_active: true,
  });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["frontends", makerspace.id] });

  useEffect(() => {
    if (singleTenantFrontend) {
      setDeploymentMode("single");
      setSingleTenantOrigin(originFromFrontend(singleTenantFrontend));
      return;
    }
    setDeploymentMode("central");
  }, [singleTenantFrontend]);

  const enableSingleTenant = useMutation({
    mutationFn: () =>
      staffRequest(`/admin/makerspace/${makerspace.id}/frontends`, {
        method: "POST",
        body: JSON.stringify({
          frontend_type: "staff_admin",
          hostname: hostnameFromOrigin(singleTenantOrigin),
          allowed_origins: singleOrigin(singleTenantOrigin),
          enabled_modules: [],
          is_primary: true,
          is_active: true,
        }),
      }),
    onSuccess: () => invalidate(),
  });

  const disableSingleTenant = useMutation({
    mutationFn: () =>
      staffRequest(`/admin/frontends/${singleTenantFrontend?.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: false, is_primary: false }),
      }),
    onSuccess: () => invalidate(),
  });

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
  const deploymentError =
    enableSingleTenant.error instanceof Error
      ? enableSingleTenant.error.message
      : disableSingleTenant.error instanceof Error
        ? disableSingleTenant.error.message
        : undefined;

  return (
    <Panel title="Frontend origins">
      <section className="mb-4 rounded-md border border-line bg-surface p-3">
        <h3 className="text-sm font-semibold text-ink">Deployment mode</h3>
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          <button
            className={`rounded-md border px-3 py-3 text-left text-sm transition ${
              deploymentMode === "central"
                ? "border-accent bg-accent/10 text-ink"
                : "border-line bg-panel text-muted hover:border-accent/60"
            }`}
            type="button"
            onClick={() => setDeploymentMode("central")}
          >
            <span className="block font-semibold">Central multi-tenant portal</span>
            <span className="mt-1 block text-xs">Uses /m/{makerspace.slug} and the shared /admin.</span>
          </button>
          <button
            className={`rounded-md border px-3 py-3 text-left text-sm transition ${
              deploymentMode === "single"
                ? "border-accent bg-accent/10 text-ink"
                : "border-line bg-panel text-muted hover:border-accent/60"
            }`}
            type="button"
            onClick={() => setDeploymentMode("single")}
          >
            <span className="block font-semibold">Single-tenant branded site</span>
            <span className="mt-1 block text-xs">Uses a tenant token in config.js for this makerspace.</span>
          </button>
        </div>

        {deploymentMode === "central" ? (
          <div className="mt-3 rounded-md border border-line bg-panel p-3 text-sm text-muted">
            <p>
              Public catalog: <span className="font-mono text-ink">/m/{makerspace.slug}</span>
            </p>
            {singleTenantFrontend ? (
              <button
                className="desk-button mt-3"
                disabled={disableSingleTenant.isPending}
                type="button"
                onClick={() => disableSingleTenant.mutate()}
              >
                {disableSingleTenant.isPending ? "Switching..." : "Switch to central mode"}
              </button>
            ) : null}
          </div>
        ) : (
          <div className="mt-3 grid gap-3 rounded-md border border-line bg-panel p-3">
            <label className="grid gap-1 text-sm">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted">Site origin</span>
              <input
                className="desk-input"
                placeholder="https://alphamakerspace.com"
                value={singleTenantOrigin}
                onChange={(event) => setSingleTenantOrigin(event.target.value)}
              />
            </label>
            {singleTenantFrontend ? (
              <div className="grid gap-1 text-sm">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted">Tenant token</span>
                <code className="break-all rounded-md border border-line bg-bg px-3 py-2 text-xs text-ink">
                  {singleTenantFrontend.token}
                </code>
                <p className="text-xs text-muted">
                  Set <span className="font-mono">TENANT_TOKEN</span> to this value on the hosted frontend.
                </p>
              </div>
            ) : (
              <button
                className="desk-button-primary w-fit"
                disabled={enableSingleTenant.isPending || !singleTenantOrigin.trim()}
                type="button"
                onClick={() => enableSingleTenant.mutate()}
              >
                {enableSingleTenant.isPending ? "Enabling..." : "Enable single-tenant site"}
              </button>
            )}
          </div>
        )}
        {deploymentError ? <p className="mt-2 text-sm text-danger">{deploymentError}</p> : null}
      </section>

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
