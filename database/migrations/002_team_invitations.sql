-- Team Invitations Table
-- Migration: Add team invitation support

-- ============================================
-- TEAM_INVITATIONS TABLE
-- Pending team member invitations
-- ============================================
CREATE TABLE IF NOT EXISTS team_invitations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    role VARCHAR(50) DEFAULT 'member' CHECK (role IN ('admin', 'manager', 'member')),
    token VARCHAR(255) UNIQUE NOT NULL,
    invited_by UUID REFERENCES users(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'expired', 'revoked')),
    expires_at TIMESTAMPTZ NOT NULL,
    accepted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Prevent duplicate pending invitations
    UNIQUE(company_id, email, status)
);

-- Index for token lookups
CREATE INDEX IF NOT EXISTS idx_team_invitations_token ON team_invitations(token);
CREATE INDEX IF NOT EXISTS idx_team_invitations_company ON team_invitations(company_id);
CREATE INDEX IF NOT EXISTS idx_team_invitations_status ON team_invitations(status);

-- ============================================
-- Add stripe_customer_id to companies table
-- ============================================
ALTER TABLE companies
ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255);

-- ============================================
-- Add password reset tokens table
-- ============================================
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_password_reset_token ON password_reset_tokens(token);

-- ============================================
-- Add email preferences to users
-- ============================================
ALTER TABLE users
ADD COLUMN IF NOT EXISTS email_preferences JSONB DEFAULT '{"weekly_summary": true, "milestone_notifications": true, "job_notifications": true}'::jsonb;

-- ============================================
-- Function to auto-expire invitations
-- ============================================
CREATE OR REPLACE FUNCTION expire_old_invitations()
RETURNS void AS $$
BEGIN
    UPDATE team_invitations
    SET status = 'expired'
    WHERE status = 'pending'
    AND expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- RLS Policies for team_invitations
-- ============================================
ALTER TABLE team_invitations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view invitations for their company" ON team_invitations
    FOR SELECT USING (company_id IN (
        SELECT company_id FROM users WHERE id = auth.uid()
    ));

CREATE POLICY "Admins can create invitations" ON team_invitations
    FOR INSERT WITH CHECK (company_id IN (
        SELECT company_id FROM users
        WHERE id = auth.uid()
        AND role IN ('owner', 'admin')
    ));

CREATE POLICY "Admins can update invitations" ON team_invitations
    FOR UPDATE USING (company_id IN (
        SELECT company_id FROM users
        WHERE id = auth.uid()
        AND role IN ('owner', 'admin')
    ));

COMMIT;
