# Part number patterns
PART_NUMBER_PATTERNS = [
    (r'\b([A-Z]{2,3}-\d{4}(?:-[A-Z0-9]+(?:\([A-Z]\))?)?)\b', 'part'),  
    (r'\b([A-Z]{3}-\d{4}-[A-Z0-9]{3})\b', 'part'),  
    (r'\b([A-Z]{3}-\d{4}-\(\*\))\b', 'part'), 
    (r'\b([A-Z]{2}\d-\d{4})\b', 'part'),  
    (r'\b(\d{6,7})\b', 'part'),  
    
    # OEM reference patterns
    (r'\b(MAK\s+[\dA-Z]+(?:P\d+)?)\b', 'oem'), 
    (r'\b(AMB\s+[A-Z0-9]+)\b', 'oem'), 
    (r'\b(SCH\s+\d+)\b', 'oem'), 
    (r'\b(AIR\s+\d+-\d+)\b', 'oem'),  
    (r'\b(RBB\s+\d+)\b', 'oem'),  
    (r'\b(NAT\s+[A-Z0-9]+)\b', 'oem'), 
    (r'\b(BCA\s+\d+[A-Z]?)\b', 'oem'), 
    (r'\b(MAK\s+[\dA-Z]+(?:P\d+)?)\b', 'oem'), 
    (r'\b(AMB\s+[A-Z0-9]+)\b', 'oem'), 
    (r'\b(SCH\s+\d+)\b', 'oem'), 
    (r'\b(AIR\s+\d+-\d+)\b', 'oem'),  
    (r'\b(RBB\s+\d+)\b', 'oem'),  
    (r'\b(NAT\s+[A-Z0-9]+)\b', 'oem'), 
    (r'\b(BCA\s+\d+[A-Z]?)\b', 'oem'), 
    
    # Kit patterns
    (r'\b(KIT[,:].*?(?:[A-Z]{2,3}-\d{4}|MAK\s+[\dA-Z]+))\b', 'kit'),
    (r'\b(ASSEMBLY[,:].*?(?:[A-Z]{2,3}-\d{4}|MAK\s+[\dA-Z]+))\b', 'kit'),
    (r'\b(SET[,:].*?(?:[A-Z]{2,3}-\d{4}|MAK\s+[\dA-Z]+))\b', 'kit'),
    (r'\b(Includes.*?(?:[A-Z]{2,3}-\d{4}|MAK\s+[\dA-Z]+))\b', 'kit'),
    (r'\b(KIT[,:].*?(?:[A-Z]{2,3}-\d{4}|MAK\s+[\dA-Z]+))\b', 'kit'),
    (r'\b(ASSEMBLY[,:].*?(?:[A-Z]{2,3}-\d{4}|MAK\s+[\dA-Z]+))\b', 'kit'),
    (r'\b(SET[,:].*?(?:[A-Z]{2,3}-\d{4}|MAK\s+[\dA-Z]+))\b', 'kit'),
    (r'\b(Includes.*?(?:[A-Z]{2,3}-\d{4}|MAK\s+[\dA-Z]+))\b', 'kit'),
    
    # Caliper and brake patterns 
    (r'\b(BRAKE.*?(?:[A-Z]{2,3}-\d{4}|MAK\s+[\dA-Z]+))\b', 'brake'),
    (r'\b(CALIPER.*?(?:[A-Z]{2,3}-\d{4}|MAK\s+[\dA-Z]+))\b', 'caliper'),
    (r'\b(\d{6}(?:[.-]\d+)?)\b', 'part'),
    (r'\b(V\d+[A-Z0-9]+)\b', 'part'),
    (r'\b(?:Kit|Complete pair|Mirror.*Kit|Assembly|Bracket.*Kit).*?\b(\d{6}(?:[.-]\d+)?|V\d+[A-Z0-9]+)\b', 'kit'),
    (r'\b(?:Bracket.*Only|Bracket Assembly).*?\b(\d{6}(?:[.-]\d+)?|V\d+[A-Z0-9]+)\b', 'bracket'),
    (r'\b(?:Replacement|Glass Kit|Head.*Only|Actuator|Cover|Motor|Switch|Harness).*?\b(\d{6}(?:[.-]\d+)?|V\d+[A-Z0-9]+)\b', 'replacement'),
    (r'\b(?:Accessories|Marker Light|Clamp.*Kit).*?\b(\d{6}(?:[.-]\d+)?|V\d+[A-Z0-9]+)\b', 'accessory'),
    (r'\b([A-Z]{1,4}\d{2,4}(?:-\d+)?[A-Z]?)\b', 'part'),
    (r'\b(\d{5,7}[A-Z]?)\b', 'part'),
    (r'\b([A-Z]{2,}-[A-Z0-9]+(?:-[A-Z0-9]+)?)\b', 'part'),
    (r'\b(?:KIT|PK)[-_]?(\d+[A-Z]?)\b', 'kit'),
    (r'\b([A-Z]?\d+[A-Z]+|[A-Z]+\d+[A-Z]*)\b', 'model'),
    (r'\b(600-\d{3,4}[A-Z]?)\b', 'caliper'),
    (r'\b(CH\d{4})\b', 'kit'),
    (r'\b([A-Z0-9]+/[A-Z0-9]+)\b', 'part'),
    
    # Pacific Truck transmission assembly patterns
    (r'\b(TA-[A-Z0-9]+-\d+[A-Z]?)\b', 'part'),
    (r'\b(RTLO?-\d+[A-Z]*\*?)\b', 'part'),
    (r'\b(FR0?-\d+[A-Z]*)\b', 'part'),
    (r'\b(FS-\d+[A-Z]*)\b', 'part'),
    
    # Pacific Truck kit patterns (from transmission kits)
    (r'\b(K-\d{4})\b', 'kit'),
    (r'\b(\d{3}-\d{3}-\d+X)\b', 'kit'),
    (r'\b(HD Transmission Kit)\b', 'kit'),
    
    # Pacific Truck transmission parts
    (r'\b([A-Z]\d{4,5})\b', 'part'),
    (r'\b([A-Z]\d{2}-\d{4})\b', 'part'),
    (r'\b([A-Z]-\d{4})\b', 'part'),
    (r'\b(S\d{4}[A-Z]?)\b', 'part'),
    (r'\b(X\d{2}-\d{4})\b', 'part'),
    
    # Pacific Truck clutch assemblies
    (r'\b(\d{6}-\d{2}[AM]?[0-9]?)\b', 'part'),
    (r'\b(MU\d{5,6}-[A-Z0-9]+)\b', 'part'),
    (r'\b(AN\d{6,7}-[A-Z0-9]+)\b', 'part'),
    (r'\b(NMU\d{3}-\d{3}-\d)\b', 'part'),
    
    # Pacific Truck Eaton clutch patterns
    (r'\b(\d{6}-\d)\b', 'part'),
    (r'\b(MU-\d{5}-\d)\b', 'part'),
    
    # Pacific Truck flywheel patterns
    (r'\b(\d{7})\b', 'part'),
    (r'\b(\d{8}[A-Z]?)\b', 'part'),
    (r'\b(\d{9}[A-Z]?)\b', 'part'),
    
    # Pacific Truck pilot bearing patterns
    (r'\b(TK\d{3}[A-Z]{2})\b', 'part'),
    (r'\b(TK\d{3}[A-Z]{3})\b', 'part'),
    
    # Pacific Truck clutch brake patterns
    (r'\b(TKW-\d{4})\b', 'part'),
    (r'\b([A-Z]{2}T\d{3})\b', 'part'),
    (r'\b(BK\d{3})\b', 'part'),
    (r'\b(SB\d{3})\b', 'part'),
    
    # Pacific Truck accessories
    (r'\b([A-Z]{2}S\d{3})\b', 'part'),
    (r'\b(M-[A-Z]\d{2,3})\b', 'part'),
    (r'\b(\d{3}C-\d+)\b', 'part'),
    (r'\b(CIT\d{3}[A-Z]?)\b', 'part'),
    (r'\b(RC\d{4}K)\b', 'part'),
    
    # Pacific Truck U-joint patterns
    (r'\b(\d-\d{3,4}X)\b', 'part'),
    (r'\b(CP\d+X)\b', 'part'),
    (r'\b(AR-\d{2,3})\b', 'part'),
    (r'\b(M\d+X)\b', 'part'),
    (r'\b(SP\d+-\dX)\b', 'part'),
    (r'\b(US\d+X)\b', 'part'),
    
    # Pacific Truck yoke patterns
    (r'\b(\d+-\d+-\d+[A-Z]*)\b', 'part'),
    (r'\b([A-Z]{2,3}N[A-Z0-9]+)\b', 'part'),
    (r'\b(N\d+-\d+-\d+[A-Z]*)\b', 'part'),
    
    # Pacific Truck center bearing patterns
    (r'\b(\d{6}[A-Z]?X)\b', 'part'),
    (r'\b(\(B2\)\d+X)\b', 'part'),
    (r'\b(N\d+X)\b', 'part'),
    
    # Pacific Truck companion flange patterns
    (r'\b(\d+\+\d+)\b', 'part'),
    (r'\b(\d{7})\b', 'part'),
    
    # Pacific Truck shaft sleeve patterns
    (r'\b(99\d{3})\b', 'part'),
    
    # Pacific Truck differential patterns
    (r'\b([A-Z]\dS[A-Z0-9]+)\b', 'part'),
    (r'\b(DT00P[A-Z0-9]+CF)\b', 'part'),
    (r'\b(DS\d+[A-Z0-9]+CF?)\b', 'part'),
    (r'\b(RS\d+[A-Z0-9]+CF?)\b', 'part'),
    (r'\b(CR0\(P\)\d+[A-Z])\b', 'part'),
    
    # Pacific Truck ring & pinion patterns
    (r'\b(\d{5}/\d{5})\b', 'part'),
    (r'\b(B\d{5}-\d)\b', 'part'),
    
    # Pacific Truck carrier seal patterns
    (r'\b(\d{5,6}K)\b', 'part'),
    (r'\b(DT\d+)\b', 'part'),
    (r'\b(GGAHIH05)\b', 'part'),
    (r'\b(\d+HIH\d{2})\b', 'part'),
    (r'\b(AI-\d+Z\d{3})\b', 'part'),
    
    # Pacific Truck overhaul kit patterns
    (r'\b(TKRA\d+[A-Z]*)\b', 'kit'),
    (r'\b(KIT\d{4})\b', 'kit'),
    
    # Pacific Truck axle shaft patterns
    (r'\b(T\d{5}[A-Z]?)\b', 'part'),
    (r'\b(\d+T\d+[A-Z]\d)\b', 'part'),
    (r'\b(\d{10})\b', 'part'),
    (r'\b(\d{4}[A-Z]\d{4})\b', 'part'),
    (r'\b(\d{2}KH\d{4}[A-Z]?\d?)\b', 'part'),
(r'\b(BRAKE.*?(?:[A-Z]{2,3}-\d{4}|MAK\s+[\dA-Z]+))\b', 'brake'),
    (r'\b(CALIPER.*?(?:[A-Z]{2,3}-\d{4}|MAK\s+[\dA-Z]+))\b', 'caliper'),
    (r'\b(\d{6}(?:[.-]\d+)?)\b', 'part'),
    (r'\b(V\d+[A-Z0-9]+)\b', 'part'),
    (r'\b(?:Kit|Complete pair|Mirror.*Kit|Assembly|Bracket.*Kit).*?\b(\d{6}(?:[.-]\d+)?|V\d+[A-Z0-9]+)\b', 'kit'),
    (r'\b(?:Bracket.*Only|Bracket Assembly).*?\b(\d{6}(?:[.-]\d+)?|V\d+[A-Z0-9]+)\b', 'bracket'),
    (r'\b(?:Replacement|Glass Kit|Head.*Only|Actuator|Cover|Motor|Switch|Harness).*?\b(\d{6}(?:[.-]\d+)?|V\d+[A-Z0-9]+)\b', 'replacement'),
    (r'\b(?:Accessories|Marker Light|Clamp.*Kit).*?\b(\d{6}(?:[.-]\d+)?|V\d+[A-Z0-9]+)\b', 'accessory'),
    (r'\b([A-Z]{1,4}\d{2,4}(?:-\d+)?[A-Z]?)\b', 'part'),
    (r'\b(\d{5,7}[A-Z]?)\b', 'part'),
    (r'\b([A-Z]{2,}-[A-Z0-9]+(?:-[A-Z0-9]+)?)\b', 'part'),
    (r'\b(?:KIT|PK)[-_]?(\d+[A-Z]?)\b', 'kit'),
    (r'\b([A-Z]?\d+[A-Z]+|[A-Z]+\d+[A-Z]*)\b', 'model'),
    (r'\b(600-\d{3,4}[A-Z]?)\b', 'caliper'),
    (r'\b(CH\d{4})\b', 'kit'),
    (r'\b([A-Z0-9]+/[A-Z0-9]+)\b', 'part'),
    
    # Pacific Truck transmission assembly patterns
    (r'\b(TA-[A-Z0-9]+-\d+[A-Z]?)\b', 'part'),
    (r'\b(RTLO?-\d+[A-Z]*\*?)\b', 'part'),
    (r'\b(FR0?-\d+[A-Z]*)\b', 'part'),
    (r'\b(FS-\d+[A-Z]*)\b', 'part'),
    
    # Pacific Truck kit patterns (from transmission kits)
    (r'\b(K-\d{4})\b', 'kit'),
    (r'\b(\d{3}-\d{3}-\d+X)\b', 'kit'),
    (r'\b(HD Transmission Kit)\b', 'kit'),
    
    # Pacific Truck transmission parts
    (r'\b([A-Z]\d{4,5})\b', 'part'),
    (r'\b([A-Z]\d{2}-\d{4})\b', 'part'),
    (r'\b([A-Z]-\d{4})\b', 'part'),
    (r'\b(S\d{4}[A-Z]?)\b', 'part'),
    (r'\b(X\d{2}-\d{4})\b', 'part'),
    
    # Pacific Truck clutch assemblies
    (r'\b(\d{6}-\d{2}[AM]?[0-9]?)\b', 'part'),
    (r'\b(MU\d{5,6}-[A-Z0-9]+)\b', 'part'),
    (r'\b(AN\d{6,7}-[A-Z0-9]+)\b', 'part'),
    (r'\b(NMU\d{3}-\d{3}-\d)\b', 'part'),
    
    # Pacific Truck Eaton clutch patterns
    (r'\b(\d{6}-\d)\b', 'part'),
    (r'\b(MU-\d{5}-\d)\b', 'part'),
    
    # Pacific Truck flywheel patterns
    (r'\b(\d{7})\b', 'part'),
    (r'\b(\d{8}[A-Z]?)\b', 'part'),
    (r'\b(\d{9}[A-Z]?)\b', 'part'),
    
    # Pacific Truck pilot bearing patterns
    (r'\b(TK\d{3}[A-Z]{2})\b', 'part'),
    (r'\b(TK\d{3}[A-Z]{3})\b', 'part'),
    
    # Pacific Truck clutch brake patterns
    (r'\b(TKW-\d{4})\b', 'part'),
    (r'\b([A-Z]{2}T\d{3})\b', 'part'),
    (r'\b(BK\d{3})\b', 'part'),
    (r'\b(SB\d{3})\b', 'part'),
    
    # Pacific Truck accessories
    (r'\b([A-Z]{2}S\d{3})\b', 'part'),
    (r'\b(M-[A-Z]\d{2,3})\b', 'part'),
    (r'\b(\d{3}C-\d+)\b', 'part'),
    (r'\b(CIT\d{3}[A-Z]?)\b', 'part'),
    
    # NELSON EXHAUST SPECIFIC PATTERNS
    # Basic part number patterns (most common)
    (r'\b(\d{5,6}[A-Z]?)\b', 'part'),  # 5-6 digit numbers like 0123D, 89005C, 89778K
    (r'\b([A-Z]{2,3}\d{3,4}[A-Z]{1,2})\b', 'part'),  # Like CPB12790, MUF101, SATA-51
    (r'\b(\d{2}[A-Z]{2,3}\d{2,4}[A-Z]{0,2})\b', 'part'),  # Like 0123D0522P, 0111SC051
    
    # Clamp patterns
    (r'\b(CLP\d{3}[A-Z]{0,2})\b', 'clamp'),  # Clamp part numbers like CLP028, CLP045SS
    (r'\b(HOSE\s*CLAMP\s*-\s*\d+)\b', 'clamp'),  # Hose clamps like HOSE CLAMP - 40
    (r'\b(TB\d{3}SL)\b', 'clamp'),  # Torque clamps like TB100SL
    (r'\b(ES-\d{3})\b', 'clamp'),  # Easy seal clamps like ES-700
    (r'\b(P\d{6})\b', 'clamp'),  # P-number clamps like P148340
    
    # Kit patterns
    (r'\b(\d{5}K)\b', 'kit'),  # Kit numbers ending with K like 89778K, 90900K
    (r'\b(TK\d{3}(?:-[A-Z0-9]+)?)\b', 'kit'),  # Tanker kits like TK127-D, TK85356L
    (r'\b(0134[KT][A-Z]+\d{3})\b', 'kit'),  # Flame proof tanker kits
    (r'\b(YP/[A-Z]+)\b', 'kit'),  # Y-piece kits like YP/WSTAR
    
    # Muffler patterns
    (r'\b(M\d{3}-\d{3}[A-Z]?)\b', 'muffler'),  # Muffler numbers like M1044-400R
    (r'\b(MUF\d{3})\b', 'muffler'),  # Muffler numbers like MUF101
    (r'\b(\d{5}[A-Z]?M)\b', 'muffler'),  # Muffler numbers ending with M like 86177M
    
    # Bracket patterns
    (r'\b(BRK\d{3})\b', 'bracket'),  # Bracket numbers like BRK001
    (r'\b(0134GB\d{3}[A-Z]?)\b', 'bracket'),  # Guard brackets
    (r'\b(FGMR\d{2})\b', 'bracket'),  # Full guard mounting rings
    (r'\b(HGR\d{2})\b', 'bracket'),  # Half guard rings
    
    # Spark arrestor patterns
    (r'\b(SAT[A-]\d{2})\b', 'spark_arrestor'),  # Spark arrestors like SATA-51
    (r'\b(SAA?-\d{4})\b', 'spark_arrestor'),  # Spark arrestors like SAA-4138
    (r'\b(SAMA?-\d{4})\b', 'spark_arrestor'),  # Spark arrestor mufflers
    (r'\b(491\d{2}[A-Z]?)\b', 'spark_arrestor'),  # USA design spark arrestors
    
    # Air intake patterns
    (r'\b(33165\d{2}[A-Z]?)\b', 'air_intake'),  # Air intake rubberware
    (r'\b(P\d{6})\b', 'air_intake'),  # P-number air intake parts
    (r'\b(RHHR\d{3})\b', 'air_intake'),  # Reducer hump hose
    (r'\b(TR\d{4})\b', 'air_intake'),  # T-Ram intakes
    
    # Flange and gasket patterns
    (r'\b(FL[A-Z]?\d{3}(?:-\d)?)\b', 'flange'),  # Flanges like FL051-2
    (r'\b(FLG\d{3}(?:-\d)?)\b', 'gasket'),  # Gaskets like FLG051-2
    (r'\b(TDF[A-Z]?\d{3})\b', 'flange'),  # Table D flanges
    (r'\b(TDG\d{3})\b', 'gasket'),  # Table D gaskets
    
    # Material-specific patterns
    (r'\b(\d{5,6}[A-Z])\b', 'part'),  # Letters indicating material like C=Chrome, A=Aluminized, S=Stainless
    (r'\b(\d{5,6}[A-Z]{2})\b', 'part'),  # Double letters for material types
    
    # Special component patterns
    (r'\b(BE1\d{3})\b', 'bellows'),  # Bellows connectors
    (r'\b(FLEXI-[0-9.x]+)\b', 'flex'),  # Flexible connectors
    (r'\b(PARROP\s*\d+)\b', 'tube'),  # Corrugated tube
    (r'\b(CAT\d{3}(?:-\d{3})?)\b', 'catalytic'),  # Catalytic converters
    (r'\b(RCS\d{4})\b', 'raincap'),  # Rain caps
    (r'\b(CPMS\d{3,4}[A-Z]{0,2})\b', 'stack'),  # Chrome plated mitre stacks
    
    
]

