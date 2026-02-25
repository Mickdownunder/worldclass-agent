"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface EventItem {
  ts: string;
  type: string;
  payload: string;
}

function humanLabel(type: string, payload: string): { text: string; jobId?: string } {
  if (type === "job") {
    const parts = payload.split(" | ");
    const [jobId, workflowId, status] = parts;
    if (status === "FAILED") {
      return { text: "Fehlgeschlagen", jobId };
    }
    if (status === "RUNNING") return { text: "Läuft …", jobId };
    if (workflowId === "research-init") return { text: "Research-Projekt angelegt", jobId };
    if (workflowId === "research-cycle") return { text: "Research: Ein Schritt erledigt", jobId };
    if (workflowId === "factory-cycle") return { text: "Factory durchgelaufen", jobId };
    if (workflowId?.startsWith("research-")) return { text: `Research: ${status === "DONE" ? "erledigt" : status}`, jobId };
    return { text: status === "DONE" ? "Erledigt" : status ?? payload, jobId };
  }
  return { text: payload };
}

export function EventFeed() {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    async function fetchEvents() {
      try {
        const res = await fetch("/api/events");
        if (!cancelled && res.ok) {
          const data = await res.json();
          setEvents(data.events ?? []);
        }
      } catch {
        //
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchEvents();
    const t = setInterval(fetchEvents, 15000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);
  if (loading && events.length === 0) return <p className="text-sm text-tron-dim">Lädt…</p>;
  if (events.length === 0) return <p className="text-sm text-tron-dim">Noch nichts passiert.</p>;
  return (
    <ul className="max-h-60 space-y-2 overflow-y-auto text-sm pr-2">
      {events.slice(0, 20).map((e, i) => {
        const { text, jobId } = humanLabel(e.type, e.payload);
        const isFailed = e.type === "job" && e.payload.includes("FAILED");
        return (
          <li key={i} className="flex gap-3 border-b border-tron-border/50 pb-2 items-center">
            <span className="shrink-0 text-xs text-tron-dim">{e.ts.slice(11, 19)}</span>
            {jobId ? (
              <Link
                href={`/jobs/${jobId}`}
                className={`truncate ${isFailed ? "text-tron-error hover:underline" : "text-tron-muted hover:text-tron-accent hover:underline"}`}
              >
                {text}
              </Link>
            ) : (
              <span className={isFailed ? "text-tron-error" : "text-tron-muted"}>{text}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}
