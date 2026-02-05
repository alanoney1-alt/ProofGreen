-- ESG Compliance System Database Schema
-- Migration: 003_esg_compliance.sql
-- ProofGreen - Comprehensive ESG tracking for home service businesses

-- ============================================
-- VERTICAL_ESG_DATA TABLE
-- Flexible storage for vertical-specific ESG data
-- ============================================
CREATE TABLE IF NOT EXISTS vertical_esg_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    vertical_id UUID REFERENCES verticals(id),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,

    -- Flexible JSON storage for vertical-specific fields
    data JSONB NOT NULL DEFAULT '{}',

    -- Auto-calculated scores (0-100)
    environmental_score DECIMAL(5,2) DEFAULT 0,
    social_score DECIMAL(5,2) DEFAULT 0,
    governance_score DECIMAL(5,2) DEFAULT 0,
    overall_esg_score DECIMAL(5,2) DEFAULT 0,

    -- Compliance flags
    contract_ready BOOLEAN DEFAULT false,
    missing_requirements JSONB DEFAULT '[]',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- ESG_DOCUMENTS TABLE
-- Document storage and management
-- ============================================
CREATE TABLE IF NOT EXISTS esg_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,

    -- Document type classification
    document_type VARCHAR(100) NOT NULL,
    -- Types: weight_ticket, donation_receipt, epa_certification, recycling_receipt,
    --        safety_data_sheet, energy_star_cert, watersense_cert, insurance_cert,
    --        license, osha_cert, refrigerant_log, disposal_manifest, cool_roof_cert,
    --        cims_gb_cert, pesticide_log, leed_documentation, e_waste_receipt,
    --        solar_interconnection, copper_recycling_receipt, hazmat_manifest

    document_url TEXT NOT NULL,
    file_name VARCHAR(255),
    file_size_bytes INTEGER,
    mime_type VARCHAR(100),

    -- Metadata extracted from document
    extracted_data JSONB DEFAULT '{}',

    uploaded_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,  -- For certs that expire

    -- Verification
    verified BOOLEAN DEFAULT false,
    verified_by UUID REFERENCES users(id),
    verified_at TIMESTAMPTZ,
    verification_notes TEXT,

    -- AI categorization
    ai_categorized BOOLEAN DEFAULT false,
    ai_confidence DECIMAL(5,4),
    ai_suggested_type VARCHAR(100),

    -- Link to requirement it fulfills
    requirement_id UUID,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- ESG_REQUIREMENTS TABLE
-- Requirements by vertical
-- ============================================
CREATE TABLE IF NOT EXISTS esg_requirements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vertical_id UUID REFERENCES verticals(id) ON DELETE CASCADE,

    requirement_name VARCHAR(255) NOT NULL,
    requirement_key VARCHAR(100) NOT NULL,  -- Machine-readable key
    requirement_type VARCHAR(100) NOT NULL,  -- 'documentation', 'calculation', 'certification', 'measurement'
    description TEXT,

    is_mandatory BOOLEAN DEFAULT true,
    compliance_level VARCHAR(50),  -- 'federal', 'state', 'local', 'industry', 'client'

    help_text TEXT,  -- User guidance
    validation_rules JSONB DEFAULT '{}',  -- Min/max values, formats, etc.

    -- Points contribution to ESG score
    score_category VARCHAR(50) DEFAULT 'environmental',  -- 'environmental', 'social', 'governance'
    max_points INTEGER DEFAULT 10,

    -- Ordering
    display_order INTEGER DEFAULT 0,

    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- COMPLIANCE_STATUS TABLE
