-- ProofGreen Mitigation Features Migration
-- Date: 2026-02-06
-- Features: AI Confidence, Health Scores, Referrals, Trials

-- =============================================================================
-- AI Analysis & Confidence Tracking
-- =============================================================================

-- Store AI analysis results for user verification
CREATE TABLE IF NOT EXISTS job_ai_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,

    -- AI results
    ai_items JSONB,
    ai_confidence_score INTEGER,
    ai_confidence_level VARCHAR(20),
    confidence_factors JSONB,

    -- User verification
    verified_items JSONB,
    verified_weight DECIMAL(10,2),
    user_attested BOOLEAN DEFAULT false,
    user_attested_at TIMESTAMP,
    user_id UUID REFERENCES users(id),
    verification_notes TEXT,

    -- Discrepancy tracking
    weight_discrepancy_lbs DECIMAL(10,2),
    weight_discrepancy_percent DECIMAL(5,2),

    -- Status
    status VARCHAR(50) DEFAULT 'pending_verification',

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_job_ai_analyses_job ON job_ai_analyses(job_id);
CREATE INDEX idx_job_ai_analyses_company ON job_ai_analyses(company_id);
CREATE INDEX idx_job_ai_analyses_status ON job_ai_analyses(status);

-- Add user verification fields to jobs table
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS user_verified BOOLEAN DEFAULT false;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS user_verified_at TIMESTAMP;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS user_verified_by UUID REFERENCES users(id);

-- =============================================================================
-- Customer Health Scores & Churn Prevention
-- =============================================================================

CREATE TABLE IF NOT EXISTS customer_health_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    score INTEGER NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    issues JSONB,
    metrics JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_health_scores_company ON customer_health_scores(company_id);
CREATE INDEX idx_health_scores_risk ON customer_health_scores(risk_level);
CREATE INDEX idx_health_scores_date ON customer_health_scores(created_at);

-- Customer alerts for internal tracking
CREATE TABLE IF NOT EXISTS customer_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    details JSONB,
    resolved BOOLEAN DEFAULT false,
    resolved_at TIMESTAMP,
    resolved_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_customer_alerts_company ON customer_alerts(company_id);
CREATE INDEX idx_customer_alerts_type ON customer_alerts(alert_type);
CREATE INDEX idx_customer_alerts_unresolved ON customer_alerts(resolved) WHERE resolved = false;

-- Customer email tracking (for check-in rate limiting)
CREATE TABLE IF NOT EXISTS customer_emails (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    email_type VARCHAR(50) NOT NULL,
    subject VARCHAR(255),
    sent_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_customer_emails_company ON customer_emails(company_id);
CREATE INDEX idx_customer_emails_type_date ON customer_emails(company_id, email_type, sent_at);

-- =============================================================================
-- Referral System
-- =============================================================================

CREATE TABLE IF NOT EXISTS referral_programs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) UNIQUE,
    referral_code VARCHAR(20) UNIQUE NOT NULL,
    referrals_sent INTEGER DEFAULT 0,
    referrals_converted INTEGER DEFAULT 0,
    total_rewards_earned DECIMAL(10,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_referral_programs_code ON referral_programs(referral_code);

CREATE TABLE IF NOT EXISTS referrals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    referrer_company_id UUID REFERENCES companies(id),
    referred_email VARCHAR(255) NOT NULL,
    referred_company_id UUID REFERENCES companies(id),
    status VARCHAR(50) DEFAULT 'sent',
    reward_amount DECIMAL(10,2) DEFAULT 500.00,
    reward_paid BOOLEAN DEFAULT false,
    converted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_referrals_referrer ON referrals(referrer_company_id);
CREATE INDEX idx_referrals_email ON referrals(referred_email);
CREATE INDEX idx_referrals_status ON referrals(status);

-- Account credits for referral rewards
CREATE TABLE IF NOT EXISTS account_credits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    amount DECIMAL(10,2) NOT NULL,
    type VARCHAR(50) NOT NULL,
    description TEXT,
    applied_to_invoice VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_account_credits_company ON account_credits(company_id);

-- Auto-create referral program on company registration
CREATE OR REPLACE FUNCTION create_referral_program()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO referral_programs (company_id, referral_code)
    VALUES (
        NEW.id,
        'PG-' || UPPER(SUBSTRING(MD5(NEW.id::TEXT) FROM 1 FOR 6))
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS create_referral_on_company ON companies;
CREATE TRIGGER create_referral_on_company
    AFTER INSERT ON companies
    FOR EACH ROW
    EXECUTE FUNCTION create_referral_program();

-- =============================================================================
-- Trial Management
-- =============================================================================

-- Add trial fields to companies table
ALTER TABLE companies ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMP;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS trial_converted BOOLEAN DEFAULT false;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS canceled_at TIMESTAMP;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS cancellation_reason TEXT;

-- Add trial status to subscriptions
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMP;

-- =============================================================================
-- Pricing Plans Update
-- =============================================================================

-- Update pricing plans with new structure
INSERT INTO pricing_plans (plan_name, display_name, price_monthly, max_jobs_per_month, features, sort_order)
VALUES
    ('founders', 'Founders (Limited)', 99.00, NULL,
     '["Unlimited jobs", "Unlimited verticals", "Lifetime price lock", "Early adopter badge"]'::jsonb, 1),
    ('starter', 'Starter', 149.00, 50,
     '["50 jobs/month", "1 vertical", "Basic support"]'::jsonb, 2),
    ('professional', 'Professional', 299.00, 200,
     '["200 jobs/month", "3 verticals", "Priority support", "White-label option"]'::jsonb, 3),
    ('business', 'Business', 599.00, 1000,
     '["1,000 jobs/month", "Unlimited verticals", "Phone support"]'::jsonb, 4),
    ('enterprise', 'Enterprise', 1999.00, NULL,
     '["Unlimited jobs", "Unlimited verticals", "Dedicated account manager", "Custom development"]'::jsonb, 5)
ON CONFLICT (plan_name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    price_monthly = EXCLUDED.price_monthly,
    max_jobs_per_month = EXCLUDED.max_jobs_per_month,
    features = EXCLUDED.features,
    sort_order = EXCLUDED.sort_order;

-- =============================================================================
-- Indexes for Performance
-- =============================================================================

-- Health score lookups
CREATE INDEX IF NOT EXISTS idx_companies_trial ON companies(trial_ends_at)
    WHERE trial_ends_at IS NOT NULL AND trial_converted = false;

-- Active companies for health checks
CREATE INDEX IF NOT EXISTS idx_companies_active ON companies(status)
    WHERE status = 'active';

-- Referral lookups
CREATE INDEX IF NOT EXISTS idx_referrals_pending ON referrals(status, created_at)
    WHERE status = 'sent';
