# Plan: UI menschlicher & Research-Fokus

**Ziel:** Die UI wirkt aktuell technisch und unübersichtlich. Sie soll menschlicher, verständlicher und optisch klar auf Research-Projekte ausgerichtet sein. Ein Klick auf ein Research-Projekt soll auf eine **schöne, klare Detailseite** führen; die aktuelle Phase soll **groß und mit Glow** sichtbar sein; der Report soll in **schöner, lesbarer Schrift** erscheinen; alle Bereiche sollen **sauberer und verständlicher** werden.

---

## 1. Ist-Probleme (kurz)

- Research-Detailseite wirkt wie eine Daten-Ansammlung: kleine Phase, technische IDs, wenig Hierarchie.
- Die aktuelle Research-Phase ist nur ein kleines Label neben Status – nicht sofort erkennbar.
- Report wird in gleicher Monospace/Techno-Optik wie der Rest dargestellt – wenig einladend zum Lesen.
- Überschriften und Bereiche sind oft technisch („Report & Findings“, IDs als Titel); wenig menschliche Sprache.
- Andere Bereiche (Command Center, Jobs, Packs, Memory) sind funktional, aber nicht klar priorisiert und nicht einheitlich „sauber“.

---

## 2. Design-Prinzipien für den Agent

- **Menschlich:** Verständliche Begriffe (z. B. „Aktuelle Phase“ statt nur „Phase“, „Zusammenfassung“ statt nur „Report“). Kurze Erklärungen wo nötig. Keine nackten IDs als Haupttitel.
- **Sauber:** Klare visuelle Hierarchie (ein klares Hero-Element, dann klar gruppierte Blöcke). Viel Weißraum/Luft. Keine überladenen Panels.
- **Research im Fokus:** Research-Projekte und deren Detailseite sind das Herzstück: größer, klarer, einladender als der Rest. Phase und Fortschritt sofort erfassbar.
- **Glow für Phase:** Die aktuelle Research-Phase soll **groß** und mit **deutlichem Glow** (text-shadow und/oder leichter Box-Glow) dargestellt werden – sofort erkennbar, fast wie ein „Status-Hero“.
- **Schöne Schrift für Report:** Der Report-Text (Markdown-Inhalt) soll in einer **lesefreundlichen Serifen- oder ruhigen Sans-Schrift** mit guter Zeilenhöhe und Absatzabstand dargestellt werden – klar abgegrenzt vom technischen UI (weiterhin Mono nur für Code/IDs wo sinnvoll).

---

## 3. Konkrete Umsetzung (für Agent zum Abarbeiten)

### 3.1 Research-Projekt-Detailseite (`app/(dashboard)/research/[id]/page.tsx` + ev. neue Komponenten)

**Ziel:** Eine „schöne Seite“, auf die man landet und sofort versteht: Welches Projekt, welche Phase, was ist der Inhalt.

1. **Hero-Bereich (oben):**
   - **Erste Zeile:** Verständlicher Titel: die **Forschungsfrage** des Projekts (nicht die Projekt-ID). Wenn die Frage sehr lang ist: erste Zeile voll anzeigen, Rest z. B. auf 2 Zeilen begrenzen mit „…“ oder kürzen. Die Frage soll die Hauptüberschrift sein (z. B. `text-2xl`/`text-3xl`, `font-semibold`).
   - **Zweite Zeile (Phase-Hero):** Die **aktuelle Phase** (explore / focus / connect / verify / synthesize / done) in **großer, gut lesbarer Schrift** (z. B. `text-4xl` oder `text-5xl`) mit **Glow-Effekt**:
     - `text-shadow` in der Accent-Farbe (z. B. `0 0 20px var(--tron-glow)`, `0 0 40px var(--tron-glow)`) und optional ein dezenter Rahmen oder Hintergrund mit `box-shadow` in derselben Farbe.
     - Beispiel-Text: „Aktuelle Phase: Explore“ oder „Phase: Synthesize“. Phase-Namen können auf Deutsch sein (Explore, Fokus, Verbinden, Verifizieren, Synthesize, Abgeschlossen).
   - Optional darunter: ein **Fortschrittsbalken** (wie bisher), aber klar der Phase untergeordnet (nicht dominierend).