-- Company-level compliance tracking
-- ============================================
CREATE TABLE IF NOT EXISTS compliance_status (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,

    period_type VARCHAR(20) DEFAULT 'monthly',  -- 'monthly', 'quarterly', 'annual'
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    -- Overall scores (0-100)
    environmental_score DECIMAL(5,2) DEFAULT 0,
    social_score DECIMAL(5,2) DEFAULT 0,
    governance_score DECIMAL(5,2) DEFAULT 0,
    overall_esg_score DECIMAL(5,2) DEFAULT 0,

    -- Key metrics
    total_jobs INTEGER DEFAULT 0,
    diversion_rate DECIMAL(5,2) DEFAULT 0,
    carbon_emissions_lbs DECIMAL(12,2) DEFAULT 0,
    carbon_offset_lbs DECIMAL(12,2) DEFAULT 0,
    net_carbon_lbs DECIMAL(12,2) DEFAULT 0,

    -- Requirements tracking
    requirements_met INTEGER DEFAULT 0,
    requirements_total INTEGER DEFAULT 0,
    requirements_percentage DECIMAL(5,2) DEFAULT 0,

    -- Document tracking
    docs_uploaded INTEGER DEFAULT 0,
    docs_verified INTEGER DEFAULT 0,
    docs_expiring_soon INTEGER DEFAULT 0,  -- Within 30 days

    -- Compliance flags
    all_docs_current BOOLEAN DEFAULT false,
    insurance_current BOOLEAN DEFAULT false,
    licenses_current BOOLEAN DEFAULT false,
    certifications_current BOOLEAN DEFAULT false,
    safety_training_current BOOLEAN DEFAULT false,

    contract_ready BOOLEAN DEFAULT false,
    contract_ready_reason TEXT,

    -- Breakdown by category
    metrics_breakdown JSONB DEFAULT '{}',

    last_calculated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(company_id, period_type, period_start)
);

-- ============================================
-- CERTIFICATIONS TABLE
-- Company certification tracking
-- ============================================
CREATE TABLE IF NOT EXISTS certifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,

    certification_name VARCHAR(255) NOT NULL,
    certification_type VARCHAR(100),  -- 'environmental', 'safety', 'quality', 'industry'
    issuing_organization VARCHAR(255),

    cert_number VARCHAR(100),
    issued_date DATE,
    expiry_date DATE,

    document_id UUID REFERENCES esg_documents(id),

    -- Status
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,

    -- Notifications
    expiry_notified_30d BOOLEAN DEFAULT false,
    expiry_notified_60d BOOLEAN DEFAULT false,
    expiry_notified_90d BOOLEAN DEFAULT false,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- VERTICAL_FORM_CONFIG TABLE
-- Configuration for vertical-specific forms
-- ============================================
CREATE TABLE IF NOT EXISTS vertical_form_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vertical_id UUID REFERENCES verticals(id) ON DELETE CASCADE,

    field_name VARCHAR(100) NOT NULL,
    field_key VARCHAR(100) NOT NULL,
    field_type VARCHAR(50) NOT NULL,  -- 'text', 'number', 'select', 'file', 'date', 'checkbox', 'calculated'

    -- Configuration
    label VARCHAR(255) NOT NULL,
    placeholder TEXT,
    help_text TEXT,

    -- Validation
    is_required BOOLEAN DEFAULT false,
    validation_rules JSONB DEFAULT '{}',  -- min, max, pattern, options, etc.

    -- For select fields
    options JSONB DEFAULT '[]',

    -- For calculated fields
    calculation_formula TEXT,  -- e.g., "fuel_gallons * 8.887"

    -- Display
    display_order INTEGER DEFAULT 0,
    field_group VARCHAR(100),  -- For grouping related fields

    -- Linked requirement
    requirement_id UUID REFERENCES esg_requirements(id),

    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(vertical_id, field_key)
);

