-- ProofGreen Database Schema
-- AI-powered ESG tracking platform for home service businesses
-- Run this in your Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- 1. COMPANIES TABLE
-- Customer accounts (home service businesses)
-- ============================================
CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(50),
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(50),
    zip_code VARCHAR(20),
    country VARCHAR(100) DEFAULT 'USA',
    logo_url TEXT,
    website VARCHAR(255),
    description TEXT,
    employee_count INTEGER,
    founded_year INTEGER,
    is_active BOOLEAN DEFAULT true,
    onboarding_completed BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 2. USERS TABLE
-- People within companies
-- ============================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(50),
    role VARCHAR(50) DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'manager', 'member')),
    avatar_url TEXT,
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 3. VERTICALS TABLE
-- 20 service types for home service businesses
-- ============================================
CREATE TABLE verticals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    icon VARCHAR(50),
    color VARCHAR(20),
    default_items JSONB DEFAULT '[]',
    carbon_multiplier DECIMAL(5,2) DEFAULT 1.0,
    is_active BOOLEAN DEFAULT true,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert 20 service verticals
INSERT INTO verticals (slug, name, description, icon, color, display_order) VALUES
    ('junk_removal', 'Junk Removal', 'General junk hauling and debris removal', 'truck', '#4F46E5', 1),
    ('hvac', 'HVAC Services', 'Heating, ventilation, and air conditioning', 'thermometer', '#10B981', 2),
    ('roofing', 'Roofing', 'Roof installation, repair, and replacement', 'home', '#F59E0B', 3),
    ('cleaning', 'Cleaning Services', 'Residential and commercial cleaning', 'sparkles', '#EC4899', 4),
    ('landscaping', 'Landscaping', 'Lawn care, gardening, and outdoor maintenance', 'tree', '#22C55E', 5),
    ('plumbing', 'Plumbing', 'Pipe installation and repair services', 'droplet', '#3B82F6', 6),
    ('electrical', 'Electrical', 'Electrical installation and repair', 'zap', '#EAB308', 7),
    ('painting', 'Painting', 'Interior and exterior painting services', 'palette', '#8B5CF6', 8),
    ('flooring', 'Flooring', 'Floor installation and refinishing', 'layout', '#78716C', 9),
    ('demolition', 'Demolition', 'Building and structure demolition', 'hammer', '#DC2626', 10),
    ('moving', 'Moving Services', 'Residential and commercial moving', 'package', '#0891B2', 11),
    ('pest_control', 'Pest Control', 'Pest extermination and prevention', 'bug', '#84CC16', 12),
    ('appliance_repair', 'Appliance Repair', 'Home appliance repair services', 'settings', '#6366F1', 13),
    ('pool_service', 'Pool Service', 'Pool cleaning and maintenance', 'waves', '#06B6D4', 14),
    ('window_cleaning', 'Window Cleaning', 'Residential window cleaning', 'grid', '#64748B', 15),
    ('garage_doors', 'Garage Doors', 'Garage door installation and repair', 'door-open', '#A855F7', 16),
    ('solar', 'Solar Installation', 'Solar panel installation and maintenance', 'sun', '#FBBF24', 17),
    ('insulation', 'Insulation', 'Home insulation services', 'shield', '#F472B6', 18),
    ('fencing', 'Fencing', 'Fence installation and repair', 'square', '#65A30D', 19),
    ('general_contractor', 'General Contracting', 'General construction and remodeling', 'hard-hat', '#1E293B', 20);

-- ============================================
-- 4. COMPANY_VERTICALS TABLE
-- Many-to-many relationship (companies can serve multiple industries)
-- ============================================
CREATE TABLE company_verticals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    vertical_id UUID REFERENCES verticals(id) ON DELETE CASCADE,
    is_primary BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, vertical_id)
);

-- ============================================
-- 5. PRICING_PLANS TABLE
-- 5 subscription tiers
-- ============================================
CREATE TABLE pricing_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price_monthly DECIMAL(10,2) NOT NULL,
    price_yearly DECIMAL(10,2),
    features JSONB DEFAULT '[]',
    job_limit INTEGER, -- NULL means unlimited
    user_limit INTEGER, -- NULL means unlimited
    ai_analysis_limit INTEGER, -- NULL means unlimited
    report_limit INTEGER,
    has_api_access BOOLEAN DEFAULT false,
    has_white_label BOOLEAN DEFAULT false,
    has_priority_support BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert 5 pricing tiers
