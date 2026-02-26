import React from "react";

export function Pagination({
  currentPage,
  totalPages,
  onPageChange,
}: {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}) {
  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-between mt-4 pt-4 border-t border-tron-border/30">
      <button
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        className="px-3 py-1.5 text-[11px] font-mono uppercase border border-tron-border/50 rounded text-tron-dim hover:text-tron-accent hover:border-tron-accent disabled:opacity-30 disabled:hover:text-tron-dim disabled:hover:border-tron-border/50 disabled:cursor-not-allowed transition-colors"
      >
        &larr; Prev
      </button>
      <span className="text-[11px] text-tron-dim font-mono">
        Seite {currentPage} / {totalPages}
      </span>
      <button
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        className="px-3 py-1.5 text-[11px] font-mono uppercase border border-tron-border/50 rounded text-tron-dim hover:text-tron-accent hover:border-tron-accent disabled:opacity-30 disabled:hover:text-tron-dim disabled:hover:border-tron-border/50 disabled:cursor-not-allowed transition-colors"
      >
        Next &rarr;
      </button>
    </div>
  );
}
