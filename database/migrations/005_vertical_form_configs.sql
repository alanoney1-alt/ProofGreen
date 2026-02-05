-- =============================================
-- COMPREHENSIVE VERTICAL-SPECIFIC FORM CONFIGURATIONS
-- Defines all data collection fields for ESG compliance
-- =============================================

-- Clear existing form configs and insert comprehensive ones
DELETE FROM vertical_form_config;

-- =============================================
-- HVAC VERTICAL
-- =============================================
INSERT INTO vertical_form_config (vertical_id, form_config)
SELECT id, '{
    "sections": [
        {
            "id": "service_type",
            "title": "Service Type",
            "fields": [
                {"name": "service_category", "type": "select", "label": "Service Category", "required": true, "options": ["Installation", "Repair", "Maintenance", "Replacement", "Inspection", "Emergency Service"]},
                {"name": "system_type", "type": "select", "label": "System Type", "required": true, "options": ["Central AC", "Heat Pump", "Furnace", "Mini-Split", "Package Unit", "Rooftop Unit", "Chiller", "Boiler", "Ductless", "Geothermal"]}
            ]
        },
        {
            "id": "equipment_details",
            "title": "Equipment Details",
            "fields": [
                {"name": "equipment_model_id", "type": "equipment_lookup", "label": "Equipment Model", "category": "hvac", "required": false},
                {"name": "custom_make", "type": "text", "label": "Make (if not in list)", "required": false},
                {"name": "custom_model", "type": "text", "label": "Model Number (if not in list)", "required": false},
                {"name": "serial_number", "type": "text", "label": "Serial Number", "required": false},
                {"name": "manufacture_year", "type": "number", "label": "Manufacture Year", "min": 1980, "max": 2030},
                {"name": "tonnage", "type": "select", "label": "Tonnage/Capacity", "options": ["1", "1.5", "2", "2.5", "3", "3.5", "4", "5", "6", "7.5", "10", "12.5", "15", "20", "25+"]},
                {"name": "seer_rating", "type": "number", "label": "SEER Rating", "min": 8, "max": 30, "step": 0.5},
                {"name": "energy_star", "type": "boolean", "label": "ENERGY STAR Certified"}
            ]
        },
        {
            "id": "refrigerant_tracking",
            "title": "Refrigerant Tracking (EPA 608)",
            "description": "Required for systems with 50+ lbs of refrigerant",
            "fields": [
                {"name": "refrigerant_id", "type": "refrigerant_lookup", "label": "Refrigerant Type", "required": true},
                {"name": "refrigerant_custom", "type": "text", "label": "Other Refrigerant Type", "showIf": "refrigerant_id === other"},
                {"name": "system_charge_oz", "type": "number", "label": "System Full Charge (oz)", "min": 0, "step": 0.1},
                {"name": "refrigerant_added_oz", "type": "number", "label": "Refrigerant Added (oz)", "min": 0, "step": 0.1, "helperText": "Amount added during service"},
                {"name": "refrigerant_recovered_oz", "type": "number", "label": "Refrigerant Recovered (oz)", "min": 0, "step": 0.1, "helperText": "Amount recovered for recycling/reclamation"},
                {"name": "refrigerant_leaked_estimated_oz", "type": "number", "label": "Estimated Leak Amount (oz)", "min": 0, "step": 0.1},
                {"name": "leak_detected", "type": "boolean", "label": "Leak Detected?"},
                {"name": "leak_location", "type": "text", "label": "Leak Location", "showIf": "leak_detected === true"},
                {"name": "leak_repaired", "type": "boolean", "label": "Leak Repaired?", "showIf": "leak_detected === true"},
                {"name": "recovery_cylinder_id", "type": "text", "label": "Recovery Cylinder ID"},
                {"name": "epa_608_cert_number", "type": "text", "label": "Technician EPA 608 Cert #", "required": true}
            ]
        },
        {
            "id": "old_equipment",
            "title": "Old Equipment (if replacing)",
            "showIf": "service_category === Replacement || service_category === Installation",
            "fields": [
                {"name": "old_equipment_removed", "type": "boolean", "label": "Old Equipment Removed?"},
                {"name": "old_make", "type": "text", "label": "Old Equipment Make"},
                {"name": "old_model", "type": "text", "label": "Old Equipment Model"},
                {"name": "old_serial", "type": "text", "label": "Old Serial Number"},
                {"name": "old_age_years", "type": "number", "label": "Old Equipment Age (years)"},
                {"name": "old_seer", "type": "number", "label": "Old SEER Rating", "helperText": "For efficiency improvement calculation"},
                {"name": "old_refrigerant_type", "type": "text", "label": "Old Refrigerant Type"},
                {"name": "old_refrigerant_recovered_oz", "type": "number", "label": "Refrigerant Recovered from Old Unit (oz)"},
                {"name": "disposal_method", "type": "select", "label": "Disposal Method", "options": ["Recycling Facility", "Manufacturer Take-Back", "Scrap Metal", "EPA-Certified Disposal", "Customer Keeping"]},
                {"name": "disposal_facility", "type": "text", "label": "Disposal Facility Name"},
                {"name": "disposal_certificate", "type": "file", "label": "Disposal Certificate/Receipt", "accept": "image/*,application/pdf"}
            ]
        },
        {
            "id": "materials_used",
            "title": "Materials Used",
            "fields": [
                {"name": "materials", "type": "material_list", "label": "Materials", "categories": ["hvac", "pipe", "wire", "insulation"]},
                {"name": "lineset_length_ft", "type": "number", "label": "Line Set Length (ft)"},
                {"name": "ductwork_added_ft", "type": "number", "label": "Ductwork Added (linear ft)"},
                {"name": "insulation_sqft", "type": "number", "label": "Insulation Added (sq ft)"},
                {"name": "thermostat_type", "type": "select", "label": "Thermostat Installed", "options": ["None", "Basic", "Programmable", "Smart/WiFi", "Zoning System"]}
            ]
        },
        {
            "id": "efficiency_impact",
            "title": "Energy Efficiency Impact",
            "fields": [
                {"name": "estimated_annual_savings_kwh", "type": "number", "label": "Estimated Annual Energy Savings (kWh)"},
                {"name": "estimated_annual_savings_dollars", "type": "number", "label": "Estimated Annual Cost Savings ($)"},
                {"name": "co2_reduction_annual_lbs", "type": "number", "label": "Estimated Annual CO2 Reduction (lbs)", "computed": true}
            ]
        }
    ]
}'::jsonb
FROM verticals WHERE slug = 'hvac';

