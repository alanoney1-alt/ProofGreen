-- Migration 007: Certificates and Agent System Tables
-- For ProofGreen multi-agent ESG verification system

-- ============================================
-- CERTIFICATES TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS certificates (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    certificate_id text UNIQUE NOT NULL,
    company_id uuid REFERENCES companies(id) ON DELETE CASCADE,
    job_id uuid REFERENCES jobs(id) ON DELETE SET NULL,
    type text NOT NULL,
    data jsonb NOT NULL DEFAULT '{}',
    issued_at timestamptz DEFAULT NOW(),
    valid_until timestamptz,
    revoked boolean DEFAULT false,
    revoked_at timestamptz,
    revoked_reason text,
    created_at timestamptz DEFAULT NOW(),
    updated_at timestamptz DEFAULT NOW()
);

-- Create indexes for certificates
CREATE INDEX IF NOT EXISTS idx_certificates_company ON certificates(company_id);
CREATE INDEX IF NOT EXISTS idx_certificates_type ON certificates(type);
CREATE INDEX IF NOT EXISTS idx_certificates_issued_at ON certificates(issued_at);
CREATE INDEX IF NOT EXISTS idx_certificates_certificate_id ON certificates(certificate_id);

-- ============================================
-- AGENT SESSIONS TABLE
-- Track agent interactions and context
-- ============================================

