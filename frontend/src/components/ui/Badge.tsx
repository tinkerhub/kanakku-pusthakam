import type { PropsWithChildren } from "react";

type BadgeTone = "success" | "warn" | "danger" | "neutral";

type BadgeProps = PropsWithChildren<{
  tone: BadgeTone;
}>;

const toneClasses: Record<BadgeTone, string> = {
  success: "border-success/30 bg-success/10 text-success",
  warn: "border-warn/30 bg-warn/10 text-warn",
  danger: "border-danger/30 bg-danger/10 text-danger",
  neutral: "border-line bg-surface text-muted",
};

export function Badge({ tone, children }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${toneClasses[tone]}`}
    >
      {children}
    </span>
  );
}