-- =============================================
-- PLUMBING VERTICAL
-- =============================================
INSERT INTO vertical_form_config (vertical_id, form_config)
SELECT id, '{
    "sections": [
        {
            "id": "service_type",
            "title": "Service Type",
            "fields": [
                {"name": "service_category", "type": "select", "label": "Service Category", "required": true, "options": ["Repair", "Installation", "Replacement", "Inspection", "Emergency", "Maintenance", "Drain Cleaning", "Water Heater Service", "Repiping", "Sewer Line"]},
                {"name": "work_area", "type": "multiselect", "label": "Work Areas", "options": ["Kitchen", "Bathroom", "Laundry", "Outdoor", "Basement", "Whole House", "Commercial"]}
            ]
        },
        {
            "id": "water_fixtures",
            "title": "Water Fixtures",
            "description": "Track fixture efficiency for water conservation",
            "fields": [
                {"name": "fixtures_installed", "type": "fixture_list", "label": "Fixtures Installed/Replaced", "options": [
                    {"type": "toilet", "label": "Toilet", "flow_field": "gpf"},
                    {"type": "faucet_bathroom", "label": "Bathroom Faucet", "flow_field": "gpm"},
                    {"type": "faucet_kitchen", "label": "Kitchen Faucet", "flow_field": "gpm"},
                    {"type": "showerhead", "label": "Showerhead", "flow_field": "gpm"},
                    {"type": "dishwasher", "label": "Dishwasher", "flow_field": "gallons_per_cycle"},
                    {"type": "washing_machine", "label": "Washing Machine", "flow_field": "gallons_per_cycle"},
                    {"type": "urinal", "label": "Urinal", "flow_field": "gpf"}
                ]},
                {"name": "watersense_certified", "type": "boolean", "label": "WaterSense Certified Fixtures"},
                {"name": "old_fixture_flow_rate", "type": "number", "label": "Old Fixture Flow Rate (GPM/GPF)", "helperText": "For water savings calculation"},
                {"name": "new_fixture_flow_rate", "type": "number", "label": "New Fixture Flow Rate (GPM/GPF)"},
                {"name": "estimated_daily_uses", "type": "number", "label": "Estimated Daily Uses"}
            ]
        },
        {
            "id": "leak_repair",
            "title": "Leak Detection & Repair",
            "fields": [
                {"name": "leak_repaired", "type": "boolean", "label": "Leak Repaired?"},
                {"name": "leak_type", "type": "select", "label": "Leak Type", "showIf": "leak_repaired === true", "options": ["Faucet Drip", "Toilet Flapper", "Supply Line", "Drain Line", "Slab Leak", "Pipe Joint", "Water Heater", "Outdoor Spigot", "Irrigation"]},
                {"name": "leak_severity", "type": "select", "label": "Leak Severity", "showIf": "leak_repaired === true", "options": ["Minor Drip (<1 GPD)", "Moderate (1-10 GPD)", "Significant (10-50 GPD)", "Major (50+ GPD)"]},
                {"name": "estimated_water_loss_gpd", "type": "number", "label": "Estimated Water Loss (gallons/day)", "showIf": "leak_repaired === true"},
                {"name": "annual_water_saved_gallons", "type": "number", "label": "Annual Water Saved (gallons)", "computed": true}
            ]
        },
        {
            "id": "piping",
            "title": "Piping Materials",
            "fields": [
                {"name": "pipe_materials", "type": "material_list", "label": "Piping Materials Used", "categories": ["pipe"]},
                {"name": "pipe_type_installed", "type": "select", "label": "Primary Pipe Type", "options": ["Copper", "PEX", "CPVC", "PVC", "Cast Iron", "Galvanized", "HDPE", "ABS"]},
                {"name": "pipe_length_ft", "type": "number", "label": "Total Pipe Length (ft)"},
                {"name": "lead_free_certified", "type": "boolean", "label": "Lead-Free Certified Materials"},
                {"name": "old_pipe_material", "type": "select", "label": "Old Pipe Material Replaced", "options": ["None", "Lead", "Galvanized", "Polybutylene", "Copper", "Cast Iron", "Other"]},
                {"name": "old_pipe_length_removed_ft", "type": "number", "label": "Old Pipe Removed (ft)"}
            ]
        },
        {
            "id": "water_heater",
            "title": "Water Heater Service",
            "showIf": "service_category === Water Heater Service || service_category === Installation || service_category === Replacement",
            "fields": [
                {"name": "water_heater_work", "type": "select", "label": "Water Heater Work", "options": ["None", "New Installation", "Replacement", "Repair", "Maintenance Flush"]},
                {"name": "wh_type", "type": "select", "label": "Water Heater Type", "options": ["Tank Gas", "Tank Electric", "Tankless Gas", "Tankless Electric", "Heat Pump", "Solar", "Hybrid"]},
                {"name": "wh_capacity_gallons", "type": "number", "label": "Capacity (gallons)", "showIf": "wh_type !== Tankless Gas && wh_type !== Tankless Electric"},
                {"name": "wh_energy_factor", "type": "number", "label": "Energy Factor (UEF)", "step": 0.01},
                {"name": "wh_energy_star", "type": "boolean", "label": "ENERGY STAR Certified"},
                {"name": "old_wh_type", "type": "select", "label": "Old Water Heater Type", "showIf": "water_heater_work === Replacement"},
                {"name": "old_wh_age_years", "type": "number", "label": "Old Water Heater Age (years)", "showIf": "water_heater_work === Replacement"},
                {"name": "old_wh_energy_factor", "type": "number", "label": "Old Energy Factor", "showIf": "water_heater_work === Replacement", "step": 0.01}
            ]
        },
        {
            "id": "waste_disposal",
            "title": "Waste & Disposal",
            "fields": [
                {"name": "waste_generated_lbs", "type": "number", "label": "Total Waste Generated (lbs)"},
                {"name": "metal_recycled_lbs", "type": "number", "label": "Metal Recycled (lbs)"},
                {"name": "hazmat_disposed", "type": "boolean", "label": "Hazardous Materials Disposed?"},
                {"name": "hazmat_type", "type": "text", "label": "Hazardous Material Type", "showIf": "hazmat_disposed === true"},
                {"name": "hazmat_weight_lbs", "type": "number", "label": "Hazmat Weight (lbs)", "showIf": "hazmat_disposed === true"}
            ]
        }
    ]
}'::jsonb
FROM verticals WHERE slug = 'plumbing';

