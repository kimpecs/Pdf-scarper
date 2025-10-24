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
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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