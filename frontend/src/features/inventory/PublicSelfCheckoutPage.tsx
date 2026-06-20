import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";

import { MakerspaceBrand } from "../../components/MakerspaceBrand";
import { Card } from "../../components/ui/Card";
import QrScanner from "../../components/ui/QrScanner";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { formatSlug } from "./PublicInventoryParts";
import { checkoutTool, returnTool } from "./selfCheckoutApi";
import type { PublicToolLoanResult } from "./selfCheckoutApi";
import { useTenantBootstrap } from "./usePublicInventory";

type Mode = "checkout" | "return";

type MutationInput = {
  identifier: string;
  payload: string;
};

function formatStatus(status: string) {
  const normalized = status.replace(/_/g, " ");
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function ResultCard({ result }: { result: PublicToolLoanResult }) {
  return (
    <div className="status-box status-box-done block w-full px-3 py-3 text-left normal-case">
      <p className="font-mono text-xs font-semibold uppercase tracking-wide">
        {formatStatus(result.status)}
      </p>
      <h2 className="mt-1 text-lg font-semibold text-ink">
        {result.target_label}
      </h2>
      <div className="mt-3 space-y-2">
        {result.items.map((item) => (
          <div
            className="flex items-center justify-between gap-3 rounded-lg border border-ink bg-panel px-3 py-2 text-sm text-ink"
            key={item.product_name}
          >
            <span>{item.product_name}</span>
            <span className="font-semibold">x{item.quantity}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function PublicSelfCheckoutPage() {
  const { slug } = useParams();
  const tenant = useTenant();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const tenantPath = useTenantPath(makerspaceSlug);
  const [mode, setMode] = useState<Mode>("checkout");
  const [identifier, setIdentifier] = useState("");
  const [scannerOpen, setScannerOpen] = useState(false);

  const bootstrapQuery = useTenantBootstrap(makerspaceSlug, tenant.mode === "central");
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const modules = useMemo(
    () => (tenant.mode === "single" ? tenant.modules : new Set(bootstrap?.modules ?? [])),
    [bootstrap?.modules, tenant],
  );
  const displayName =
    bootstrap?.branding.display_name ||
    bootstrap?.makerspace.name ||
    formatSlug(makerspaceSlug) ||
    "Makerspace";
  const enabled = modules.has("self_checkout");

  const loanMutation = useMutation({
    mutationFn: ({ identifier: scanIdentifier, payload }: MutationInput) =>
      mode === "checkout"
        ? checkoutTool(makerspaceSlug, scanIdentifier, payload)
        : returnTool(makerspaceSlug, scanIdentifier, payload),
  });

  function scanTool(payload: string) {
    const scanIdentifier = identifier.trim();
    if (!scanIdentifier) {
      return;
    }
    setScannerOpen(false);
    loanMutation.mutate({ identifier: scanIdentifier, payload });
  }

  return (
    <main className="desk-shell">
      <header className="border-b border-line bg-panel">
        <div className="mx-auto flex max-w-screen-xl flex-col gap-4 px-5 py-6 sm:px-8">
          <p className="text-sm font-semibold uppercase tracking-wide text-accent">
            Public Tool Checkout
          </p>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div className="min-w-0">
              <MakerspaceBrand
                name={displayName}
                logoUrl={bootstrap?.makerspace.logo_url}
                size="lg"
              />
              <p className="mt-2 text-sm text-muted">
                Scan a physical tool label to check it out or return it.
              </p>
            </div>
            <Link className="desk-button" to={tenantPath()}>
              Back to inventory
            </Link>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-screen-sm px-5 py-6 sm:px-8">
        {bootstrapQuery.isLoading ? (
          <Card>
            <p className="text-sm text-muted">Loading checkout access...</p>
          </Card>
        ) : null}

        {!bootstrapQuery.isLoading && !enabled ? (
          <Card>
            <p className="text-xs font-semibold uppercase tracking-wide text-accent">
              Self-checkout
            </p>
            <h2 className="mt-2 text-xl font-semibold text-ink">
              Self-checkout is not enabled for this makerspace.
            </h2>
            <Link className="desk-button mt-4" to={tenantPath()}>
              Back to inventory
            </Link>
          </Card>
        ) : null}

        {!bootstrapQuery.isLoading && enabled ? (
          <Card>
            <div
              aria-label="Checkout mode"
              className="pill flex gap-1 border border-ink bg-bg p-1 shadow-brutal-sm"
              role="tablist"
            >
              <button
                aria-selected={mode === "checkout"}
                className={
                  mode === "checkout"
                    ? "pill flex-1 bg-accent px-4 py-2 font-mono text-sm font-semibold uppercase tracking-tight text-on-accent"
                    : "pill flex-1 px-4 py-2 font-mono text-sm font-semibold uppercase tracking-tight text-ink hover:bg-surface"
                }
                role="tab"
                type="button"
                onClick={() => setMode("checkout")}
              >
                Use (check out)
              </button>
              <button
                aria-selected={mode === "return"}
                className={
                  mode === "return"
                    ? "pill flex-1 bg-accent px-4 py-2 font-mono text-sm font-semibold uppercase tracking-tight text-on-accent"
                    : "pill flex-1 px-4 py-2 font-mono text-sm font-semibold uppercase tracking-tight text-ink hover:bg-surface"
                }
                role="tab"
                type="button"
                onClick={() => setMode("return")}
              >
                Return
              </button>
            </div>

            <label className="mt-4 block">
              <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted">
                Check-In ID
              </span>
              <input
                className="desk-input pill w-full bg-panel"
                required
                value={identifier}
                onChange={(event) => setIdentifier(event.target.value)}
              />
            </label>

            <button
              className="desk-button-primary mt-4 w-full disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!identifier.trim() || loanMutation.isPending}
              type="button"
              onClick={() => setScannerOpen(true)}
            >
              {loanMutation.isPending ? "Submitting..." : "Scan QR"}
            </button>

            {loanMutation.isError ? (
              <p className="status-box status-box-danger mt-4 w-full justify-start px-3 py-2 text-sm normal-case">
                {loanMutation.error.message}
              </p>
            ) : null}

            {loanMutation.isSuccess ? (
              <div className="mt-4">
                <ResultCard result={loanMutation.data} />
              </div>
            ) : null}
          </Card>
        ) : null}
      </section>

      {scannerOpen ? (
        <QrScanner onClose={() => setScannerOpen(false)} onScan={scanTool} />
      ) : null}
    </main>
  );
}