-- =============================================
-- ELECTRICAL VERTICAL
-- =============================================
INSERT INTO vertical_form_config (vertical_id, form_config)
SELECT id, '{
    "sections": [
        {
            "id": "service_type",
            "title": "Service Type",
            "fields": [
                {"name": "service_category", "type": "select", "label": "Service Category", "required": true, "options": ["Installation", "Repair", "Upgrade", "Inspection", "Panel Work", "Lighting", "EV Charger", "Solar", "Generator", "Emergency"]},
                {"name": "permit_required", "type": "boolean", "label": "Permit Required"},
                {"name": "permit_number", "type": "text", "label": "Permit Number", "showIf": "permit_required === true"}
            ]
        },
        {
            "id": "panel_work",
            "title": "Electrical Panel",
            "showIf": "service_category === Panel Work || service_category === Upgrade",
            "fields": [
                {"name": "panel_work_type", "type": "select", "label": "Panel Work Type", "options": ["New Installation", "Upgrade", "Replacement", "Subpanel", "Repair"]},
                {"name": "new_panel_amps", "type": "select", "label": "New Panel Capacity (Amps)", "options": ["100", "150", "200", "320", "400"]},
                {"name": "old_panel_amps", "type": "number", "label": "Old Panel Capacity (Amps)"},
                {"name": "solar_ready", "type": "boolean", "label": "Solar-Ready Panel"},
                {"name": "ev_ready", "type": "boolean", "label": "EV Charging Ready"},
                {"name": "whole_home_surge", "type": "boolean", "label": "Whole Home Surge Protector Installed"}
            ]
        },
        {
            "id": "lighting",
            "title": "Lighting",
            "showIf": "service_category === Lighting || service_category === Installation",
            "fields": [
                {"name": "fixtures_installed", "type": "number", "label": "Number of Fixtures Installed"},
                {"name": "lighting_type", "type": "select", "label": "Lighting Type", "options": ["LED", "CFL", "Incandescent", "Halogen", "Fluorescent", "Mixed"]},
                {"name": "total_wattage_new", "type": "number", "label": "Total New Wattage"},
                {"name": "total_wattage_replaced", "type": "number", "label": "Total Old Wattage Replaced"},
                {"name": "smart_controls", "type": "boolean", "label": "Smart Controls/Dimmers Installed"},
                {"name": "occupancy_sensors", "type": "number", "label": "Occupancy Sensors Installed"},
                {"name": "daylight_harvesting", "type": "boolean", "label": "Daylight Harvesting System"},
                {"name": "estimated_kwh_savings_annual", "type": "number", "label": "Estimated Annual kWh Savings", "computed": true}
            ]
        },
        {
            "id": "ev_charger",
            "title": "EV Charger Installation",
            "showIf": "service_category === EV Charger",
            "fields": [
                {"name": "charger_level", "type": "select", "label": "Charger Level", "options": ["Level 1 (120V)", "Level 2 (240V)", "Level 3 DC Fast Charger"]},
                {"name": "charger_amps", "type": "select", "label": "Charger Amperage", "options": ["16", "24", "32", "40", "48", "50", "80"]},
                {"name": "charger_make", "type": "text", "label": "Charger Make/Brand"},
                {"name": "charger_model", "type": "text", "label": "Charger Model"},
                {"name": "energy_star_certified", "type": "boolean", "label": "ENERGY STAR Certified"},
                {"name": "smart_charger", "type": "boolean", "label": "Smart/Connected Charger"},
                {"name": "circuit_distance_ft", "type": "number", "label": "Circuit Run Distance (ft)"},
                {"name": "estimated_annual_kwh", "type": "number", "label": "Estimated Annual Usage (kWh)"},
                {"name": "replaces_gas_vehicle", "type": "boolean", "label": "Customer Replacing Gas Vehicle"},
                {"name": "estimated_gas_gallons_saved", "type": "number", "label": "Estimated Annual Gas Gallons Saved", "showIf": "replaces_gas_vehicle === true"}
            ]
        },
        {
            "id": "solar",
            "title": "Solar Installation",
            "showIf": "service_category === Solar",
            "fields": [
                {"name": "system_size_kw", "type": "number", "label": "System Size (kW)", "step": 0.1},
                {"name": "panel_count", "type": "number", "label": "Number of Panels"},
                {"name": "panel_wattage", "type": "number", "label": "Panel Wattage Each"},
                {"name": "panel_manufacturer", "type": "text", "label": "Panel Manufacturer"},
                {"name": "inverter_type", "type": "select", "label": "Inverter Type", "options": ["String Inverter", "Microinverters", "Power Optimizers", "Hybrid"]},
                {"name": "battery_storage", "type": "boolean", "label": "Battery Storage Included"},
                {"name": "battery_capacity_kwh", "type": "number", "label": "Battery Capacity (kWh)", "showIf": "battery_storage === true"},
                {"name": "estimated_annual_production_kwh", "type": "number", "label": "Estimated Annual Production (kWh)"},
                {"name": "roof_type", "type": "select", "label": "Roof Type", "options": ["Composite Shingle", "Metal", "Tile", "Flat/TPO", "Slate", "Wood Shake"]},
                {"name": "roof_age_years", "type": "number", "label": "Roof Age (years)"},
                {"name": "azimuth_degrees", "type": "number", "label": "Array Azimuth (degrees)"},
                {"name": "tilt_degrees", "type": "number", "label": "Array Tilt (degrees)"}
            ]
        },
        {
            "id": "generator",
            "title": "Generator Installation",
            "showIf": "service_category === Generator",
            "fields": [
                {"name": "generator_type", "type": "select", "label": "Generator Type", "options": ["Portable", "Standby Natural Gas", "Standby Propane", "Standby Diesel", "Solar/Battery Backup"]},
                {"name": "generator_kw", "type": "number", "label": "Generator Capacity (kW)"},
                {"name": "generator_make", "type": "text", "label": "Generator Make"},
                {"name": "generator_model", "type": "text", "label": "Generator Model"},
                {"name": "transfer_switch_type", "type": "select", "label": "Transfer Switch", "options": ["Manual", "Automatic", "None"]},
                {"name": "whole_home_coverage", "type": "boolean", "label": "Whole Home Coverage"},
                {"name": "estimated_annual_runtime_hours", "type": "number", "label": "Estimated Annual Runtime (hours)"},
                {"name": "fuel_consumption_gph", "type": "number", "label": "Fuel Consumption (gal/hr)", "step": 0.1}
            ]
        },
        {
            "id": "materials",
            "title": "Materials Used",
            "fields": [
                {"name": "wire_materials", "type": "material_list", "label": "Wire/Cable", "categories": ["wire"]},
                {"name": "total_wire_ft", "type": "number", "label": "Total Wire/Cable (ft)"},
                {"name": "conduit_ft", "type": "number", "label": "Conduit Installed (ft)"},
                {"name": "outlets_installed", "type": "number", "label": "Outlets Installed"},
                {"name": "switches_installed", "type": "number", "label": "Switches Installed"},
                {"name": "breakers_installed", "type": "number", "label": "Breakers Installed"}
            ]
        }
    ]
}'::jsonb
FROM verticals WHERE slug = 'electrical';

