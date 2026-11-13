PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS unified_facts (
    business_key TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT,               -- Название книги или название локации
    metric_numeric REAL,      -- Цена книги или температура
    collected_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    
    -- Проверки ограничений
    CHECK (metric_numeric >= 0 OR metric_numeric < 0), -- Универсальная проверка
    CHECK (length(business_key) > 3)
);

CREATE TABLE IF NOT EXISTS rejects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payload TEXT,
    reason TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_key TEXT,
    field TEXT,
    old_value TEXT,
    new_value TEXT,
    changed_at TEXT
);