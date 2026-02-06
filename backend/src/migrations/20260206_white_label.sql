-- ProofGreen Multi-Tenant / White Label Schema
-- Enables enterprise white-label deployments

-- =============================================================================
-- Tenant System (White Label Partners)
-- =============================================================================

CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Basic Info
    name VARCHAR(255) NOT NULL,                    -- "Greystar"
    slug VARCHAR(100) UNIQUE NOT NULL,             -- "greystar" (for URLs)

    -- Domain Configuration
    subdomain VARCHAR(100) UNIQUE,                 -- "greystar" → greystar.proofgreen.io
    custom_domain VARCHAR(255),                    -- "esg.greystar.com"
    custom_domain_verified BOOLEAN DEFAULT false,

    -- Branding
    branding JSONB DEFAULT '{}'::jsonb,
    -- Structure:
    -- {
    --   "logo_url": "https://...",
    --   "logo_dark_url": "https://...",
    --   "favicon_url": "https://...",
    --   "primary_color": "#1E40AF",
    --   "secondary_color": "#3B82F6",
    --   "accent_color": "#10B981",
    --   "portal_name": "Greystar ESG Portal",
    --   "support_email": "support@greystar.com",
    --   "powered_by_visible": false,
    --   "custom_css": ""
    -- }

    -- Contact
    admin_email VARCHAR(255) NOT NULL,
    admin_name VARCHAR(255),
    billing_email VARCHAR(255),

    -- Subscription
    plan VARCHAR(50) DEFAULT 'white_label_standard',
    pricing_model VARCHAR(50) DEFAULT 'per_vendor',  -- 'flat', 'per_vendor', 'revenue_share', 'hybrid'
    pricing_config JSONB DEFAULT '{}'::jsonb,
    -- Structure for per_vendor:
    -- {
    --   "tiers": [
    --     { "min": 1, "max": 100, "price": 25 },
    --     { "min": 101, "max": 300, "price": 20 },
    --     { "min": 301, "max": 500, "price": 15 },
    --     { "min": 501, "max": null, "price": 12 }
    --   ],
    --   "base_fee": 0,
    --   "minimum_monthly": 500
    -- }

    -- Settings
    settings JSONB DEFAULT '{}'::jsonb,
    -- Structure:
    -- {
    --   "require_vendor_approval": true,
    --   "auto_create_companies": false,
    --   "allowed_verticals": ["junk_removal", "hvac"],
    --   "custom_fields": [...],
    --   "report_footer": "Custom footer text",
    --   "email_from_name": "Greystar ESG Portal"
    -- }

    -- Status
    status VARCHAR(50) DEFAULT 'active',           -- active, suspended, pending

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tenants_subdomain ON tenants(subdomain);
CREATE INDEX idx_tenants_custom_domain ON tenants(custom_domain) WHERE custom_domain IS NOT NULL;
CREATE INDEX idx_tenants_status ON tenants(status);

-- =============================================================================
-- Add Tenant Reference to Companies
-- =============================================================================

ALTER TABLE companies ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS is_vendor BOOLEAN DEFAULT false;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS vendor_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE companies ADD COLUMN IF NOT EXISTS vendor_approved_at TIMESTAMP;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS vendor_approved_by UUID;

CREATE INDEX idx_companies_tenant ON companies(tenant_id) WHERE tenant_id IS NOT NULL;
CREATE INDEX idx_companies_vendor_status ON companies(tenant_id, vendor_status) WHERE tenant_id IS NOT NULL;

-- =============================================================================
-- Tenant Admins (Property Manager Users)
-- =============================================================================

CREATE TABLE IF NOT EXISTS tenant_admins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) DEFAULT 'admin',              -- admin, manager, viewer
    permissions JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, user_id)
);

CREATE INDEX idx_tenant_admins_tenant ON tenant_admins(tenant_id);
CREATE INDEX idx_tenant_admins_user ON tenant_admins(user_id);

-- =============================================================================
-- Tenant Invitations (Vendor Onboarding)
-- =============================================================================

CREATE TABLE IF NOT EXISTS tenant_invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,

    -- Invitation Details
    email VARCHAR(255) NOT NULL,
    company_name VARCHAR(255),
    invitation_code VARCHAR(100) UNIQUE NOT NULL,

    -- Status
    status VARCHAR(50) DEFAULT 'pending',          -- pending, accepted, expired

    -- Tracking
    sent_at TIMESTAMP DEFAULT NOW(),
    accepted_at TIMESTAMP,
    accepted_by_company_id UUID REFERENCES companies(id),
    expires_at TIMESTAMP DEFAULT (NOW() + INTERVAL '30 days'),

    -- Metadata
    invited_by UUID REFERENCES users(id),
    message TEXT,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tenant_invitations_tenant ON tenant_invitations(tenant_id);
CREATE INDEX idx_tenant_invitations_code ON tenant_invitations(invitation_code);
CREATE INDEX idx_tenant_invitations_email ON tenant_invitations(email);

