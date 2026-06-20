import type { Availability } from "../../types/inventory";

type AvailabilityBadgeProps = {
  availability: Availability;
};

type Tone = "success" | "warn" | "danger" | "neutral";

const TONE_CLASS: Record<Tone, string> = {
  success: "border-ink bg-[#74dd9c] text-[#00321b]",
  warn: "border-ink bg-[#fcdf46] text-[#3d3400]",
  danger: "border-ink bg-[#ffdad6] text-[#93000a]",
  neutral: "border-outline bg-surface text-muted",
};

function toneForAvailability(
  label: NonNullable<Availability>["label"],
): Tone {
  if (label === "Limited") {
    return "warn";
  }

  if (label === "Unavailable") {
    return "danger";
  }

  if (label === "Available") {
    return "success";
  }

  return "neutral";
}

function textForAvailability(availability: NonNullable<Availability>): string {
  const label = availability.label;

  if (availability.mode === "exact_count" && availability.count != null) {
    if (label === "Unavailable") {
      return "Unavailable";
    }

    if (label === "Limited") {
      return `${availability.count} limited`;
    }

    return `${availability.count} available`;
  }

  return label ?? "Available";
}

export function AvailabilityBadge({ availability }: AvailabilityBadgeProps) {
  if (availability === null) {
    return null;
  }

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-xs font-semibold uppercase tracking-tight ${TONE_CLASS[toneForAvailability(availability.label)]}`}
    >
      {textForAvailability(availability)}
    </span>
  );
}
