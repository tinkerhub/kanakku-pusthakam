import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";
import type { EmailTemplateRow } from "./EmailTemplates";

type EmailTemplateForm = {
  subject: string;
  text_body: string;
  html_body: string;
  is_active: boolean;
};

type PreviewResponse = {
  subject: string;
  text_body: string;
  html_body: string;
};

type EditableField = keyof Pick<EmailTemplateForm, "subject" | "text_body" | "html_body">;

export function EmailTemplateEditor({
  makerspaceId,
  row,
}: {
  makerspaceId: number;
  row: EmailTemplateRow;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<EmailTemplateForm>(() => formFromRow(row));
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const subjectRef = useRef<HTMLInputElement | null>(null);
  const textRef = useRef<HTMLTextAreaElement | null>(null);
  const htmlRef = useRef<HTMLTextAreaElement | null>(null);
  const lastFocused = useRef<EditableField>("text_body");

  useEffect(() => {
    setForm(formFromRow(row));
    setPreview(null);
  }, [row.key, row.subject, row.text_body, row.html_body, row.is_active]);

  const templatePath = `/admin/makerspace/${makerspaceId}/email-templates/${row.key}`;

  const invalidateTemplateQueries = () => {
    queryClient.invalidateQueries({ queryKey: ["email-templates", makerspaceId] });
    queryClient.invalidateQueries({ queryKey: ["email-template", makerspaceId, row.key] });
  };

  const saveTemplate = useMutation({
    mutationFn: () =>
      staffRequest<EmailTemplateRow>(templatePath, {
        method: "PUT",
        body: JSON.stringify(form),
      }),
    onSuccess: (updated) => {
      setForm(formFromRow(updated));
      setPreview(null);
      invalidateTemplateQueries();
    },
  });

  const resetTemplate = useMutation({
    mutationFn: async () => {
      await staffRequest<void>(templatePath, { method: "DELETE" });
      return staffRequest<EmailTemplateRow>(templatePath);
    },
    onSuccess: (updated) => {
      setForm(formFromRow(updated));
      setPreview(null);
      invalidateTemplateQueries();
    },
  });

  const previewTemplate = useMutation({
    mutationFn: () =>
      // Send the UNSAVED editor draft so the preview matches what's on screen, not the
      // last-saved template.
      staffRequest<PreviewResponse>(`${templatePath}/preview`, {
        method: "POST",
        body: JSON.stringify({
          subject: form.subject,
          text_body: form.text_body,
          html_body: form.html_body,
        }),
      }),
    onSuccess: setPreview,
  });

  const setField = (field: keyof EmailTemplateForm, value: string | boolean) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const markFocused = (field: EditableField) => {
    lastFocused.current = field;
  };

  const insertToken = (name: string) => {
    const field = lastFocused.current;
    const token = `{{ ${name} }}`;
    const element = elementForField(field, subjectRef.current, textRef.current, htmlRef.current);
    const currentValue = form[field];
    const start = element?.selectionStart ?? currentValue.length;
    const end = element?.selectionEnd ?? currentValue.length;
    const nextValue = `${currentValue.slice(0, start)}${token}${currentValue.slice(end)}`;

    setForm((current) => ({ ...current, [field]: nextValue }));
    window.requestAnimationFrame(() => {
      element?.focus();
      element?.setSelectionRange(start + token.length, start + token.length);
    });
  };

  return (
    <div className="grid min-w-0 gap-4">
      <div className="rounded-2xl border border-ink bg-bg p-4 shadow-brutal-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="grid max-w-2xl gap-2">
            <h3 className="text-base font-semibold text-ink">{row.label}</h3>
            <p className="text-sm text-muted">
              {row.family === "hardware" ? "Hardware" : "Printing"} template for{" "}
              {row.audience === "staff" ? "staff" : "requesters"}.
            </p>
          </div>
          <label className="flex items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(event) => setField("is_active", event.target.checked)}
            />
            Active
          </label>
        </div>

        <div className="mt-4 grid gap-3">
          <label className="grid gap-1 text-sm font-semibold text-ink">
            Subject
            <input
              ref={subjectRef}
              className="desk-input font-normal"
              value={form.subject}
              onFocus={() => markFocused("subject")}
              onChange={(event) => setField("subject", event.target.value)}
            />
          </label>
          <label className="grid gap-1 text-sm font-semibold text-ink">
            Text body
            <textarea
              ref={textRef}
              className="desk-input min-h-48 font-mono text-xs font-normal"
              value={form.text_body}
              onFocus={() => markFocused("text_body")}
              onChange={(event) => setField("text_body", event.target.value)}
            />
          </label>
          <label className="grid gap-1 text-sm font-semibold text-ink">
            HTML body
            <textarea
              ref={htmlRef}
              className="desk-input min-h-56 font-mono text-xs font-normal"
              value={form.html_body}
              onFocus={() => markFocused("html_body")}
              onChange={(event) => setField("html_body", event.target.value)}
            />
          </label>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            className="desk-button-primary"
            type="button"
            disabled={saveTemplate.isPending}
            onClick={() => saveTemplate.mutate()}
          >
            {saveTemplate.isPending ? "Saving..." : "Save"}
          </button>
          <button
            className="desk-button"
            type="button"
            disabled={resetTemplate.isPending}
            onClick={() => {
              if (window.confirm("Reset this email template to the default copy?")) {
                resetTemplate.mutate();
              }
            }}
          >
            {resetTemplate.isPending ? "Resetting..." : "Reset to default"}
          </button>
          <button
            className="desk-button"
            type="button"
            disabled={previewTemplate.isPending}
            onClick={() => previewTemplate.mutate()}
          >
            {previewTemplate.isPending ? "Previewing..." : "Preview"}
          </button>
        </div>

        {saveTemplate.error ? (
          <p className="mt-3 text-sm text-danger">{saveTemplate.error.message}</p>
        ) : null}
        {resetTemplate.error ? (
          <p className="mt-3 text-sm text-danger">{resetTemplate.error.message}</p>
        ) : null}
        {previewTemplate.error ? (
          <p className="mt-3 text-sm text-danger">{previewTemplate.error.message}</p>
        ) : null}
      </div>

      <div className="rounded-2xl border border-ink bg-bg p-4 shadow-brutal-sm">
        <h3 className="text-base font-semibold text-ink">Merge fields</h3>
        <div className="mt-3 flex flex-wrap gap-2">
          {row.variables.map((variable) => (
            <button
              key={variable.name}
              className="desk-button rounded-full bg-surface px-3 py-1 text-left text-xs normal-case text-ink hover:bg-panel"
              type="button"
              title={`${variable.description} Sample: ${variable.sample}`}
              onClick={() => insertToken(variable.name)}
            >
              <span className="font-mono">{"{{ "}{variable.name}{" }}"}</span>
              <span className="ml-2 text-muted">{variable.description}</span>
            </button>
          ))}
        </div>
        {row.variables.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No merge fields for this template.</p>
        ) : null}
      </div>

      {preview ? (
        <div className="rounded-2xl border border-ink bg-bg p-4 shadow-brutal-sm">
          <h3 className="text-base font-semibold text-ink">Preview</h3>
          <div className="mt-3 grid gap-3">
            <div className="rounded-xl border border-ink bg-surface p-3">
              <p className="text-xs font-semibold uppercase tracking-tight text-muted">
                Subject
              </p>
              <p className="mt-1 whitespace-pre-wrap text-sm text-ink">{preview.subject}</p>
            </div>
            <div className="rounded-xl border border-ink bg-surface p-3">
              <p className="text-xs font-semibold uppercase tracking-tight text-muted">
                Text body
              </p>
              <pre className="mt-1 whitespace-pre-wrap break-words text-sm text-ink">
                {preview.text_body}
              </pre>
            </div>
            <iframe title="Email preview" sandbox="" srcDoc={preview.html_body} referrerPolicy="no-referrer" className="h-80 w-full rounded-xl border border-ink bg-white" />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function formFromRow(row: EmailTemplateRow): EmailTemplateForm {
  return {
    subject: row.subject ?? "",
    text_body: row.text_body ?? "",
    html_body: row.html_body ?? "",
    is_active: row.is_active,
  };
}

function elementForField(
  field: EditableField,
  subject: HTMLInputElement | null,
  text: HTMLTextAreaElement | null,
  html: HTMLTextAreaElement | null,
) {
  if (field === "subject") return subject;
  if (field === "html_body") return html;
  return text;
}
