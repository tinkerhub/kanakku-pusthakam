import { Card } from "../../components/ui/Card";

type PrintRulesCardProps = {
  /** Active makerspace display name, used in the disclaimer copy. */
  makerspaceName: string;
};

/**
 * Sidebar rules + disclaimer for the public 3D-print request page. Split out of
 * PublicPrintRequestPage so that view stays within the file-size ceiling.
 */
export function PrintRulesCard({ makerspaceName }: PrintRulesCardProps) {
  return (
    <Card className="card-tilt-1 panel-mint">
      <p className="font-mono text-xs font-semibold uppercase tracking-wide">Rules</p>
      <ul className="mt-3 space-y-2 text-sm leading-6">
        <li className="flex gap-2">
          <span aria-hidden>&bull;</span>
          <span>Only checked-in users can submit requests.</span>
        </li>
        <li className="flex gap-2">
          <span aria-hidden>&bull;</span>
          <span>All requests require admin approval.</span>
        </li>
        <li className="flex gap-2">
          <span aria-hidden>&bull;</span>
          <span>Complex prints (&gt;4h) may be rescheduled to off-hours.</span>
        </li>
        <li className="flex gap-2">
          <span aria-hidden>&bull;</span>
          <span>You must provide a screenshot of the sliced model.</span>
        </li>
      </ul>
      <p className="mt-4 border-t border-ink/20 pt-4 text-sm leading-6">
        <span className="font-semibold">Disclaimer:</span> This is a community-driven
        initiative, not a 3D printing shop. We will only be printing your requested files
        if you are checked into {makerspaceName}.{" "}
        <span className="font-semibold">Please refrain from calling us for updates.</span>{" "}
        You will receive notifications about your print status exclusively via email.
      </p>
    </Card>
  );
}
