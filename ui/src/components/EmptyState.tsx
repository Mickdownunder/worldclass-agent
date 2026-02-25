"use client";

import { ReactNode } from "react";

export function EmptyState({
  title,
  description,
  action,
  className = "",
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`tron-panel flex flex-col items-center justify-center gap-3 p-12 text-center ${className}`}
    >
      <p className="font-medium text-tron-text">{title}</p>
      {description && <p className="max-w-md text-sm text-tron-dim">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
