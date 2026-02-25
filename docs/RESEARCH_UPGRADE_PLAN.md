# Research Upgrade Plan — State-of-the-Art Autonomous Research System

Ziel: Das Operator-System zu einem autonomen, mehrtägigen Forschungs-System ausbauen mit Cross-Domain Discovery und professioneller Report-Engine.

---

## Phase 1 — Augen und Hände (Woche 1–2)

**Ziel:** Das System kann die Welt sehen (Web, PDFs, akademische Quellen).

- [ ] Web Search API (Brave Search oder Serper)
- [ ] Web Reader (URL → strukturierter Text)
- [ ] PDF Parser (Papers lesen)
- [ ] Akademische APIs: Semantic Scholar, arXiv, PubMed, Google Patents, SEC EDGAR
- [ ] Research-Projekt-Struktur unter `research/proj-<id>/`
- [ ] Workflows: `research-init.sh`, `research-search.sh`, `research-read.sh`, `research-synthesize.sh`

**Deliverable:** Ein Research-Projekt kann angelegt werden; Quellen können gesucht, gelesen und als Findings gespeichert werden.

---

## Phase 2 — Forschungs-Methodik (Woche 2–3)

**Ziel:** Mehrtägiger autonomer Research-Cycle mit Lückenanalyse und Widerspruchserkennung.

- [ ] Research Cycle: EXPLORE → FOCUS → CONNECT → VERIFY → SYNTHESIZE
- [ ] Brain-Upgrade: Reasoning-Modi (hypothesis_formation, gap_analysis, contradiction_detection)
- [ ] Research-Playbooks (Marktanalyse, Literatur-Review, Patent-Landscape, Due Diligence)
- [ ] Source Management: Quelle + Confidence + Widerspruchserkennung
- [ ] Multi-Model: gpt-4.1 für Synthese, gpt-4.1-mini für Search/Extract

**Deliverable:** Ein Research-Projekt läuft über mehrere Tage autonom und produziert strukturierte Findings mit Quellen.

---

## Phase 3 — Wissens-Vernetzung & Cross-Domain (Woche 3–4)

**Ziel:** Verbindungen zwischen Projekten und Domänen automatisch finden.

- [ ] Embeddings in Memory aktivieren (text-embedding-3-small)
- [ ] Neue Tabellen: entities, relations, cross_links
- [ ] Semantische Suche über Findings
- [ ] Cross-Domain Discovery Workflow (periodisch)
- [ ] Notification bei relevanten Cross-Domain-Insights

**Deliverable:** Das System schlägt Querverbindungen zwischen verschiedenen Research-Projekten vor.

---

## Phase 4 — Feedback & Lernschleife (Woche 4–5)

**Ziel:** Vom Nutzer lernen (Telegram + UI).

- [ ] Telegram: "Dig deeper on X", "This is wrong", "Excellent", "Ignore Y"
- [ ] UI: Per-Finding-Bewertung, Kommentare, Research-Redirect
- [ ] Feedback → Memory → Playbook-Updates
- [ ] Research-Redirect: neue Frage im laufenden Projekt

**Deliverable:** Nutzerfeedback verbessert Playbooks und zukünftige Recherchen.

---

## Phase 5 — Report-Engine & Delivery (Woche 5–6)

**Ziel:** Professionelle Research-Reports, die Kunden bezahlen würden.

- [ ] Strukturierter Report: Executive Summary, Methodik, Key Findings, Quellen, Anhang
- [ ] Formate: Markdown, HTML, PDF
- [ ] UI: Research-Dashboard (aktive Projekte, Finding-Browser, Knowledge-Graph)
- [ ] Delivery: Telegram + UI + optional PDF-Download

**Deliverable:** End-to-End: Frage → mehrtägige Recherche → professioneller Report mit Citations.

---

## Git-Strategie

Nach jeder Phase: `git add`, `git commit -m "Phase N: ..."`, `git push`.

Runtime-Daten (proj-*/sources, große Reports) können in `.gitignore` stehen; Code und Schema werden versioniert.