# Machine patterns
MACHINE_PATTERNS = [
    r'\b(V[0-9]\s*Series?)\b',
    r'\b(E[6-9]\s*Series?)\b',
    r'\b(MP\s*[7-8]\s*Series?)\b',
    r'\b(D1[1-3]\s*Series?)\b',
    r'\b(EM9-[4-5][0-9]{2})\b',
    r'\b(ENDT?-[6-8][0-9]{2})\b',
    r'\b(ASET\s*Engine)\b',
    r'\b(E-Tech)\b',
    r'\b(Cylinder\s*Head\s*Assembly)\b',
    r'\b(Turbocharger)\b',
    r'\b(Water\s*Pump)\b',
    r'\b(Oil\s*Cooler)\b',
    r'\b(Fuel\s*Injection)\b',
    r'\b(Rocker\s*Arm\s*Assembly)\b',
    r'\b(Timing\s*Cover)\b',
    r'\b(2020(?:XG|SS)?\s*(?:System|Mirror))\b',
    r'\b(Model\s*\d{3,4})\b',
    r'\b(West\s*Coast\s*Mirror)\b',
    r'\b(Convex\s*Mirror)\b',
    r'\b(Hood\s*Mount\s*Mirror)\b',
    r'\b(Rear\s*Cross\s*View)\b',
    r'\b(D[3-9]|D1[0-1]|[0-9]{3}[A-Z]?)\b',
    r'\b([0-9]{1,2}[A-Z]*\s*Series?)\b',
    r'\b([A-Z]+\s*[0-9]+[A-Z]*)\b',
    r'\b(RTLO?-\d+[A-Z]*)\b',
    r'\b(FR0?-\d+[A-Z]*)\b',
    r'\b(FS-\d+[A-Z]*)\b',
    r'\b(TTC\s+MIDRANGE)\b',
    r'\b(Caterpillar\s+(?:306|C10|C12|C13|3406|C15|C16|C18))\b',
    r'\b(Cummins\s+(?:L10|M11|ISX|Signature\s+600|8\.3L))\b',
    r'\b(Detroit\s+60\s+Series)\b',
    r'\b(Mack\s+E[67])\b',
    r'\b(International\s+(?:DT466|7\.3L))\b',
    r'\b(SOLO\s+ADVANTAGE)\b',
    r'\b(EASY\s+PEDAL)\b',
    r'\b(EVERTOUGH)\b',
    r'\b(Meritor\s+RD?\d+)\b',
    r'\b(Spicer\s+(?:T00P|D\d{3}|RS\d+))\b',
    r'\b(Mack\s+CR0\(P\))\b',
    r'\b(Alliance\s+Axle)\b',
 r'\b(Caterpillar|CAT\b)',
    r'\b(Komatsu)\b',
    r'\b(Hitachi)\b',
    r'\b(Volvo)\b',
    r'\b(International)\b',
    r'\b(Cummins)\b',
    r'\b(Kenworth)\b',
    r'\b(Mack)\b',
    r'\b(Western\s+Star)\b',
    r'\b(Detroit\s+Diesel|DD\b)',
]