-- ============================================
-- INDEXES
-- ============================================
CREATE INDEX IF NOT EXISTS idx_vertical_esg_job ON vertical_esg_data(job_id);
CREATE INDEX IF NOT EXISTS idx_vertical_esg_company ON vertical_esg_data(company_id);
CREATE INDEX IF NOT EXISTS idx_vertical_esg_vertical ON vertical_esg_data(vertical_id);
CREATE INDEX IF NOT EXISTS idx_esg_docs_company ON esg_documents(company_id);
CREATE INDEX IF NOT EXISTS idx_esg_docs_job ON esg_documents(job_id);
CREATE INDEX IF NOT EXISTS idx_esg_docs_type ON esg_documents(document_type);
CREATE INDEX IF NOT EXISTS idx_esg_docs_expires ON esg_documents(expires_at);
CREATE INDEX IF NOT EXISTS idx_esg_requirements_vertical ON esg_requirements(vertical_id);
CREATE INDEX IF NOT EXISTS idx_compliance_company ON compliance_status(company_id);
CREATE INDEX IF NOT EXISTS idx_compliance_period ON compliance_status(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_certifications_company ON certifications(company_id);
CREATE INDEX IF NOT EXISTS idx_certifications_expiry ON certifications(expiry_date);
CREATE INDEX IF NOT EXISTS idx_form_config_vertical ON vertical_form_config(vertical_id);

-- ============================================
-- SEED ESG REQUIREMENTS
-- ============================================

-- Clear existing requirements first (for re-running migration)
DELETE FROM esg_requirements;

-- JUNK REMOVAL Requirements
INSERT INTO esg_requirements (vertical_id, requirement_name, requirement_key, requirement_type, is_mandatory, compliance_level, description, help_text, score_category, max_points, display_order) VALUES
((SELECT id FROM verticals WHERE slug = 'junk_removal'),
 'Waste Diversion Rate Calculation', 'diversion_rate', 'calculation', true, 'industry',
 'Calculate percentage of waste diverted from landfill',
 'Target: 75%+ diversion rate. Calculate: (recycled_lbs + donated_lbs) / total_lbs × 100',
 'environmental', 40, 1),

((SELECT id FROM verticals WHERE slug = 'junk_removal'),
 'Weight Ticket Documentation', 'weight_ticket', 'documentation', true, 'industry',
 'Upload weight tickets from recycling centers',
 'Scan or photo of weight ticket showing company name, date, weight, material type',
 'environmental', 15, 2),

((SELECT id FROM verticals WHERE slug = 'junk_removal'),
 'Donation Receipt', 'donation_receipt', 'documentation', false, 'industry',
 'Upload donation receipts for tax-deductible items',
 'Receipt from charity showing items donated and estimated value',
 'social', 10, 3),

((SELECT id FROM verticals WHERE slug = 'junk_removal'),
 'Carbon Emissions Tracking', 'carbon_tracking', 'calculation', true, 'client',
 'Calculate carbon emissions from fuel consumption',
 'Formula: fuel_gallons × 8.887 = kg CO2. Track fuel usage and miles driven.',
 'environmental', 20, 4),

((SELECT id FROM verticals WHERE slug = 'junk_removal'),
 'Recycling Center Certification', 'recycling_cert', 'documentation', false, 'industry',
 'Proof that recycling center is certified',
 'R2, e-Stewards, or state certification for recycling facilities used',
 'environmental', 15, 5);

-- HVAC Requirements
INSERT INTO esg_requirements (vertical_id, requirement_name, requirement_key, requirement_type, is_mandatory, compliance_level, description, help_text, score_category, max_points, display_order) VALUES
((SELECT id FROM verticals WHERE slug = 'hvac'),
 'EPA 608 Certification', 'epa_608_cert', 'certification', true, 'federal',
 'Technician must have EPA 608 Universal Certification',
 'Required by EPA Clean Air Act for refrigerant handling. Upload certification document.',
 'governance', 25, 1),

((SELECT id FROM verticals WHERE slug = 'hvac'),
 'Refrigerant Recovery Log', 'refrigerant_log', 'documentation', true, 'federal',
 'Document all refrigerant recovered during service',
 'Include: refrigerant type (R-22, R-410A, etc.), pounds recovered, disposal method',
 'environmental', 25, 2),

((SELECT id FROM verticals WHERE slug = 'hvac'),
 'Energy Efficiency Calculation', 'energy_efficiency', 'calculation', true, 'client',
 'Calculate energy savings from SEER rating improvements',
 'Document old unit SEER and new unit SEER. Savings = ((1/old_SEER - 1/new_SEER) × BTU × hours) / 1000',
 'environmental', 20, 3),

((SELECT id FROM verticals WHERE slug = 'hvac'),
 'Refrigerant Disposal Manifest', 'disposal_manifest', 'documentation', true, 'federal',
 'Proof of proper refrigerant disposal',
 'EPA-compliant disposal documentation from certified reclaimer',
 'environmental', 15, 4),

((SELECT id FROM verticals WHERE slug = 'hvac'),
 'Energy Star Installation', 'energy_star', 'certification', false, 'client',
 'Install Energy Star certified equipment',
 'Energy Star certification provides utility rebates and LEED credits',
 'environmental', 15, 5);

-- ROOFING Requirements
INSERT INTO esg_requirements (vertical_id, requirement_name, requirement_key, requirement_type, is_mandatory, compliance_level, description, help_text, score_category, max_points, display_order) VALUES
((SELECT id FROM verticals WHERE slug = 'roofing'),
 'Shingle Recycling Documentation', 'shingle_recycling', 'documentation', true, 'industry',
 'Weight tickets from shingle recycling facility',
 'Many jurisdictions now require C&D waste diversion. Document all shingle recycling.',
 'environmental', 30, 1),

((SELECT id FROM verticals WHERE slug = 'roofing'),
 'Cool Roof Certification', 'cool_roof_cert', 'certification', false, 'client',
 'Energy Star Cool Roof certification if applicable',
 'Required for LEED credits and some utility rebates. Document solar reflectance index.',
 'environmental', 20, 2),

((SELECT id FROM verticals WHERE slug = 'roofing'),
 'Material Waste Calculation', 'material_waste', 'calculation', true, 'industry',
 'Calculate waste diversion rate for all roofing materials',
 'Track: shingles, metal, wood, underlayment. Calculate diversion percentage.',
 'environmental', 25, 3),

((SELECT id FROM verticals WHERE slug = 'roofing'),
 'Metal Recycling Receipt', 'metal_recycling', 'documentation', false, 'industry',
 'Receipts for metal roofing materials recycled',
 'Document pounds of metal (steel, aluminum, copper) sent to recycling',
 'environmental', 15, 4),

((SELECT id FROM verticals WHERE slug = 'roofing'),
 'Hazardous Material Handling', 'hazmat_handling', 'documentation', false, 'federal',
 'Documentation for asbestos or other hazardous materials',
 'Required if older roof contains asbestos. EPA and OSHA compliance.',
 'governance', 10, 5);

-- CLEANING Requirements
INSERT INTO esg_requirements (vertical_id, requirement_name, requirement_key, requirement_type, is_mandatory, compliance_level, description, help_text, score_category, max_points, display_order) VALUES
((SELECT id FROM verticals WHERE slug = 'cleaning'),
 'Green Product Usage Tracking', 'green_products', 'measurement', true, 'client',
 'Track percentage of EPA Safer Choice / Green Seal products used',
 'Many contracts require 80%+ green products. Document all products used.',
 'environmental', 30, 1),

((SELECT id FROM verticals WHERE slug = 'cleaning'),
 'Safety Data Sheets (SDS)', 'sds_documentation', 'documentation', true, 'federal',
 'Maintain SDS for all chemical products used',
 'OSHA requirement - must be accessible to workers. Upload all SDS documents.',
 'governance', 25, 2),

((SELECT id FROM verticals WHERE slug = 'cleaning'),
 'CIMS-GB Certification', 'cims_gb_cert', 'certification', false, 'industry',
 'Cleaning Industry Management Standard - Green Building',
 'Preferred certification for commercial contracts. Demonstrates sustainability commitment.',
 'environmental', 20, 3),

((SELECT id FROM verticals WHERE slug = 'cleaning'),
 'Water Usage Tracking', 'water_usage', 'measurement', false, 'client',
 'Track water consumption for cleaning operations',
 'Document gallons used per square foot. Target reduction goals.',
 'environmental', 15, 4),

((SELECT id FROM verticals WHERE slug = 'cleaning'),
 'Waste Reduction Metrics', 'waste_reduction', 'calculation', false, 'client',
 'Track and reduce cleaning waste',
 'Document concentrated product usage, refillable containers, reduced packaging.',
 'environmental', 10, 5);

-- LANDSCAPING Requirements
INSERT INTO esg_requirements (vertical_id, requirement_name, requirement_key, requirement_type, is_mandatory, compliance_level, description, help_text, score_category, max_points, display_order) VALUES
((SELECT id FROM verticals WHERE slug = 'landscaping'),
 'Pesticide Application Log', 'pesticide_log', 'documentation', true, 'state',
 'Document all pesticide applications',
 'Required by most state agriculture departments. Include product, rate, location, date.',
 'governance', 25, 1),

((SELECT id FROM verticals WHERE slug = 'landscaping'),
 'Water Usage Tracking', 'irrigation_tracking', 'measurement', true, 'client',
 'Track irrigation water consumption',
 'Many contracts require water conservation documentation. Track gallons per area.',
 'environmental', 25, 2),

((SELECT id FROM verticals WHERE slug = 'landscaping'),
 'Native Plant Installation', 'native_plants', 'measurement', false, 'client',
 'Track native vs non-native plants installed',
 'LEED and sustainable landscape certifications require 50%+ native plants.',
 'environmental', 20, 3),

((SELECT id FROM verticals WHERE slug = 'landscaping'),
 'Green Waste Composting', 'green_waste', 'documentation', false, 'local',
 'Documentation of green waste diversion',
 'Weight tickets or receipts from composting facility. Track tons diverted.',
 'environmental', 15, 4),

((SELECT id FROM verticals WHERE slug = 'landscaping'),
 'Integrated Pest Management', 'ipm_documentation', 'documentation', false, 'industry',
 'IPM plan documentation',
 'Document pest monitoring, threshold-based treatments, least-toxic methods.',
 'environmental', 15, 5);

-- PLUMBING Requirements
INSERT INTO esg_requirements (vertical_id, requirement_name, requirement_key, requirement_type, is_mandatory, compliance_level, description, help_text, score_category, max_points, display_order) VALUES
((SELECT id FROM verticals WHERE slug = 'plumbing'),
 'WaterSense Certification', 'watersense_cert', 'certification', false, 'client',
 'Install WaterSense certified fixtures',
 'Required for LEED, utility rebates, green building codes. Document all WaterSense products.',
 'environmental', 25, 1),

((SELECT id FROM verticals WHERE slug = 'plumbing'),
 'Water Savings Calculation', 'water_savings', 'calculation', true, 'client',
 'Calculate annual water savings from fixture upgrades',
 'Formula: (old_gpm - new_gpm) × daily_uses × 365 = gallons/year saved',
 'environmental', 30, 2),

((SELECT id FROM verticals WHERE slug = 'plumbing'),
 'Copper Recycling Documentation', 'copper_recycling', 'documentation', true, 'industry',
 'Receipts from metal recycling',
 'Track pounds of copper, brass recycled. Document scrap value if applicable.',
 'environmental', 20, 3),

((SELECT id FROM verticals WHERE slug = 'plumbing'),
 'Lead-Free Certification', 'lead_free_cert', 'certification', true, 'federal',
 'Certification that materials are lead-free',
 'Safe Drinking Water Act requires lead-free materials for potable water.',
 'governance', 15, 4),

((SELECT id FROM verticals WHERE slug = 'plumbing'),
 'Backflow Prevention Testing', 'backflow_cert', 'documentation', false, 'local',
 'Backflow preventer test reports',
 'Many jurisdictions require annual testing and documentation.',
 'governance', 10, 5);

-- ELECTRICAL Requirements
INSERT INTO esg_requirements (vertical_id, requirement_name, requirement_key, requirement_type, is_mandatory, compliance_level, description, help_text, score_category, max_points, display_order) VALUES
((SELECT id FROM verticals WHERE slug = 'electrical'),
 'Energy Savings Calculation', 'energy_savings', 'calculation', true, 'client',
 'Calculate kWh savings from LED and efficiency upgrades',
 'Formula: watts_saved × hours_per_day × 365 ÷ 1000 = kWh/year',
 'environmental', 30, 1),

((SELECT id FROM verticals WHERE slug = 'electrical'),
 'Solar Interconnection Agreement', 'solar_interconnection', 'documentation', false, 'client',
 'Utility interconnection for solar installations',
 'Required for grid-tied solar systems. Upload utility agreement.',
 'environmental', 20, 2),

((SELECT id FROM verticals WHERE slug = 'electrical'),
 'E-waste Disposal Documentation', 'ewaste_disposal', 'documentation', true, 'state',
 'Proper disposal of electronic waste',
 'Many states ban e-waste from landfills. Document certified e-waste recycling.',
 'environmental', 25, 3),

((SELECT id FROM verticals WHERE slug = 'electrical'),
 'Energy Star Equipment', 'energy_star_equip', 'certification', false, 'client',
 'Install Energy Star certified equipment',
 'Document all Energy Star rated equipment installed.',
 'environmental', 15, 4),

((SELECT id FROM verticals WHERE slug = 'electrical'),
 'Electrical Permit Documentation', 'electrical_permit', 'documentation', true, 'local',
 'Required permits and inspections',
 'Upload permit and final inspection sign-off.',
 'governance', 10, 5);

-- DEMOLITION Requirements
INSERT INTO esg_requirements (vertical_id, requirement_name, requirement_key, requirement_type, is_mandatory, compliance_level, description, help_text, score_category, max_points, display_order) VALUES
((SELECT id FROM verticals WHERE slug = 'demolition'),
 'C&D Waste Diversion', 'cd_diversion', 'calculation', true, 'local',
 'Construction & Demolition waste diversion rate',
 'Many jurisdictions require 75%+ diversion. Track concrete, metal, lumber, drywall separately.',
 'environmental', 35, 1),

((SELECT id FROM verticals WHERE slug = 'demolition'),
 'Hazmat Disposal Manifests', 'hazmat_manifests', 'documentation', true, 'federal',
 'Asbestos, lead paint, contaminated materials disposal',
 'EPA and OSHA requirements for hazardous materials. Upload all manifests.',
 'governance', 25, 2),

((SELECT id FROM verticals WHERE slug = 'demolition'),
 'Material Salvage Documentation', 'salvage_docs', 'documentation', false, 'industry',
 'Documentation of salvaged materials',
 'Track architectural salvage, reusable materials, donation receipts.',
 'environmental', 20, 3),

((SELECT id FROM verticals WHERE slug = 'demolition'),
 'Air Quality Monitoring', 'air_quality', 'documentation', false, 'local',
 'Air quality monitoring during demolition',
 'Required for some jurisdictions. Document dust control measures.',
 'environmental', 10, 4),

((SELECT id FROM verticals WHERE slug = 'demolition'),
 'Recycling Facility Receipts', 'recycling_receipts', 'documentation', true, 'industry',
 'Weight tickets from C&D recycling facilities',
 'Document all materials sent to recycling: concrete, metal, wood, drywall.',
 'environmental', 10, 5);

-- ============================================
-- SEED VERTICAL FORM CONFIGURATIONS
-- ============================================

DELETE FROM vertical_form_config;

-- JUNK REMOVAL Form Fields
INSERT INTO vertical_form_config (vertical_id, field_name, field_key, field_type, label, placeholder, help_text, is_required, validation_rules, display_order, field_group) VALUES
((SELECT id FROM verticals WHERE slug = 'junk_removal'), 'Total Weight', 'total_weight_lbs', 'number', 'Total Weight (lbs)', 'Enter total weight', 'AI can estimate from photo. Enter actual weight from scale if available.', true, '{"min": 0}', 1, 'weight'),
((SELECT id FROM verticals WHERE slug = 'junk_removal'), 'Recycled Weight', 'recycled_weight_lbs', 'number', 'Recycled Weight (lbs)', 'Enter recycled weight', 'Weight of materials sent to recycling facilities.', true, '{"min": 0}', 2, 'weight'),
((SELECT id FROM verticals WHERE slug = 'junk_removal'), 'Donated Weight', 'donated_weight_lbs', 'number', 'Donated Weight (lbs)', 'Enter donated weight', 'Weight of items donated to charity.', false, '{"min": 0}', 3, 'weight'),
((SELECT id FROM verticals WHERE slug = 'junk_removal'), 'Landfill Weight', 'landfill_weight_lbs', 'number', 'Landfill Weight (lbs)', 'Enter landfill weight', 'Weight of materials sent to landfill (non-recyclable).', true, '{"min": 0}', 4, 'weight'),
((SELECT id FROM verticals WHERE slug = 'junk_removal'), 'Recycling Center', 'recycling_center', 'text', 'Recycling Center Name', 'Enter recycling center name', 'Name and location of recycling facility used.', true, '{}', 5, 'documentation'),
((SELECT id FROM verticals WHERE slug = 'junk_removal'), 'Weight Ticket', 'weight_ticket_url', 'file', 'Weight Ticket', 'Upload weight ticket', 'Scan or photo of weight ticket from recycling center.', true, '{"accept": "image/*,application/pdf"}', 6, 'documentation'),
((SELECT id FROM verticals WHERE slug = 'junk_removal'), 'Donation Receipt', 'donation_receipt_url', 'file', 'Donation Receipt', 'Upload donation receipt', 'Receipt from charity for donated items.', false, '{"accept": "image/*,application/pdf"}', 7, 'documentation'),
((SELECT id FROM verticals WHERE slug = 'junk_removal'), 'Fuel Used', 'fuel_gallons', 'number', 'Fuel Used (gallons)', 'Enter gallons of fuel', 'Total fuel consumed for this job.', true, '{"min": 0, "step": 0.1}', 8, 'carbon'),
((SELECT id FROM verticals WHERE slug = 'junk_removal'), 'Miles Driven', 'miles_driven', 'number', 'Miles Driven', 'Enter miles driven', 'Total miles driven for this job (round trip).', true, '{"min": 0}', 9, 'carbon'),
((SELECT id FROM verticals WHERE slug = 'junk_removal'), 'Carbon Emissions', 'carbon_emissions_lbs', 'calculated', 'Carbon Emissions (lbs CO2)', '', 'Auto-calculated: fuel_gallons × 19.6', false, '{}', 10, 'carbon'),
((SELECT id FROM verticals WHERE slug = 'junk_removal'), 'Diversion Rate', 'diversion_rate', 'calculated', 'Diversion Rate (%)', '', 'Auto-calculated: (recycled + donated) / total × 100', false, '{}', 11, 'metrics');

-- HVAC Form Fields
INSERT INTO vertical_form_config (vertical_id, field_name, field_key, field_type, label, placeholder, help_text, is_required, validation_rules, options, display_order, field_group) VALUES
((SELECT id FROM verticals WHERE slug = 'hvac'), 'Refrigerant Type', 'refrigerant_type', 'select', 'Refrigerant Type', 'Select refrigerant', 'Type of refrigerant in the system.', true, '{}', '["R-22", "R-410A", "R-32", "R-134a", "R-404A", "R-407C", "Other"]', 1, 'refrigerant'),
((SELECT id FROM verticals WHERE slug = 'hvac'), 'Refrigerant Recovered', 'refrigerant_recovered_lbs', 'number', 'Refrigerant Recovered (lbs)', 'Enter pounds recovered', 'Amount of refrigerant recovered during service.', true, '{"min": 0, "step": 0.1}', '[]', 2, 'refrigerant'),
((SELECT id FROM verticals WHERE slug = 'hvac'), 'EPA Cert Number', 'epa_cert_number', 'text', 'EPA 608 Certification Number', 'Enter cert number', 'Your EPA Section 608 certification number.', true, '{"pattern": "[A-Za-z0-9-]+"}', '[]', 3, 'certification'),
((SELECT id FROM verticals WHERE slug = 'hvac'), 'Old Unit SEER', 'old_unit_seer', 'number', 'Old Unit SEER Rating', 'Enter SEER', 'SEER rating of unit being replaced (if applicable).', false, '{"min": 6, "max": 30}', '[]', 4, 'efficiency'),
((SELECT id FROM verticals WHERE slug = 'hvac'), 'New Unit SEER', 'new_unit_seer', 'number', 'New Unit SEER Rating', 'Enter SEER', 'SEER rating of new unit installed (if applicable).', false, '{"min": 13, "max": 30}', '[]', 5, 'efficiency'),
((SELECT id FROM verticals WHERE slug = 'hvac'), 'BTU Capacity', 'btu_capacity', 'number', 'System BTU Capacity', 'Enter BTU', 'Cooling capacity of the system.', false, '{"min": 0}', '[]', 6, 'efficiency'),
((SELECT id FROM verticals WHERE slug = 'hvac'), 'Unit Weight', 'unit_weight_lbs', 'number', 'Old Unit Weight (lbs)', 'Enter weight', 'Weight of removed HVAC unit for recycling calculation.', false, '{"min": 0}', '[]', 7, 'weight'),
((SELECT id FROM verticals WHERE slug = 'hvac'), 'Disposal Manifest', 'disposal_manifest_url', 'file', 'Refrigerant Disposal Manifest', 'Upload manifest', 'EPA-compliant disposal documentation.', true, '{"accept": "image/*,application/pdf"}', '[]', 8, 'documentation'),
((SELECT id FROM verticals WHERE slug = 'hvac'), 'Energy Savings', 'energy_savings_kwh', 'calculated', 'Estimated Annual Energy Savings (kWh)', '', 'Auto-calculated from SEER improvement.', false, '{}', '[]', 9, 'metrics'),
((SELECT id FROM verticals WHERE slug = 'hvac'), 'Carbon Offset', 'carbon_offset_lbs', 'calculated', 'Carbon Offset (lbs CO2/year)', '', 'Auto-calculated from energy savings.', false, '{}', '[]', 10, 'metrics');

-- ROOFING Form Fields
INSERT INTO vertical_form_config (vertical_id, field_name, field_key, field_type, label, placeholder, help_text, is_required, validation_rules, options, display_order, field_group) VALUES
((SELECT id FROM verticals WHERE slug = 'roofing'), 'Roof Area', 'roof_area_sqft', 'number', 'Roof Area (sq ft)', 'Enter square footage', 'Total roof area for the project.', true, '{"min": 0}', '[]', 1, 'measurements'),
((SELECT id FROM verticals WHERE slug = 'roofing'), 'Material Type', 'material_type', 'select', 'Primary Roofing Material', 'Select material', 'Main roofing material removed/installed.', true, '{}', '["Asphalt Shingles", "Metal", "Tile", "Wood Shake", "Slate", "Flat/TPO", "EPDM", "Other"]', 2, 'materials'),
((SELECT id FROM verticals WHERE slug = 'roofing'), 'Old Material Weight', 'old_material_weight_lbs', 'number', 'Removed Material Weight (lbs)', 'Enter weight', 'Total weight of old roofing materials removed.', true, '{"min": 0}', '[]', 3, 'weight'),
((SELECT id FROM verticals WHERE slug = 'roofing'), 'Recycled Weight', 'recycled_weight_lbs', 'number', 'Recycled Weight (lbs)', 'Enter recycled weight', 'Weight of materials sent to recycling.', true, '{"min": 0}', '[]', 4, 'weight'),
((SELECT id FROM verticals WHERE slug = 'roofing'), 'Landfill Weight', 'landfill_weight_lbs', 'number', 'Landfill Weight (lbs)', 'Enter landfill weight', 'Weight of materials sent to landfill.', true, '{"min": 0}', '[]', 5, 'weight'),
((SELECT id FROM verticals WHERE slug = 'roofing'), 'Metal Recycled', 'metal_recycled_lbs', 'number', 'Metal Recycled (lbs)', 'Enter metal weight', 'Weight of metal (flashing, gutters, etc.) recycled.', false, '{"min": 0}', '[]', 6, 'weight'),
((SELECT id FROM verticals WHERE slug = 'roofing'), 'Recycling Receipt', 'recycling_receipt_url', 'file', 'Recycling Weight Ticket', 'Upload receipt', 'Weight ticket from recycling facility.', true, '{"accept": "image/*,application/pdf"}', '[]', 7, 'documentation'),
((SELECT id FROM verticals WHERE slug = 'roofing'), 'Cool Roof', 'is_cool_roof', 'checkbox', 'Energy Star Cool Roof', '', 'Check if cool roof materials were installed.', false, '{}', '[]', 8, 'certification'),
((SELECT id FROM verticals WHERE slug = 'roofing'), 'SRI Value', 'sri_value', 'number', 'Solar Reflectance Index (SRI)', 'Enter SRI', 'SRI value of installed roofing (for cool roofs).', false, '{"min": 0, "max": 150}', '[]', 9, 'certification'),
((SELECT id FROM verticals WHERE slug = 'roofing'), 'Diversion Rate', 'diversion_rate', 'calculated', 'Diversion Rate (%)', '', 'Auto-calculated from weights.', false, '{}', '[]', 10, 'metrics');

-- CLEANING Form Fields
INSERT INTO vertical_form_config (vertical_id, field_name, field_key, field_type, label, placeholder, help_text, is_required, validation_rules, options, display_order, field_group) VALUES
((SELECT id FROM verticals WHERE slug = 'cleaning'), 'Area Cleaned', 'area_sqft', 'number', 'Area Cleaned (sq ft)', 'Enter square footage', 'Total area cleaned.', true, '{"min": 0}', '[]', 1, 'measurements'),
((SELECT id FROM verticals WHERE slug = 'cleaning'), 'Cleaning Type', 'cleaning_type', 'select', 'Cleaning Type', 'Select type', 'Type of cleaning service performed.', true, '{}', '["Regular Maintenance", "Deep Clean", "Post-Construction", "Move In/Out", "Specialty"]', 2, 'service'),
((SELECT id FROM verticals WHERE slug = 'cleaning'), 'Green Products Used', 'green_products_count', 'number', 'Number of Green Products Used', 'Enter count', 'EPA Safer Choice or Green Seal certified products used.', true, '{"min": 0}', '[]', 3, 'products'),
((SELECT id FROM verticals WHERE slug = 'cleaning'), 'Total Products Used', 'total_products_count', 'number', 'Total Products Used', 'Enter count', 'Total number of cleaning products used.', true, '{"min": 1}', '[]', 4, 'products'),
((SELECT id FROM verticals WHERE slug = 'cleaning'), 'Water Used', 'water_gallons', 'number', 'Water Used (gallons)', 'Enter gallons', 'Estimated water consumption.', false, '{"min": 0}', '[]', 5, 'resources'),
((SELECT id FROM verticals WHERE slug = 'cleaning'), 'SDS Uploaded', 'sds_uploaded', 'checkbox', 'Safety Data Sheets on File', '', 'Confirm SDS available for all products.', true, '{}', '[]', 6, 'compliance'),
((SELECT id FROM verticals WHERE slug = 'cleaning'), 'Product List', 'product_list_url', 'file', 'Product List Document', 'Upload product list', 'List of all products used with certifications noted.', false, '{"accept": "application/pdf,image/*"}', '[]', 7, 'documentation'),
((SELECT id FROM verticals WHERE slug = 'cleaning'), 'Green Product %', 'green_product_percentage', 'calculated', 'Green Product Percentage (%)', '', 'Auto-calculated from product counts.', false, '{}', '[]', 8, 'metrics');

COMMIT;
