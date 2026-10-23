-- Bounded shared demo state. The version guards every account/seat/audit transition.
CREATE TABLE IF NOT EXISTS sandbox_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL DEFAULT 0,
    payload TEXT NOT NULL DEFAULT ''
);
INSERT OR IGNORE INTO sandbox_state (id, version, payload) VALUES (1, 0, '');