INSERT INTO pricing_plans (slug, name, description, price_monthly, price_yearly, job_limit, user_limit, ai_analysis_limit, report_limit, features, display_order) VALUES
    ('founders', 'Founders', 'Early adopter special pricing', 99.00, 948.00, 100, 3, 100, 10,
     '["AI photo analysis", "Basic ESG reports", "Email support", "Dashboard access"]', 1),
    ('starter', 'Starter', 'Perfect for small businesses', 149.00, 1428.00, 250, 5, 250, 25,
     '["AI photo analysis", "Standard ESG reports", "Email support", "Dashboard access", "Carbon tracking"]', 2),
    ('professional', 'Professional', 'For growing companies', 299.00, 2868.00, 1000, 15, 1000, 100,
     '["AI photo analysis", "Advanced ESG reports", "Priority support", "Dashboard access", "Carbon tracking", "API access", "Custom branding"]', 3),
    ('business', 'Business', 'For established businesses', 599.00, 5748.00, 5000, 50, 5000, 500,
     '["Unlimited AI analysis", "Premium ESG reports", "Priority support", "Full API access", "White label reports", "Dedicated account manager"]', 4),
    ('enterprise', 'Enterprise', 'Custom solutions for large organizations', 1999.00, 19188.00, NULL, NULL, NULL, NULL,
     '["Unlimited everything", "Custom integrations", "24/7 support", "SLA guarantee", "On-premise option", "Custom AI training"]', 5);

-- ============================================
-- 6. SUBSCRIPTIONS TABLE
-- Customer subscription records
-- ============================================
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    plan_id UUID REFERENCES pricing_plans(id),
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'cancelled', 'past_due', 'trialing', 'paused')),
    billing_cycle VARCHAR(20) DEFAULT 'monthly' CHECK (billing_cycle IN ('monthly', 'yearly')),
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    trial_end TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    stripe_subscription_id VARCHAR(255),
    stripe_customer_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 7. JOBS TABLE
-- Service calls/projects
-- ============================================
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    vertical_id UUID REFERENCES verticals(id),
    assigned_user_id UUID REFERENCES users(id),

    -- Job details
    job_number VARCHAR(50),
    title VARCHAR(255),
    description TEXT,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),

    -- Customer info
    customer_name VARCHAR(255),
    customer_email VARCHAR(255),
    customer_phone VARCHAR(50),

    -- Location
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(50),
    zip_code VARCHAR(20),
    latitude DECIMAL(10,8),
    longitude DECIMAL(11,8),

    -- Scheduling
    scheduled_date DATE,
    scheduled_time_start TIME,
    scheduled_time_end TIME,
    completed_at TIMESTAMPTZ,

    -- Photos
    before_photos JSONB DEFAULT '[]',
    after_photos JSONB DEFAULT '[]',

    -- ESG Metrics (calculated by AI agent)
    total_weight_lbs DECIMAL(10,2) DEFAULT 0,
    recycled_weight_lbs DECIMAL(10,2) DEFAULT 0,
    landfill_weight_lbs DECIMAL(10,2) DEFAULT 0,
    donated_weight_lbs DECIMAL(10,2) DEFAULT 0,
    carbon_offset_lbs DECIMAL(10,2) DEFAULT 0,
    diversion_rate DECIMAL(5,2) DEFAULT 0,
    esg_score INTEGER DEFAULT 0 CHECK (esg_score >= 0 AND esg_score <= 100),

    -- AI processing
    ai_processed BOOLEAN DEFAULT false,
    ai_processed_at TIMESTAMPTZ,
    ai_confidence DECIMAL(3,2),

    -- Pricing
    estimated_cost DECIMAL(10,2),
    final_cost DECIMAL(10,2),

    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 8. JOB_ITEMS TABLE
