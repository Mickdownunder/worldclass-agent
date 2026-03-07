# Test Suite Guide

Diese Tests laufen lokal gegen ein isoliertes Operator-Testlayout.

## Fixtures

- **`mock_operator_root`** — setzt `OPERATOR_ROOT` auf ein temporäres Verzeichnis mit minimaler Struktur.
- **`tmp_project`** — erstellt ein kanonisches Testprojekt unter `research/proj-test` inklusive `project.json` und Standardordnern.
- **`mock_env`** — setzt z. B. `RESEARCH_PROJECT_ID=proj-test` für Tests, die Env brauchen (keine echten API-Keys).
- **`memory_conn`** — liefert eine In-Memory-SQLite-DB mit initialisiertem Memory-Schema.
