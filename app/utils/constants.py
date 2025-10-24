# Part number patterns
PART_NUMBER_PATTERNS = [
    (r'\b([A-Z]{1,4}\d{2,4}(?:-\d+)?[A-Z]?)\b', 'part'),
    (r'\b(\d{5,7}[A-Z]?)\b', 'part'),
    (r'\b([A-Z]{2,}-[A-Z0-9]+(?:-[A-Z0-9]+)?)\b', 'part'),
    (r'\b(?:KIT|PK)[-_]?(\d+[A-Z]?)\b', 'kit'),
    (r'\b([A-Z]?\d+[A-Z]+|[A-Z]+\d+[A-Z]*)\b', 'model'),
    (r'\b(600-\d{3,4}[A-Z]?)\b', 'caliper'),
    (r'\b(CH\d{4})\b', 'kit'),
    (r'\b([A-Z0-9]+/[A-Z0-9]+)\b', 'part'),
]

# Machine patterns
MACHINE_PATTERNS = [
    r'\b(D[3-9]|D1[0-1]|[0-9]{3}[A-Z]?)\b',
    r'\b([0-9]{1,2}[A-Z]*\s*Series?)\b',
    r'\b([A-Z]+\s*[0-9]+[A-Z]*)\b',
]

# Catalog type indicators
CATALOG_INDICATORS = {
    'dayton': ['dayton', 'hydraulic brake'],
    'caterpillar': ['caterpillar', 'cat ', 'fp-'],
    'fort_pro': ['fort pro', 'fortpro', 'heavy duty'],
    'dana_spicer': ['dana', 'spicer', 'axle'],
    'cummins': ['cummins', 'engine'],
    'detroit': ['detroit diesel'],
    'international': ['international', 'navistar'],
}