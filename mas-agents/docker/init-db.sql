-- ProofGreen MAS - Database Initialization
-- PostgreSQL 15+

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================
-- Green Ledger - Core ESG Data
-- ============================================
CREATE TABLE IF NOT EXISTS green_ledger (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(255) UNIQUE NOT NULL,
    company_id VARCHAR(100) NOT NULL,

    -- Equipment Details
    old_equipment_type VARCHAR(100),
    old_refrigerant VARCHAR(50),
    old_seer DECIMAL(4,1),
    new_equipment_type VARCHAR(100),
    new_refrigerant VARCHAR(50),
    new_seer DECIMAL(4,1),

    -- Environmental Impact
    co2_avoided_lbs DECIMAL(10,2),
    kwh_saved_annual DECIMAL(10,2),
    refrigerant_lbs_recovered DECIMAL(6,2),

    -- Financials (encrypted in app layer)
    total_job_cost DECIMAL(12,2),
    federal_rebate DECIMAL(10,2),
    state_rebate DECIMAL(10,2),
    utility_rebate DECIMAL(10,2),
    total_incentives DECIMAL(10,2),
    customer_net_cost DECIMAL(12,2),

    -- Compliance
    epa_aim_compliant BOOLEAN DEFAULT FALSE,
    seer2_compliant BOOLEAN DEFAULT FALSE,
    state_code VARCHAR(10),
    compliance_notes TEXT,

    -- Governance
    approved_by VARCHAR(100),
    approved_at TIMESTAMP,
    workflow_id VARCHAR(255),

    -- Audit Trail
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_green_ledger_company ON green_ledger(company_id);
CREATE INDEX idx_green_ledger_state ON green_ledger(state_code);
CREATE INDEX idx_green_ledger_created ON green_ledger(created_at);

-- ============================================
-- Workflow Checkpoints - LangGraph State
-- ============================================
CREATE TABLE IF NOT EXISTS workflow_checkpoints (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(255) NOT NULL,
    thread_id VARCHAR(255) NOT NULL,
    current_node VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',

    -- State Storage
    state_json JSONB NOT NULL,

    -- Human-in-the-Loop
    requires_approval BOOLEAN DEFAULT FALSE,
    approved BOOLEAN,
    approved_by VARCHAR(100),
    approval_notes TEXT,
    approved_at TIMESTAMP,

    -- Timing
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_checkpoints_job ON workflow_checkpoints(job_id);
CREATE INDEX idx_checkpoints_thread ON workflow_checkpoints(thread_id);
CREATE INDEX idx_checkpoints_status ON workflow_checkpoints(status);
CREATE INDEX idx_checkpoints_approval ON workflow_checkpoints(requires_approval, approved);

-- ============================================
-- Audit Trail - Governance Events
-- ============================================
CREATE TABLE IF NOT EXISTS audit_trail (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    company_id VARCHAR(100),

    -- Actor
    actor_type VARCHAR(50) NOT NULL,  -- 'user', 'agent', 'system'
    actor_id VARCHAR(100),
    actor_name VARCHAR(255),

    -- Event Details
    action VARCHAR(100) NOT NULL,
    old_value JSONB,
    new_value JSONB,
    metadata JSONB,

    -- Security
    ip_address INET,
    user_agent TEXT,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_entity ON audit_trail(entity_type, entity_id);
CREATE INDEX idx_audit_company ON audit_trail(company_id);
CREATE INDEX idx_audit_actor ON audit_trail(actor_type, actor_id);
CREATE INDEX idx_audit_created ON audit_trail(created_at);

-- ============================================
-- Credentials Vault - Encrypted Storage
-- ============================================
CREATE TABLE IF NOT EXISTS credentials_vault (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id VARCHAR(100) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    auth_type VARCHAR(20) NOT NULL,  -- 'oauth', 'api_key'

    -- Encrypted credentials (AES-256)
    encrypted_data TEXT NOT NULL,
    encryption_iv TEXT NOT NULL,

    -- OAuth specific
    token_expires_at TIMESTAMP,
    refresh_token_expires_at TIMESTAMP,

    -- Status
    status VARCHAR(20) DEFAULT 'active',
    last_used_at TIMESTAMP,
    last_refresh_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(company_id, provider)
);

CREATE INDEX idx_credentials_company ON credentials_vault(company_id);
CREATE INDEX idx_credentials_status ON credentials_vault(status);
CREATE INDEX idx_credentials_expires ON credentials_vault(token_expires_at);

-- ============================================
-- Lessons Learned - RLHF Memory
-- ============================================
CREATE TABLE IF NOT EXISTS lessons_learned (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id VARCHAR(100) NOT NULL,
    job_id VARCHAR(255),

    -- What was learned
    lesson_type VARCHAR(50) NOT NULL,
    field_overridden VARCHAR(100),
    original_value TEXT,
    corrected_value TEXT,
    reason TEXT,

    -- Context for RAG retrieval
    context_json JSONB,
    embedding_id VARCHAR(255),

    -- Attribution
    technician_id VARCHAR(100),
    technician_name VARCHAR(255),

    -- Usage tracking
    times_cited INTEGER DEFAULT 0,
    last_cited_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_lessons_company ON lessons_learned(company_id);
CREATE INDEX idx_lessons_type ON lessons_learned(lesson_type);
CREATE INDEX idx_lessons_field ON lessons_learned(field_overridden);

-- ============================================
-- Legal Scout - Regulatory Tracking
-- ============================================
CREATE TABLE IF NOT EXISTS regulatory_scan_log (
    id SERIAL PRIMARY KEY,
    scan_time TIMESTAMP NOT NULL,
    sources_checked INTEGER NOT NULL,
    updates_found INTEGER DEFAULT 0,
    errors JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS indexed_regulations (
    id VARCHAR(255) PRIMARY KEY,
    source VARCHAR(100) NOT NULL,
    title TEXT,
    summary TEXT,
    category VARCHAR(50),
    state VARCHAR(10),
    effective_date DATE,
    priority VARCHAR(20),
    indexed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_regulations_category ON indexed_regulations(category);
CREATE INDEX idx_regulations_state ON indexed_regulations(state);
CREATE INDEX idx_regulations_effective ON indexed_regulations(effective_date);

-- ============================================
-- FSM Integration - Connection Status
-- ============================================
CREATE TABLE IF NOT EXISTS fsm_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id VARCHAR(100) NOT NULL,
    provider VARCHAR(50) NOT NULL,

    -- Connection Config
    connection_config JSONB,
    field_mappings JSONB,

    -- Status
    status VARCHAR(20) DEFAULT 'pending',
    last_sync_at TIMESTAMP,
    last_error TEXT,
    error_count INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(company_id, provider)
);

CREATE INDEX idx_fsm_company ON fsm_connections(company_id);
CREATE INDEX idx_fsm_status ON fsm_connections(status);

-- ============================================
-- Scheduling - Technician Availability
-- ============================================
CREATE TABLE IF NOT EXISTS technician_schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    technician_id VARCHAR(100) NOT NULL,
    company_id VARCHAR(100) NOT NULL,

    -- Time slot
    slot_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,

    -- Job assignment
    job_id VARCHAR(255),
    job_type VARCHAR(50),
    location_lat DECIMAL(9,6),
    location_lng DECIMAL(9,6),

    -- Status
    status VARCHAR(20) DEFAULT 'available',

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_schedules_tech ON technician_schedules(technician_id);
CREATE INDEX idx_schedules_date ON technician_schedules(slot_date);
CREATE INDEX idx_schedules_status ON technician_schedules(status);

-- ============================================
-- Functions & Triggers
-- ============================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_green_ledger_updated_at
    BEFORE UPDATE ON green_ledger
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_checkpoints_updated_at
    BEFORE UPDATE ON workflow_checkpoints
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_credentials_updated_at
    BEFORE UPDATE ON credentials_vault
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_fsm_updated_at
    BEFORE UPDATE ON fsm_connections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Initial Data
-- ============================================

-- Insert default regulatory sources
INSERT INTO indexed_regulations (id, source, title, category, priority, indexed_at) VALUES
('epa_aim_2024', 'epa_aim_act', 'EPA AIM Act - HFC Phasedown 2024', 'refrigerant', 'high', NOW()),
('seer2_2023', 'doe_efficiency', 'DOE SEER2 Standards Effective 2023', 'efficiency', 'high', NOW()),
('ira_25c_2024', 'irs_incentives', 'IRA Section 25C - Energy Efficient Home Improvement Credit', 'incentives', 'high', NOW())
ON CONFLICT (id) DO NOTHING;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO proofgreen;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO proofgreen;
