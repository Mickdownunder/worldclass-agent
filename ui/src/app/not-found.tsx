import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-tron-bg text-tron-text">
      <h1 className="text-2xl font-semibold text-tron-accent">404</h1>
      <p className="mt-2 text-tron-muted">Seite nicht gefunden.</p>
      <Link
        href="/"
        className="mt-8 flex h-10 items-center justify-center rounded-sm bg-transparent border-2 border-tron-accent px-6 text-sm font-bold text-tron-accent shadow-[0_0_15px_var(--tron-glow)] transition-all hover:bg-tron-accent hover:text-black hover:shadow-[0_0_25px_var(--tron-glow)] active:scale-[0.98] uppercase tracking-wider"
      >
        Zurück zum Command Center
      </Link>
    </div>
  );
}