2. **Metadaten-Block (kompakt):**
   - Projekt-ID nur als kleines Zusatzinfo (z. B. `text-sm text-tron-dim`, „Projekt: proj-…“).
   - Status (z. B. aktiv / abgeschlossen) als Badge.
   - Kurz: Anzahl Findings, Anzahl Reports, ggf. Feedback-Anzahl – in einer Zeile oder kompakten Gruppe, nicht überladen.

3. **Aktionen (klar gruppiert):**
   - „Nächste Phase starten“ nur wenn nicht done.
   - „Aus Next Steps neue Projekte erstellen“ nur wenn done.
   - Buttons optisch klar, gleicher Stil wie im Rest der App, aber mit ausreichend Abstand.

4. **Report & Findings (darunter):**
   - Überschrift z. B. „Report & Quellen“ oder „Zusammenfassung & Findings“ – verständlich, nicht technisch.
   - Der **Report-Tab** soll den Markdown-Inhalt in **schöner Schrift** darstellen (siehe 3.2). Findings/Sources/Verlauf bleiben in Tabs; Tab-Leiste klar und ruhig gestalten.

**Dateien:**  
- `app/(dashboard)/research/[id]/page.tsx` anpassen (Layout, Hero mit Phase+Glow, Frage als Titel).  
- Optional: eigene Client-Komponente z. B. `ResearchProjectHero.tsx` für Phase-Glow + Frage, damit die Seite übersichtlich bleibt.

---

### 3.2 Report-Anzeige (schöne, lesbare Schrift)

**Ziel:** Der Report (Markdown) liest sich wie ein gut formatierter Artikel, nicht wie Technik-Log.

1. **Eigener Bereich für Report-Typografie (globals.css oder Komponente):**
   - Eine **Leseschrift** für den Report-Body: z. B. **Georgia**, **Lora**, **Source Serif** oder eine ruhige Sans wie **Source Sans 3** / **Inter** mit größerer Zeilenhöhe.
   - In `MarkdownView` (oder wo der Report gerendert wird): Klasse für den Report-Container, z. B. `.report-prose` oder `report-content`, mit:
     - `font-family: Georgia, "Times New Roman", serif;` (oder eine eingebundene Google Font).
     - `line-height: 1.7` bis `1.8`.
     - `font-size: 1.0625rem` oder `1.125rem` (gut lesbar).
     - Ausreichend `margin` für Absätze und Überschriften (z. B. `margin-bottom: 1em` für `p`, Überschriften hierarchisch).
   - Überschriften im Report (h1–h6) können in der Accent-Farbe oder in der normalen Textfarbe mit etwas mehr Gewicht sein – einheitlich und ruhig.
   - Listen und Zitate mit gutem Abstand; Code-Blöcke weiterhin in Mono, aber klar vom Fließtext getrennt.

2. **MarkdownView / ResearchDetailTabs:**
   - Im **Report-Tab** den Markdown-Container mit dieser neuen Report-Klasse versehen.
   - Sicherstellen, dass nur der Report-Inhalt (nicht die ganze App) diese Schrift nutzt, damit der Rest der UI konsistent bleibt.

**Dateien:**  
- `components/MarkdownView.tsx` oder die Report-Anzeige in `ResearchDetailTabs.tsx` anpassen.  
- `app/globals.css`: Klasse `.report-prose` (oder ähnlich) mit obigen Eigenschaften + ev. `@import` einer Google Font für die Leseschrift.

---

### 3.3 Research-Liste (`app/(dashboard)/research/page.tsx`)

**Ziel:** Klarere, einladendere Liste der Projekte.

