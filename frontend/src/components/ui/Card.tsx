import type { PropsWithChildren } from "react";

type CardProps = PropsWithChildren<{
  className?: string;
}>;

export function Card({ children, className = "" }: CardProps) {
  return (
    <div
      className={`desk-panel p-4 ${className}`}
    >
      {children}
    </div>
  );
}
