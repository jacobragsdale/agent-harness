PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tickets (
    azure_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    acceptance_criteria TEXT NOT NULL DEFAULT '',
    repro_steps TEXT NOT NULL DEFAULT '',
    work_item_type TEXT NOT NULL,
    state TEXT NOT NULL,
    reason TEXT,
    team_project TEXT,
    area_path TEXT,
    iteration_path TEXT,
    tags TEXT NOT NULL DEFAULT '',
    priority INTEGER,
    backlog_rank REAL,
    stack_rank REAL,
    severity TEXT,
    assigned_to TEXT,
    created_at TEXT,
    changed_at TEXT,
    source_url TEXT,
    raw_json TEXT NOT NULL,
    imported_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS tickets_priority_changed_idx
    ON tickets(priority, changed_at DESC);
CREATE INDEX IF NOT EXISTS tickets_project_state_idx
    ON tickets(team_project, state);

CREATE TABLE IF NOT EXISTS terminal_states (
    state TEXT PRIMARY KEY COLLATE NOCASE
);

INSERT OR IGNORE INTO terminal_states(state) VALUES
    ('Closed'),
    ('Done'),
    ('Removed');

CREATE TABLE IF NOT EXISTS triage_decisions (
    id INTEGER PRIMARY KEY,
    ticket_id TEXT NOT NULL REFERENCES tickets(azure_id),
    disposition TEXT NOT NULL CHECK (disposition IN ('deferred', 'rejected', 'duplicate')),
    rationale TEXT NOT NULL,
    duplicate_of TEXT,
    decided_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS triage_decisions_ticket_id_idx
    ON triage_decisions(ticket_id, id DESC);

CREATE TABLE IF NOT EXISTS work_items (
    ticket_id TEXT PRIMARY KEY REFERENCES tickets(azure_id),
    brief_path TEXT NOT NULL,
    brief_status TEXT NOT NULL,
    target_repository TEXT,
    synced_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS ticket_fts USING fts5(
    title,
    description,
    content = 'tickets',
    content_rowid = 'rowid'
);

CREATE TRIGGER IF NOT EXISTS tickets_ai AFTER INSERT ON tickets BEGIN
    INSERT INTO ticket_fts(rowid, title, description)
    VALUES (new.rowid, new.title, new.description);
END;

CREATE TRIGGER IF NOT EXISTS tickets_ad AFTER DELETE ON tickets BEGIN
    INSERT INTO ticket_fts(ticket_fts, rowid, title, description)
    VALUES ('delete', old.rowid, old.title, old.description);
END;

CREATE TRIGGER IF NOT EXISTS tickets_au AFTER UPDATE ON tickets BEGIN
    INSERT INTO ticket_fts(ticket_fts, rowid, title, description)
    VALUES ('delete', old.rowid, old.title, old.description);
    INSERT INTO ticket_fts(rowid, title, description)
    VALUES (new.rowid, new.title, new.description);
END;
