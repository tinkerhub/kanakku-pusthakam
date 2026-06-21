import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";
import { type Makerspace, useStaffGet } from "../StaffPanels";
import { EmailTemplateEditor } from "./EmailTemplateEditor";

export type EmailTemplateVariable = {
  name: string;
  description: string;
  sample: string;
  trusted_html: boolean;
};

export type EmailTemplateRow = {
  key: string;
  family: "hardware" | "printing";
  audience: "requester" | "staff";
  label: string;
  variables: EmailTemplateVariable[];
  subject: string;
  text_body: string;
  html_body: string;
  is_active: boolean;
  is_customized: boolean;
};

type EmailLayout = {
  html: string;
  is_active: boolean;
  is_default: boolean;
};

export function EmailTemplatesPanel({
  makerspace,
  canManageMakerspace,
}: {
  makerspace: Makerspace;
  canManageMakerspace: boolean;
}) {
  const [selectedKey, setSelectedKey] = useState("");
  const templates = useStaffGet<EmailTemplateRow[]>(
    ["email-templates", makerspace.id],
    `/admin/makerspace/${makerspace.id}/email-templates`,
  );
  const rows = templates.data ?? [];

  useEffect(() => {
    if (!rows.length) {
      setSelectedKey("");
      return;
    }
    if (!rows.some((row) => row.key === selectedKey)) {
      setSelectedKey(rows[0].key);
    }
  }, [rows, selectedKey]);

  const grouped = useMemo(
    () => ({
      hardware: rows.filter((row) => row.family === "hardware"),
      printing: rows.filter((row) => row.family === "printing"),
    }),
    [rows],
  );
  const selectedRow = rows.find((row) => row.key === selectedKey) ?? rows[0];

  return (
    <div className="grid gap-4">
      <section className="rounded-2xl border border-ink bg-bg p-4 shadow-brutal-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="grid max-w-2xl gap-2">
            <h2 className="text-base font-semibold text-ink">Email templates</h2>
            <p className="text-sm text-muted">
              Edit lifecycle email copy for the templates your role can manage.
            </p>
          </div>
        </div>

        {templates.isLoading ? (
          <p className="mt-3 text-sm text-muted">Loading email templates...</p>
        ) : null}
        {templates.error ? (
          <p className="mt-3 text-sm text-danger">{templates.error.message}</p>
        ) : null}

        <div className="mt-4 grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
          <div className="grid content-start gap-4">
            <TemplateGroup
              title="Hardware"
              rows={grouped.hardware}
              selectedKey={selectedRow?.key ?? ""}
              onSelect={setSelectedKey}
            />
            <TemplateGroup
              title="Printing"
              rows={grouped.printing}
              selectedKey={selectedRow?.key ?? ""}
              onSelect={setSelectedKey}
            />
            {!templates.isLoading && rows.length === 0 ? (
              <p className="text-sm text-muted">No editable templates are available.</p>
            ) : null}
          </div>

          {selectedRow ? (
            <EmailTemplateEditor makerspaceId={makerspace.id} row={selectedRow} />
          ) : (
            <div className="rounded-2xl border border-ink bg-surface p-4 text-sm text-muted">
              Select a template to edit.
            </div>
          )}
        </div>
      </section>

      {canManageMakerspace ? <EmailLayoutCard makerspaceId={makerspace.id} /> : null}
    </div>
  );
}

function TemplateGroup({
  title,
  rows,
  selectedKey,
  onSelect,
}: {
  title: string;
  rows: EmailTemplateRow[];
  selectedKey: string;
  onSelect: (key: string) => void;
}) {
  if (!rows.length) return null;

  return (
    <div>
      <h3 className="font-display text-sm font-bold uppercase tracking-tight text-ink">
        {title}
      </h3>
      <div className="mt-2 grid gap-2">
        {rows.map((row) => (
          <button
            key={row.key}
            className={`desk-button w-full justify-start rounded-xl p-3 text-left normal-case ${
              selectedKey === row.key
                ? "bg-accent text-on-accent"
                : "bg-surface text-ink hover:bg-panel"
            }`}
            type="button"
            onClick={() => onSelect(row.key)}
          >
            <span className="block font-semibold">{row.label}</span>
            <span className="mt-1 flex flex-wrap items-center gap-2 text-xs">
              <span className={selectedKey === row.key ? "text-on-accent" : "text-muted"}>
                {row.audience === "staff" ? "Staff" : "Requester"}
              </span>
              {row.is_customized ? (
                <span className="rounded-full border border-ink bg-bg px-2 py-0.5 font-semibold text-ink">
                  Customized
                </span>
              ) : null}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function EmailLayoutCard({ makerspaceId }: { makerspaceId: number }) {
  const queryClient = useQueryClient();
  const layout = useStaffGet<EmailLayout>(
    ["email-layout", makerspaceId],
    `/admin/makerspace/${makerspaceId}/email-layout`,
  );
  const [html, setHtml] = useState("");
  const [isActive, setIsActive] = useState(true);

  useEffect(() => {
    if (!layout.data) return;
    setHtml(layout.data.html ?? "");
    setIsActive(layout.data.is_active);
  }, [layout.data]);

  const saveLayout = useMutation({
    mutationFn: () =>
      staffRequest<EmailLayout>(`/admin/makerspace/${makerspaceId}/email-layout`, {
        method: "PUT",
        body: JSON.stringify({ html, is_active: isActive }),
      }),
    onSuccess: (updated) => {
      setHtml(updated.html ?? "");
      setIsActive(updated.is_active);
      queryClient.invalidateQueries({ queryKey: ["email-layout", makerspaceId] });
    },
  });

  return (
    <section className="rounded-2xl border border-ink bg-bg p-4 shadow-brutal-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid max-w-2xl gap-2">
          <h2 className="text-base font-semibold text-ink">Email layout</h2>
          <p className="text-sm text-muted">
            The layout wraps template HTML and must contain the literal token {"{{ content }}"}.
          </p>
          {layout.data?.is_default ? (
            <p className="text-sm text-muted">No custom layout has been saved yet.</p>
          ) : null}
        </div>
        <button
          className="desk-button-primary"
          type="button"
          disabled={saveLayout.isPending || layout.isLoading}
          onClick={() => saveLayout.mutate()}
        >
          {saveLayout.isPending ? "Saving..." : "Save layout"}
        </button>
      </div>

      {layout.isLoading ? <p className="mt-3 text-sm text-muted">Loading layout...</p> : null}
      {layout.error ? <p className="mt-3 text-sm text-danger">{layout.error.message}</p> : null}

      <textarea
        className="desk-input mt-4 min-h-64 w-full font-mono text-xs"
        value={html}
        onChange={(event) => setHtml(event.target.value)}
      />
      <label className="mt-3 flex items-center gap-2 text-sm text-muted">
        <input
          type="checkbox"
          checked={isActive}
          onChange={(event) => setIsActive(event.target.checked)}
        />
        Active
      </label>
      {saveLayout.error ? (
        <p className="mt-3 text-sm text-danger">{saveLayout.error.message}</p>
      ) : null}
    </section>
  );
}