CREATE TABLE IF NOT EXISTS agent_sessions (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id text UNIQUE NOT NULL,
    company_id uuid REFERENCES companies(id) ON DELETE CASCADE,
    user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    agent_type text NOT NULL, -- 'intake', 'ops', 'verifier', 'tax'
    status text DEFAULT 'active', -- 'active', 'completed', 'abandoned'
    context jsonb DEFAULT '{}',
    started_at timestamptz DEFAULT NOW(),
    last_activity_at timestamptz DEFAULT NOW(),
    completed_at timestamptz,
    created_at timestamptz DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_sessions_company ON agent_sessions(company_id);
CREATE INDEX IF NOT EXISTS idx_agent_sessions_user ON agent_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_sessions_type ON agent_sessions(agent_type);

-- ============================================
-- AGENT MESSAGES TABLE
-- Store conversation history
-- ============================================

CREATE TABLE IF NOT EXISTS agent_messages (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id uuid REFERENCES agent_sessions(id) ON DELETE CASCADE,
    role text NOT NULL, -- 'user', 'assistant', 'system'
    content text NOT NULL,
    metadata jsonb DEFAULT '{}',
    created_at timestamptz DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_messages_session ON agent_messages(session_id);

-- ============================================
-- CARBON CALCULATIONS TABLE
-- Store verified carbon calculations
-- ============================================

CREATE TABLE IF NOT EXISTS carbon_calculations (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    company_id uuid REFERENCES companies(id) ON DELETE CASCADE,
    job_id uuid REFERENCES jobs(id) ON DELETE SET NULL,
    calculation_type text NOT NULL, -- 'transport', 'freight', 'hvac', 'waste', 'refrigerant'
    scope text, -- 'scope1', 'scope2', 'scope3'
    input_data jsonb NOT NULL,
    result_data jsonb NOT NULL,
    methodology text, -- 'climatiq', 'ghg_protocol', 'glec_framework'
    source text,
    co2e_kg decimal(12,4),
    co2e_lbs decimal(12,4),
    verified boolean DEFAULT false,
    verification_source text,
    created_at timestamptz DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_carbon_calculations_company ON carbon_calculations(company_id);
CREATE INDEX IF NOT EXISTS idx_carbon_calculations_job ON carbon_calculations(job_id);
CREATE INDEX IF NOT EXISTS idx_carbon_calculations_type ON carbon_calculations(calculation_type);
CREATE INDEX IF NOT EXISTS idx_carbon_calculations_scope ON carbon_calculations(scope);

-- ============================================
-- TAX CREDIT TRACKING TABLE
-- Track identified and claimed tax credits
-- ============================================

CREATE TABLE IF NOT EXISTS tax_credits (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    company_id uuid REFERENCES companies(id) ON DELETE CASCADE,
    credit_type text NOT NULL, -- '45W', '48C', '179D', '25C', '30D', 'state'
    tax_year integer NOT NULL,
    status text DEFAULT 'identified', -- 'identified', 'applied', 'approved', 'claimed', 'denied'

    -- Credit details
    qualifying_activity text,
    qualifying_amount decimal(12,2),
    credit_rate decimal(5,4),
    estimated_credit decimal(12,2),
    actual_credit decimal(12,2),

    -- Supporting data
    job_ids uuid[],
    equipment_ids uuid[],
    documentation jsonb DEFAULT '{}',

    -- State credit details
    state_code char(2),
    state_program text,

    -- Dates
    identified_at timestamptz DEFAULT NOW(),
    applied_at timestamptz,
    decision_at timestamptz,
    claimed_at timestamptz,

    notes text,
    created_at timestamptz DEFAULT NOW(),
    updated_at timestamptz DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tax_credits_company ON tax_credits(company_id);
CREATE INDEX IF NOT EXISTS idx_tax_credits_type ON tax_credits(credit_type);
CREATE INDEX IF NOT EXISTS idx_tax_credits_year ON tax_credits(tax_year);
CREATE INDEX IF NOT EXISTS idx_tax_credits_status ON tax_credits(status);

-- ============================================
-- MOVING SURVEYS TABLE
-- Store CV survey results for moving
-- ============================================

CREATE TABLE IF NOT EXISTS moving_surveys (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    company_id uuid REFERENCES companies(id) ON DELETE CASCADE,
    customer_name text,
    customer_email text,
    customer_phone text,

    -- Location info
    origin_address text,
    destination_address text,
    origin_floor integer,
    destination_floor integer,
    origin_elevator boolean DEFAULT false,
    destination_elevator boolean DEFAULT false,
    distance_miles decimal(8,2),

    -- Survey results
    rooms_analyzed integer DEFAULT 0,
    room_data jsonb DEFAULT '[]',
    inventory jsonb DEFAULT '{}',

    -- Totals
    total_items integer DEFAULT 0,
    total_weight_lbs decimal(10,2) DEFAULT 0,
    total_cubic_ft decimal(10,2) DEFAULT 0,
    special_items_count integer DEFAULT 0,

    -- Generated quote
    quote_data jsonb,
    quote_amount decimal(10,2),
    quote_valid_until timestamptz,

    -- Status
    status text DEFAULT 'draft', -- 'draft', 'quoted', 'accepted', 'declined', 'expired'
    converted_to_job_id uuid REFERENCES jobs(id),

    move_date date,
    created_at timestamptz DEFAULT NOW(),
    updated_at timestamptz DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_moving_surveys_company ON moving_surveys(company_id);
CREATE INDEX IF NOT EXISTS idx_moving_surveys_status ON moving_surveys(status);

-- ============================================
-- FLEET TELEMATICS DATA TABLE
-- Store telematics data from Samsara, Geotab, etc.
-- ============================================

CREATE TABLE IF NOT EXISTS fleet_telematics (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    company_id uuid REFERENCES companies(id) ON DELETE CASCADE,
    vehicle_id uuid REFERENCES vehicles(id) ON DELETE CASCADE,

    -- Telematics source
    provider text NOT NULL, -- 'samsara', 'geotab', 'verizon', 'fleetio'
    external_vehicle_id text,

    -- Location data
    latitude decimal(10,7),
    longitude decimal(10,7),
    location_address text,

    -- Trip data
    trip_id text,
    trip_start_time timestamptz,
    trip_end_time timestamptz,
    trip_distance_miles decimal(10,2),
    trip_duration_minutes integer,

    -- Fuel and emissions
    fuel_consumed_gallons decimal(8,3),
    idle_time_minutes integer,
    idle_fuel_gallons decimal(8,3),

    -- Driver behavior
    driver_id text,
    harsh_braking_count integer DEFAULT 0,
    harsh_acceleration_count integer DEFAULT 0,
    speeding_duration_minutes integer DEFAULT 0,

    -- Engine data
    engine_hours decimal(10,2),
    odometer_miles decimal(12,2),

    -- Raw data
    raw_data jsonb,

    recorded_at timestamptz NOT NULL,
    synced_at timestamptz DEFAULT NOW(),
    created_at timestamptz DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fleet_telematics_company ON fleet_telematics(company_id);
CREATE INDEX IF NOT EXISTS idx_fleet_telematics_vehicle ON fleet_telematics(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_fleet_telematics_recorded_at ON fleet_telematics(recorded_at);
CREATE INDEX IF NOT EXISTS idx_fleet_telematics_trip ON fleet_telematics(trip_id);

-- ============================================
-- ROUTE OPTIMIZATION RESULTS TABLE
-- Store optimized route calculations
-- ============================================

CREATE TABLE IF NOT EXISTS route_optimizations (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    company_id uuid REFERENCES companies(id) ON DELETE CASCADE,

    -- Input data
    date date NOT NULL,
    job_ids uuid[],
    vehicle_ids uuid[],
    start_location jsonb,

    -- Optimization results
    optimized_routes jsonb NOT NULL,
    total_distance_miles decimal(10,2),
    total_duration_minutes integer,
    estimated_fuel_gallons decimal(8,2),
    estimated_co2_lbs decimal(10,2),

    -- Comparison with non-optimized
    original_distance_miles decimal(10,2),
    distance_saved_miles decimal(10,2),
    distance_saved_percent decimal(5,2),
    fuel_saved_gallons decimal(8,2),
    co2_saved_lbs decimal(10,2),

    -- Empty miles analysis
    empty_miles decimal(10,2),
    empty_miles_percent decimal(5,2),
    backhaul_opportunities jsonb,

    status text DEFAULT 'generated', -- 'generated', 'accepted', 'executed', 'completed'
    executed_at timestamptz,

    created_at timestamptz DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_route_optimizations_company ON route_optimizations(company_id);
CREATE INDEX IF NOT EXISTS idx_route_optimizations_date ON route_optimizations(date);

-- ============================================
-- ESG ANNUAL REPORTS TABLE
-- Store generated annual ESG reports
-- ============================================

CREATE TABLE IF NOT EXISTS esg_annual_reports (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    company_id uuid REFERENCES companies(id) ON DELETE CASCADE,
    reporting_year integer NOT NULL,

    -- Emissions by scope
    scope1_co2e_kg decimal(12,2) DEFAULT 0,
    scope2_co2e_kg decimal(12,2) DEFAULT 0,
    scope3_co2e_kg decimal(12,2) DEFAULT 0,
    total_co2e_kg decimal(12,2) DEFAULT 0,

    -- Avoided/offset emissions
    avoided_co2e_kg decimal(12,2) DEFAULT 0,
    offset_co2e_kg decimal(12,2) DEFAULT 0,
    net_co2e_kg decimal(12,2) DEFAULT 0,

    -- Key metrics
    total_jobs integer DEFAULT 0,
    total_miles decimal(12,2) DEFAULT 0,
    total_fuel_gallons decimal(12,2) DEFAULT 0,
    recycling_rate decimal(5,2),
    diversion_rate decimal(5,2),

    -- Certificates issued
    certificates_count integer DEFAULT 0,
    certificates_by_type jsonb DEFAULT '{}',

    -- Tax credits
    tax_credits_identified decimal(12,2) DEFAULT 0,
    tax_credits_claimed decimal(12,2) DEFAULT 0,

    -- Full report data
    report_data jsonb NOT NULL,

    -- Status
    status text DEFAULT 'draft', -- 'draft', 'final', 'published'
    finalized_at timestamptz,
    published_at timestamptz,

    created_at timestamptz DEFAULT NOW(),
    updated_at timestamptz DEFAULT NOW(),

    UNIQUE(company_id, reporting_year)
);

CREATE INDEX IF NOT EXISTS idx_esg_reports_company ON esg_annual_reports(company_id);
CREATE INDEX IF NOT EXISTS idx_esg_reports_year ON esg_annual_reports(reporting_year);

-- ============================================
-- UPDATE TRIGGERS
-- ============================================

CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply update triggers
DROP TRIGGER IF EXISTS update_certificates_modtime ON certificates;
CREATE TRIGGER update_certificates_modtime
    BEFORE UPDATE ON certificates
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

DROP TRIGGER IF EXISTS update_tax_credits_modtime ON tax_credits;
CREATE TRIGGER update_tax_credits_modtime
    BEFORE UPDATE ON tax_credits
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

DROP TRIGGER IF EXISTS update_moving_surveys_modtime ON moving_surveys;
CREATE TRIGGER update_moving_surveys_modtime
    BEFORE UPDATE ON moving_surveys
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

DROP TRIGGER IF EXISTS update_esg_reports_modtime ON esg_annual_reports;
CREATE TRIGGER update_esg_reports_modtime
    BEFORE UPDATE ON esg_annual_reports
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- ============================================
-- ROW LEVEL SECURITY
-- ============================================

ALTER TABLE certificates ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE carbon_calculations ENABLE ROW LEVEL SECURITY;
ALTER TABLE tax_credits ENABLE ROW LEVEL SECURITY;
ALTER TABLE moving_surveys ENABLE ROW LEVEL SECURITY;
ALTER TABLE fleet_telematics ENABLE ROW LEVEL SECURITY;
ALTER TABLE route_optimizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE esg_annual_reports ENABLE ROW LEVEL SECURITY;

-- Certificates policies
CREATE POLICY "Users can view their company certificates" ON certificates
    FOR SELECT USING (
        company_id IN (
            SELECT company_id FROM users WHERE id = auth.uid()
        )
    );

CREATE POLICY "Service role full access to certificates" ON certificates
    FOR ALL USING (auth.role() = 'service_role');

-- Agent sessions policies
CREATE POLICY "Users can view their sessions" ON agent_sessions
    FOR SELECT USING (user_id = auth.uid() OR company_id IN (
        SELECT company_id FROM users WHERE id = auth.uid()
    ));

CREATE POLICY "Service role full access to agent_sessions" ON agent_sessions
    FOR ALL USING (auth.role() = 'service_role');

-- Agent messages policies
CREATE POLICY "Users can view messages from their sessions" ON agent_messages
    FOR SELECT USING (
        session_id IN (
            SELECT id FROM agent_sessions WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Service role full access to agent_messages" ON agent_messages
    FOR ALL USING (auth.role() = 'service_role');

-- Carbon calculations policies
CREATE POLICY "Users can view their company calculations" ON carbon_calculations
    FOR SELECT USING (
        company_id IN (
            SELECT company_id FROM users WHERE id = auth.uid()
        )
    );

CREATE POLICY "Service role full access to carbon_calculations" ON carbon_calculations
    FOR ALL USING (auth.role() = 'service_role');

-- Tax credits policies
CREATE POLICY "Users can view their company tax credits" ON tax_credits
    FOR SELECT USING (
        company_id IN (
            SELECT company_id FROM users WHERE id = auth.uid()
        )
    );

CREATE POLICY "Service role full access to tax_credits" ON tax_credits
    FOR ALL USING (auth.role() = 'service_role');

-- Moving surveys policies
CREATE POLICY "Users can view their company surveys" ON moving_surveys
    FOR SELECT USING (
        company_id IN (
            SELECT company_id FROM users WHERE id = auth.uid()
        )
    );

CREATE POLICY "Service role full access to moving_surveys" ON moving_surveys
    FOR ALL USING (auth.role() = 'service_role');

-- Fleet telematics policies
CREATE POLICY "Users can view their company telematics" ON fleet_telematics
    FOR SELECT USING (
        company_id IN (
            SELECT company_id FROM users WHERE id = auth.uid()
        )
    );

CREATE POLICY "Service role full access to fleet_telematics" ON fleet_telematics
    FOR ALL USING (auth.role() = 'service_role');

-- Route optimizations policies
CREATE POLICY "Users can view their company routes" ON route_optimizations
    FOR SELECT USING (
        company_id IN (
            SELECT company_id FROM users WHERE id = auth.uid()
        )
    );

CREATE POLICY "Service role full access to route_optimizations" ON route_optimizations
    FOR ALL USING (auth.role() = 'service_role');

-- ESG reports policies
CREATE POLICY "Users can view their company ESG reports" ON esg_annual_reports
    FOR SELECT USING (
        company_id IN (
            SELECT company_id FROM users WHERE id = auth.uid()
        )
    );

CREATE POLICY "Service role full access to esg_annual_reports" ON esg_annual_reports
    FOR ALL USING (auth.role() = 'service_role');
