import type { PropsWithChildren } from "react";

type BadgeTone = "success" | "warn" | "danger" | "neutral";

type BadgeProps = PropsWithChildren<{
  tone: BadgeTone;
}>;

const toneClasses: Record<BadgeTone, string> = {
  success: "border-success bg-success/10 text-success",
  warn: "border-warn bg-warn/10 text-warn",
  danger: "border-danger bg-danger/10 text-danger",
  neutral: "border-outline bg-surface text-muted",
};

export function Badge({ tone, children }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-sm border px-2 py-0.5 font-mono text-xs font-medium uppercase tracking-tight ${toneClasses[tone]}`}
    >
      {children}
    </span>
  );
}