-- =============================================================================
-- Tenant Billing / Usage Tracking
-- =============================================================================

CREATE TABLE IF NOT EXISTS tenant_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,

    -- Period
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    -- Metrics
    active_vendors INTEGER DEFAULT 0,
    total_jobs INTEGER DEFAULT 0,
    total_reports INTEGER DEFAULT 0,

    -- Billing
    amount_due DECIMAL(10,2) DEFAULT 0,
    amount_paid DECIMAL(10,2) DEFAULT 0,
    invoice_id VARCHAR(255),
    paid_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, period_start)
);

CREATE INDEX idx_tenant_usage_tenant ON tenant_usage(tenant_id);
CREATE INDEX idx_tenant_usage_period ON tenant_usage(period_start);

-- =============================================================================
-- Default ProofGreen Tenant (for direct customers)
-- =============================================================================

INSERT INTO tenants (id, name, slug, subdomain, admin_email, branding, status)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'ProofGreen',
    'proofgreen',
    'app',
    'admin@proofgreen.io',
    '{
        "logo_url": "/logo.svg",
        "primary_color": "#10B981",
        "portal_name": "ProofGreen",
        "powered_by_visible": false
    }'::jsonb,
    'active'
) ON CONFLICT (slug) DO NOTHING;

-- =============================================================================
-- Helper Functions
-- =============================================================================

-- Get tenant by subdomain or custom domain
CREATE OR REPLACE FUNCTION get_tenant_by_domain(domain_input VARCHAR)
RETURNS TABLE (
    tenant_id UUID,
    branding JSONB,
    settings JSONB
) AS $$
BEGIN
    -- Check subdomain first (greystar.proofgreen.io → greystar)
    RETURN QUERY
    SELECT t.id, t.branding, t.settings
    FROM tenants t
    WHERE t.subdomain = split_part(domain_input, '.', 1)
       OR t.custom_domain = domain_input
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Count active vendors for a tenant
CREATE OR REPLACE FUNCTION count_active_vendors(tenant_uuid UUID)
RETURNS INTEGER AS $$
DECLARE
    vendor_count INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO vendor_count
    FROM companies
    WHERE tenant_id = tenant_uuid
      AND is_vendor = true
      AND vendor_status = 'approved'
      AND status = 'active';

    RETURN vendor_count;
END;
$$ LANGUAGE plpgsql;

-- Calculate monthly bill for tenant
CREATE OR REPLACE FUNCTION calculate_tenant_bill(tenant_uuid UUID)
RETURNS DECIMAL AS $$
DECLARE
    tenant_record RECORD;
    vendor_count INTEGER;
    total_bill DECIMAL := 0;
    tier RECORD;
    remaining INTEGER;
BEGIN
    -- Get tenant pricing config
    SELECT pricing_model, pricing_config
    INTO tenant_record
    FROM tenants
    WHERE id = tenant_uuid;

    -- Get vendor count
    vendor_count := count_active_vendors(tenant_uuid);

    -- Calculate based on model
    IF tenant_record.pricing_model = 'flat' THEN
        RETURN (tenant_record.pricing_config->>'annual_fee')::DECIMAL / 12;

    ELSIF tenant_record.pricing_model = 'per_vendor' THEN
        remaining := vendor_count;

        FOR tier IN SELECT * FROM jsonb_array_elements(tenant_record.pricing_config->'tiers') AS t
        LOOP
            IF remaining <= 0 THEN EXIT; END IF;

            DECLARE
                tier_min INTEGER := (tier.t->>'min')::INTEGER;
                tier_max INTEGER := COALESCE((tier.t->>'max')::INTEGER, 999999);
                tier_price DECIMAL := (tier.t->>'price')::DECIMAL;
                tier_count INTEGER;
            BEGIN
                tier_count := LEAST(remaining, tier_max - tier_min + 1);
                total_bill := total_bill + (tier_count * tier_price);
                remaining := remaining - tier_count;
            END;
        END LOOP;

        -- Apply minimum
        RETURN GREATEST(total_bill, COALESCE((tenant_record.pricing_config->>'minimum_monthly')::DECIMAL, 0));

    ELSIF tenant_record.pricing_model = 'hybrid' THEN
        -- Base fee + per vendor over threshold
        total_bill := COALESCE((tenant_record.pricing_config->>'base_monthly')::DECIMAL, 0);
        DECLARE
            threshold INTEGER := COALESCE((tenant_record.pricing_config->>'included_vendors')::INTEGER, 0);
            overage_price DECIMAL := COALESCE((tenant_record.pricing_config->>'overage_price')::DECIMAL, 10);
        BEGIN
            IF vendor_count > threshold THEN
                total_bill := total_bill + ((vendor_count - threshold) * overage_price);
            END IF;
        END;
        RETURN total_bill;
    END IF;

    RETURN 0;
END;
$$ LANGUAGE plpgsql;
