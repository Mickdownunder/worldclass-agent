# Council Sandbox: Was PASS bedeutet und wo Vorsicht geboten ist

Kurzdokumentation, damit wir den Council-Sandbox-„PASS“ nicht überinterpretieren.

## Was der Sandbox-Test zeigt

- Eine **definierte These** wurde in Code übersetzt.
- **Utility-Maß**, **Monotonie-Bedingung** und **Resource-Bounds** wurden in einem Lauf geprüft.
- **PASS** = In diesem Lauf: Selektionslogik funktioniert (akzeptierte Mutationen haben die Utility erhöht, keine Grenzverletzung).

Das ist der erste **empirische** Schritt: nicht nur Konzept, sondern ein lauffähiger Selektionsmechanismus unter definierten Bedingungen.

## Was PASS nicht beweist

- **Kein strenges FME:** „Fitness Monotonic Execution“ im vollen Sinn verlangt: jede akzeptierte Modifikation ist *provably* besser, keine versteckten Seiteneffekte, keine lokale Optimierung auf Kosten globaler Stabilität. Unser Test zeigt Monotonie *innerhalb eines Experiments*, nicht Langzeit-Stabilität über viele Generationen.
- **Ein Lauf ≠ Beweis:** Ein einzelner PASS zeigt keine sichere Self-Replication; er zeigt kontrollierte Mutation unter den gewählten Bedingungen.

## Wo Selbsttäuschung droht

- **Utility zu glatt / zu einfach?** Starker Anstieg (z. B. 0.30 → 0.97) kann von einer bewusst schwachen Ausgangskonfiguration oder einer zu „freundlichen“ Bewertungsfunktion kommen.
- **Overfitting:** Das generierte Programm könnte auf genau diese eine Aufgabe optimiert sein.
- **Feste Bewertung:** Wenn der Agent die Bewertungsfunktion (direkt oder indirekt) beeinflussen kann, ist es kein sauberer Test der These.

## Die 3 Metriken, die wir loggen (gegen stillen Drift)

Damit das System nicht in stillem Drift untergeht, loggen wir bei jedem Council-Sandbox-Lauf:

| # | Metrik | Was wir messen | Warum |
|---|--------|----------------|--------|
| 1 | **Utility-Trajektorie** | `utility_history`: Utility pro Iteration (oder jede N-te), mind. 100+ Punkte | Drift erkennen: Steigt Utility stabil oder kollabiert sie nach einigen Schritten? Lokale Optimierung zeigt oft frühen Anstieg, dann Plateau oder Einbruch. |
| 2 | **Boundary-Adherence** | `boundary_violations`: Anzahl der Ressourcen-Grenzverletzungen (oder pro Schritt „in_bounds“) | Ob der Lauf die Regeln einhält oder „cheatet“. Jede Verletzung invalidiert FME. |
| 3 | **Monotonie / Stabilität** | `accepted_mutations` + Ableitung aus `utility_history`: Monotonie über den ganzen Lauf? `first_monotonicity_break` (Iteration) falls vorhanden | Ein PASS soll nicht nur „am Ende gut“ sein: Monotonie muss durchgehend gelten. Wenn sie erst spät bricht, war es lokale Optimierung. |

**Konkret im Lauf:** Das generierte Skript gibt am Ende eine Zeile aus:  
`METRICS_JSON: {"utility_history": [...], "boundary_violations": 0, "accepted_mutations": N}`  
Der Council-Sandbox-Parser speichert das in `council_sandbox_result.json` unter `metrics` und schreibt daraus z. B. `monotonicity_held`, `utility_drift` (Anstieg/Abstieg in zweiter Hälfte) ins Dossier.

Wenn die Monotonie über viele Iterationen stabil bleibt und keine Boundary-Violations auftreten, wird der Lauf aussagekräftiger; bricht es nach wenigen Iterationen, war es eher lokale Optimierung.

---

*Referenz: Forschungs-Feedback „Jetzt wird es ernst“ (Council Sandbox PASS-Interpretation).*
