type SkeletonProps = {
  className?: string;
};

export function Skeleton({ className = "" }: SkeletonProps) {
  return <span className={`block animate-pulse rounded-md bg-muted/20 ${className}`} />;
}
