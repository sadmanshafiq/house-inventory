CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    parent_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    photo_filename TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS items (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    location_id INTEGER NOT NULL REFERENCES locations(id) ON DELETE RESTRICT,
    tags TEXT[] NOT NULL DEFAULT '{}',
    photo_filename TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    -- Auto-maintained Full-Text Search column over name + description
    search_vector TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(name, '') || ' ' || coalesce(description, ''))
    ) STORED
);

-- Fast GIN indexes for Full-Text Search and Tag array filtering
CREATE INDEX IF NOT EXISTS idx_items_search ON items USING GIN (search_vector);
CREATE INDEX IF NOT EXISTS idx_items_tags ON items USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_locations_parent ON locations(parent_id);