-- =============================================
-- PEST CONTROL VERTICAL
-- =============================================
INSERT INTO vertical_form_config (vertical_id, form_config)
SELECT id, '{
    "sections": [
        {
            "id": "service_type",
            "title": "Service Type",
            "fields": [
                {"name": "service_category", "type": "select", "label": "Service Category", "required": true, "options": ["Initial Treatment", "Recurring Service", "One-Time Treatment", "Inspection", "Emergency", "Exclusion Work"]},
                {"name": "target_pests", "type": "multiselect", "label": "Target Pests", "required": true, "options": ["Ants", "Cockroaches", "Spiders", "Termites", "Bed Bugs", "Rodents", "Mosquitoes", "Wasps/Bees", "Fleas/Ticks", "Wildlife", "Stored Product Pests", "Other"]}
            ]
        },
        {
            "id": "treatment_area",
            "title": "Treatment Area",
            "fields": [
                {"name": "treatment_location", "type": "multiselect", "label": "Treatment Locations", "options": ["Interior - All Rooms", "Interior - Kitchen", "Interior - Bathrooms", "Interior - Bedrooms", "Interior - Basement", "Interior - Attic", "Exterior - Foundation", "Exterior - Perimeter", "Exterior - Yard", "Exterior - Trees/Shrubs", "Crawl Space", "Garage"]},
                {"name": "total_sqft_treated", "type": "number", "label": "Total Area Treated (sq ft)"},
                {"name": "linear_ft_treated", "type": "number", "label": "Linear Feet Treated (perimeter)"}
            ]
        },
        {
            "id": "chemicals_used",
            "title": "Chemicals/Products Applied",
            "description": "Document all pesticide applications for regulatory compliance",
            "fields": [
                {"name": "chemicals", "type": "chemical_list", "label": "Products Applied", "required": true},
                {"name": "application_method", "type": "multiselect", "label": "Application Methods", "options": ["Spray - Broadcast", "Spray - Crack & Crevice", "Spray - Spot Treatment", "Bait - Gel", "Bait - Granular", "Bait - Station", "Dust", "Foam", "Fumigation", "Trapping", "Exclusion Materials"]},
                {"name": "total_product_oz", "type": "number", "label": "Total Product Used (oz)", "step": 0.1},
                {"name": "dilution_ratio", "type": "text", "label": "Dilution Ratio (if applicable)"},
                {"name": "total_solution_gallons", "type": "number", "label": "Total Solution Applied (gallons)", "step": 0.1}
            ]
        },
        {
            "id": "applicator_info",
            "title": "Applicator Information",
            "fields": [
                {"name": "applicator_license", "type": "text", "label": "Applicator License Number", "required": true},
                {"name": "license_state", "type": "text", "label": "License State"},
                {"name": "license_category", "type": "multiselect", "label": "License Categories", "options": ["General Pest", "Termite/WDO", "Fumigation", "Rodent", "Wildlife", "Lawn & Ornamental"]}
            ]
        },
        {
            "id": "environmental_conditions",
            "title": "Environmental Conditions",
            "fields": [
                {"name": "temperature_f", "type": "number", "label": "Temperature (°F)"},
                {"name": "wind_speed_mph", "type": "number", "label": "Wind Speed (mph)"},
                {"name": "precipitation", "type": "select", "label": "Precipitation", "options": ["None", "Light Rain", "Heavy Rain", "Snow"]},
                {"name": "wind_direction", "type": "select", "label": "Wind Direction", "options": ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "Calm"]}
            ]
        },
        {
            "id": "ipm_practices",
            "title": "IPM (Integrated Pest Management)",
            "fields": [
                {"name": "ipm_inspection_completed", "type": "boolean", "label": "IPM Inspection Completed"},
                {"name": "sanitation_recommendations", "type": "textarea", "label": "Sanitation Recommendations"},
                {"name": "exclusion_work", "type": "boolean", "label": "Exclusion Work Performed"},
                {"name": "exclusion_details", "type": "textarea", "label": "Exclusion Details", "showIf": "exclusion_work === true"},
                {"name": "monitoring_devices_placed", "type": "number", "label": "Monitoring Devices Placed"},
                {"name": "habitat_modification", "type": "textarea", "label": "Habitat Modification Recommendations"},
                {"name": "organic_treatment", "type": "boolean", "label": "Organic/Green Treatment Used"},
                {"name": "pollinator_safe_products", "type": "boolean", "label": "Pollinator-Safe Products Only"}
            ]
        },
        {
            "id": "termite_specific",
            "title": "Termite Treatment Details",
            "showIf": "target_pests includes Termites",
            "fields": [
                {"name": "termite_treatment_type", "type": "select", "label": "Treatment Type", "options": ["Liquid Barrier", "Bait System", "Spot Treatment", "Fumigation", "Heat Treatment", "Wood Treatment"]},
                {"name": "linear_ft_treated", "type": "number", "label": "Linear Feet Treated"},
                {"name": "gallons_termiticide", "type": "number", "label": "Gallons of Termiticide"},
                {"name": "bait_stations_installed", "type": "number", "label": "Bait Stations Installed"},
                {"name": "wdo_report_filed", "type": "boolean", "label": "WDO Report Filed"},
                {"name": "wdo_report_number", "type": "text", "label": "WDO Report Number", "showIf": "wdo_report_filed === true"}
            ]
        },
        {
            "id": "safety_compliance",
            "title": "Safety & Compliance",
            "fields": [
                {"name": "sds_provided", "type": "boolean", "label": "SDS Available to Customer"},
                {"name": "reentry_interval_hours", "type": "number", "label": "Re-entry Interval (hours)"},
                {"name": "pets_removed", "type": "boolean", "label": "Pets Removed During Treatment"},
                {"name": "children_present", "type": "boolean", "label": "Children Under 12 in Home"},
                {"name": "sensitive_populations", "type": "boolean", "label": "Sensitive Populations Present", "helperText": "Pregnant, elderly, immune-compromised"},
                {"name": "ppe_worn", "type": "multiselect", "label": "PPE Worn", "options": ["Gloves", "Respirator", "Safety Glasses", "Coveralls", "Boot Covers"]}
            ]
        }
    ]
}'::jsonb
FROM verticals WHERE slug = 'pest-control';

-- =============================================
-- MOVING VERTICAL
-- =============================================
INSERT INTO vertical_form_config (vertical_id, form_config)
SELECT id, '{
    "sections": [
        {
            "id": "move_type",
            "title": "Move Details",
            "fields": [
                {"name": "move_type", "type": "select", "label": "Move Type", "required": true, "options": ["Local (< 50 miles)", "Long Distance (50+ miles)", "Interstate", "International", "Commercial/Office", "Storage Only"]},
                {"name": "service_level", "type": "select", "label": "Service Level", "options": ["Full Service Pack & Move", "Load & Unload Only", "Unload Only", "Labor Only", "Container/Pod"]},
                {"name": "move_date", "type": "date", "label": "Move Date"}
            ]
        },
        {
            "id": "locations",
            "title": "Origin & Destination",
            "fields": [
                {"name": "origin_address", "type": "address", "label": "Origin Address", "required": true},
                {"name": "origin_floor", "type": "number", "label": "Origin Floor Level"},
                {"name": "origin_elevator", "type": "boolean", "label": "Origin Has Elevator"},
                {"name": "origin_stairs_flights", "type": "number", "label": "Origin Stairs (flights)", "showIf": "origin_elevator === false"},
                {"name": "origin_property_type", "type": "select", "label": "Origin Property Type", "options": ["House", "Apartment", "Condo", "Townhouse", "Storage Unit", "Office", "Warehouse"]},
                {"name": "destination_address", "type": "address", "label": "Destination Address", "required": true},
                {"name": "destination_floor", "type": "number", "label": "Destination Floor Level"},
                {"name": "destination_elevator", "type": "boolean", "label": "Destination Has Elevator"},
                {"name": "destination_stairs_flights", "type": "number", "label": "Destination Stairs (flights)", "showIf": "destination_elevator === false"},
                {"name": "destination_property_type", "type": "select", "label": "Destination Property Type", "options": ["House", "Apartment", "Condo", "Townhouse", "Storage Unit", "Office", "Warehouse"]}
            ]
        },
        {
            "id": "distance_fuel",
            "title": "Distance & Fuel Tracking",
            "description": "Auto-calculated from addresses, or enter manually",
            "fields": [
                {"name": "total_distance_miles", "type": "number", "label": "Total Distance (miles)", "computed": true, "helperText": "Auto-calculated or enter manually"},
                {"name": "route_type", "type": "select", "label": "Route Type", "options": ["Direct", "Multiple Stops", "Round Trip"]},
                {"name": "additional_stops", "type": "number", "label": "Additional Stops", "showIf": "route_type === Multiple Stops"},
                {"name": "return_trip", "type": "boolean", "label": "Return Trip Empty?"},
                {"name": "return_miles", "type": "number", "label": "Return Trip Miles", "showIf": "return_trip === true"}
            ]
        },
        {
            "id": "vehicles",
            "title": "Vehicles Used",
            "fields": [
                {"name": "vehicles", "type": "vehicle_list", "label": "Vehicles Used", "fields": [
                    {"name": "vehicle_type", "type": "select", "options": ["Cargo Van", "16ft Box Truck", "20ft Box Truck", "26ft Box Truck", "Semi Trailer", "Pickup Truck"]},
                    {"name": "fuel_type", "type": "select", "options": ["Diesel", "Gasoline", "Electric", "Hybrid", "CNG"]},
                    {"name": "miles_driven", "type": "number"},
                    {"name": "fuel_used_gallons", "type": "number"}
                ]},
                {"name": "total_fuel_gallons", "type": "number", "label": "Total Fuel Used (gallons)", "computed": true},
                {"name": "fuel_receipts", "type": "file", "label": "Fuel Receipts", "accept": "image/*,application/pdf", "multiple": true}
            ]
        },
        {
            "id": "inventory",
            "title": "Move Inventory",
            "fields": [
                {"name": "total_weight_lbs", "type": "number", "label": "Total Weight (lbs)"},
                {"name": "cubic_feet", "type": "number", "label": "Total Volume (cubic feet)"},
                {"name": "room_count", "type": "number", "label": "Number of Rooms"},
                {"name": "major_items", "type": "multiselect", "label": "Major Items", "options": ["Piano", "Pool Table", "Safe (heavy)", "Hot Tub", "Gym Equipment", "Appliances", "Antiques", "Artwork", "Electronics"]},
                {"name": "special_handling_items", "type": "textarea", "label": "Special Handling Items"}
            ]
        },
        {
            "id": "packing_materials",
            "title": "Packing Materials",
            "description": "Track materials for waste/recycling reporting",
            "fields": [
                {"name": "boxes_small", "type": "number", "label": "Small Boxes Used"},
                {"name": "boxes_medium", "type": "number", "label": "Medium Boxes Used"},
                {"name": "boxes_large", "type": "number", "label": "Large Boxes Used"},
                {"name": "boxes_wardrobe", "type": "number", "label": "Wardrobe Boxes Used"},
                {"name": "boxes_specialty", "type": "number", "label": "Specialty Boxes (dish, mirror, etc.)"},
                {"name": "packing_paper_lbs", "type": "number", "label": "Packing Paper (lbs)"},
                {"name": "bubble_wrap_ft", "type": "number", "label": "Bubble Wrap (linear ft)"},
                {"name": "tape_rolls", "type": "number", "label": "Tape Rolls Used"},
                {"name": "blankets_used", "type": "number", "label": "Moving Blankets Used"},
                {"name": "plastic_wrap_rolls", "type": "number", "label": "Stretch Wrap Rolls"},
                {"name": "recycled_materials_used", "type": "boolean", "label": "Used Recycled Packing Materials"},
                {"name": "materials_left_for_recycling", "type": "boolean", "label": "Materials Left for Customer Recycling"}
            ]
        },
        {
            "id": "disposal_donations",
            "title": "Disposal & Donations",
            "fields": [
                {"name": "items_disposed", "type": "boolean", "label": "Items Disposed/Hauled Away"},
                {"name": "disposal_weight_lbs", "type": "number", "label": "Disposal Weight (lbs)", "showIf": "items_disposed === true"},
                {"name": "disposal_destination", "type": "select", "label": "Disposal Destination", "showIf": "items_disposed === true", "options": ["Landfill", "Recycling Center", "Donation Center", "Junk Removal Service", "Customer Arranged"]},
                {"name": "items_donated", "type": "boolean", "label": "Items Donated"},
                {"name": "donation_organization", "type": "text", "label": "Donation Organization", "showIf": "items_donated === true"},
                {"name": "donation_receipt", "type": "file", "label": "Donation Receipt", "showIf": "items_donated === true", "accept": "image/*,application/pdf"}
            ]
        },
        {
            "id": "labor",
            "title": "Labor Details",
            "fields": [
                {"name": "crew_size", "type": "number", "label": "Crew Size"},
                {"name": "total_labor_hours", "type": "number", "label": "Total Labor Hours", "step": 0.25},
                {"name": "drive_time_hours", "type": "number", "label": "Drive Time (hours)", "step": 0.25}
            ]
        }
    ]
}'::jsonb
FROM verticals WHERE slug = 'moving';

