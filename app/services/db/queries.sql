-- queries.sql

-- 🎯 PARTS QUERIES

-- 1. Get all parts with pagination
SELECT p.*, 
       (SELECT COUNT(*) FROM part_images pi WHERE pi.part_id = p.id) as image_count,
       (SELECT COUNT(*) FROM part_guides pg WHERE pg.part_id = p.id) as guide_count
FROM parts p
ORDER BY p.id
LIMIT ? OFFSET ?;

-- 2. Search parts by part number (exact match)
SELECT p.*, 
       GROUP_CONCAT(DISTINCT pi.image_filename) as images,
       GROUP_CONCAT(DISTINCT tg.display_name) as guides
FROM parts p
LEFT JOIN part_images pi ON p.id = pi.part_id
LEFT JOIN part_guides pg ON p.id = pg.part_id
LEFT JOIN technical_guides tg ON pg.guide_id = tg.id
WHERE p.part_number = ?
GROUP BY p.id;

-- 3. Search parts by description (fuzzy search)
SELECT p.*, 
       snippet(parts_fts, 2, '<b>', '</b>', '...', 64) as snippet
FROM parts_fts
JOIN parts p ON p.id = parts_fts.rowid
WHERE parts_fts MATCH ?
ORDER BY rank
LIMIT 50;

-- 4. Get parts by catalog
SELECT p.*, 
       COUNT(pi.id) as image_count
FROM parts p
LEFT JOIN part_images pi ON p.id = pi.part_id
WHERE p.catalog_name = ?
GROUP BY p.id
ORDER BY p.page, p.part_number;

-- 5. Get parts with images
SELECT p.id, p.part_number, p.description, p.catalog_name,
       pi.image_filename, pi.image_width, pi.image_height
FROM parts p
JOIN part_images pi ON p.id = pi.part_id
WHERE p.id = ?;

-- 6. Get parts statistics by catalog
SELECT catalog_name, 
       COUNT(*) as total_parts,
       COUNT(DISTINCT part_number) as unique_parts,
       AVG(LENGTH(description)) as avg_desc_length,
       COUNT(image_path) as parts_with_images
FROM parts
GROUP BY catalog_name
ORDER BY total_parts DESC;

-- 🎯 IMAGES QUERIES

-- 7. Get all images for a part
SELECT pi.* 
FROM part_images pi
WHERE pi.part_id = ?
ORDER BY pi.confidence DESC, pi.created_at DESC;

-- 8. Get image by filename
SELECT pi.*, p.part_number, p.description
FROM part_images pi
JOIN parts p ON pi.part_id = p.id
WHERE pi.image_filename = ?;

-- 9. Get images by catalog and page
SELECT pi.*, p.part_number
FROM part_images pi
JOIN parts p ON pi.part_id = p.id
WHERE p.catalog_name = ? AND pi.page_number = ?
ORDER BY p.part_number;

-- 10. Image statistics
SELECT 
    COUNT(*) as total_images,
    COUNT(DISTINCT part_id) as parts_with_images,
    AVG(file_size) as avg_file_size,
    MIN(file_size) as min_file_size,
    MAX(file_size) as max_file_size
FROM part_images;

-- 🎯 GUIDES QUERIES

-- 11. Get all technical guides
SELECT tg.*,
       COUNT(pg.part_id) as associated_parts
FROM technical_guides tg
LEFT JOIN part_guides pg ON tg.id = pg.guide_id
WHERE tg.is_active = 1
GROUP BY tg.id
ORDER BY tg.display_name;

-- 12. Get guide by ID with associated parts
SELECT tg.*,
       p.id as part_id, p.part_number, p.description,
       pg.confidence_score
FROM technical_guides tg
JOIN part_guides pg ON tg.id = pg.guide_id
JOIN parts p ON pg.part_id = p.id
WHERE tg.id = ?
ORDER BY pg.confidence_score DESC;

-- 13. Get guides for a specific part
SELECT tg.*, pg.confidence_score
FROM technical_guides tg
JOIN part_guides pg ON tg.id = pg.guide_id
WHERE pg.part_id = ?
ORDER BY pg.confidence_score DESC;

-- 14. Search guides by name or description
SELECT tg.*,
       COUNT(pg.part_id) as part_count
FROM technical_guides tg
LEFT JOIN part_guides pg ON tg.id = pg.guide_id
WHERE tg.display_name LIKE ? OR tg.description LIKE ?
GROUP BY tg.id
ORDER BY part_count DESC;

-- 🎯 ASSOCIATION QUERIES

-- 15. Create part-guide association
INSERT OR IGNORE INTO part_guides (part_id, guide_id, confidence_score)
VALUES (?, ?, ?);

-- 16. Remove part-guide association
DELETE FROM part_guides 
WHERE part_id = ? AND guide_id = ?;

-- 17. Get association statistics
SELECT 
    COUNT(*) as total_associations,
    COUNT(DISTINCT part_id) as unique_parts,
    COUNT(DISTINCT guide_id) as unique_guides,
    AVG(confidence_score) as avg_confidence
FROM part_guides;

-- 🎯 ANALYTICS QUERIES

-- 18. Catalog statistics
SELECT 
    catalog_name,
    COUNT(*) as part_count,
    COUNT(DISTINCT part_number) as unique_part_numbers,
    COUNT(DISTINCT category) as category_count,
    ROUND(COUNT(image_path) * 100.0 / COUNT(*), 2) as image_coverage_percent
FROM parts
GROUP BY catalog_name
ORDER BY part_count DESC;

-- 19. Category distribution
SELECT 
    category,
    COUNT(*) as part_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM parts), 2) as percentage
FROM parts
WHERE category IS NOT NULL AND category != ''
GROUP BY category
ORDER BY part_count DESC;

-- 20. Parts without images
SELECT p.*
FROM parts p
LEFT JOIN part_images pi ON p.id = pi.part_id
WHERE pi.id IS NULL
LIMIT 100;

-- 21. Parts without guides
SELECT p.*
FROM parts p
LEFT JOIN part_guides pg ON p.id = pg.part_id
WHERE pg.id IS NULL
LIMIT 100;

-- 22. Database health check
SELECT 
    (SELECT COUNT(*) FROM parts) as total_parts,
    (SELECT COUNT(*) FROM part_images) as total_images,
    (SELECT COUNT(*) FROM technical_guides) as total_guides,
    (SELECT COUNT(*) FROM part_guides) as total_associations,
    (SELECT COUNT(*) FROM parts WHERE image_path IS NOT NULL) as parts_with_image_reference,
    (SELECT COUNT(DISTINCT part_id) FROM part_images) as unique_parts_with_images;