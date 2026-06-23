import type { Dispatch, FormEvent, ReactNode, SetStateAction } from "react";
import type { UseQueryResult } from "@tanstack/react-query";

import { Card } from "../../components/ui/Card";
import { FilePicker, TextArea, TextInput } from "./PublicPrintRequestParts";
import type { PublicFilamentSpool } from "./publicApi";

export type FormState = {
  requesterName: string;
  title: string;
  projectBrief: string;
  preferredSettings: string;
  filamentSpoolId: string;
  material: string;
  color: string;
  quantity: number;
  sourceLink: string;
  contactEmail: string;
  contactPhone: string;
};

export const initialForm: FormState = {
  requesterName: "",
  title: "",
  projectBrief: "",
  preferredSettings: "",
  filamentSpoolId: "",
  material: "",
  color: "",
  quantity: 1,
  sourceLink: "",
  contactEmail: "",
  contactPhone: "",
};

export function optional(value: string) {
  const trimmed = value.trim();
  return trimmed || undefined;
}

// Group active spools by material so same-material filaments are listed together and
// distinguished by color (the public /spools endpoint already orders by material,color).
export function groupSpoolsByMaterial(
  spools: PublicFilamentSpool[],
): [string, PublicFilamentSpool[]][] {
  const groups = new Map<string, PublicFilamentSpool[]>();
  for (const spool of spools) {
    const key = spool.material || "Other";
    const bucket = groups.get(key);
    if (bucket) bucket.push(spool);
    else groups.set(key, [spool]);
  }
  return [...groups.entries()];
}