-- =============================================
-- LANDSCAPING VERTICAL
-- =============================================
INSERT INTO vertical_form_config (vertical_id, form_config)
SELECT id, '{
    "sections": [
        {
            "id": "service_type",
            "title": "Service Type",
            "fields": [
                {"name": "service_category", "type": "multiselect", "label": "Services Performed", "required": true, "options": ["Mowing", "Edging", "Trimming", "Leaf Removal", "Mulching", "Planting", "Tree Service", "Irrigation", "Fertilization", "Weed Control", "Aeration", "Seeding/Sodding", "Hardscaping", "Drainage", "Snow Removal", "Design/Consultation"]}
            ]
        },
        {
            "id": "property_details",
            "title": "Property Details",
            "fields": [
                {"name": "property_type", "type": "select", "label": "Property Type", "options": ["Residential", "Commercial", "HOA/Community", "Municipal", "Industrial"]},
                {"name": "total_sqft", "type": "number", "label": "Total Property (sq ft)"},
                {"name": "lawn_sqft", "type": "number", "label": "Lawn Area (sq ft)"},
                {"name": "garden_beds_sqft", "type": "number", "label": "Garden Beds (sq ft)"},
                {"name": "hardscape_sqft", "type": "number", "label": "Hardscape Area (sq ft)"}
            ]
        },
        {
            "id": "equipment_fuel",
            "title": "Equipment & Fuel Usage",
            "description": "Track fuel consumption for emissions reporting",
            "fields": [
                {"name": "equipment_used", "type": "equipment_list", "label": "Equipment Used", "options": [
                    {"type": "mower_riding", "label": "Riding Mower", "fuel_field": "gallons"},
                    {"type": "mower_push", "label": "Push Mower", "fuel_field": "gallons"},
                    {"type": "mower_zero_turn", "label": "Zero-Turn Mower", "fuel_field": "gallons"},
                    {"type": "trimmer", "label": "String Trimmer", "fuel_field": "gallons"},
                    {"type": "edger", "label": "Edger", "fuel_field": "gallons"},
                    {"type": "blower", "label": "Leaf Blower", "fuel_field": "gallons"},
                    {"type": "chainsaw", "label": "Chainsaw", "fuel_field": "gallons"},
                    {"type": "hedge_trimmer", "label": "Hedge Trimmer", "fuel_field": "gallons"},
                    {"type": "aerator", "label": "Aerator", "fuel_field": "gallons"},
                    {"type": "tractor", "label": "Tractor", "fuel_field": "gallons"},
                    {"type": "skid_steer", "label": "Skid Steer", "fuel_field": "gallons"}
                ]},
                {"name": "total_gas_gallons", "type": "number", "label": "Total Gasoline Used (gallons)", "step": 0.1},
                {"name": "total_diesel_gallons", "type": "number", "label": "Total Diesel Used (gallons)", "step": 0.1},
                {"name": "electric_equipment_used", "type": "boolean", "label": "Electric Equipment Used"},
                {"name": "electric_equipment_kwh", "type": "number", "label": "Electric Equipment (kWh)", "showIf": "electric_equipment_used === true"}
            ]
        },
        {
            "id": "fertilizers_chemicals",
            "title": "Fertilizers & Chemicals",
            "fields": [
                {"name": "fertilizer_applied", "type": "boolean", "label": "Fertilizer Applied"},
                {"name": "fertilizer_type", "type": "select", "label": "Fertilizer Type", "showIf": "fertilizer_applied === true", "options": ["Synthetic Granular", "Synthetic Liquid", "Organic Granular", "Organic Liquid", "Slow Release", "Custom Blend"]},
                {"name": "fertilizer_npk", "type": "text", "label": "NPK Ratio", "showIf": "fertilizer_applied === true", "placeholder": "e.g., 10-10-10"},
                {"name": "fertilizer_lbs", "type": "number", "label": "Fertilizer Applied (lbs)", "showIf": "fertilizer_applied === true"},
                {"name": "fertilizer_sqft_coverage", "type": "number", "label": "Area Fertilized (sq ft)", "showIf": "fertilizer_applied === true"},
                {"name": "herbicide_applied", "type": "boolean", "label": "Herbicide Applied"},
                {"name": "herbicide_product", "type": "chemical_lookup", "label": "Herbicide Product", "showIf": "herbicide_applied === true"},
                {"name": "herbicide_oz", "type": "number", "label": "Herbicide (oz)", "showIf": "herbicide_applied === true"},
                {"name": "pesticide_applied", "type": "boolean", "label": "Pesticide Applied"},
                {"name": "pesticide_product", "type": "chemical_lookup", "label": "Pesticide Product", "showIf": "pesticide_applied === true"},
                {"name": "pesticide_oz", "type": "number", "label": "Pesticide (oz)", "showIf": "pesticide_applied === true"},
                {"name": "organic_products_only", "type": "boolean", "label": "Organic Products Only"}
            ]
        },
        {
            "id": "water_usage",
            "title": "Water Usage & Irrigation",
            "fields": [
                {"name": "irrigation_work", "type": "select", "label": "Irrigation Work", "options": ["None", "Install New System", "Repair", "Winterize", "Spring Startup", "Add Zones", "Smart Controller Install"]},
                {"name": "water_used_gallons", "type": "number", "label": "Water Used (gallons)"},
                {"name": "irrigation_zones", "type": "number", "label": "Irrigation Zones Serviced"},
                {"name": "smart_controller", "type": "boolean", "label": "Smart Controller Installed/Present"},
                {"name": "rain_sensor", "type": "boolean", "label": "Rain Sensor Present"},
                {"name": "drip_irrigation_installed", "type": "boolean", "label": "Drip Irrigation Installed"},
                {"name": "estimated_water_savings_monthly", "type": "number", "label": "Estimated Monthly Water Savings (gallons)"}
            ]
        },
        {
            "id": "materials",
            "title": "Materials Used",
            "fields": [
                {"name": "mulch_yards", "type": "number", "label": "Mulch (cubic yards)", "step": 0.5},
                {"name": "mulch_type", "type": "select", "label": "Mulch Type", "options": ["Hardwood", "Pine Bark", "Cedar", "Cypress", "Rubber", "Stone/Gravel", "Compost"]},
                {"name": "topsoil_yards", "type": "number", "label": "Topsoil (cubic yards)", "step": 0.5},
                {"name": "compost_yards", "type": "number", "label": "Compost (cubic yards)", "step": 0.5},
                {"name": "sod_sqft", "type": "number", "label": "Sod Installed (sq ft)"},
                {"name": "seed_lbs", "type": "number", "label": "Grass Seed (lbs)"},
                {"name": "plants_installed", "type": "number", "label": "Plants/Shrubs Installed"},
                {"name": "trees_installed", "type": "number", "label": "Trees Installed"},
                {"name": "native_plants", "type": "boolean", "label": "Native Plants Used"},
                {"name": "drought_tolerant", "type": "boolean", "label": "Drought-Tolerant Plants"}
            ]
        },
        {
            "id": "waste_disposal",
            "title": "Green Waste & Disposal",
            "fields": [
                {"name": "green_waste_yards", "type": "number", "label": "Green Waste Generated (cubic yards)", "step": 0.5},
                {"name": "green_waste_destination", "type": "select", "label": "Green Waste Destination", "options": ["Composting Facility", "Landfill", "Chipped On-Site", "Left for Customer", "Municipal Pickup"]},
                {"name": "debris_removed_yards", "type": "number", "label": "Other Debris Removed (cubic yards)"},
                {"name": "on_site_composting", "type": "boolean", "label": "On-Site Composting/Mulching"}
            ]
        },
        {
            "id": "tree_service",
            "title": "Tree Service Details",
            "showIf": "service_category includes Tree Service",
            "fields": [
                {"name": "tree_work_type", "type": "multiselect", "label": "Tree Work Type", "options": ["Pruning", "Removal", "Stump Grinding", "Cabling/Bracing", "Disease Treatment", "Planting"]},
                {"name": "trees_removed", "type": "number", "label": "Trees Removed"},
                {"name": "trees_pruned", "type": "number", "label": "Trees Pruned"},
                {"name": "stumps_ground", "type": "number", "label": "Stumps Ground"},
                {"name": "wood_recycled", "type": "boolean", "label": "Wood Recycled/Repurposed"},
                {"name": "wood_destination", "type": "select", "label": "Wood Destination", "showIf": "wood_recycled === true", "options": ["Firewood", "Mulch/Chips", "Lumber Mill", "Biomass Facility"]}
            ]
        }
    ]
}'::jsonb
FROM verticals WHERE slug = 'landscaping';