-- Items processed per job
-- ============================================
CREATE TABLE job_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,

    name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    subcategory VARCHAR(100),

    quantity INTEGER DEFAULT 1,
    weight_lbs DECIMAL(10,2),

    disposal_method VARCHAR(50) CHECK (disposal_method IN ('recycled', 'donated', 'landfill', 'hazardous', 'compost', 'reused')),

    -- Carbon calculations
    carbon_factor_id UUID,
    carbon_offset_lbs DECIMAL(10,2) DEFAULT 0,

    -- AI detection
    detected_by_ai BOOLEAN DEFAULT false,
    ai_confidence DECIMAL(3,2),

    photo_reference TEXT,
    notes TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 9. JOB_CUSTOM_DATA TABLE
-- Vertical-specific fields (flexible schema)
-- ============================================
CREATE TABLE job_custom_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    vertical_id UUID REFERENCES verticals(id),

    field_name VARCHAR(100) NOT NULL,
    field_value TEXT,
    field_type VARCHAR(50) DEFAULT 'text',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 10. CARBON_FACTORS TABLE
-- Lookup table for carbon calculations
-- ============================================
CREATE TABLE carbon_factors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category VARCHAR(100) NOT NULL,
    subcategory VARCHAR(100),

    -- Carbon factors (lbs CO2 per lb of material)
    landfill_factor DECIMAL(6,4) DEFAULT 0,
    recycle_factor DECIMAL(6,4) DEFAULT 0,
    reuse_factor DECIMAL(6,4) DEFAULT 0,

    -- Defaults
    default_weight_lbs DECIMAL(10,2),
    recyclable BOOLEAN DEFAULT true,

    description TEXT,
    source VARCHAR(255),
    last_updated TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(category, subcategory)
);

-- Insert carbon factors for common materials
INSERT INTO carbon_factors (category, subcategory, landfill_factor, recycle_factor, reuse_factor, default_weight_lbs, recyclable) VALUES
    -- Furniture
    ('furniture', 'wood', 1.2, 0.3, 0.1, 50, true),
    ('furniture', 'metal', 1.5, 0.2, 0.1, 75, true),
    ('furniture', 'upholstered', 1.8, 0.5, 0.2, 100, true),
    ('furniture', 'mattress', 2.0, 0.6, 0.3, 80, true),

    -- Electronics
    ('electronics', 'large', 3.5, 0.4, 0.2, 50, true),
    ('electronics', 'small', 2.8, 0.3, 0.1, 5, true),
    ('electronics', 'computer', 3.2, 0.3, 0.1, 25, true),
    ('electronics', 'tv', 3.0, 0.4, 0.2, 40, true),

    -- Metals
    ('metal', 'ferrous', 1.8, 0.1, 0.05, 20, true),
    ('metal', 'non_ferrous', 4.5, 0.2, 0.1, 10, true),
    ('metal', 'aluminum', 5.0, 0.15, 0.08, 5, true),
    ('metal', 'copper', 4.0, 0.1, 0.05, 8, true),

    -- Construction
    ('construction', 'concrete', 0.5, 0.1, 0.05, 100, true),
    ('construction', 'drywall', 0.3, 0.15, 0.1, 30, true),
    ('construction', 'lumber', 1.0, 0.2, 0.1, 40, true),
    ('construction', 'insulation', 0.8, 0.3, 0.2, 20, true),

    -- HVAC specific
    ('hvac', 'unit', 4.0, 0.3, 0.15, 150, true),
    ('hvac', 'ductwork', 1.5, 0.15, 0.08, 25, true),
    ('hvac', 'refrigerant', 10.0, 0.1, 0, 5, true),

    -- Roofing specific
    ('roofing', 'shingles_asphalt', 0.8, 0.2, 0.1, 200, true),
    ('roofing', 'shingles_wood', 0.6, 0.15, 0.08, 150, true),
    ('roofing', 'metal_roofing', 2.0, 0.1, 0.05, 100, true),
    ('roofing', 'underlayment', 0.5, 0.2, 0.1, 50, false),

    -- Appliances
    ('appliance', 'refrigerator', 4.5, 0.3, 0.15, 200, true),
    ('appliance', 'washer', 3.5, 0.25, 0.12, 150, true),
    ('appliance', 'dryer', 3.2, 0.25, 0.12, 125, true),
    ('appliance', 'dishwasher', 3.0, 0.25, 0.12, 100, true),
    ('appliance', 'oven', 3.2, 0.25, 0.12, 150, true),

    -- Yard waste
    ('yard', 'green_waste', 0.3, 0.05, 0.02, 50, true),
    ('yard', 'wood_debris', 0.6, 0.1, 0.05, 75, true),

    -- General
    ('general', 'mixed_waste', 1.0, 0.4, 0.2, 25, false),
    ('general', 'cardboard', 0.4, 0.05, 0.02, 10, true),
    ('general', 'plastic', 2.5, 0.3, 0.15, 5, true),
    ('general', 'glass', 0.6, 0.1, 0.05, 15, true),
    ('general', 'textile', 1.2, 0.2, 0.1, 10, true);