- Tabellen- oder Karten-Ansicht: Jede Zeile/Karte soll die **Frage** (oder eine gekürzte Version) prominent zeigen, nicht die Projekt-ID.
- Phase und Status pro Projekt klar sichtbar (Badge oder kurzer Text).
- „Öffnen“-Link oder Klick auf die Zeile/Karte führt auf die neue Research-Detailseite (schöne Seite mit Phase-Glow und Report).
- Kurzbeschreibung unter der Überschrift der Seite: z. B. „Deine Forschungsprojekte. Klicke auf ein Projekt, um Fortschritt und Report zu sehen.“ – eine Zeile reicht.

---

### 3.4 Command Center & andere Bereiche (sauberer und verständlicher)

**Ziel:** Einheitlich klare Sprache und Hierarchie; weniger technisch, mehr menschlich.

- **Command Center (Dashboard):**
  - Überschrift z. B. „Überblick“ oder „Command Center“ beibehalten, darunter eine kurze Erklärung (eine Zeile).
  - Blöcke: „Aktuelle Research-Projekte“, „Letzte Aktionen“, „Quick-Actions“ – Bezeichnungen so, dass man sofort versteht, was gemeint ist.
  - Research-Projekt-Karten/Links: gleicher Stil wie auf der Research-Liste (Frage im Fokus, Phase sichtbar).

- **Jobs, Packs, Memory, Agents, Clients:**
  - Überschriften und Untertitel in verständlicher Sprache (z. B. „Laufende und abgeschlossene Jobs“ statt nur „Jobs“).
  - Tabellen oder Listen mit klaren Spaltenbeschriftungen; wo sinnvoll kurze Hilfetexte (ein Satz).

- **Allgemein:**
  - Keine nackten technischen IDs als einzige Hauptüberschrift; entweder Menschen-lesbarer Titel + ID als Zusatz oder klare Beschriftung (z. B. „Projekt: …“).
  - Einheitliche Abstände und Gruppierung (z. B. `space-y-6` oder `space-y-8` zwischen Sektionen), damit die Seite „atmet“.

---

## 4. Technische Hinweise für den Agent

- **Phase-Glow:** CSS z. B. `text-shadow: 0 0 20px var(--tron-glow), 0 0 40px var(--tron-glow);` und optional `box-shadow` auf einem umschließenden Element. Die Phase kann in Großbuchstaben oder mit erstem Buchstaben groß (z. B. „Explore“) angezeigt werden.
- **Farben und Tokens:** Bestehende CSS-Variablen (`--tron-*`) und Tailwind-Klassen (`text-tron-accent`, `border-tron-border` etc.) weiterverwenden; keine neuen wilden Farben.
- **Light Mode:** Alle Änderungen sollen im Light-Theme weiterhin gut lesbar und konsistent aussehen (Tokens werden bereits umgestellt).
- **Responsive:** Phase-Hero und Report-Bereich auf kleinen Screens lesbar halten (Schriftgröße anpassen, kein zu großer Glow auf Mobile).
- **Keine Logik-Änderungen:** Nur UI/Layout/Typografie/Text anpassen; keine Änderung an API, Datenmodell oder Workflows.

---

## 5. Reihenfolge der Umsetzung (Empfehlung)

1. **Research-Detailseite:** Hero mit Forschungsfrage als Titel + Phase groß mit Glow + Metadaten + Aktionen. (page.tsx + optional Hero-Komponente.)
2. **Report-Typografie:** Leseschrift und `.report-prose` in globals.css; MarkdownView/Report-Tab mit dieser Klasse.
3. **Research-Liste:** Frage prominent, Phase/Status klar, verständliche Kurzbeschreibung.
4. **Command Center & restliche Bereiche:** Überschriften und Blöcke verständlicher benennen, einheitliche Abstände, keine IDs als Haupttitel.

---

## 6. Abnahmekriterien (kurz)

- Beim Öffnen eines Research-Projekts ist sofort sichtbar: **welche Phase** (groß, mit Glow) und **welche Frage** (als Haupttitel).
- Der Report liest sich in **ruhiger, lesbarer Schrift** mit guter Zeilenhöhe und Abstand.
- Research-Liste und Detailseite wirken **sauber und einladend**; der Rest der App **einheitlich verständlicher** und weniger technisch.

Ende des Plans.