-- =============================================
-- ROOFING VERTICAL
-- =============================================
INSERT INTO vertical_form_config (vertical_id, form_config)
SELECT id, '{
    "sections": [
        {
            "id": "service_type",
            "title": "Service Type",
            "fields": [
                {"name": "service_category", "type": "select", "label": "Service Category", "required": true, "options": ["Full Replacement", "Partial Replacement", "Repair", "Inspection", "Maintenance", "Emergency Repair", "New Construction", "Coating/Restoration"]},
                {"name": "roof_type", "type": "select", "label": "Roof Type", "required": true, "options": ["Asphalt Shingle", "Metal Standing Seam", "Metal Corrugated", "Tile - Clay", "Tile - Concrete", "Slate", "Wood Shake", "Flat - TPO", "Flat - EPDM", "Flat - Modified Bitumen", "Flat - Built-Up", "Flat - PVC", "Green/Living Roof", "Solar Roof"]},
                {"name": "roof_pitch", "type": "select", "label": "Roof Pitch", "options": ["Flat (0-2:12)", "Low Slope (2-4:12)", "Medium (4-8:12)", "Steep (8-12:12)", "Very Steep (12+:12)"]}
            ]
        },
        {
            "id": "roof_dimensions",
            "title": "Roof Dimensions",
            "fields": [
                {"name": "total_sqft", "type": "number", "label": "Total Roof Area (sq ft)"},
                {"name": "squares", "type": "number", "label": "Roofing Squares (100 sq ft each)", "computed": true},
                {"name": "stories", "type": "number", "label": "Building Stories"},
                {"name": "valleys", "type": "number", "label": "Number of Valleys"},
                {"name": "hips", "type": "number", "label": "Number of Hips"},
                {"name": "chimneys", "type": "number", "label": "Number of Chimneys"},
                {"name": "skylights", "type": "number", "label": "Number of Skylights"},
                {"name": "vents", "type": "number", "label": "Number of Vents/Penetrations"}
            ]
        },
        {
            "id": "materials_new",
            "title": "New Materials Installed",
            "fields": [
                {"name": "shingle_brand", "type": "text", "label": "Shingle/Material Brand"},
                {"name": "shingle_type", "type": "text", "label": "Shingle/Material Model"},
                {"name": "shingle_warranty_years", "type": "number", "label": "Material Warranty (years)"},
                {"name": "energy_star_rated", "type": "boolean", "label": "ENERGY STAR Rated"},
                {"name": "cool_roof", "type": "boolean", "label": "Cool Roof (reflective)"},
                {"name": "solar_reflectance_index", "type": "number", "label": "Solar Reflectance Index (SRI)"},
                {"name": "underlayment_type", "type": "select", "label": "Underlayment Type", "options": ["Synthetic", "Felt 15#", "Felt 30#", "Ice & Water Shield", "Self-Adhering"]},
                {"name": "underlayment_sqft", "type": "number", "label": "Underlayment (sq ft)"},
                {"name": "decking_replaced_sqft", "type": "number", "label": "Decking Replaced (sq ft)"},
                {"name": "ridge_vent_ft", "type": "number", "label": "Ridge Vent (linear ft)"},
                {"name": "drip_edge_ft", "type": "number", "label": "Drip Edge (linear ft)"},
                {"name": "flashing_ft", "type": "number", "label": "Flashing (linear ft)"},
                {"name": "nails_lbs", "type": "number", "label": "Nails/Fasteners (lbs)"}
            ]
        },
        {
            "id": "old_roof",
            "title": "Old Roof Removed",
            "showIf": "service_category === Full Replacement || service_category === Partial Replacement",
            "fields": [
                {"name": "layers_removed", "type": "number", "label": "Layers Removed"},
                {"name": "old_material_type", "type": "select", "label": "Old Material Type", "options": ["Asphalt Shingle", "Metal", "Tile", "Slate", "Wood Shake", "Flat Membrane", "Built-Up", "Other"]},
                {"name": "old_roof_age_years", "type": "number", "label": "Old Roof Age (years)"},
                {"name": "tear_off_weight_lbs", "type": "number", "label": "Material Removed (lbs)"},
                {"name": "hazardous_materials", "type": "boolean", "label": "Hazardous Materials Present"},
                {"name": "asbestos_found", "type": "boolean", "label": "Asbestos Found", "showIf": "hazardous_materials === true"},
                {"name": "asbestos_abatement_cert", "type": "file", "label": "Asbestos Abatement Certificate", "showIf": "asbestos_found === true"}
            ]
        },
        {
            "id": "waste_disposal",
            "title": "Waste & Recycling",
            "fields": [
                {"name": "dumpster_size_yards", "type": "select", "label": "Dumpster Size (cubic yards)", "options": ["10", "15", "20", "30", "40"]},
                {"name": "total_waste_tons", "type": "number", "label": "Total Waste (tons)", "step": 0.1},
                {"name": "recycled_tons", "type": "number", "label": "Material Recycled (tons)", "step": 0.1},
                {"name": "recycling_facility", "type": "text", "label": "Recycling Facility Name"},
                {"name": "recycling_certificate", "type": "file", "label": "Recycling Certificate", "accept": "image/*,application/pdf"},
                {"name": "shingles_recycled", "type": "boolean", "label": "Shingles Sent to Recycling"},
                {"name": "metal_recycled", "type": "boolean", "label": "Metal Recycled"},
                {"name": "landfill_tons", "type": "number", "label": "Sent to Landfill (tons)", "step": 0.1}
            ]
        },
        {
            "id": "ventilation",
            "title": "Ventilation & Insulation",
            "fields": [
                {"name": "ventilation_improved", "type": "boolean", "label": "Ventilation Improved"},
                {"name": "intake_vents_added", "type": "number", "label": "Intake Vents Added"},
                {"name": "exhaust_vents_added", "type": "number", "label": "Exhaust Vents Added"},
                {"name": "powered_vent_installed", "type": "boolean", "label": "Powered Attic Vent Installed"},
                {"name": "solar_powered_vent", "type": "boolean", "label": "Solar-Powered Vent", "showIf": "powered_vent_installed === true"},
                {"name": "insulation_added", "type": "boolean", "label": "Insulation Added"},
                {"name": "insulation_r_value", "type": "number", "label": "Insulation R-Value", "showIf": "insulation_added === true"},
                {"name": "insulation_sqft", "type": "number", "label": "Insulation Area (sq ft)", "showIf": "insulation_added === true"}
            ]
        },
        {
            "id": "energy_impact",
            "title": "Energy & Environmental Impact",
            "fields": [
                {"name": "estimated_cooling_savings_percent", "type": "number", "label": "Estimated Cooling Savings (%)"},
                {"name": "estimated_heating_savings_percent", "type": "number", "label": "Estimated Heating Savings (%)"},
                {"name": "estimated_annual_kwh_savings", "type": "number", "label": "Estimated Annual kWh Savings"},
                {"name": "stormwater_management", "type": "boolean", "label": "Stormwater Management Features"},
                {"name": "solar_ready", "type": "boolean", "label": "Solar-Ready Installation"}
            ]
        }
    ]
}'::jsonb
FROM verticals WHERE slug = 'roofing';

