import { Badge } from "./Badge";

export type StatusBadgeTone = "success" | "warn" | "danger" | "neutral";

export const statusToneMap: Record<string, StatusBadgeTone> = {
  accepted: "success",
  active: "success",
  available: "success",
  returned: "success",
  limited: "warn",
  low: "warn",
  partially_returned: "warn",
  pending_approval: "warn",
  reserved: "warn",
  checked_out: "danger",
  closed_with_issue: "danger",
  damaged: "danger",
  issued: "danger",
  lost: "danger",
  rejected: "danger",
};

type StatusBadgeProps = {
  status: string;
  label?: string;
};

export function StatusBadge({ status, label }: StatusBadgeProps) {
  const normalized = status.toLowerCase();
  const display = label ?? normalized.replace(/_/g, " ");

  return <Badge tone={statusToneMap[normalized] ?? "neutral"}>{display}</Badge>;
}