-- ============================================
-- 11. ESG_METRICS TABLE
-- Aggregated sustainability data per company
-- ============================================
CREATE TABLE esg_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,

    period_type VARCHAR(20) NOT NULL CHECK (period_type IN ('daily', 'weekly', 'monthly', 'quarterly', 'yearly')),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    -- Volume metrics
    total_jobs INTEGER DEFAULT 0,
    total_weight_lbs DECIMAL(12,2) DEFAULT 0,
    recycled_weight_lbs DECIMAL(12,2) DEFAULT 0,
    donated_weight_lbs DECIMAL(12,2) DEFAULT 0,
    landfill_weight_lbs DECIMAL(12,2) DEFAULT 0,

    -- Carbon metrics
    carbon_offset_lbs DECIMAL(12,2) DEFAULT 0,
    carbon_equivalent_trees INTEGER DEFAULT 0,
    carbon_equivalent_miles INTEGER DEFAULT 0,

    -- Rates
    diversion_rate DECIMAL(5,2) DEFAULT 0,
    recycle_rate DECIMAL(5,2) DEFAULT 0,
    donation_rate DECIMAL(5,2) DEFAULT 0,

    -- Score
    esg_score INTEGER DEFAULT 0 CHECK (esg_score >= 0 AND esg_score <= 100),

    -- By category breakdown
    metrics_by_category JSONB DEFAULT '{}',

    calculated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(company_id, period_type, period_start)
);

-- ============================================
-- 12. ESG_REPORTS TABLE
-- Generated reports
-- ============================================
CREATE TABLE esg_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,

    report_type VARCHAR(50) NOT NULL CHECK (report_type IN ('job', 'weekly', 'monthly', 'quarterly', 'annual', 'custom')),
    title VARCHAR(255) NOT NULL,

    period_start DATE,
    period_end DATE,

    -- Report content
    summary TEXT,
    metrics_snapshot JSONB,
    report_data JSONB,

    -- File info
    file_url TEXT,
    file_format VARCHAR(20) DEFAULT 'json',

    -- Sharing
    is_public BOOLEAN DEFAULT false,
    public_token VARCHAR(100),

    generated_at TIMESTAMPTZ DEFAULT NOW(),
    viewed_count INTEGER DEFAULT 0,
    last_viewed_at TIMESTAMPTZ
);

-- ============================================
-- 13. MILESTONES TABLE
-- Achievement tracking
-- ============================================
CREATE TABLE milestones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,

    milestone_type VARCHAR(50) NOT NULL CHECK (milestone_type IN ('tons_diverted', 'carbon_saved', 'jobs_completed', 'diversion_rate', 'custom')),
    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Threshold
    threshold_value DECIMAL(12,2) NOT NULL,
    threshold_unit VARCHAR(50),

    -- Achievement
    achieved BOOLEAN DEFAULT false,
    achieved_at TIMESTAMPTZ,
    current_value DECIMAL(12,2) DEFAULT 0,

    -- Display
    icon VARCHAR(50),
    badge_url TEXT,
    points INTEGER DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default milestone templates (will be created per company)
-- These serve as templates for new companies

