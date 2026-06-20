import type { PropsWithChildren } from "react";

type BadgeTone = "success" | "warn" | "danger" | "neutral" | "info" | "active";

type BadgeProps = PropsWithChildren<{
  tone: BadgeTone;
}>;

const toneClasses: Record<BadgeTone, string> = {
  success: "border-ink bg-[#74dd9c] text-[#00321b]",
  warn: "border-ink bg-[#fcdf46] text-[#3d3400]",
  danger: "border-ink bg-[#ffdad6] text-[#93000a]",
  neutral: "border-ink bg-surface text-muted",
  info: "border-ink bg-[#7dd3fc] text-[#00374a]",
  active: "border-ink bg-[#7dd3fc] text-[#00374a]",
};

export function Badge({ tone, children }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-1 font-mono text-xs font-semibold uppercase tracking-tight ${toneClasses[tone]}`}
    >
      {children}
    </span>
  );
}
