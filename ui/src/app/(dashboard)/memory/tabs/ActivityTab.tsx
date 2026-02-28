import React, { useState } from "react";
import { Pagination } from "./Pagination";

interface EpisodeRow {
  kind: string;
  content: string;
  ts: string;
}
interface ReflectionRow {
  job_id?: string;
  quality: number;
  learnings?: string;
  ts: string;
}

export function ActivityTab({
  episodes,
  reflections,
}: {
  episodes: EpisodeRow[];
  reflections: ReflectionRow[];
}) {
  const [episodePage, setEpisodePage] = useState(1);
  const [reflectionPage, setReflectionPage] = useState(1);
  
  const episodesPerPage = 10;
  const reflectionsPerPage = 10;

  const allEpisodes = episodes ?? [];
  const allReflections = reflections ?? [];

  const episodeTotalPages = Math.ceil(allEpisodes.length / episodesPerPage);
  const reflectionTotalPages = Math.ceil(allReflections.length / reflectionsPerPage);

  const displayedEpisodes = allEpisodes.slice((episodePage - 1) * episodesPerPage, episodePage * episodesPerPage);
  const displayedReflections = allReflections.slice((reflectionPage - 1) * reflectionsPerPage, reflectionPage * reflectionsPerPage);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="tron-panel p-6 flex flex-col">
        <h2 className="mb-4 text-lg font-medium text-tron-muted">Letzte Ereignisse</h2>
        <div className="flex-1">
          <ul className="space-y-2">
            {displayedEpisodes.map((e: EpisodeRow, i: number) => (
              <li key={i} className="flex gap-3 text-sm">
                <span className="text-tron-dim shrink-0">{e.ts}</span>
                <span className="text-tron-accent">{e.kind}</span>
                <span className="text-tron-text">{e.content}</span>
              </li>
            ))}
          </ul>
          {allEpisodes.length === 0 && (
            <p className="text-tron-dim">Noch keine Episoden.</p>
          )}
        </div>
        <div className="mt-auto">
          <Pagination currentPage={episodePage} totalPages={episodeTotalPages} onPageChange={setEpisodePage} />
        </div>
      </div>
      
      <div className="tron-panel p-6 flex flex-col">
        <h2 className="mb-4 text-lg font-medium text-tron-muted">Was das System gelernt hat (Reflections)</h2>
        <div className="flex-1">
          <ul className="space-y-3">
            {displayedReflections.map((r: ReflectionRow, i: number) => (
              <li key={i} className="border-l-2 border-tron-accent/30 pl-3 text-sm">
                <span className="text-tron-dim">{r.ts}</span>
                <span className="ml-2 text-tron-success">Q: {r.quality}</span>
                {r.learnings != null && (
                  <p className="mt-1 text-tron-text">{r.learnings}</p>
                )}
              </li>
            ))}
          </ul>
          {allReflections.length === 0 && (
            <p className="text-tron-dim">Noch keine Reflexionen.</p>
          )}
        </div>
        <div className="mt-auto">
          <Pagination currentPage={reflectionPage} totalPages={reflectionTotalPages} onPageChange={setReflectionPage} />
        </div>
      </div>
    </div>
  );
}