-- ============================================
-- 14. AGENT_EXECUTIONS TABLE
-- AI agent logs for debugging and audit
-- ============================================
CREATE TABLE agent_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,

    agent_type VARCHAR(50) NOT NULL,
    function_name VARCHAR(100) NOT NULL,

    -- Input/Output
    input_data JSONB,
    output_data JSONB,

    -- Status
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    error_message TEXT,

    -- Metrics
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    execution_time_ms INTEGER,

    -- AI specifics
    model_used VARCHAR(100),
    tokens_used INTEGER,
    cost_usd DECIMAL(10,6)
);

-- ============================================
-- 15. VERTICAL_AI_PROMPTS TABLE
-- Industry-specific AI instructions
-- ============================================
CREATE TABLE vertical_ai_prompts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vertical_id UUID REFERENCES verticals(id) ON DELETE CASCADE,

    prompt_type VARCHAR(50) NOT NULL CHECK (prompt_type IN ('photo_analysis', 'item_detection', 'categorization', 'report_generation')),
    prompt_template TEXT NOT NULL,

    -- Customization
    focus_items JSONB DEFAULT '[]',
    category_mappings JSONB DEFAULT '{}',

    is_active BOOLEAN DEFAULT true,
    version INTEGER DEFAULT 1,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(vertical_id, prompt_type)
);

-- Insert vertical-specific AI prompts
INSERT INTO vertical_ai_prompts (vertical_id, prompt_type, prompt_template, focus_items)
SELECT id, 'photo_analysis',
    'Analyze this image from a junk removal job. Identify all items visible, estimate weights, and categorize them for recycling, donation, or landfill disposal. Focus on furniture, appliances, electronics, and construction materials.',
    '["furniture", "appliances", "electronics", "construction_debris", "yard_waste"]'::jsonb
FROM verticals WHERE slug = 'junk_removal';

INSERT INTO vertical_ai_prompts (vertical_id, prompt_type, prompt_template, focus_items)
SELECT id, 'photo_analysis',
    'Analyze this HVAC service image. Identify equipment types (AC units, furnaces, ductwork), estimate weights of removed equipment, and note any refrigerant-containing components that require special handling.',
    '["hvac_units", "ductwork", "refrigerant_equipment", "filters", "thermostats"]'::jsonb
FROM verticals WHERE slug = 'hvac';

INSERT INTO vertical_ai_prompts (vertical_id, prompt_type, prompt_template, focus_items)
SELECT id, 'photo_analysis',
    'Analyze this roofing job image. Identify roofing materials (asphalt shingles, metal roofing, tiles), estimate square footage and weight of removed materials, and categorize for recycling.',
    '["shingles_asphalt", "shingles_wood", "metal_roofing", "underlayment", "flashing", "gutters"]'::jsonb
FROM verticals WHERE slug = 'roofing';

