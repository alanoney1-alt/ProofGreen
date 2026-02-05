-- =============================================
-- PROOFGREEN EQUIPMENT & MATERIALS DATABASE
-- Comprehensive data collection for ESG compliance
-- =============================================

-- Equipment Manufacturers
CREATE TABLE IF NOT EXISTS manufacturers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    website VARCHAR(500),
    logo_url VARCHAR(500),
    country VARCHAR(100),
    sustainability_rating VARCHAR(10), -- A, B, C, D, F
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Equipment Models Database (HVAC, Appliances, etc.)
CREATE TABLE IF NOT EXISTS equipment_models (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    manufacturer_id UUID REFERENCES manufacturers(id),
    model_number VARCHAR(255) NOT NULL,
    model_name VARCHAR(500),
    category VARCHAR(100) NOT NULL, -- hvac, appliance, water_heater, etc.
    subcategory VARCHAR(100), -- split_system, package_unit, mini_split, etc.

    -- Efficiency Ratings
    seer_rating DECIMAL(5,2), -- HVAC cooling efficiency
    eer_rating DECIMAL(5,2), -- Energy Efficiency Ratio
    hspf_rating DECIMAL(5,2), -- Heating Seasonal Performance Factor
    afue_rating DECIMAL(5,2), -- Annual Fuel Utilization Efficiency (furnaces)
    energy_star_certified BOOLEAN DEFAULT FALSE,

    -- Refrigerant Info
    refrigerant_type VARCHAR(50), -- R-410A, R-32, R-454B, etc.
    refrigerant_charge_oz DECIMAL(10,2), -- Factory charge in ounces
    gwp_value INTEGER, -- Global Warming Potential

    -- Power Specs
    voltage VARCHAR(20),
    amperage DECIMAL(10,2),
    wattage INTEGER,
    btu_capacity INTEGER,
    tonnage DECIMAL(4,2),

    -- Physical Specs
    weight_lbs DECIMAL(10,2),
    dimensions_json JSONB, -- {height, width, depth}

    -- Environmental Data
    annual_energy_kwh INTEGER, -- Estimated annual energy consumption
    co2_emissions_annual_lbs DECIMAL(10,2),
    expected_lifespan_years INTEGER,
    recyclable_percentage DECIMAL(5,2),

    -- Documentation
    spec_sheet_url VARCHAR(500),
    manual_url VARCHAR(500),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Refrigerant Types (EPA Section 608)
CREATE TABLE IF NOT EXISTS refrigerants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    epa_designation VARCHAR(50), -- R-410A, R-22, etc.
    chemical_formula VARCHAR(100),
    gwp_value INTEGER NOT NULL, -- Global Warming Potential (CO2 = 1)
    odp_value DECIMAL(5,3), -- Ozone Depletion Potential
    phase_out_date DATE, -- If being phased out
    replacement_refrigerant VARCHAR(50),
    safety_classification VARCHAR(10), -- A1, A2L, B1, etc.
    is_regulated BOOLEAN DEFAULT TRUE,
    disposal_requirements TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Chemical Products (Pest Control, Cleaning, etc.)
CREATE TABLE IF NOT EXISTS chemicals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    epa_registration_number VARCHAR(100),
    manufacturer_id UUID REFERENCES manufacturers(id),
    category VARCHAR(100), -- pesticide, herbicide, cleaning, etc.
    active_ingredients JSONB, -- [{name, percentage}]

    -- Safety Data
    signal_word VARCHAR(50), -- Danger, Warning, Caution
    toxicity_category INTEGER, -- 1-4 (1 most toxic)
    ppe_required JSONB, -- Personal Protective Equipment

    -- Environmental Impact
    eco_toxicity_rating VARCHAR(10),
    water_contamination_risk VARCHAR(20),
    soil_persistence_days INTEGER,
    pollinator_safe BOOLEAN,
    organic_certified BOOLEAN DEFAULT FALSE,

    -- Application Data
    application_methods JSONB, -- [spray, bait, fog, etc.]
    dilution_ratio VARCHAR(50),
    coverage_sqft_per_gallon DECIMAL(10,2),
    reentry_interval_hours INTEGER,

    -- Documentation
    sds_url VARCHAR(500), -- Safety Data Sheet
    label_url VARCHAR(500),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Materials Database (Plumbing, Electrical, Construction)
CREATE TABLE IF NOT EXISTS materials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL, -- pipe, wire, insulation, etc.
    subcategory VARCHAR(100),

    -- Specifications
    material_type VARCHAR(100), -- copper, pvc, pex, etc.
    size_options JSONB, -- Available sizes
    unit_of_measure VARCHAR(50), -- ft, each, lb, etc.

    -- Environmental Data
    embodied_carbon_kg_per_unit DECIMAL(10,4),
    recyclable BOOLEAN DEFAULT FALSE,
    recycled_content_percentage DECIMAL(5,2),
    voc_emissions VARCHAR(50), -- Low, Medium, High, None
    lifespan_years INTEGER,

    -- Water-Specific (Plumbing)
    flow_rate_gpm DECIMAL(5,2),
    water_efficiency_rating VARCHAR(20),
    lead_free BOOLEAN,

    -- Certifications
    certifications JSONB, -- [NSF, LEED, WaterSense, etc.]

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Vehicle Fleet Database
CREATE TABLE IF NOT EXISTS vehicles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    vehicle_type VARCHAR(50) NOT NULL, -- van, truck, car
    make VARCHAR(100),
    model VARCHAR(100),
    year INTEGER,
    license_plate VARCHAR(20),
    vin VARCHAR(50),

    -- Fuel/Energy
    fuel_type VARCHAR(50), -- gasoline, diesel, electric, hybrid
    mpg_city DECIMAL(5,2),
    mpg_highway DECIMAL(5,2),
    tank_capacity_gallons DECIMAL(5,2),
    battery_capacity_kwh DECIMAL(10,2), -- For EVs

    -- Emissions
    co2_grams_per_mile DECIMAL(10,2),
    emissions_class VARCHAR(20),

    -- Tracking
    gps_tracker_id VARCHAR(100),
    current_odometer INTEGER,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Service Trip Tracking (Mileage)
CREATE TABLE IF NOT EXISTS service_trips (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    vehicle_id UUID REFERENCES vehicles(id),
    technician_id UUID REFERENCES users(id),

    -- Locations
    origin_address TEXT,
    origin_lat DECIMAL(10,7),
    origin_lng DECIMAL(10,7),
    destination_address TEXT,
    destination_lat DECIMAL(10,7),
    destination_lng DECIMAL(10,7),

    -- Trip Data
    distance_miles DECIMAL(10,2),
    duration_minutes INTEGER,
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,

    -- Emissions Calculated
    fuel_used_gallons DECIMAL(10,3),
    co2_emissions_lbs DECIMAL(10,2),

    -- Route Info
    route_polyline TEXT, -- Encoded route
    trip_type VARCHAR(50), -- to_job, from_job, between_jobs

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Job Materials Used (Links jobs to materials)
CREATE TABLE IF NOT EXISTS job_materials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    material_id UUID REFERENCES materials(id),

    quantity DECIMAL(10,2) NOT NULL,
    unit VARCHAR(50),

    -- For custom/unlisted materials
    custom_material_name VARCHAR(255),
    custom_material_specs JSONB,

    -- Environmental tracking
    waste_generated_lbs DECIMAL(10,2),
    recycled_lbs DECIMAL(10,2),
    disposed_lbs DECIMAL(10,2),

    -- Cost tracking
    unit_cost DECIMAL(10,2),
    total_cost DECIMAL(10,2),

    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Job Equipment (Equipment installed/serviced)
CREATE TABLE IF NOT EXISTS job_equipment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    equipment_model_id UUID REFERENCES equipment_models(id),

    action_type VARCHAR(50) NOT NULL, -- install, repair, replace, remove, service

    -- For HVAC refrigerant tracking
    refrigerant_id UUID REFERENCES refrigerants(id),
    refrigerant_added_oz DECIMAL(10,2),
    refrigerant_recovered_oz DECIMAL(10,2),
    refrigerant_leaked_oz DECIMAL(10,2),

    -- Old equipment (if replacing)
    old_equipment_model VARCHAR(255),
    old_equipment_age_years INTEGER,
    old_equipment_disposed BOOLEAN,
    disposal_method VARCHAR(100), -- recycled, scrapped, donated
    disposal_certificate_url VARCHAR(500),

    -- Serial numbers
    serial_number VARCHAR(255),
    old_serial_number VARCHAR(255),

    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Job Chemicals Used (Pest Control, Cleaning)
CREATE TABLE IF NOT EXISTS job_chemicals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    chemical_id UUID REFERENCES chemicals(id),

    quantity_used DECIMAL(10,3),
    unit VARCHAR(50), -- oz, gal, lb
    dilution_ratio VARCHAR(50),

    -- Application details
    application_method VARCHAR(100),
    area_treated_sqft DECIMAL(10,2),
    target_pest VARCHAR(255),

    -- For custom/unlisted chemicals
    custom_chemical_name VARCHAR(255),
    custom_epa_reg_number VARCHAR(100),

    -- Safety compliance
    applicator_license_number VARCHAR(100),
    weather_conditions JSONB, -- {temp, wind, humidity}

    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Water Usage Tracking (Plumbing, Irrigation)
CREATE TABLE IF NOT EXISTS job_water_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,

    -- Water metrics
    water_used_gallons DECIMAL(10,2),
    water_saved_gallons DECIMAL(10,2), -- From efficiency upgrades

    -- Fixture changes
    old_fixture_gpm DECIMAL(5,2),
    new_fixture_gpm DECIMAL(5,2),
    fixtures_replaced INTEGER,

    -- Leak repairs
    leak_fixed BOOLEAN,
    estimated_leak_gpd DECIMAL(10,2), -- Gallons per day leaked

    -- Irrigation
    irrigation_zone_sqft DECIMAL(10,2),
    irrigation_efficiency_rating VARCHAR(20),
    smart_controller_installed BOOLEAN,

    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Waste Tracking
CREATE TABLE IF NOT EXISTS job_waste (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,

    waste_type VARCHAR(100) NOT NULL, -- construction, hazardous, recyclable, organic
    material_description TEXT,

    quantity_lbs DECIMAL(10,2),

    -- Disposal
    disposal_method VARCHAR(100), -- landfill, recycled, hazmat, donated
    disposal_facility VARCHAR(255),
    manifest_number VARCHAR(100), -- For hazardous waste

    -- Recycling
    recycled BOOLEAN DEFAULT FALSE,
    recycling_certificate_url VARCHAR(500),

    -- Cost
    disposal_cost DECIMAL(10,2),
    recycling_rebate DECIMAL(10,2),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Document Storage (Invoices, Manifests, Certificates)
CREATE TABLE IF NOT EXISTS job_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,

    document_type VARCHAR(100) NOT NULL, -- invoice, manifest, certificate, permit, photo
    title VARCHAR(255),
    description TEXT,

    -- File info
    file_url VARCHAR(500) NOT NULL,
    file_name VARCHAR(255),
    file_size_bytes INTEGER,
    mime_type VARCHAR(100),

    -- OCR Data
    ocr_processed BOOLEAN DEFAULT FALSE,
    ocr_extracted_data JSONB, -- Extracted text and structured data
    ocr_confidence DECIMAL(5,2),

    -- Metadata
    tags JSONB, -- ['epa', 'disposal', 'refrigerant']

    uploaded_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- External System Integrations
CREATE TABLE IF NOT EXISTS integrations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,

    provider VARCHAR(100) NOT NULL, -- servicetitan, housecall_pro, jobber, quickbooks, etc.
    status VARCHAR(50) DEFAULT 'pending', -- pending, active, error, disconnected

    -- OAuth tokens (encrypted in production)
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TIMESTAMP WITH TIME ZONE,

    -- Settings
    sync_enabled BOOLEAN DEFAULT TRUE,
    last_sync_at TIMESTAMP WITH TIME ZONE,
    sync_frequency_minutes INTEGER DEFAULT 60,

    -- Mapping config
    field_mappings JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Integration Sync Logs
CREATE TABLE IF NOT EXISTS integration_sync_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    integration_id UUID REFERENCES integrations(id) ON DELETE CASCADE,

    sync_type VARCHAR(50), -- full, incremental, manual
    status VARCHAR(50), -- started, completed, failed

    records_synced INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    error_message TEXT,

    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_equipment_models_category ON equipment_models(category);
CREATE INDEX IF NOT EXISTS idx_equipment_models_manufacturer ON equipment_models(manufacturer_id);
CREATE INDEX IF NOT EXISTS idx_equipment_models_model_number ON equipment_models(model_number);
CREATE INDEX IF NOT EXISTS idx_chemicals_category ON chemicals(category);
CREATE INDEX IF NOT EXISTS idx_chemicals_epa_reg ON chemicals(epa_registration_number);
CREATE INDEX IF NOT EXISTS idx_materials_category ON materials(category);
CREATE INDEX IF NOT EXISTS idx_vehicles_company ON vehicles(company_id);
CREATE INDEX IF NOT EXISTS idx_service_trips_job ON service_trips(job_id);
CREATE INDEX IF NOT EXISTS idx_job_materials_job ON job_materials(job_id);
CREATE INDEX IF NOT EXISTS idx_job_equipment_job ON job_equipment(job_id);
CREATE INDEX IF NOT EXISTS idx_job_chemicals_job ON job_chemicals(job_id);
CREATE INDEX IF NOT EXISTS idx_job_documents_job ON job_documents(job_id);
CREATE INDEX IF NOT EXISTS idx_integrations_company ON integrations(company_id);

-- =============================================
-- SEED DATA
-- =============================================

-- Insert Manufacturers
INSERT INTO manufacturers (name, website, country, sustainability_rating) VALUES
('Carrier', 'https://www.carrier.com', 'USA', 'A'),
('Trane', 'https://www.trane.com', 'USA', 'A'),
('Lennox', 'https://www.lennox.com', 'USA', 'A'),
('Rheem', 'https://www.rheem.com', 'USA', 'B'),
('Goodman', 'https://www.goodmanmfg.com', 'USA', 'B'),
('Daikin', 'https://www.daikin.com', 'Japan', 'A'),
('Mitsubishi Electric', 'https://www.mitsubishielectric.com', 'Japan', 'A'),
('Fujitsu', 'https://www.fujitsu-general.com', 'Japan', 'A'),
('Bosch', 'https://www.bosch.com', 'Germany', 'A'),
('LG', 'https://www.lg.com', 'South Korea', 'B'),
('Samsung', 'https://www.samsung.com', 'South Korea', 'B'),
('Kohler', 'https://www.kohler.com', 'USA', 'A'),
('Moen', 'https://www.moen.com', 'USA', 'B'),
('Delta', 'https://www.deltafaucet.com', 'USA', 'B'),
('A.O. Smith', 'https://www.aosmith.com', 'USA', 'B'),
('Bradford White', 'https://www.bradfordwhite.com', 'USA', 'B'),
('Rinnai', 'https://www.rinnai.us', 'Japan', 'A'),
('Navien', 'https://www.navieninc.com', 'South Korea', 'A'),
('SunPower', 'https://www.sunpower.com', 'USA', 'A'),
('Tesla', 'https://www.tesla.com', 'USA', 'A'),
('Generac', 'https://www.generac.com', 'USA', 'B'),
('Orkin', 'https://www.orkin.com', 'USA', 'B'),
('Terminix', 'https://www.terminix.com', 'USA', 'B'),
('BASF', 'https://www.basf.com', 'Germany', 'B'),
('Bayer', 'https://www.bayer.com', 'Germany', 'B'),
('Scotts', 'https://www.scotts.com', 'USA', 'C'),
('John Deere', 'https://www.deere.com', 'USA', 'B'),
('Husqvarna', 'https://www.husqvarna.com', 'Sweden', 'A'),
('STIHL', 'https://www.stihlusa.com', 'Germany', 'B'),
('Milwaukee Tool', 'https://www.milwaukeetool.com', 'USA', 'B')
ON CONFLICT DO NOTHING;

-- Insert Refrigerants (EPA Section 608)
INSERT INTO refrigerants (name, epa_designation, chemical_formula, gwp_value, odp_value, phase_out_date, replacement_refrigerant, safety_classification, is_regulated, disposal_requirements) VALUES
('R-22 (HCFC-22)', 'R-22', 'CHClF2', 1810, 0.055, '2020-01-01', 'R-410A', 'A1', TRUE, 'Must be recovered by EPA-certified technician. Cannot be vented.'),
('R-410A', 'R-410A', 'CH2F2/CHF2CF3', 2088, 0, '2025-01-01', 'R-32, R-454B', 'A1', TRUE, 'Must be recovered. Being phased down under AIM Act.'),
('R-32', 'R-32', 'CH2F2', 675, 0, NULL, NULL, 'A2L', TRUE, 'Must be recovered. Lower GWP alternative.'),
('R-454B', 'R-454B', 'R-32/R-1234yf', 466, 0, NULL, NULL, 'A2L', TRUE, 'Must be recovered. Approved R-410A replacement.'),
('R-134a', 'R-134a', 'CH2FCF3', 1430, 0, NULL, 'R-1234yf', 'A1', TRUE, 'Must be recovered. Common in automotive and chillers.'),
('R-1234yf', 'R-1234yf', 'CF3CF=CH2', 4, 0, NULL, NULL, 'A2L', FALSE, 'Low GWP. Preferred for new automotive systems.'),
('R-290 (Propane)', 'R-290', 'C3H8', 3, 0, NULL, NULL, 'A3', TRUE, 'Flammable. Special handling required.'),
('R-404A', 'R-404A', 'R-125/R-143a/R-134a', 3922, 0, '2024-01-01', 'R-448A, R-449A', 'A1', TRUE, 'High GWP. Being phased out for commercial refrigeration.'),
('R-407C', 'R-407C', 'R-32/R-125/R-134a', 1774, 0, NULL, 'R-32', 'A1', TRUE, 'Must be recovered.'),
('R-123', 'R-123', 'CHCl2CF3', 77, 0.02, '2030-01-01', 'R-514A', 'B1', TRUE, 'HCFC being phased out. Used in centrifugal chillers.')
ON CONFLICT DO NOTHING;

-- Insert Common Materials
INSERT INTO materials (name, category, subcategory, material_type, unit_of_measure, embodied_carbon_kg_per_unit, recyclable, recycled_content_percentage, lifespan_years) VALUES
-- Plumbing Pipes
('Copper Pipe Type L 1/2"', 'pipe', 'water_supply', 'copper', 'ft', 0.89, TRUE, 35, 50),
('Copper Pipe Type L 3/4"', 'pipe', 'water_supply', 'copper', 'ft', 1.34, TRUE, 35, 50),
('PEX Tubing 1/2"', 'pipe', 'water_supply', 'pex', 'ft', 0.12, TRUE, 0, 40),
('PEX Tubing 3/4"', 'pipe', 'water_supply', 'pex', 'ft', 0.18, TRUE, 0, 40),
('PVC Pipe Schedule 40 2"', 'pipe', 'drain', 'pvc', 'ft', 0.45, TRUE, 0, 30),
('PVC Pipe Schedule 40 4"', 'pipe', 'drain', 'pvc', 'ft', 0.89, TRUE, 0, 30),
('Cast Iron Pipe 4"', 'pipe', 'drain', 'cast_iron', 'ft', 2.34, TRUE, 95, 75),
('CPVC Pipe 1/2"', 'pipe', 'water_supply', 'cpvc', 'ft', 0.15, TRUE, 0, 35),

-- Electrical Wire
('Romex 14/2 NM-B', 'wire', 'residential', 'copper', 'ft', 0.23, TRUE, 30, 40),
('Romex 12/2 NM-B', 'wire', 'residential', 'copper', 'ft', 0.31, TRUE, 30, 40),
('THHN Wire 12 AWG', 'wire', 'commercial', 'copper', 'ft', 0.18, TRUE, 30, 40),
('MC Cable 12/2', 'wire', 'commercial', 'aluminum_clad', 'ft', 0.42, TRUE, 45, 40),

-- Insulation
('Fiberglass Batt R-13', 'insulation', 'wall', 'fiberglass', 'sqft', 0.08, TRUE, 40, 50),
('Fiberglass Batt R-19', 'insulation', 'attic', 'fiberglass', 'sqft', 0.11, TRUE, 40, 50),
('Spray Foam Closed Cell', 'insulation', 'wall', 'polyurethane', 'sqft', 0.45, FALSE, 0, 80),
('Blown Cellulose R-38', 'insulation', 'attic', 'cellulose', 'sqft', 0.03, TRUE, 85, 40),

-- HVAC Materials
('Refrigerant Line Set 3/8 x 3/4', 'hvac', 'lineset', 'copper', 'ft', 1.45, TRUE, 35, 25),
('Ductwork Flex 6"', 'hvac', 'duct', 'fiberglass_flex', 'ft', 0.34, FALSE, 0, 15),
('Ductwork Sheet Metal 6"', 'hvac', 'duct', 'galvanized_steel', 'ft', 0.78, TRUE, 25, 30),
('Condensate Drain Line 3/4"', 'hvac', 'drain', 'pvc', 'ft', 0.08, TRUE, 0, 20)
ON CONFLICT DO NOTHING;

-- Insert Common Chemicals (Pest Control)
INSERT INTO chemicals (name, epa_registration_number, category, active_ingredients, signal_word, toxicity_category, eco_toxicity_rating, pollinator_safe, organic_certified, application_methods, coverage_sqft_per_gallon) VALUES
('Termidor SC', '7969-210', 'termiticide', '[{"name": "Fipronil", "percentage": 9.1}]', 'Caution', 3, 'Moderate', FALSE, FALSE, '["soil_injection", "trench"]', 1000),
('Demand CS', '100-1066', 'insecticide', '[{"name": "Lambda-cyhalothrin", "percentage": 9.7}]', 'Caution', 3, 'High', FALSE, FALSE, '["spray", "crack_crevice"]', 2000),
('Temprid FX', '432-1544', 'insecticide', '[{"name": "Imidacloprid", "percentage": 21}, {"name": "Beta-cyfluthrin", "percentage": 10.5}]', 'Caution', 3, 'Moderate', FALSE, FALSE, '["spray"]', 1500),
('Advion Cockroach Gel', '100-1484', 'insecticide', '[{"name": "Indoxacarb", "percentage": 0.6}]', 'Caution', 4, 'Low', TRUE, FALSE, '["bait"]', NULL),
('Sentricon Bait', '62719-699', 'termiticide', '[{"name": "Noviflumuron", "percentage": 0.5}]', 'Caution', 4, 'Low', TRUE, FALSE, '["bait_station"]', NULL),
('EcoRaider', '89997-3', 'insecticide', '[{"name": "Cedar oil", "percentage": 1}, {"name": "Geraniol", "percentage": 1}]', 'None', 4, 'Low', TRUE, TRUE, '["spray"]', 1000),
('Talstar P', '279-3206', 'insecticide', '[{"name": "Bifenthrin", "percentage": 7.9}]', 'Caution', 3, 'High', FALSE, FALSE, '["spray", "granular"]', 1000),
('Suspend SC', '432-763', 'insecticide', '[{"name": "Deltamethrin", "percentage": 4.75}]', 'Caution', 3, 'Moderate', FALSE, FALSE, '["spray"]', 1500),
('Phantom', '241-392', 'insecticide', '[{"name": "Chlorfenapyr", "percentage": 21.45}]', 'Warning', 2, 'Moderate', FALSE, FALSE, '["spray", "foam"]', 1000),
('Essentria IC3', '86530-2', 'insecticide', '[{"name": "Rosemary oil", "percentage": 10}, {"name": "Peppermint oil", "percentage": 2}]', 'None', 4, 'Low', TRUE, TRUE, '["spray"]', 1000)
ON CONFLICT DO NOTHING;

-- Insert Sample Equipment Models
INSERT INTO equipment_models (manufacturer_id, model_number, model_name, category, subcategory, seer_rating, eer_rating, hspf_rating, energy_star_certified, refrigerant_type, refrigerant_charge_oz, gwp_value, btu_capacity, tonnage, annual_energy_kwh, co2_emissions_annual_lbs)
SELECT
    m.id,
    '24ACC636A003',
    'Carrier Comfort 16 Central AC',
    'hvac',
    'split_system_ac',
    16,
    13,
    NULL,
    TRUE,
    'R-410A',
    124,
    2088,
    36000,
    3,
    1200,
    1584
FROM manufacturers m WHERE m.name = 'Carrier'
ON CONFLICT DO NOTHING;

INSERT INTO equipment_models (manufacturer_id, model_number, model_name, category, subcategory, seer_rating, eer_rating, hspf_rating, energy_star_certified, refrigerant_type, refrigerant_charge_oz, gwp_value, btu_capacity, tonnage, annual_energy_kwh, co2_emissions_annual_lbs)
SELECT
    m.id,
    'XR15-048',
    'Trane XR15 Heat Pump',
    'hvac',
    'heat_pump',
    15,
    12.5,
    8.5,
    TRUE,
    'R-410A',
    148,
    2088,
    48000,
    4,
    1600,
    2112
FROM manufacturers m WHERE m.name = 'Trane'
ON CONFLICT DO NOTHING;

INSERT INTO equipment_models (manufacturer_id, model_number, model_name, category, subcategory, seer_rating, eer_rating, hspf_rating, energy_star_certified, refrigerant_type, refrigerant_charge_oz, gwp_value, btu_capacity, tonnage, annual_energy_kwh, co2_emissions_annual_lbs)
SELECT
    m.id,
    'MSZ-FH12NA',
    'Mitsubishi Hyper-Heating Mini Split',
    'hvac',
    'mini_split',
    26,
    15.4,
    12.5,
    TRUE,
    'R-410A',
    38,
    2088,
    12000,
    1,
    450,
    594
FROM manufacturers m WHERE m.name = 'Mitsubishi Electric'
ON CONFLICT DO NOTHING;

-- Water Heaters
INSERT INTO equipment_models (manufacturer_id, model_number, model_name, category, subcategory, energy_star_certified, annual_energy_kwh, co2_emissions_annual_lbs, expected_lifespan_years)
SELECT
    m.id,
    'DERA50',
    'Rheem ProTerra Hybrid Heat Pump Water Heater 50 Gal',
    'water_heater',
    'heat_pump',
    TRUE,
    800,
    1056,
    15
FROM manufacturers m WHERE m.name = 'Rheem'
ON CONFLICT DO NOTHING;

INSERT INTO equipment_models (manufacturer_id, model_number, model_name, category, subcategory, energy_star_certified, annual_energy_kwh, co2_emissions_annual_lbs, expected_lifespan_years)
SELECT
    m.id,
    'RU199iN',
    'Rinnai Tankless Water Heater',
    'water_heater',
    'tankless_gas',
    TRUE,
    150,
    650,
    20
FROM manufacturers m WHERE m.name = 'Rinnai'
ON CONFLICT DO NOTHING;

RAISE NOTICE 'Equipment database migration completed successfully';
