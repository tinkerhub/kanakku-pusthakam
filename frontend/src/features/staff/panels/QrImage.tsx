import { useMemo } from "react";

import { useStaffGet } from "./shared";

type QrPrintPayload = {
  payload: string;
  svg: string;
};

export function QrImage({ qrId, label }: { qrId: number; label: string }) {
  const qr = useStaffGet<QrPrintPayload>(["qr-image", qrId], `/admin/qr/${qrId}/print`);
  const src = useMemo(() => {
    if (!qr.data?.svg) return "";
    return `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(qr.data.svg)))}`;
  }, [qr.data?.svg]);

  if (qr.isLoading) {
    return <div className="grid aspect-square place-items-center rounded-xl border border-ink bg-bg text-xs text-muted">Loading QR</div>;
  }

  if (qr.isError || !src) {
    return <div className="status-box status-box-danger grid aspect-square place-items-center rounded-xl text-xs">QR unavailable</div>;
  }

  return <img className="aspect-square w-full rounded-xl border border-ink bg-white p-2 shadow-brutal-sm" src={src} alt={`${label} QR`} />;
}
