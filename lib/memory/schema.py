"""Schema creation and migrations for the memory DB."""
import sqlite3


SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS episodes (
        id          TEXT PRIMARY KEY,
        ts          TEXT NOT NULL,
        kind        TEXT NOT NULL,
        job_id      TEXT,
        workflow_id TEXT,
        content     TEXT NOT NULL,
        metadata    TEXT DEFAULT '{}',
        embedding   BLOB
    );

    CREATE TABLE IF NOT EXISTS decisions (
        id          TEXT PRIMARY KEY,
        ts          TEXT NOT NULL,
        phase       TEXT NOT NULL,
        inputs      TEXT NOT NULL,
        reasoning   TEXT NOT NULL,
        decision    TEXT NOT NULL,
        confidence  REAL NOT NULL DEFAULT 0.5,
        trace_id    TEXT,
        job_id      TEXT,
        metadata    TEXT DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS reflections (
        id          TEXT PRIMARY KEY,
        ts          TEXT NOT NULL,
        job_id      TEXT NOT NULL,
        workflow_id TEXT,
        goal        TEXT,
        outcome     TEXT NOT NULL,
        went_well   TEXT,
        went_wrong  TEXT,
        learnings   TEXT,
        quality     REAL NOT NULL DEFAULT 0.5,
        metadata    TEXT DEFAULT '{}',
        embedding   BLOB
    );

    CREATE TABLE IF NOT EXISTS playbooks (
        id          TEXT PRIMARY KEY,
        ts_created  TEXT NOT NULL,
        ts_updated  TEXT NOT NULL,
        domain      TEXT NOT NULL,
        strategy    TEXT NOT NULL,
        evidence    TEXT DEFAULT '[]',
        success_rate REAL DEFAULT 0.0,
        version     INTEGER DEFAULT 1,
        metadata    TEXT DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS quality_scores (
        id          TEXT PRIMARY KEY,
        ts          TEXT NOT NULL,
        job_id      TEXT NOT NULL,
        workflow_id TEXT,
        score       REAL NOT NULL,
        dimension   TEXT DEFAULT 'overall',
        notes       TEXT DEFAULT ''
    );

    CREATE INDEX IF NOT EXISTS idx_episodes_kind ON episodes(kind);
    CREATE INDEX IF NOT EXISTS idx_episodes_job ON episodes(job_id);
    CREATE INDEX IF NOT EXISTS idx_episodes_ts ON episodes(ts DESC);
    CREATE INDEX IF NOT EXISTS idx_reflections_job ON reflections(job_id);
    CREATE INDEX IF NOT EXISTS idx_reflections_quality ON reflections(quality DESC);
    CREATE INDEX IF NOT EXISTS idx_decisions_trace ON decisions(trace_id);
    CREATE INDEX IF NOT EXISTS idx_quality_workflow ON quality_scores(workflow_id);

    CREATE TABLE IF NOT EXISTS research_findings (
        id              TEXT PRIMARY KEY,
        project_id      TEXT NOT NULL,
        finding_key     TEXT NOT NULL,
        content_preview  TEXT NOT NULL,
        embedding_json  TEXT,
        ts              TEXT NOT NULL,
        url             TEXT,
        title           TEXT
    );
    CREATE TABLE IF NOT EXISTS memory_admission_events (
        id              TEXT PRIMARY KEY,
        ts             TEXT NOT NULL,
        project_id      TEXT NOT NULL,
        finding_key     TEXT NOT NULL,
        decision        TEXT NOT NULL,
        reason         TEXT DEFAULT '',
        scores_json    TEXT DEFAULT '{}'
    );
    CREATE INDEX IF NOT EXISTS idx_admission_events_project ON memory_admission_events(project_id);
    CREATE INDEX IF NOT EXISTS idx_admission_events_ts ON memory_admission_events(ts DESC);
    CREATE TABLE IF NOT EXISTS cross_links (
        id              TEXT PRIMARY KEY,
        finding_a_id    TEXT NOT NULL,
        finding_b_id    TEXT NOT NULL,
        project_a       TEXT NOT NULL,
        project_b       TEXT NOT NULL,
        similarity      REAL NOT NULL,
        ts              TEXT NOT NULL,
        notified        INTEGER DEFAULT 0,
        UNIQUE(finding_a_id, finding_b_id)
    );
    CREATE INDEX IF NOT EXISTS idx_research_findings_project ON research_findings(project_id);
    CREATE INDEX IF NOT EXISTS idx_cross_links_projects ON cross_links(project_a, project_b);

    CREATE TABLE IF NOT EXISTS entities (
        id              TEXT PRIMARY KEY,
        name            TEXT NOT NULL,
        type            TEXT NOT NULL,
        properties_json  TEXT DEFAULT '{}',
        first_seen_project TEXT,
        created_at      TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS entity_relations (
        id              TEXT PRIMARY KEY,
        entity_a_id     TEXT NOT NULL,
        entity_b_id     TEXT NOT NULL,
        relation_type   TEXT NOT NULL,
        source_project  TEXT NOT NULL,
        evidence        TEXT DEFAULT '',
        created_at     TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS entity_mentions (
        id              TEXT PRIMARY KEY,
        entity_id      TEXT NOT NULL,
        project_id     TEXT NOT NULL,
        finding_key    TEXT,
        context_snippet TEXT DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
    CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
    CREATE INDEX IF NOT EXISTS idx_entity_mentions_project ON entity_mentions(project_id);

    CREATE TABLE IF NOT EXISTS strategic_principles (
        id TEXT PRIMARY KEY,
        principle_type TEXT NOT NULL,
        description TEXT NOT NULL,
        domain TEXT,
        source_project_id TEXT NOT NULL,
        evidence_json TEXT DEFAULT '[]',
        metric_score REAL DEFAULT 0.5,
        usage_count INTEGER DEFAULT 0,
        success_count INTEGER DEFAULT 0,
        embedding_json TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS memory_utility (
        memory_type TEXT NOT NULL,
        memory_id TEXT NOT NULL,
        utility_score REAL DEFAULT 0.5,
        retrieval_count INTEGER DEFAULT 0,
        helpful_count INTEGER DEFAULT 0,
        last_updated TEXT,
        PRIMARY KEY (memory_type, memory_id)
    );
    CREATE TABLE IF NOT EXISTS project_outcomes (
        project_id TEXT PRIMARY KEY,
        domain TEXT,
        critic_score REAL,
        user_verdict TEXT,
        gate_metrics_json TEXT,
        strategy_used TEXT,
        principles_used_json TEXT,
        findings_count INTEGER,
        source_count INTEGER,
        completed_at TEXT
    );
    CREATE TABLE IF NOT EXISTS source_credibility (
        domain TEXT PRIMARY KEY,
        times_used INTEGER DEFAULT 0,
        verified_count INTEGER DEFAULT 0,
        failed_verification_count INTEGER DEFAULT 0,
        learned_credibility REAL DEFAULT 0.5,
        last_updated TEXT
    );
    CREATE TABLE IF NOT EXISTS run_episodes (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        question TEXT NOT NULL,
        domain TEXT,
        status TEXT NOT NULL,
        plan_query_mix_json TEXT DEFAULT '{}',
        source_mix_json TEXT DEFAULT '{}',
        gate_metrics_json TEXT DEFAULT '{}',
        critic_score REAL,
        user_verdict TEXT,
        fail_codes_json TEXT DEFAULT '[]',
        what_helped_json TEXT DEFAULT '[]',
        what_hurt_json TEXT DEFAULT '[]',
        strategy_profile_id TEXT,
        created_at TEXT NOT NULL,
        run_index INTEGER DEFAULT 1,
        memory_mode TEXT,
        strategy_confidence REAL,
        verified_claim_count INTEGER,
        claim_support_rate REAL
    );
    CREATE TABLE IF NOT EXISTS memory_utility_context (
        memory_type TEXT NOT NULL,
        memory_id TEXT NOT NULL,
        context_key TEXT NOT NULL,
        utility_score REAL DEFAULT 0.5,
        retrieval_count INTEGER DEFAULT 0,
        helpful_count INTEGER DEFAULT 0,
        last_updated TEXT,
        PRIMARY KEY (memory_type, memory_id, context_key)
    );
    CREATE TABLE IF NOT EXISTS strategy_profiles (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        domain TEXT,
        policy_json TEXT NOT NULL,
        score REAL DEFAULT 0.5,
        confidence REAL DEFAULT 0.5,
        usage_count INTEGER DEFAULT 0,
        success_count INTEGER DEFAULT 0,
        fail_count INTEGER DEFAULT 0,
        status TEXT DEFAULT 'active',
        version INTEGER DEFAULT 1,
        metadata_json TEXT DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(name, domain, version)
    );
    CREATE TABLE IF NOT EXISTS strategy_application_events (
        id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        project_id TEXT NOT NULL,
        strategy_profile_id TEXT,
        phase TEXT NOT NULL,
        applied_policy_json TEXT DEFAULT '{}',
        fallback_used INTEGER DEFAULT 0,
        outcome_hint TEXT DEFAULT '',
        status TEXT DEFAULT 'ok'
    );
    CREATE TABLE IF NOT EXISTS source_domain_stats_v2 (
        domain TEXT NOT NULL,
        topic_domain TEXT NOT NULL,
        times_seen INTEGER DEFAULT 0,
        verified_hits INTEGER DEFAULT 0,
        relevant_hits INTEGER DEFAULT 0,
        fail_hits INTEGER DEFAULT 0,
        last_updated TEXT NOT NULL,
        PRIMARY KEY (domain, topic_domain)
    );
    CREATE TABLE IF NOT EXISTS memory_decision_log (
        id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        project_id TEXT,
        phase TEXT,
        decision_type TEXT NOT NULL,
        strategy_profile_id TEXT,
        confidence REAL DEFAULT 0.5,
        details_json TEXT DEFAULT '{}'
    );
    CREATE TABLE IF NOT EXISTS memory_graph_edges (
        id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        edge_type TEXT NOT NULL,
        from_node_type TEXT NOT NULL,
        from_node_id TEXT NOT NULL,
        to_node_type TEXT NOT NULL,
        to_node_id TEXT NOT NULL,
        project_id TEXT
    );
    CREATE TABLE IF NOT EXISTS read_urls (
        question_hash TEXT NOT NULL,
        url TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (question_hash, url)
    );
    CREATE INDEX IF NOT EXISTS idx_read_urls_question ON read_urls(question_hash);
    CREATE INDEX IF NOT EXISTS idx_strategic_principles_domain ON strategic_principles(domain);
    CREATE INDEX IF NOT EXISTS idx_strategic_principles_type ON strategic_principles(principle_type);
    CREATE INDEX IF NOT EXISTS idx_run_episodes_domain ON run_episodes(domain);
    CREATE INDEX IF NOT EXISTS idx_run_episodes_status ON run_episodes(status);
    CREATE INDEX IF NOT EXISTS idx_run_episodes_created ON run_episodes(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_strategy_profiles_domain ON strategy_profiles(domain, status);
    CREATE INDEX IF NOT EXISTS idx_strategy_profiles_score ON strategy_profiles(score DESC, confidence DESC);
    CREATE INDEX IF NOT EXISTS idx_strategy_app_project ON strategy_application_events(project_id, ts DESC);
    CREATE INDEX IF NOT EXISTS idx_source_domain_stats_topic ON source_domain_stats_v2(topic_domain, verified_hits DESC);
    CREATE INDEX IF NOT EXISTS idx_memory_decision_project ON memory_decision_log(project_id, ts DESC);
    CREATE INDEX IF NOT EXISTS idx_memory_graph_from ON memory_graph_edges(from_node_type, from_node_id);
    CREATE INDEX IF NOT EXISTS idx_memory_graph_to ON memory_graph_edges(to_node_type, to_node_id);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    migrate_run_episodes_project_unique(conn)
    migrate_research_findings_quality(conn)
    migrate_run_episodes_memory_value(conn)
    migrate_run_episodes_run_index(conn)
    migrate_read_urls_signature(conn)


def migrate_research_findings_quality(conn: sqlite3.Connection) -> None:
    """Add quality/admission columns to research_findings if missing (backward compat)."""
    cur = conn.execute("PRAGMA table_info(research_findings)")
    existing = {row[1] for row in cur.fetchall()}
    new_cols = [
        ("relevance_score", "REAL"),
        ("reliability_score", "REAL"),
        ("verification_status", "TEXT"),
        ("evidence_count", "INTEGER"),
        ("critic_score", "REAL"),
        ("importance_score", "REAL"),
        ("admission_state", "TEXT"),
    ]
    for name, typ in new_cols:
        if name not in existing:
            conn.execute(f"ALTER TABLE research_findings ADD COLUMN {name} {typ}")
    conn.execute(
        "UPDATE research_findings SET admission_state = 'quarantined' WHERE admission_state IS NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_research_findings_admission ON research_findings(admission_state)"
    )
    conn.commit()


def migrate_run_episodes_memory_value(conn: sqlite3.Connection) -> None:
    """Add memory_value columns to run_episodes (Priority 1: Memory Value Score)."""
    cur = conn.execute("PRAGMA table_info(run_episodes)")
    existing = {row[1] for row in cur.fetchall()}
    for name, typ in [
        ("memory_mode", "TEXT"),
        ("strategy_confidence", "REAL"),
        ("verified_claim_count", "INTEGER"),
        ("claim_support_rate", "REAL"),
    ]:
        if name not in existing:
            conn.execute(f"ALTER TABLE run_episodes ADD COLUMN {name} {typ}")
    conn.commit()


def migrate_run_episodes_run_index(conn: sqlite3.Connection) -> None:
    """Add run_index to run_episodes for per-project run history ordering."""
    cur = conn.execute("PRAGMA table_info(run_episodes)")
    existing = {row[1] for row in cur.fetchall()}
    if "run_index" not in existing:
        conn.execute("ALTER TABLE run_episodes ADD COLUMN run_index INTEGER DEFAULT 1")
    conn.commit()


def migrate_read_urls_signature(conn: sqlite3.Connection) -> None:
    """Add question_signature for semantic-ish dedup (similar questions return same URLs)."""
    cur = conn.execute("PRAGMA table_info(read_urls)")
    existing = {row[1] for row in cur.fetchall()}
    if "question_signature" not in existing:
        conn.execute("ALTER TABLE read_urls ADD COLUMN question_signature TEXT DEFAULT ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_read_urls_signature ON read_urls(question_signature)")
    conn.commit()


def migrate_run_episodes_project_unique(conn: sqlite3.Connection) -> None:
    """
    Remove old UNIQUE(project_id) constraint on run_episodes.
    Older DBs used one-row-per-project semantics (INSERT OR REPLACE); rebuild table once.
    """
    cur = conn.execute("PRAGMA index_list(run_episodes)")
    idx_rows = cur.fetchall()
    has_project_unique = False
    for row in idx_rows:
        idx_name = row[1]
        is_unique = int(row[2]) == 1
        if not is_unique:
            continue
        cols = conn.execute(f"PRAGMA index_info({idx_name!r})").fetchall()
        col_names = [c[2] for c in cols]
        if col_names == ["project_id"]:
            has_project_unique = True
            break
    if not has_project_unique:
        return

    cols = {row[1] for row in conn.execute("PRAGMA table_info(run_episodes)").fetchall()}
    run_index_expr = "COALESCE(run_index, 1)" if "run_index" in cols else "1"

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS run_episodes_new (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            question TEXT NOT NULL,
            domain TEXT,
            status TEXT NOT NULL,
            plan_query_mix_json TEXT DEFAULT '{}',
            source_mix_json TEXT DEFAULT '{}',
            gate_metrics_json TEXT DEFAULT '{}',
            critic_score REAL,
            user_verdict TEXT,
            fail_codes_json TEXT DEFAULT '[]',
            what_helped_json TEXT DEFAULT '[]',
            what_hurt_json TEXT DEFAULT '[]',
            strategy_profile_id TEXT,
            created_at TEXT NOT NULL,
            run_index INTEGER DEFAULT 1,
            memory_mode TEXT,
            strategy_confidence REAL,
            verified_claim_count INTEGER,
            claim_support_rate REAL
        );
        """
    )
    conn.execute(
        f"""
        INSERT INTO run_episodes_new (
            id, project_id, question, domain, status, plan_query_mix_json, source_mix_json,
            gate_metrics_json, critic_score, user_verdict, fail_codes_json, what_helped_json,
            what_hurt_json, strategy_profile_id, created_at, run_index, memory_mode,
            strategy_confidence, verified_claim_count, claim_support_rate
        )
        SELECT
            id, project_id, question, domain, status, plan_query_mix_json, source_mix_json,
            gate_metrics_json, critic_score, user_verdict, fail_codes_json, what_helped_json,
            what_hurt_json, strategy_profile_id, created_at, {run_index_expr},
            memory_mode, strategy_confidence, verified_claim_count, claim_support_rate
        FROM run_episodes
        """
    )
    conn.executescript(
        """
        DROP TABLE run_episodes;
        ALTER TABLE run_episodes_new RENAME TO run_episodes;
        CREATE INDEX IF NOT EXISTS idx_run_episodes_domain ON run_episodes(domain);
        CREATE INDEX IF NOT EXISTS idx_run_episodes_status ON run_episodes(status);
        CREATE INDEX IF NOT EXISTS idx_run_episodes_created ON run_episodes(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_run_episodes_project ON run_episodes(project_id, created_at DESC);
        """
    )
    conn.commit()
