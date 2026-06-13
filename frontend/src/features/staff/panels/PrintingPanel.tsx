import type React from "react";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";
import { Panel, type Makerspace, useStaffGet } from "./shared";

type FilamentSpool = {
  id: number;
  printer: number | null;
  printer_name?: string;
  material: string;
  color: string;
  brand: string;
  initial_weight_grams: string;
  remaining_weight_grams: string;
  is_active: boolean;
};
type PrintPrinter = {
  id: number;
  makerspace: number;
  name: string;
  model: string;
  status: string;
  is_active: boolean;
  active_spool: FilamentSpool | null;
  current_request: { id: number; title: string; estimated_minutes: number } | null;
  is_free: boolean;
  pending_estimated_minutes: number;
  estimated_spool_remaining_after_queue_grams: string | null;
};
type PrintRequest = {
  id: number;
  title: string;
  requester_username: string;
  status: string;
  material: string;
  color: string;
  estimated_minutes: number;
  estimated_filament_grams: string;
  printer: PrintPrinter | null;
  filament_spool: FilamentSpool | null;
};

export function PrintingPanel({ makerspace }: { makerspace: Makerspace }) {
  const queryClient = useQueryClient();
  const printers = useStaffGet<{ results: PrintPrinter[] }>(
    ["print-printers", makerspace.id],
    `/printing/manage/printers/?makerspace=${makerspace.id}`,
  );
  const spools = useStaffGet<{ results: FilamentSpool[] }>(
    ["print-spools", makerspace.id],
    `/printing/manage/spools/?makerspace=${makerspace.id}`,
  );
  const accepted = useStaffGet<{ results: PrintRequest[] }>(
    ["print-requests", makerspace.id, "accepted"],
    `/printing/manage/requests/?makerspace=${makerspace.id}&status=accepted`,
  );
  const printing = useStaffGet<{ results: PrintRequest[] }>(
    ["print-requests", makerspace.id, "printing"],
    `/printing/manage/requests/?makerspace=${makerspace.id}&status=printing`,
  );
  const [printerName, setPrinterName] = useState("");
  const [printerModel, setPrinterModel] = useState("");
  const [spoolPrinter, setSpoolPrinter] = useState("");
  const [spoolMaterial, setSpoolMaterial] = useState("PLA");
  const [spoolColor, setSpoolColor] = useState("");
  const [spoolWeight, setSpoolWeight] = useState("1000");
  const [selectedPrinter, setSelectedPrinter] = useState("");
  const [selectedSpool, setSelectedSpool] = useState("");
  const [estimatedMinutes, setEstimatedMinutes] = useState("60");
  const [estimatedGrams, setEstimatedGrams] = useState("100");

  const invalidatePrinting = () => {
    queryClient.invalidateQueries({ queryKey: ["print-printers", makerspace.id] });
    queryClient.invalidateQueries({ queryKey: ["print-spools", makerspace.id] });
    queryClient.invalidateQueries({ queryKey: ["print-requests", makerspace.id] });
  };
  const createPrinter = useMutation({
    mutationFn: () =>
      staffRequest("/printing/manage/printers/", {
        method: "POST",
        body: JSON.stringify({
          makerspace: makerspace.id,
          name: printerName,
          model: printerModel,
          status: "active",
        }),
      }),
    onSuccess: () => {
      setPrinterName("");
      setPrinterModel("");
      invalidatePrinting();
    },
  });
  const createSpool = useMutation({
    mutationFn: () =>
      staffRequest("/printing/manage/spools/", {
        method: "POST",
        body: JSON.stringify({
          makerspace: makerspace.id,
          printer: spoolPrinter ? Number(spoolPrinter) : null,
          material: spoolMaterial,
          color: spoolColor,
          initial_weight_grams: spoolWeight,
          remaining_weight_grams: spoolWeight,
          is_active: true,
        }),
      }),
    onSuccess: () => {
      setSpoolColor("");
      invalidatePrinting();
    },
  });
  const action = useMutation({
    mutationFn: ({ request, name }: { request: PrintRequest; name: "start" | "complete" | "fail" }) => {
      const body =
        name === "start"
          ? {
              printer_id: selectedPrinter ? Number(selectedPrinter) : undefined,
              filament_spool_id: selectedSpool ? Number(selectedSpool) : undefined,
              estimated_minutes: Number(estimatedMinutes),
              estimated_filament_grams: estimatedGrams,
            }
          : name === "fail"
            ? { reason: prompt("Failure reason") ?? "Failed from staff app." }
            : {};
      return staffRequest(`/printing/manage/requests/${request.id}/${name}`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    onSuccess: invalidatePrinting,
  });

  const printerRows = printers.data?.results ?? [];
  const spoolRows = spools.data?.results ?? [];
  return (
    <div className="grid gap-4">
      <Panel title="3D printers">
        <div className="grid gap-3 md:grid-cols-3">
          {printerRows.map((printer) => (
            <div key={printer.id} className="rounded-md border border-line bg-surface p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-ink">{printer.name}</h3>
                  <p className="text-xs text-muted">{printer.model || "No model"}</p>
                </div>
                <span className={`rounded-md px-2 py-1 text-xs font-semibold ${printer.is_free ? "bg-success/15 text-success" : "bg-warn/15 text-warn"}`}>
                  {printer.is_free ? "Free" : "Busy"}
                </span>
              </div>
              <dl className="mt-3 grid gap-1 text-sm text-muted">
                <div className="flex justify-between gap-2"><dt>Status</dt><dd>{printer.status}</dd></div>
                <div className="flex justify-between gap-2"><dt>Pending</dt><dd>{printer.pending_estimated_minutes} min</dd></div>
                <div className="flex justify-between gap-2"><dt>Current</dt><dd>{printer.current_request?.title ?? "None"}</dd></div>
                <div className="flex justify-between gap-2">
                  <dt>Spool</dt>
                  <dd>{printer.active_spool ? `${printer.active_spool.material} ${printer.active_spool.color}` : "None"}</dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt>Left after queue</dt>
                  <dd>{printer.estimated_spool_remaining_after_queue_grams ?? "-"} g</dd>
                </div>
              </dl>
            </div>
          ))}
        </div>
        <div className="mt-4 grid gap-2 md:grid-cols-[1fr_1fr_auto]">
          <input className="desk-input" placeholder="Printer name" value={printerName} onChange={(event) => setPrinterName(event.target.value)} />
          <input className="desk-input" placeholder="Model" value={printerModel} onChange={(event) => setPrinterModel(event.target.value)} />
          <button disabled={!printerName || createPrinter.isPending} onClick={() => createPrinter.mutate()}>Add printer</button>
        </div>
      </Panel>

      <Panel title="Filament spools">
        <div className="grid gap-2 md:grid-cols-[1fr_1fr_1fr_1fr_auto]">
          <select className="desk-input" value={spoolPrinter} onChange={(event) => setSpoolPrinter(event.target.value)}>
            <option value="">Unassigned printer</option>
            {printerRows.map((printer) => <option key={printer.id} value={printer.id}>{printer.name}</option>)}
          </select>
          <input className="desk-input" placeholder="Material" value={spoolMaterial} onChange={(event) => setSpoolMaterial(event.target.value)} />
          <input className="desk-input" placeholder="Color" value={spoolColor} onChange={(event) => setSpoolColor(event.target.value)} />
          <input className="desk-input" placeholder="Weight g" type="number" min="0" value={spoolWeight} onChange={(event) => setSpoolWeight(event.target.value)} />
          <button disabled={!spoolMaterial || !spoolWeight || createSpool.isPending} onClick={() => createSpool.mutate()}>Add spool</button>
        </div>
        <div className="mt-3 grid gap-2 text-sm">
          {spoolRows.map((spool) => (
            <div key={spool.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line bg-surface px-3 py-2">
              <span className="font-medium text-ink">{spool.material} {spool.color || ""}</span>
              <span className="text-muted">{spool.printer_name ?? "Unassigned"}</span>
              <span className="text-muted">{spool.remaining_weight_grams}g left</span>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="Print queue">
        <div className="mb-3 grid gap-2 md:grid-cols-4">
          <select className="desk-input" value={selectedPrinter} onChange={(event) => setSelectedPrinter(event.target.value)}>
            <option value="">Printer</option>
            {printerRows.map((printer) => <option key={printer.id} value={printer.id}>{printer.name}</option>)}
          </select>
          <select className="desk-input" value={selectedSpool} onChange={(event) => setSelectedSpool(event.target.value)}>
            <option value="">Spool</option>
            {spoolRows
              .filter((spool) => !selectedPrinter || spool.printer === Number(selectedPrinter) || spool.printer === null)
              .map((spool) => <option key={spool.id} value={spool.id}>{spool.material} {spool.color} ({spool.remaining_weight_grams}g)</option>)}
          </select>
          <input className="desk-input" type="number" min="0" value={estimatedMinutes} onChange={(event) => setEstimatedMinutes(event.target.value)} />
          <input className="desk-input" type="number" min="0" value={estimatedGrams} onChange={(event) => setEstimatedGrams(event.target.value)} />
        </div>
        <div className="grid gap-3 lg:grid-cols-2">
          <PrintRows title="Accepted" rows={accepted.data?.results ?? []} action={(row) => (
            <button disabled={!selectedPrinter || action.isPending} onClick={() => action.mutate({ request: row, name: "start" })}>Start on printer</button>
          )} />
          <PrintRows title="Printing" rows={printing.data?.results ?? []} action={(row) => (
            <>
              <button onClick={() => action.mutate({ request: row, name: "complete" })}>Complete</button>
              <button onClick={() => action.mutate({ request: row, name: "fail" })}>Fail</button>
            </>
          )} />
        </div>
      </Panel>
    </div>
  );
}

function PrintRows({
  title,
  rows,
  action,
}: {
  title: string;
  rows: PrintRequest[];
  action: (row: PrintRequest) => React.ReactNode;
}) {
  return (
    <div className="rounded-md border border-line">
      <h3 className="border-b border-line bg-surface px-3 py-2 text-sm font-semibold text-muted">{title}</h3>
      <div className="grid gap-0">
        {rows.length ? rows.map((row) => (
          <article key={row.id} className="border-b border-line p-3 last:border-b-0">
            <div className="flex flex-wrap items-center gap-2">
              <strong className="text-ink">#{row.id} {row.title}</strong>
              <span className="rounded-md border border-line bg-bg px-2 py-0.5 text-xs text-muted">{row.status}</span>
              <div className="desk-actions ml-auto flex flex-wrap gap-2 text-sm">{action(row)}</div>
            </div>
            <p className="mt-2 text-xs text-muted">
              {row.requester_username} · {row.material || "material n/a"} {row.color || ""} · {row.estimated_minutes || 0} min · {row.estimated_filament_grams || "0.00"}g
            </p>
          </article>
        )) : <p className="p-3 text-sm text-muted">No print requests.</p>}
      </div>
    </div>
  );
}
