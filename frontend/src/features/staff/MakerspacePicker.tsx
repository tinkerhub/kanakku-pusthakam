import { Badge } from "../../components/ui";
import type { Makerspace } from "./StaffPanels";

/**
 * Superadmin entry screen: the superadmin operates one makerspace at a time, so
 * before the console loads they explicitly pick which makerspace to operate. The
 * chosen id then scopes every staff API call (the backend already takes a
 * makerspace_id per request). Reachable again via "Switch makerspace" in the shell.
 */
export function MakerspacePicker({
  makerspaces,
  loading,
  username,
  onSelect,
  onSignOut,
}: {
  makerspaces: Makerspace[];
  loading: boolean;
  username: string;
  onSelect: (id: number) => void;
  onSignOut: () => void;
}) {
  return (
    <main className="desk-shell min-h-screen px-5 py-10">
      <div className="mx-auto w-full max-w-3xl">
        <div className="desk-panel mb-6 flex flex-wrap items-center justify-between gap-3 p-5">
          <div>
            <p className="font-display text-2xl font-bold text-ink">TinkerSpace</p>
            <p className="mt-1 font-mono text-xs font-semibold uppercase text-accent">Super Admin</p>
            <h1 className="mt-2 text-2xl font-bold text-ink">Choose a makerspace to operate</h1>
            <p className="mt-1 text-sm text-muted">Signed in as {username}. Pick a makerspace to manage its operations.</p>
          </div>
          <div className="flex items-center gap-2">
            <button className="desk-button" type="button" onClick={onSignOut}>
              Sign out
            </button>
          </div>
        </div>

        {loading ? (
          <p className="text-sm text-muted">Loading makerspaces...</p>
        ) : !makerspaces.length ? (
          <div className="desk-panel p-6">
            <p className="text-sm text-muted">No makerspaces exist yet. Create one from the Django control plane.</p>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {makerspaces.map((makerspace) => (
              <button
                key={makerspace.id}
                type="button"
                onClick={() => onSelect(makerspace.id)}
                className="desk-panel flex flex-col items-start gap-1 bg-panel p-4 text-left transition-all hover:-translate-y-0.5 hover:scale-[1.02] hover:border-accent hover:shadow-brutal-lg"
              >
                <span className="pill border border-ink bg-surface px-2 py-1 font-mono text-xs font-semibold uppercase text-accent">
                  {makerspace.public_code ?? makerspace.slug}
                </span>
                <span className="text-lg font-semibold text-ink">{makerspace.name}</span>
                {makerspace.superadmin_access_enabled === false ? (
                  <span className="mt-1">
                    <Badge tone="warn">Superadmin access: Off</Badge>
                  </span>
                ) : null}
                <span className="mt-2 text-xs text-muted">Operate this makerspace -&gt;</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