# Catalog type indicators
CATALOG_INDICATORS = {
    'pai': ['pai industries', 'pai', 'mack', 'volvo', 'e6 series', 'e7 series', 'v8 series', 'engine components', 'turbocharger', 'cylinder head'],
    'velvac': ['velvac', 'mirror', 'west coast', 'convex', 'hood mount', 'rear cross view', '2020 System', '2020XG', 'DuraBall'],
    'dayton': ['dayton', 'hydraulic brake'],
    'caterpillar': ['caterpillar', 'cat ', 'fp-'],
    'fort_pro': ['fort pro', 'fortpro', 'heavy duty'],
    'dana_spicer': ['dana', 'spicer', 'axle'],
    'cummins': ['cummins', 'engine'],
    'detroit': ['detroit diesel'],
    'international': ['international', 'navistar'],
    'pacific_truck': [ 'pacific truck', 'heavy duty', 'transmission assemblies','fuller', 'eaton', 'meritor', 'spicer', 'dana', 'clutch assemblies', 'u-joints', 'yokes', 'differential',
        'axle shafts', 'powertrain specialists', 'drivetrain experts' ],
    'eaton_fuller': ['fuller', 'eaton', 'roadranger', 'transmission'],
    'meritor': ['meritor', 'clutch', 'axle'],
    'spicer': ['spicer', 'dana', 'u-joint', 'yoke'],
    'nelson_exhaust': ['nelson exhaust', 'diesel exhaust', 'muffler', 'exhaust stack', 'chrome stack', 'catalytic converter', 'spark arrestor', 'flame proof', 'tanker kit', 'v-band clamp', 'flexible tube', 'exhaust purifier'],

}