-- =============================================
-- CLEANING VERTICAL
-- =============================================
INSERT INTO vertical_form_config (vertical_id, form_config)
SELECT id, '{
    "sections": [
        {
            "id": "service_type",
            "title": "Service Type",
            "fields": [
                {"name": "service_category", "type": "select", "label": "Service Category", "required": true, "options": ["Regular Cleaning", "Deep Cleaning", "Move-In/Move-Out", "Post-Construction", "Commercial", "Carpet Cleaning", "Window Cleaning", "Pressure Washing", "Specialty"]},
                {"name": "property_type", "type": "select", "label": "Property Type", "options": ["Residential", "Office", "Retail", "Medical", "Industrial", "Restaurant", "School", "Hospitality"]},
                {"name": "recurring_service", "type": "boolean", "label": "Recurring Service"}
            ]
        },
        {
            "id": "area_cleaned",
            "title": "Area Details",
            "fields": [
                {"name": "total_sqft", "type": "number", "label": "Total Area (sq ft)"},
                {"name": "rooms_cleaned", "type": "number", "label": "Rooms Cleaned"},
                {"name": "bathrooms", "type": "number", "label": "Bathrooms"},
                {"name": "kitchens", "type": "number", "label": "Kitchens"},
                {"name": "windows", "type": "number", "label": "Windows Cleaned"},
                {"name": "floors_type", "type": "multiselect", "label": "Floor Types", "options": ["Hardwood", "Tile", "Carpet", "Vinyl", "Concrete", "Marble", "Laminate"]}
            ]
        },
        {
            "id": "products_used",
            "title": "Cleaning Products",
            "fields": [
                {"name": "green_certified_products", "type": "boolean", "label": "Green Certified Products Used"},
                {"name": "products", "type": "product_list", "label": "Products Used", "fields": [
                    {"name": "product_name", "type": "text"},
                    {"name": "certification", "type": "select", "options": ["Green Seal", "EPA Safer Choice", "EcoLogo", "USDA BioPreferred", "None"]},
                    {"name": "amount_oz", "type": "number"}
                ]},
                {"name": "total_product_oz", "type": "number", "label": "Total Product Used (oz)"},
                {"name": "concentrate_diluted", "type": "boolean", "label": "Used Concentrate (diluted on-site)"},
                {"name": "refillable_containers", "type": "boolean", "label": "Refillable Containers Used"},
                {"name": "fragrance_free", "type": "boolean", "label": "Fragrance-Free Products"},
                {"name": "voc_free", "type": "boolean", "label": "VOC-Free Products"}
            ]
        },
        {
            "id": "water_usage",
            "title": "Water Usage",
            "fields": [
                {"name": "water_used_gallons", "type": "number", "label": "Water Used (gallons)", "step": 0.5},
                {"name": "hot_water_used", "type": "boolean", "label": "Hot Water Used"},
                {"name": "pressure_washing_gallons", "type": "number", "label": "Pressure Washing Water (gallons)", "showIf": "service_category === Pressure Washing"}
            ]
        },
        {
            "id": "equipment",
            "title": "Equipment Used",
            "fields": [
                {"name": "vacuum_type", "type": "select", "label": "Vacuum Type", "options": ["Upright", "Canister", "Backpack", "Commercial", "HEPA Certified", "Robot"]},
                {"name": "hepa_filtration", "type": "boolean", "label": "HEPA Filtration Used"},
                {"name": "carpet_extractor_used", "type": "boolean", "label": "Carpet Extractor Used"},
                {"name": "floor_machine_used", "type": "boolean", "label": "Floor Machine Used"},
                {"name": "pressure_washer_used", "type": "boolean", "label": "Pressure Washer Used"},
                {"name": "electric_equipment_only", "type": "boolean", "label": "Electric Equipment Only (no gas)"}
            ]
        },
        {
            "id": "waste_disposal",
            "title": "Waste & Recycling",
            "fields": [
                {"name": "trash_bags_used", "type": "number", "label": "Trash Bags Used"},
                {"name": "trash_bags_biodegradable", "type": "boolean", "label": "Biodegradable Trash Bags"},
                {"name": "recycling_collected", "type": "boolean", "label": "Recycling Collected Separately"},
                {"name": "microfiber_cloths_used", "type": "number", "label": "Microfiber Cloths Used"},
                {"name": "disposable_items_used", "type": "number", "label": "Disposable Items Used (paper towels, etc.)"},
                {"name": "wastewater_disposed_properly", "type": "boolean", "label": "Wastewater Disposed Properly"}
            ]
        },
        {
            "id": "iaq",
            "title": "Indoor Air Quality",
            "fields": [
                {"name": "air_fresheners_used", "type": "boolean", "label": "Air Fresheners Used"},
                {"name": "natural_air_fresheners", "type": "boolean", "label": "Natural/Essential Oil Based", "showIf": "air_fresheners_used === true"},
                {"name": "hvac_vents_cleaned", "type": "boolean", "label": "HVAC Vents Cleaned"},
                {"name": "allergen_treatment", "type": "boolean", "label": "Allergen Treatment Applied"}
            ]
        }
    ]
}'::jsonb
FROM verticals WHERE slug = 'cleaning';