-- ============================================
-- INDEXES for performance
-- ============================================
CREATE INDEX idx_users_company ON users(company_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_company_verticals_company ON company_verticals(company_id);
CREATE INDEX idx_company_verticals_vertical ON company_verticals(vertical_id);
CREATE INDEX idx_jobs_company ON jobs(company_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_scheduled ON jobs(scheduled_date);
CREATE INDEX idx_jobs_created ON jobs(created_at);
CREATE INDEX idx_job_items_job ON job_items(job_id);
CREATE INDEX idx_job_items_category ON job_items(category);
CREATE INDEX idx_esg_metrics_company ON esg_metrics(company_id);
CREATE INDEX idx_esg_metrics_period ON esg_metrics(period_start, period_end);
CREATE INDEX idx_esg_reports_company ON esg_reports(company_id);
CREATE INDEX idx_milestones_company ON milestones(company_id);
CREATE INDEX idx_agent_executions_job ON agent_executions(job_id);
CREATE INDEX idx_subscriptions_company ON subscriptions(company_id);

-- ============================================
-- ROW LEVEL SECURITY (RLS) Policies
-- ============================================
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE esg_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE esg_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE milestones ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- Companies: users can only see their own company
CREATE POLICY "Users can view own company" ON companies
    FOR SELECT USING (auth.uid() IN (
        SELECT id FROM users WHERE company_id = companies.id
    ));

-- Jobs: users can only see jobs from their company
CREATE POLICY "Users can view own company jobs" ON jobs
    FOR SELECT USING (company_id IN (
        SELECT company_id FROM users WHERE id = auth.uid()
    ));

CREATE POLICY "Users can insert jobs for own company" ON jobs
    FOR INSERT WITH CHECK (company_id IN (
        SELECT company_id FROM users WHERE id = auth.uid()
    ));

CREATE POLICY "Users can update own company jobs" ON jobs
    FOR UPDATE USING (company_id IN (
        SELECT company_id FROM users WHERE id = auth.uid()
    ));

-- ============================================
-- FUNCTIONS for calculations
-- ============================================

-- Function to calculate ESG score
CREATE OR REPLACE FUNCTION calculate_esg_score(
    p_diversion_rate DECIMAL,
    p_recycle_rate DECIMAL,
    p_carbon_offset DECIMAL
) RETURNS INTEGER AS $$
DECLARE
    v_score INTEGER;
BEGIN
    -- Weighted scoring: 40% diversion, 30% recycling, 30% carbon
    v_score := (
        (COALESCE(p_diversion_rate, 0) * 0.4) +
        (COALESCE(p_recycle_rate, 0) * 0.3) +
        (LEAST(COALESCE(p_carbon_offset, 0) / 100, 100) * 0.3)
    )::INTEGER;

    RETURN LEAST(v_score, 100);
END;
$$ LANGUAGE plpgsql;

-- Function to update company ESG metrics
CREATE OR REPLACE FUNCTION update_company_metrics(p_company_id UUID)
RETURNS VOID AS $$
DECLARE
    v_total_weight DECIMAL;
    v_recycled_weight DECIMAL;
    v_landfill_weight DECIMAL;
    v_donated_weight DECIMAL;
    v_carbon_offset DECIMAL;
    v_job_count INTEGER;
BEGIN
    -- Calculate totals from all completed jobs
    SELECT
        COUNT(*),
        COALESCE(SUM(total_weight_lbs), 0),
        COALESCE(SUM(recycled_weight_lbs), 0),
        COALESCE(SUM(landfill_weight_lbs), 0),
        COALESCE(SUM(donated_weight_lbs), 0),
        COALESCE(SUM(carbon_offset_lbs), 0)
    INTO v_job_count, v_total_weight, v_recycled_weight, v_landfill_weight, v_donated_weight, v_carbon_offset
    FROM jobs
    WHERE company_id = p_company_id AND status = 'completed';

    -- Insert or update monthly metrics
    INSERT INTO esg_metrics (
        company_id, period_type, period_start, period_end,
        total_jobs, total_weight_lbs, recycled_weight_lbs, donated_weight_lbs, landfill_weight_lbs,
        carbon_offset_lbs, diversion_rate, recycle_rate, donation_rate
    ) VALUES (
        p_company_id, 'monthly', date_trunc('month', CURRENT_DATE), date_trunc('month', CURRENT_DATE) + interval '1 month' - interval '1 day',
        v_job_count, v_total_weight, v_recycled_weight, v_donated_weight, v_landfill_weight,
        v_carbon_offset,
        CASE WHEN v_total_weight > 0 THEN ((v_recycled_weight + v_donated_weight) / v_total_weight * 100) ELSE 0 END,
        CASE WHEN v_total_weight > 0 THEN (v_recycled_weight / v_total_weight * 100) ELSE 0 END,
        CASE WHEN v_total_weight > 0 THEN (v_donated_weight / v_total_weight * 100) ELSE 0 END
    )
    ON CONFLICT (company_id, period_type, period_start)
    DO UPDATE SET
        total_jobs = EXCLUDED.total_jobs,
        total_weight_lbs = EXCLUDED.total_weight_lbs,
        recycled_weight_lbs = EXCLUDED.recycled_weight_lbs,
        donated_weight_lbs = EXCLUDED.donated_weight_lbs,
        landfill_weight_lbs = EXCLUDED.landfill_weight_lbs,
        carbon_offset_lbs = EXCLUDED.carbon_offset_lbs,
        diversion_rate = EXCLUDED.diversion_rate,
        recycle_rate = EXCLUDED.recycle_rate,
        donation_rate = EXCLUDED.donation_rate,
        calculated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- Trigger to update metrics after job completion
CREATE OR REPLACE FUNCTION trigger_update_metrics()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'completed' AND (OLD.status IS NULL OR OLD.status != 'completed') THEN
        PERFORM update_company_metrics(NEW.company_id);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER job_completed_trigger
AFTER INSERT OR UPDATE ON jobs
FOR EACH ROW
EXECUTE FUNCTION trigger_update_metrics();

-- ============================================
-- SEED DATA for development
-- ============================================

-- Note: In production, remove or modify this seed data
-- This creates a demo company for testing

-- Create demo company
INSERT INTO companies (id, name, email, phone, city, state, zip_code) VALUES
    ('11111111-1111-1111-1111-111111111111', 'Demo Junk Removal Co', 'demo@proofgreen.com', '555-0100', 'San Francisco', 'CA', '94102');

-- Set up demo subscription (Founders plan)
INSERT INTO subscriptions (company_id, plan_id, status, billing_cycle, current_period_start, current_period_end)
SELECT
    '11111111-1111-1111-1111-111111111111',
    id,
    'active',
    'monthly',
    CURRENT_DATE,
    CURRENT_DATE + interval '1 month'
FROM pricing_plans WHERE slug = 'founders';

-- Assign verticals to demo company
INSERT INTO company_verticals (company_id, vertical_id, is_primary)
SELECT '11111111-1111-1111-1111-111111111111', id, slug = 'junk_removal'
FROM verticals WHERE slug IN ('junk_removal', 'demolition', 'moving');

-- Create default milestones for demo company
INSERT INTO milestones (company_id, milestone_type, name, description, threshold_value, threshold_unit, icon, points) VALUES
    ('11111111-1111-1111-1111-111111111111', 'tons_diverted', 'First Ton', 'Diverted your first ton from landfill', 2000, 'lbs', 'trophy', 100),
    ('11111111-1111-1111-1111-111111111111', 'tons_diverted', '10 Tons Club', 'Diverted 10 tons from landfill', 20000, 'lbs', 'medal', 500),
    ('11111111-1111-1111-1111-111111111111', 'tons_diverted', '50 Tons Achievement', 'Diverted 50 tons from landfill', 100000, 'lbs', 'award', 2500),
    ('11111111-1111-1111-1111-111111111111', 'tons_diverted', '100 Tons Legend', 'Diverted 100 tons from landfill', 200000, 'lbs', 'crown', 5000),
    ('11111111-1111-1111-1111-111111111111', 'carbon_saved', 'Carbon Starter', 'Saved 1,000 lbs of CO2', 1000, 'lbs', 'leaf', 100),
    ('11111111-1111-1111-1111-111111111111', 'carbon_saved', 'Carbon Champion', 'Saved 10,000 lbs of CO2', 10000, 'lbs', 'tree', 500),
    ('11111111-1111-1111-1111-111111111111', 'carbon_saved', 'Carbon Hero', 'Saved 50,000 lbs of CO2', 50000, 'lbs', 'globe', 2500),
    ('11111111-1111-1111-1111-111111111111', 'jobs_completed', '10 Jobs', 'Completed 10 tracked jobs', 10, 'jobs', 'check', 50),
    ('11111111-1111-1111-1111-111111111111', 'jobs_completed', '50 Jobs', 'Completed 50 tracked jobs', 50, 'jobs', 'star', 250),
    ('11111111-1111-1111-1111-111111111111', 'jobs_completed', '100 Jobs', 'Completed 100 tracked jobs', 100, 'jobs', 'stars', 500),
    ('11111111-1111-1111-1111-111111111111', 'diversion_rate', 'Green Starter', 'Achieved 50% diversion rate', 50, 'percent', 'recycle', 100),
    ('11111111-1111-1111-1111-111111111111', 'diversion_rate', 'Green Champion', 'Achieved 75% diversion rate', 75, 'percent', 'leaf', 250),
    ('11111111-1111-1111-1111-111111111111', 'diversion_rate', 'Green Legend', 'Achieved 90% diversion rate', 90, 'percent', 'sparkles', 500);

COMMIT;
