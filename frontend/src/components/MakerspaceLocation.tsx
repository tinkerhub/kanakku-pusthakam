type MakerspaceLocationProps = {
  location?: string | null;
  mapUrl?: string | null;
  fallback?: string;
  className?: string;
};

export function MakerspaceLocation({
  location,
  mapUrl,
  fallback,
  className = "",
}: MakerspaceLocationProps) {
  const label = location || fallback || "";

  if (!label) {
    return null;
  }

  const baseClass = `block font-mono text-xs uppercase ${className}`.trim();

  if (mapUrl) {
    return (
      <a
        className={`${baseClass} text-secondary underline-offset-2 hover:underline`}
        href={mapUrl}
        rel="noopener noreferrer"
        target="_blank"
      >
        {"\u{1F4CD}"} {label} {"\u2197"}
      </a>
    );
  }

  return <span className={`${baseClass} text-muted`}>{label}</span>;
}