-- =============================================
-- POOL SERVICE VERTICAL
-- =============================================
INSERT INTO vertical_form_config (vertical_id, form_config)
SELECT id, '{
    "sections": [
        {
            "id": "service_type",
            "title": "Service Type",
            "fields": [
                {"name": "service_category", "type": "select", "label": "Service Category", "required": true, "options": ["Regular Maintenance", "Opening", "Closing", "Repair", "Equipment Installation", "Renovation", "Inspection", "Emergency"]},
                {"name": "pool_type", "type": "select", "label": "Pool Type", "options": ["In-Ground Concrete", "In-Ground Vinyl", "In-Ground Fiberglass", "Above-Ground", "Spa/Hot Tub", "Commercial"]},
                {"name": "pool_gallons", "type": "number", "label": "Pool Volume (gallons)"}
            ]
        },
        {
            "id": "chemicals",
            "title": "Chemical Treatment",
            "fields": [
                {"name": "chlorine_lbs", "type": "number", "label": "Chlorine Added (lbs)", "step": 0.1},
                {"name": "chlorine_type", "type": "select", "label": "Chlorine Type", "options": ["Liquid", "Granular", "Tablets", "Salt (chlorine generator)"]},
                {"name": "acid_gallons", "type": "number", "label": "Muriatic Acid (gallons)", "step": 0.1},
                {"name": "shock_lbs", "type": "number", "label": "Shock Treatment (lbs)", "step": 0.1},
                {"name": "algaecide_oz", "type": "number", "label": "Algaecide (oz)"},
                {"name": "stabilizer_lbs", "type": "number", "label": "Stabilizer/CYA (lbs)", "step": 0.1},
                {"name": "phosphate_remover_oz", "type": "number", "label": "Phosphate Remover (oz)"},
                {"name": "clarifier_oz", "type": "number", "label": "Clarifier (oz)"},
                {"name": "salt_lbs", "type": "number", "label": "Salt Added (lbs)"},
                {"name": "other_chemicals", "type": "textarea", "label": "Other Chemicals Used"}
            ]
        },
        {
            "id": "water_testing",
            "title": "Water Testing Results",
            "fields": [
                {"name": "ph_level", "type": "number", "label": "pH Level", "step": 0.1, "min": 6, "max": 9},
                {"name": "chlorine_ppm", "type": "number", "label": "Free Chlorine (ppm)", "step": 0.1},
                {"name": "total_chlorine_ppm", "type": "number", "label": "Total Chlorine (ppm)", "step": 0.1},
                {"name": "alkalinity_ppm", "type": "number", "label": "Alkalinity (ppm)"},
                {"name": "calcium_hardness_ppm", "type": "number", "label": "Calcium Hardness (ppm)"},
                {"name": "cya_ppm", "type": "number", "label": "Cyanuric Acid (ppm)"},
                {"name": "salt_ppm", "type": "number", "label": "Salt Level (ppm)"},
                {"name": "phosphates_ppb", "type": "number", "label": "Phosphates (ppb)"},
                {"name": "tds_ppm", "type": "number", "label": "Total Dissolved Solids (ppm)"}
            ]
        },
        {
            "id": "water_usage",
            "title": "Water Usage",
            "fields": [
                {"name": "water_added_gallons", "type": "number", "label": "Water Added (gallons)"},
                {"name": "water_drained_gallons", "type": "number", "label": "Water Drained (gallons)"},
                {"name": "backwash_gallons", "type": "number", "label": "Backwash Water (gallons)"},
                {"name": "drain_destination", "type": "select", "label": "Drain Water Destination", "showIf": "water_drained_gallons > 0", "options": ["Sewer", "Landscaping", "Storm Drain (if permitted)", "Pump Truck"]}
            ]
        },
        {
            "id": "equipment",
            "title": "Equipment Service",
            "fields": [
                {"name": "pump_serviced", "type": "boolean", "label": "Pump Serviced"},
                {"name": "pump_hp", "type": "number", "label": "Pump HP", "step": 0.25},
                {"name": "variable_speed_pump", "type": "boolean", "label": "Variable Speed Pump"},
                {"name": "filter_cleaned", "type": "boolean", "label": "Filter Cleaned"},
                {"name": "filter_type", "type": "select", "label": "Filter Type", "options": ["Sand", "Cartridge", "DE (Diatomaceous Earth)"]},
                {"name": "heater_serviced", "type": "boolean", "label": "Heater Serviced"},
                {"name": "heater_type", "type": "select", "label": "Heater Type", "showIf": "heater_serviced === true", "options": ["Gas", "Electric", "Heat Pump", "Solar"]},
                {"name": "salt_cell_cleaned", "type": "boolean", "label": "Salt Cell Cleaned"},
                {"name": "automation_system", "type": "boolean", "label": "Pool Automation System Present"}
            ]
        },
        {
            "id": "equipment_install",
            "title": "Equipment Installation",
            "showIf": "service_category === Equipment Installation",
            "fields": [
                {"name": "equipment_installed", "type": "multiselect", "label": "Equipment Installed", "options": ["Variable Speed Pump", "Salt System", "Heat Pump", "Solar Heater", "Automation System", "LED Lights", "Robotic Cleaner", "Pool Cover"]},
                {"name": "old_pump_hp", "type": "number", "label": "Old Pump HP (if replaced)"},
                {"name": "new_pump_hp", "type": "number", "label": "New Pump HP"},
                {"name": "energy_star_equipment", "type": "boolean", "label": "ENERGY STAR Certified Equipment"},
                {"name": "estimated_annual_kwh_savings", "type": "number", "label": "Estimated Annual kWh Savings"},
                {"name": "old_equipment_recycled", "type": "boolean", "label": "Old Equipment Recycled"}
            ]
        },
        {
            "id": "maintenance",
            "title": "Maintenance Tasks",
            "fields": [
                {"name": "skimmed", "type": "boolean", "label": "Surface Skimmed"},
                {"name": "brushed", "type": "boolean", "label": "Walls/Floor Brushed"},
                {"name": "vacuumed", "type": "boolean", "label": "Pool Vacuumed"},
                {"name": "tile_cleaned", "type": "boolean", "label": "Tile Line Cleaned"},
                {"name": "baskets_emptied", "type": "boolean", "label": "Skimmer Baskets Emptied"},
                {"name": "debris_removed_lbs", "type": "number", "label": "Debris Removed (lbs)", "step": 0.5}
            ]
        }
    ]
}'::jsonb
FROM verticals WHERE slug = 'pool-service';

RAISE NOTICE 'Vertical form configurations completed successfully';
