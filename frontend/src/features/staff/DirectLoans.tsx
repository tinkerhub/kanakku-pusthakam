import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import QrScanner from "../../components/ui/QrScanner";
import { staffRequest } from "../../lib/api";
import { DirectLoanList, type DirectLoan } from "./DirectLoanList";
import { invalidateInventoryViews } from "./queryInvalidation";
import { DirectLoanReturnModal } from "./DirectLoanReturnModal";
import { Panel, type Makerspace, useStaffGet } from "./StaffPanels";
import { EvidenceUpload } from "./panels/EvidenceUpload";

type ProductOption = {
  id: number;
  name: string;
  storage_location: string;
  available_quantity: number;
  tracking_mode: string;
  is_public: boolean;
  public_self_checkout_enabled: boolean;
  is_archived: boolean;
};
type ContainerOption = { id: number; label: string };
type ContainerResponse = ContainerOption[] | { results: ContainerOption[] };
type VerifyResponse = { username: string };
type LineDraft = { key: number; productId: string; quantity: string };
type ScannedPayload = { payload: string; label: string };
type ReturnLoanPayload = { loanId: number; evidenceId: number; notes: string };
type QrResolveResponse = {
  target:
    | { type: "product"; id: number; name: string }
    | { type: "asset"; id: number; asset_tag: string; product: string; status: string }
    | { type: "box"; id: number; label: string; code: string };
};