type PrintDetailsFormProps = {
  form: FormState;
  updateField: <K extends keyof FormState>(key: K, value: FormState[K]) => void;
  spoolsQuery: UseQueryResult<PublicFilamentSpool[], Error>;
  modelFiles: File[];
  setModelFiles: Dispatch<SetStateAction<File[]>>;
  screenshotFiles: File[];
  setScreenshotFiles: Dispatch<SetStateAction<File[]>>;
  verified: boolean;
  submitPending: boolean;
  submitError?: Error | null;
  uploadProgress: string;
  website: string;
  onWebsiteChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function PrintDetailsForm({
  form,
  updateField,
  spoolsQuery,
  modelFiles,
  setModelFiles,
  screenshotFiles,
  setScreenshotFiles,
  verified,
  submitPending,
  submitError,
  uploadProgress,
  website,
  onWebsiteChange,
  onSubmit,
}: PrintDetailsFormProps) {
  return (
    <Card>
      <p className="font-mono text-xs font-semibold uppercase tracking-wide text-accent">
        Print Details
      </p>
      <form className="mt-4 space-y-4" onSubmit={onSubmit}>
        {/* Honeypot: hidden from humans; bots that autofill it trigger the server decoy. */}
        <input
          aria-hidden="true"
          autoComplete="off"
          className="hidden"
          name="website"
          tabIndex={-1}
          value={website}
          onChange={(event) => onWebsiteChange(event.target.value)}
        />
        <fieldset className="space-y-4" disabled={!verified || submitPending}>
          <FormSection icon="01" panelClass="panel-blue" title="Project Details">
            <div className="grid gap-4 md:grid-cols-2">
              <TextInput
                label="Title"
                required
                value={form.title}
                onChange={(value) => updateField("title", value)}
              />
              <TextInput
                label="Source link (optional)"
                value={form.sourceLink}
                onChange={(value) => updateField("sourceLink", value)}
              />
            </div>
            <TextArea
              label="Project brief"
              value={form.projectBrief}
              onChange={(value) => updateField("projectBrief", value)}
            />
            <TextArea
              label="Slicer settings / personal preferences"
              value={form.preferredSettings}
              onChange={(value) => updateField("preferredSettings", value)}
            />
          </FormSection>

          <FormSection icon="02" panelClass="panel-yellow" title="Material Specs">
            <div className="grid gap-4 md:grid-cols-2">
              <label className="block">
                <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted">
                  Filament / material
                </span>
                <select
                  className="desk-input w-full bg-panel"
                  value={form.filamentSpoolId}
                  onChange={(event) =>
                    updateField("filamentSpoolId", event.target.value)
                  }
                >
                  <option value="">No preference</option>
                  {groupSpoolsByMaterial(spoolsQuery.data ?? []).map(([material, spools]) => (
                    <optgroup key={material} label={material}>
                      {spools.map((spool) => (
                        <option key={spool.id} value={spool.id}>
                          {`${spool.color || "Default color"}${spool.remaining_weight_grams ? ` - ${spool.remaining_weight_grams}g left` : ""}`}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
                {spoolsQuery.isLoading ? (
                  <p className="mt-1 text-xs text-muted">Loading filament...</p>
                ) : null}
                {spoolsQuery.isError ? (
                  <p className="mt-1 text-xs text-danger">
                    {spoolsQuery.error.message}
                  </p>
                ) : null}
              </label>
              <label className="block">
                <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted">
                  Quantity
                </span>
                <input
                  className="desk-input w-full bg-panel"
                  min={1}
                  type="number"
                  value={form.quantity}
                  onChange={(event) =>
                    updateField("quantity", Math.max(1, Number(event.target.value) || 1))
                  }
                />
              </label>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <FilePicker
                accept=".stl,.3mf,.step,.stp,.obj"
                files={modelFiles}
                label="STL/model files"
                setFiles={setModelFiles}
              />
              <FilePicker
                accept="image/*,application/pdf"
                files={screenshotFiles}
                label="Estimated print-time screenshots (Bambu Lab)"
                setFiles={setScreenshotFiles}
              />
            </div>
          </FormSection>

          <FormSection icon="03" panelClass="panel-coral" title="Contact">
            <div className="grid gap-4 md:grid-cols-2">
              <TextInput
                label="Your name"
                required
                value={form.requesterName}
                onChange={(value) => updateField("requesterName", value)}
              />
              <TextInput
                label="Contact phone"
                required
                value={form.contactPhone}
                onChange={(value) => updateField("contactPhone", value)}
              />
            </div>
          </FormSection>
        </fieldset>

        {!verified ? (
          <p className="rounded-lg border-2 border-ink panel-yellow px-3 py-2 text-sm font-semibold">
            Verify your Check-In before submitting a print request.
          </p>
        ) : null}
        {uploadProgress ? <p className="text-sm text-muted">{uploadProgress}</p> : null}
        {submitError ? (
          <p className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            {submitError.message}
          </p>
        ) : null}
        <button
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg border-2 border-ink panel-mint px-3 py-2 font-mono text-sm font-semibold uppercase tracking-tight shadow-brutal-sm transition-all hover:-translate-y-0.5 hover:shadow-brutal disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0 disabled:hover:shadow-brutal-sm"
          disabled={
            !verified ||
            !form.requesterName.trim() ||
            !form.contactEmail.trim() ||
            !form.contactPhone.trim() ||
            !form.title.trim() ||
            submitPending
          }
          type="submit"
        >
          {submitPending ? "Submitting..." : "Submit print request"}
        </button>
      </form>
    </Card>
  );
}

// A numbered, color-coded brutalist section: a tinted header bar (panelClass) over a
// white body. Restores the vibrant grouping the public print form is built around.
function FormSection({
  icon,
  panelClass,
  title,
  children,
}: {
  icon: string;
  panelClass: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-lg border-2 border-ink bg-bg shadow-brutal-sm">
      <div
        className={`${panelClass} flex items-center gap-2 border-b-2 border-ink px-3 py-2 font-mono text-xs font-semibold uppercase tracking-wide`}
      >
        <span className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-ink bg-panel text-ink">
          {icon}
        </span>
        <span>{title}</span>
      </div>
      <div className="space-y-4 p-4">{children}</div>
    </section>
  );
}
