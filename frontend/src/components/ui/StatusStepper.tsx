const STAGES = ["Requested", "Approved", "Collected", "Returned"] as const;

function statusStageIndex(status: string): number {
  switch (status) {
    case "accepted":
      return 1;
    case "issued":
    case "partially_returned":
      return 2;
    case "returned":
    case "closed_with_issue":
      return 3;
    case "draft":
    case "pending_approval":
    case "rejected":
    default:
      return 0;
  }
}

export function statusStageLabel(status: string): string {
  if (status === "rejected") return "Rejected";
  return STAGES[statusStageIndex(status)] ?? STAGES[0];
}

function StepBox({
  step,
  label,
  state,
  rejected,
}: {
  step: number;
  label: string;
  state: "completed" | "current" | "upcoming";
  rejected: boolean;
}) {
  const className = rejected && step === 0
    ? "status-box status-box-danger"
    : state === "completed"
      ? "status-box status-box-done"
      : state === "current"
        ? "status-box status-box-active"
        : "status-box";

  return (
    <span className={className} aria-current={state === "current" ? "step" : undefined}>
      <span>{step + 1}</span>
      <span className="min-w-0 break-words">{label}</span>
    </span>
  );
}

function RejectedBadge() {
  return <span className="status-box status-box-danger">Rejected</span>;
}

export function StatusStepper({ status }: { status: string }) {
  const rejected = status === "rejected";
  const activeIndex = rejected ? 0 : statusStageIndex(status);

  return (
    <nav
      aria-label={`Request status: ${statusStageLabel(status)}`}
      className="w-full"
    >
      <ol className="grid grid-cols-2 items-start gap-2 sm:grid-cols-4">
        {STAGES.map((stage, index) => {
          const state =
            index < activeIndex
              ? "completed"
              : index === activeIndex
                ? "current"
                : "upcoming";
          const lineActive = index < activeIndex;

          return (
            <li
              className="relative flex min-w-0 flex-col items-center text-center"
              key={stage}
            >
              {index < STAGES.length - 1 ? (
                <span
                  aria-hidden="true"
                  className={`absolute left-1/2 top-4 hidden w-full border-t-2 sm:block ${
                    lineActive ? "border-success" : "border-line"
                  }`}
                />
              ) : null}
              <span className="relative z-10 flex min-w-0 max-w-full flex-col items-center gap-1 bg-surface px-1">
                <StepBox
                  step={index}
                  label={stage}
                  state={state}
                  rejected={rejected}
                />
                {rejected && index === 0 ? <RejectedBadge /> : null}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
