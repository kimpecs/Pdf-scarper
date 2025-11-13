-- Parts table
CREATE TABLE IF NOT EXISTS parts (
    id INTEGER PRIMARY KEY,
    catalog_name TEXT NOT NULL,
    catalog_type TEXT,
    part_type TEXT,
    part_number TEXT NOT NULL,
    description TEXT,
    category TEXT,
    page INTEGER,
    image_path TEXT,
    page_text TEXT,
    pdf_path TEXT,
    machine_info TEXT,
    specifications TEXT,
    oe_numbers TEXT,
    applications TEXT,
    features TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Technical guides table
CREATE TABLE IF NOT EXISTS technical_guides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guide_name TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    s3_key TEXT,
    template_fields TEXT,
    pdf_path TEXT,  -- ADDED: Store local PDF path
    related_parts TEXT,  -- ADDED: Store related parts as JSON
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Guide-Parts association table (NEW)
CREATE TABLE IF NOT EXISTS guide_parts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guide_id INTEGER,
    part_number TEXT,
    confidence_score REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guide_id) REFERENCES technical_guides (id),
    UNIQUE(guide_id, part_number)
);

-- Full Text Search table
CREATE VIRTUAL TABLE IF NOT EXISTS parts_fts USING fts5(
    catalog_name,
    catalog_type,
    part_number,
    description,
    page_text,
    machine_info,
    specifications,
    oe_numbers,
    applications,
    content='parts',
    content_rowid='id'
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_part_number ON parts(part_number);
CREATE INDEX IF NOT EXISTS idx_catalog_name ON parts(catalog_name);
CREATE INDEX IF NOT EXISTS idx_category ON parts(category);
CREATE INDEX IF NOT EXISTS idx_page ON parts(page);
CREATE INDEX IF NOT EXISTS idx_catalog_type ON parts(catalog_type);
CREATE INDEX IF NOT EXISTS idx_part_type ON parts(part_type);
CREATE INDEX IF NOT EXISTS idx_oe_numbers ON parts(oe_numbers);

-- NEW: Index for guide_parts table
CREATE INDEX IF NOT EXISTS idx_guide_parts_guide_id ON guide_parts(guide_id);
CREATE INDEX IF NOT EXISTS idx_guide_parts_part_number ON guide_parts(part_number);