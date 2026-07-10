-- name: candidates
WITH latest_decisions AS (
    SELECT ticket_id, disposition,
           ROW_NUMBER() OVER (PARTITION BY ticket_id ORDER BY id DESC) AS row_number
    FROM triage_decisions
)
SELECT
    t.azure_id AS id,
    t.title,
    t.work_item_type AS type,
    t.state,
    t.team_project AS project,
    t.priority,
    t.severity,
    t.tags,
    t.changed_at,
    t.source_url
FROM tickets AS t
LEFT JOIN latest_decisions AS d
    ON d.ticket_id = t.azure_id AND d.row_number = 1
LEFT JOIN work_items AS w ON w.ticket_id = t.azure_id
WHERE NOT EXISTS (
    SELECT 1 FROM terminal_states AS terminal
    WHERE terminal.state = t.state
)
AND COALESCE(d.disposition, '') NOT IN ('deferred', 'rejected', 'duplicate')
AND w.ticket_id IS NULL
ORDER BY
    CASE WHEN t.priority IS NULL THEN 1 ELSE 0 END,
    t.priority ASC,
    t.changed_at ASC,
    t.azure_id ASC
LIMIT :limit;

-- name: stale
WITH latest_decisions AS (
    SELECT ticket_id, disposition,
           ROW_NUMBER() OVER (PARTITION BY ticket_id ORDER BY id DESC) AS row_number
    FROM triage_decisions
)
SELECT
    t.azure_id AS id,
    t.title,
    t.work_item_type AS type,
    t.state,
    t.priority,
    t.changed_at,
    t.source_url
FROM tickets AS t
LEFT JOIN latest_decisions AS d
    ON d.ticket_id = t.azure_id AND d.row_number = 1
LEFT JOIN work_items AS w ON w.ticket_id = t.azure_id
WHERE NOT EXISTS (
    SELECT 1 FROM terminal_states AS terminal
    WHERE terminal.state = t.state
)
AND COALESCE(d.disposition, '') NOT IN ('deferred', 'rejected', 'duplicate')
AND w.ticket_id IS NULL
AND datetime(t.changed_at) <= datetime('now', '-' || :days || ' days')
ORDER BY t.changed_at ASC, t.priority ASC, t.azure_id ASC
LIMIT :limit;

-- name: in_flight
SELECT
    w.ticket_id AS id,
    t.title,
    w.brief_status,
    w.target_repository,
    w.brief_path,
    w.synced_at
FROM work_items AS w
JOIN tickets AS t ON t.azure_id = w.ticket_id
ORDER BY w.synced_at DESC, w.ticket_id ASC;

-- name: duplicates
SELECT
    t.azure_id AS id,
    t.title,
    t.state,
    t.team_project AS project,
    t.changed_at,
    ROUND(bm25(ticket_fts), 4) AS similarity_rank,
    t.source_url
FROM ticket_fts
JOIN tickets AS t ON t.rowid = ticket_fts.rowid
WHERE ticket_fts MATCH :match
AND t.azure_id <> :ticket_id
ORDER BY similarity_rank ASC, t.changed_at DESC
LIMIT :limit;