export function DirectLoans({ makerspace }: { makerspace: Makerspace }) {
  const queryClient = useQueryClient();
  const [requesterName, setRequesterName] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [lineRows, setLineRows] = useState<LineDraft[]>([{ key: 1, productId: "", quantity: "1" }]);
  const [nextLineKey, setNextLineKey] = useState(2);
  const [scanned, setScanned] = useState<ScannedPayload[]>([]);
  const [showScanner, setShowScanner] = useState(false);
  const [qrPayloads, setQrPayloads] = useState("");
  const [containerId, setContainerId] = useState("");
  const [showContainerScanner, setShowContainerScanner] = useState(false);
  const [containerScanError, setContainerScanError] = useState("");
  // Track WHICH email was verified, not just a boolean: editing the field
  // mid-flight must never approve a stale, mismatched identity.
  const [verifiedIdentifier, setVerifiedIdentifier] = useState("");
  const [verifiedUsername, setVerifiedUsername] = useState("");
  const [returningLoan, setReturningLoan] = useState<DirectLoan | null>(null);
  const [issueEvidenceId, setIssueEvidenceId] = useState<number | null>(null);
  const [issueRemark, setIssueRemark] = useState("Issued from direct handout.");
  const [issueUploadKey, setIssueUploadKey] = useState(0);
  const [returnEvidenceId, setReturnEvidenceId] = useState<number | null>(null);
  const [returnNotes, setReturnNotes] = useState("");
  useEffect(() => {
    setRequesterName("");
    setContactEmail("");
    setContactPhone("");
    setLineRows([{ key: 1, productId: "", quantity: "1" }]);
    setNextLineKey(2);
    setScanned([]);
    setShowScanner(false);
    setQrPayloads("");
    setContainerId("");
    setShowContainerScanner(false);
    setContainerScanError("");
    setVerifiedIdentifier("");
    setVerifiedUsername("");
    setReturningLoan(null);
    setIssueEvidenceId(null);
    setIssueRemark("Issued from direct handout.");
    setIssueUploadKey((key) => key + 1);
    setReturnEvidenceId(null);
    setReturnNotes("");
  }, [makerspace.id]);
  const products = useStaffGet<{ results: ProductOption[] }>(
    ["inventory-all", makerspace.id],
    `/admin/makerspace/${makerspace.id}/inventory?page_size=1000`,
  );
  // Fetch ALL containers (distinct cache key from the shared ["containers"] entry so a
  // truncated first page can't leak in): the dropdown + the scan membership check both
  // need the complete list, else a valid container past page one falsely reads as "not found".
  const containers = useStaffGet<ContainerResponse>(
    ["containers-all", makerspace.id],
    `/admin/makerspace/${makerspace.id}/containers?page_size=1000`,
  );
  const containerOptions = Array.isArray(containers.data)
    ? containers.data
    : containers.data?.results ?? [];
  // Manual (non-QR) direct handout accepts non-archived quantity products. Asset/individual items must be
  // QR-scanned instead, so don't offer rejectable options in the manual dropdown.
  const eligibleProducts = (products.data?.results ?? []).filter(
    (product) => !product.is_archived && product.tracking_mode !== "individual",
  );
  const loans = useStaffGet<{ results: DirectLoan[] }>(
    ["direct-loans", makerspace.id],
    `/admin/makerspace/${makerspace.id}/direct-loans`,
  );
  const verify = useMutation({
    mutationFn: (submitted: string) =>
      staffRequest<VerifyResponse>(`/admin/makerspace/${makerspace.id}/checkin/verify`, {
        method: "POST",
        body: JSON.stringify({ identifier: submitted }),
      }),
    onMutate: () => {
      setVerifiedIdentifier("");
      setVerifiedUsername("");
    },
    onSuccess: (result, submitted) => {
      // Bind the success to the exact identifier that was verified.
      setVerifiedIdentifier(submitted);
      setVerifiedUsername(result.username);
    },
  });
  const isVerified =
    verifiedIdentifier !== "" && verifiedIdentifier === contactEmail.trim();
  const issue = useMutation({
    mutationFn: () =>
      staffRequest(`/admin/makerspace/${makerspace.id}/direct-loans`, {
        method: "POST",
        body: JSON.stringify({
          requester_name: requesterName.trim(),
          contact_email: contactEmail.trim(),
          contact_phone: contactPhone.trim(),
          evidence_id: issueEvidenceId as number,
          remark: issueRemark.trim(),
          container_id: containerId ? Number(containerId) : null,
          qr_payloads: Array.from(new Set([
            ...scanned.map((item) => item.payload),
            ...pastedQrPayloads,
          ])),
          items: validManualLines
            .map((line) => ({ product_id: Number(line.productId), quantity: Number(line.quantity) })),
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["direct-loans", makerspace.id] });
      invalidateInventoryViews(queryClient, makerspace.id, makerspace.slug);
      setLineRows([{ key: 1, productId: "", quantity: "1" }]);
      setNextLineKey(2);
      setScanned([]);
      setQrPayloads("");
      setContainerId("");
      setShowContainerScanner(false);
      setContainerScanError("");
      setIssueEvidenceId(null);
      setIssueRemark("Issued from direct handout.");
      setIssueUploadKey((key) => key + 1);
    },
  });
  const pastedQrPayloads = qrPayloads.split("\n").map((value) => value.trim()).filter(Boolean);
  const validManualLines = lineRows.filter(
    (line) => line.productId && Number(line.quantity) > 0,
  );
  const hasIssueContent =
    validManualLines.length > 0 || scanned.length > 0 || pastedQrPayloads.length > 0 || Boolean(containerId);
  const canIssue =
    isVerified &&
    requesterName.trim().length > 0 &&
    contactEmail.trim().length > 0 &&
    contactPhone.trim().length > 0 &&
    hasIssueContent &&
    issueEvidenceId !== null &&
        {!hasIssueContent ? <p className="mt-3 text-sm text-muted">Add at least one item, QR payload, or container before issuing.</p> : null}
        <button className="desk-button-primary mt-3" disabled={!canIssue} onClick={() => issue.mutate()}>
          Issue direct handout
        </button>
        {issue.error ? <p className="mt-3 text-sm text-danger">{issue.error.message}</p> : null}
        {products.error ? <p className="mt-3 text-sm text-danger">{products.error.message}</p> : null}
        {containers.error ? <p className="mt-3 text-sm text-danger">{containers.error.message}</p> : null}
        {showScanner ? <QrScanner onScan={handleScan} onClose={() => setShowScanner(false)} /> : null}
        {showContainerScanner ? <QrScanner onScan={handleContainerScan} onClose={() => setShowContainerScanner(false)} /> : null}
      </Panel>
      <DirectLoanList loans={loans.data?.results ?? []} onReturn={openReturnModal} />
      <DirectLoanReturnModal
        loan={returningLoan}
        makerspaceId={makerspace.id}
        evidenceId={returnEvidenceId}
        notes={returnNotes}
        pending={returnLoan.isPending}
        error={returnLoan.error?.message ?? ""}
        onEvidenceUploaded={setReturnEvidenceId}
        onNotesChange={setReturnNotes}
        onCancel={closeReturnModal}
        onSubmit={submitReturn}
      />
    </div>
  );
}

function labelForTarget(target: QrResolveResponse["target"], fallback: string) {
  if (target.type === "product") return target.name || fallback;
  if (target.type === "asset") return target.product || target.asset_tag || fallback;
  return target.label || target.code || fallback;
}
