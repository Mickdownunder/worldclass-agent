# Memory-UI: Lücken und Umbau — Wird dem System gerecht?

**Anspruch:** Ein Mensch will **so viel wie möglich visualisieren**; der Memory-Menüpunkt soll dem **weltklassen Memory-System** (SOTA/Novel) gerecht werden.

**Verdict:** **Nein** – der aktuelle Memory-Menüpunkt wird dem System **nicht** gerecht. Es fehlen zentrale Visualisierungen für Run-Verlauf, Memory Value, Utility, Strategies, Graph und Explainability-Links. **Umbau/Erweiterung nötig.**

---

## Was die UI heute zeigt

| Bereich | Inhalt | Quelle |
|--------|--------|--------|
| **Stats** | Episodes, Decisions, Reflections, Ø Qualität, Principles, Outcomes | state_summary().totals (episodes = **alte** episodes-Tabelle) |
| **Activity** | Letzte Ereignisse (kind, content, ts) + Reflections | recent_episodes / recent_reflections aus **episodes** (alt), nicht run_episodes |
| **Principles** | Liste Principles (type, description, domain, metric_score) | /api/memory/principles |
| **Sources** | Credibility | /api/memory/credibility |
| **Brain** | Cognitive Traces (Phasen, Reasoning, **Basierend auf P:/F:/E:**) | /api/memory/decisions |
| **Knowledge** | Entities, Playbooks, Outcomes | /api/memory/entities, outcomes + playbooks aus Summary |

**Memory Value** (applied_avg vs fallback_avg, memory_value) wird nur auf dem **Dashboard** (Startseite) genutzt, **nicht** auf der Memory-Seite.

---

## Was fehlt (Lücken)

1. **Run-Episoden (v2) — Kern des SOTA-Gedächtnisses**  
   - `run_episodes`: Projekt, Frage, Domain, Status, critic_score, what_helped/what_hurt, Strategy, run_index.  
   - **Aktuell:** Nirgends in der UI. Activity zeigt nur die **alte** episodes-Tabelle (cycle_start, job_complete, …), **nicht** den Research-Run-Verlauf.  
   - **Mensch will sehen:** „Welche Runs gab es? Was half, was schadete? Welche Strategy wurde genutzt?“

2. **Memory Value auf der Memory-Seite**  
   - `memory_value`, applied_avg, fallback_avg, applied_count, fallback_count.  
   - **Aktuell:** Nur auf dem Dashboard, nicht unter Memory.  
   - **Mensch will sehen:** „Lohnt sich Memory? Applied vs. Fallback?“ direkt im Memory-Kontext.

3. **Strategy-Profile (inkl. empirische)**  
   - Welche Strategies existieren, welche sind „empirical“, Nutzung, Score.  
   - **Aktuell:** Nicht sichtbar.  
   - **Mensch will sehen:** „Welche Strategies nutzt das System? Welche performen gut?“

4. **Utility (welche Memories nützen)**  
   - principle_id/finding_id → utility_score, retrieval_count, helpful_count.  
   - **Aktuell:** Nicht sichtbar.  
   - **Mensch will sehen:** „Welche Principles/Findings haben in der Praxis am meisten geholfen?“

5. **Graph (Strategy ↔ Episoden)**  
   - Kanten used_in: welche Episoden nutzten welche Strategy.  
   - **Aktuell:** Nicht visualisiert.  
   - **Mensch will sehen:** „Diese Strategy wurde in Runs X, Y, Z genutzt.“

6. **Explainability klickbar**  
   - Brain-Tab zeigt „Basierend auf: P:abc F:def“.  
   - **Aktuell:** IDs nur als Text, kein Link zum Principle/Finding.  
   - **Mensch will sehen:** Klick auf P:abc → Principle anzeigen oder zum Principles-Tab springen mit Highlight.

7. **Konsolidierung**  
   - Letzter Lauf, verarbeitete Domains, Anzahl synthetisierter Principles.  
   - **Aktuell:** Nicht sichtbar.  
   - **Mensch will sehen:** „Wann lief zuletzt memory-consolidate? Was kam raus?“

8. **Totals ehrlich**  
   - `totals.episodes` = alte episodes; **run_episodes**-Anzahl fehlt.  
   - **Mensch will sehen:** Run-Episoden-Zahl (Research-Verlauf) zusätzlich oder statt nur „Ereignisse“.

---

## Konkrete Umbau-Vorschläge (priorisiert)

| Prio | Maßnahme | Aufwand | Nutzen |
|------|----------|---------|--------|
| 1 | **Memory Value** auf der Memory-Seite anzeigen (Karte oder Stat), gleiche Daten wie Dashboard | Klein | Direkt sichtbar: „Lohnt sich Memory?“ |
| 2 | **Run-Episoden (v2)** in state_summary + UI: `totals.run_episodes`, `recent_run_episodes`; neuer Tab **„Runs“** oder Bereich in Activity: Tabelle project_id, question, domain, status, critic_score, what_helped/what_hurt, strategy, run_index | Mittel | Kern des SOTA-Gedächtnisses sichtbar |
| 3 | **Explainability klickbar:** P:/F:/E: als Link zum Principles-Tab (z.B. ?highlight=id) oder Modal mit Principle/Finding-Detail | Klein | Nachvollziehen, welches Memory eine Decision beeinflusst hat |
| 4 | **Strategy-Profile** anzeigen: API /api/memory/strategies (oder aus principles/state), Tab „Strategies“: Name, Domain, Score, empirisch?, Nutzung | Mittel | Transparenz, welche Strategies existieren und performen |
| 5 | **Utility-Top** anzeigen: API für Top-Principles/Findings nach utility_score; Bereich „Nützlichste Memories“ | Mittel | Zeigt, was in der Praxis am meisten hilft |
| 6 | **Graph-Visualisierung** (optional): Strategy → Episoden als Liste oder Mini-Graph (z.B. pro Strategy „genutzt in N Episoden“ mit Link zu Run-Liste) | Größer | Vollständige Transparenz der Verknüpfungen |
| 7 | **Konsolidierung:** Letzte Ausgabe (z.B. consolidation_last.json) oder Status „Zuletzt gelaufen: …“ | Klein | Operative Transparenz |

---

## Kurz-Checkliste für „wird dem System gerecht“

- [ ] Run-Episoden (v2) sichtbar (Anzahl + Liste mit what_helped/what_hurt, Strategy)
- [ ] Memory Value auf der Memory-Seite sichtbar
- [ ] Explainability: P:/F:/E: klickbar oder mit Detail
- [ ] Strategy-Profile (inkl. empirische) sichtbar
- [ ] Utility (Top Memories) sichtbar
- [ ] Optional: Graph (Strategy ↔ Episoden), Konsolidierungs-Status

**Fazit:** Mit den Prioritäten 1–3 (Memory Value, Run-Episoden, Explainability-Links) ist ein **erster Umbau** erledigt; mit 4–6 wird die UI dem Anspruch „so viel wie möglich visualisieren“ und dem weltklassen Memory-System gerecht.
