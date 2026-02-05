-- =============================================
-- ADDITIONAL VERTICAL FORM CONFIGURATIONS
-- =============================================

-- =============================================
-- APPLIANCE REPAIR VERTICAL
-- =============================================
INSERT INTO vertical_form_config (vertical_id, form_config)
SELECT id, '{
    "sections": [
        {
            "id": "service_type",
            "title": "Service Type",
            "fields": [
                {"name": "service_category", "type": "select", "label": "Service Category", "required": true, "options": ["Repair", "Installation", "Maintenance", "Diagnostic", "Replacement"]},
                {"name": "appliance_type", "type": "select", "label": "Appliance Type", "required": true, "options": ["Refrigerator", "Freezer", "Dishwasher", "Washing Machine", "Dryer", "Oven/Range", "Microwave", "Garbage Disposal", "Ice Maker", "Wine Cooler", "Trash Compactor", "Range Hood"]}
            ]
        },
        {
            "id": "appliance_details",
            "title": "Appliance Details",
            "fields": [
                {"name": "brand", "type": "text", "label": "Brand"},
                {"name": "model_number", "type": "text", "label": "Model Number"},
                {"name": "serial_number", "type": "text", "label": "Serial Number"},
                {"name": "manufacture_year", "type": "number", "label": "Manufacture Year"},
                {"name": "age_years", "type": "number", "label": "Appliance Age (years)"},
                {"name": "energy_star", "type": "boolean", "label": "ENERGY STAR Certified"},
                {"name": "annual_kwh", "type": "number", "label": "Annual Energy Use (kWh)", "helperText": "From EnergyGuide label"}
            ]
        },
        {
            "id": "refrigerant",
            "title": "Refrigerant (Cooling Appliances)",
            "showIf": "appliance_type === Refrigerator || appliance_type === Freezer || appliance_type === Wine Cooler || appliance_type === Ice Maker",
            "fields": [
                {"name": "refrigerant_type", "type": "select", "label": "Refrigerant Type", "options": ["R-134a", "R-600a (Isobutane)", "R-290 (Propane)", "R-404A", "R-22", "Unknown"]},
                {"name": "refrigerant_added_oz", "type": "number", "label": "Refrigerant Added (oz)", "step": 0.1},
                {"name": "refrigerant_recovered_oz", "type": "number", "label": "Refrigerant Recovered (oz)", "step": 0.1},
                {"name": "leak_detected", "type": "boolean", "label": "Leak Detected"},
                {"name": "leak_repaired", "type": "boolean", "label": "Leak Repaired", "showIf": "leak_detected === true"}
            ]
        },
        {
            "id": "water_usage",
            "title": "Water Usage (Applicable Appliances)",
            "showIf": "appliance_type === Dishwasher || appliance_type === Washing Machine || appliance_type === Ice Maker",
            "fields": [
                {"name": "gallons_per_cycle", "type": "number", "label": "Water Usage (gallons/cycle)", "step": 0.1},
                {"name": "water_efficiency_improved", "type": "boolean", "label": "Water Efficiency Improved"},
                {"name": "old_gallons_per_cycle", "type": "number", "label": "Old Water Usage (gallons/cycle)", "showIf": "water_efficiency_improved === true"}
            ]
        },
        {
            "id": "parts_replaced",
            "title": "Parts Replaced",
            "fields": [
                {"name": "parts", "type": "parts_list", "label": "Parts Used", "fields": [
                    {"name": "part_name", "type": "text"},
                    {"name": "part_number", "type": "text"},
                    {"name": "quantity", "type": "number"},
                    {"name": "oem_part", "type": "boolean"}
                ]},
                {"name": "compressor_replaced", "type": "boolean", "label": "Compressor Replaced"},
                {"name": "motor_replaced", "type": "boolean", "label": "Motor Replaced"},
                {"name": "control_board_replaced", "type": "boolean", "label": "Control Board Replaced"}
            ]
        },
        {
            "id": "disposal",
            "title": "Old Appliance Disposal",
            "showIf": "service_category === Replacement",
            "fields": [
                {"name": "old_appliance_removed", "type": "boolean", "label": "Old Appliance Removed"},
                {"name": "old_brand", "type": "text", "label": "Old Appliance Brand"},
                {"name": "old_model", "type": "text", "label": "Old Appliance Model"},
                {"name": "old_age_years", "type": "number", "label": "Old Appliance Age (years)"},
                {"name": "old_annual_kwh", "type": "number", "label": "Old Annual Energy Use (kWh)"},
                {"name": "disposal_method", "type": "select", "label": "Disposal Method", "options": ["Recycling Program", "Utility Rebate Program", "Scrap Metal", "Donation", "Customer Keeping", "Landfill"]},
                {"name": "refrigerant_properly_recovered", "type": "boolean", "label": "Refrigerant Properly Recovered"},
                {"name": "recycling_certificate", "type": "file", "label": "Recycling Certificate", "accept": "image/*,application/pdf"}
            ]
        },
        {
            "id": "energy_impact",
            "title": "Energy Impact",
            "fields": [
                {"name": "efficiency_improved", "type": "boolean", "label": "Energy Efficiency Improved"},
                {"name": "estimated_annual_kwh_savings", "type": "number", "label": "Estimated Annual kWh Savings"},
                {"name": "estimated_annual_water_savings", "type": "number", "label": "Estimated Annual Water Savings (gallons)"}
            ]
        }
    ]
}'::jsonb
FROM verticals WHERE slug = 'appliance-repair';

-- =============================================
-- GARAGE DOOR VERTICAL
-- =============================================
INSERT INTO vertical_form_config (vertical_id, form_config)
SELECT id, '{
    "sections": [
        {
            "id": "service_type",
            "title": "Service Type",
            "fields": [
                {"name": "service_category", "type": "select", "label": "Service Category", "required": true, "options": ["Installation", "Repair", "Replacement", "Maintenance", "Opener Service", "Spring Replacement", "Emergency"]},
                {"name": "door_count", "type": "number", "label": "Number of Doors Serviced"}
            ]
        },
        {
            "id": "door_details",
            "title": "Door Details",
            "fields": [
                {"name": "door_type", "type": "select", "label": "Door Type", "options": ["Sectional", "Roll-Up", "Swing-Out", "Swing-Up", "Slide to Side"]},
                {"name": "door_material", "type": "select", "label": "Door Material", "options": ["Steel", "Aluminum", "Wood", "Fiberglass", "Vinyl", "Composite"]},
                {"name": "door_width_ft", "type": "number", "label": "Door Width (ft)"},
                {"name": "door_height_ft", "type": "number", "label": "Door Height (ft)"},
                {"name": "insulated", "type": "boolean", "label": "Insulated Door"},
                {"name": "r_value", "type": "number", "label": "R-Value (if insulated)", "showIf": "insulated === true"},
                {"name": "windows", "type": "boolean", "label": "Door Has Windows"},
                {"name": "window_insulated", "type": "boolean", "label": "Windows Insulated", "showIf": "windows === true"}
            ]
        },
        {
            "id": "opener",
            "title": "Opener Details",
            "fields": [
                {"name": "opener_serviced", "type": "boolean", "label": "Opener Serviced/Installed"},
                {"name": "opener_brand", "type": "text", "label": "Opener Brand", "showIf": "opener_serviced === true"},
                {"name": "opener_model", "type": "text", "label": "Opener Model", "showIf": "opener_serviced === true"},
                {"name": "opener_type", "type": "select", "label": "Opener Type", "showIf": "opener_serviced === true", "options": ["Chain Drive", "Belt Drive", "Screw Drive", "Direct Drive", "Jackshaft"]},
                {"name": "opener_hp", "type": "select", "label": "Opener HP", "showIf": "opener_serviced === true", "options": ["1/3", "1/2", "3/4", "1", "1.25"]},
                {"name": "dc_motor", "type": "boolean", "label": "DC Motor (more efficient)", "showIf": "opener_serviced === true"},
                {"name": "battery_backup", "type": "boolean", "label": "Battery Backup", "showIf": "opener_serviced === true"},
                {"name": "smart_enabled", "type": "boolean", "label": "Smart/WiFi Enabled", "showIf": "opener_serviced === true"}
            ]
        },
        {
            "id": "old_door",
            "title": "Old Door Removal",
            "showIf": "service_category === Replacement || service_category === Installation",
            "fields": [
                {"name": "old_door_removed", "type": "boolean", "label": "Old Door Removed"},
                {"name": "old_door_material", "type": "select", "label": "Old Door Material", "showIf": "old_door_removed === true", "options": ["Steel", "Aluminum", "Wood", "Fiberglass", "Vinyl"]},
                {"name": "old_door_insulated", "type": "boolean", "label": "Old Door Was Insulated", "showIf": "old_door_removed === true"},
                {"name": "old_door_weight_lbs", "type": "number", "label": "Old Door Weight (lbs)", "showIf": "old_door_removed === true"},
                {"name": "disposal_method", "type": "select", "label": "Disposal Method", "showIf": "old_door_removed === true", "options": ["Metal Recycling", "Wood Recycling", "Landfill", "Customer Keeping"]},
                {"name": "metal_recycled_lbs", "type": "number", "label": "Metal Recycled (lbs)"}
            ]
        },
        {
            "id": "materials",
            "title": "Materials Used",
            "fields": [
                {"name": "springs_replaced", "type": "number", "label": "Springs Replaced"},
                {"name": "spring_type", "type": "select", "label": "Spring Type", "options": ["Torsion", "Extension"]},
                {"name": "cables_replaced", "type": "boolean", "label": "Cables Replaced"},
                {"name": "rollers_replaced", "type": "number", "label": "Rollers Replaced"},
                {"name": "hinges_replaced", "type": "number", "label": "Hinges Replaced"},
                {"name": "weatherstripping_ft", "type": "number", "label": "Weatherstripping (ft)"},
                {"name": "bottom_seal_ft", "type": "number", "label": "Bottom Seal (ft)"}
            ]
        },
        {
            "id": "energy_impact",
            "title": "Energy Impact",
            "fields": [
                {"name": "insulation_upgraded", "type": "boolean", "label": "Insulation Upgraded"},
                {"name": "weatherstripping_improved", "type": "boolean", "label": "Weatherstripping Improved"},
                {"name": "estimated_heating_savings_percent", "type": "number", "label": "Estimated Heating Savings (%)"},
                {"name": "estimated_cooling_savings_percent", "type": "number", "label": "Estimated Cooling Savings (%)"}
            ]
        }
    ]
}'::jsonb
FROM verticals WHERE slug = 'garage-door';

-- =============================================
-- PAINTING VERTICAL
-- =============================================
INSERT INTO vertical_form_config (vertical_id, form_config)
SELECT id, '{
    "sections": [
        {
            "id": "service_type",
            "title": "Service Type",
            "fields": [
                {"name": "service_category", "type": "select", "label": "Service Category", "required": true, "options": ["Interior Painting", "Exterior Painting", "Cabinet Painting", "Staining", "Wallpaper", "Specialty Finishes", "Commercial"]},
                {"name": "property_type", "type": "select", "label": "Property Type", "options": ["Residential", "Commercial", "Industrial", "Multi-Family"]}
            ]
        },
        {
            "id": "area_details",
            "title": "Area Details",
            "fields": [
                {"name": "total_sqft", "type": "number", "label": "Total Area (sq ft)"},
                {"name": "rooms", "type": "number", "label": "Number of Rooms", "showIf": "service_category === Interior Painting"},
                {"name": "ceilings", "type": "boolean", "label": "Ceilings Included"},
                {"name": "trim_linear_ft", "type": "number", "label": "Trim/Baseboards (linear ft)"},
                {"name": "doors", "type": "number", "label": "Doors"},
                {"name": "windows", "type": "number", "label": "Windows/Frames"},
                {"name": "cabinets_linear_ft", "type": "number", "label": "Cabinets (linear ft)", "showIf": "service_category === Cabinet Painting"}
            ]
        },
        {
            "id": "paint_products",
            "title": "Paint Products Used",
            "fields": [
                {"name": "paint_brand", "type": "text", "label": "Primary Paint Brand"},
                {"name": "paint_line", "type": "text", "label": "Paint Line/Product"},
                {"name": "paint_finish", "type": "select", "label": "Paint Finish", "options": ["Flat/Matte", "Eggshell", "Satin", "Semi-Gloss", "High-Gloss"]},
                {"name": "gallons_used", "type": "number", "label": "Total Gallons Used", "step": 0.25},
                {"name": "primer_gallons", "type": "number", "label": "Primer Gallons", "step": 0.25},
                {"name": "low_voc", "type": "boolean", "label": "Low-VOC Paint"},
                {"name": "zero_voc", "type": "boolean", "label": "Zero-VOC Paint"},
                {"name": "voc_grams_per_liter", "type": "number", "label": "VOC Content (g/L)"},
                {"name": "greenguard_certified", "type": "boolean", "label": "GREENGUARD Certified"},
                {"name": "recycled_content", "type": "boolean", "label": "Contains Recycled Content"}
            ]
        },
        {
            "id": "prep_work",
            "title": "Preparation Work",
            "fields": [
                {"name": "power_washing", "type": "boolean", "label": "Power Washing Required", "showIf": "service_category === Exterior Painting"},
                {"name": "power_wash_gallons", "type": "number", "label": "Power Wash Water (gallons)", "showIf": "power_washing === true"},
                {"name": "scraping_required", "type": "boolean", "label": "Scraping/Sanding Required"},
                {"name": "lead_paint_present", "type": "boolean", "label": "Lead Paint Present (pre-1978)"},
                {"name": "lead_safe_practices", "type": "boolean", "label": "EPA Lead-Safe Practices Used", "showIf": "lead_paint_present === true"},
                {"name": "lead_cert_number", "type": "text", "label": "Lead-Safe Certification #", "showIf": "lead_paint_present === true"},
                {"name": "caulking_tubes", "type": "number", "label": "Caulking Tubes Used"},
                {"name": "wood_filler_oz", "type": "number", "label": "Wood Filler (oz)"},
                {"name": "drywall_repair_sqft", "type": "number", "label": "Drywall Repair (sq ft)"}
            ]
        },
        {
            "id": "waste_disposal",
            "title": "Waste & Disposal",
            "fields": [
                {"name": "paint_waste_gallons", "type": "number", "label": "Paint Waste (gallons)", "step": 0.1},
                {"name": "paint_waste_disposal", "type": "select", "label": "Paint Waste Disposal", "options": ["Hazardous Waste Facility", "Paint Recycling Program", "Dried and Landfill", "Customer Keeping"]},
                {"name": "drop_cloths_reusable", "type": "boolean", "label": "Reusable Drop Cloths Used"},
                {"name": "plastic_sheeting_sqft", "type": "number", "label": "Plastic Sheeting (sq ft)"},
                {"name": "tape_rolls", "type": "number", "label": "Painters Tape Rolls"},
                {"name": "lead_waste_lbs", "type": "number", "label": "Lead Waste Generated (lbs)", "showIf": "lead_paint_present === true"},
                {"name": "lead_waste_manifest", "type": "file", "label": "Lead Waste Manifest", "showIf": "lead_paint_present === true"}
            ]
        },
        {
            "id": "iaq",
            "title": "Indoor Air Quality",
            "showIf": "service_category === Interior Painting || service_category === Cabinet Painting",
            "fields": [
                {"name": "ventilation_used", "type": "boolean", "label": "Ventilation Equipment Used"},
                {"name": "air_scrubber_used", "type": "boolean", "label": "Air Scrubber Used"},
                {"name": "recommended_reoccupancy_hours", "type": "number", "label": "Recommended Re-occupancy (hours)"},
                {"name": "sensitive_occupants_notified", "type": "boolean", "label": "Sensitive Occupants Notified"}
            ]
        }
    ]
}'::jsonb
FROM verticals WHERE slug = 'painting';

-- =============================================
-- FLOORING VERTICAL
-- =============================================
INSERT INTO vertical_form_config (vertical_id, form_config)
SELECT id, '{
    "sections": [
        {
            "id": "service_type",
            "title": "Service Type",
            "fields": [
                {"name": "service_category", "type": "select", "label": "Service Category", "required": true, "options": ["Installation", "Replacement", "Refinishing", "Repair", "Cleaning"]},
                {"name": "flooring_type", "type": "select", "label": "Flooring Type", "required": true, "options": ["Hardwood", "Engineered Wood", "Laminate", "Vinyl Plank (LVP)", "Vinyl Sheet", "Tile - Ceramic", "Tile - Porcelain", "Tile - Natural Stone", "Carpet", "Bamboo", "Cork", "Concrete"]}
            ]
        },
        {
            "id": "area_details",
            "title": "Area Details",
            "fields": [
                {"name": "total_sqft", "type": "number", "label": "Total Area (sq ft)", "required": true},
                {"name": "rooms_count", "type": "number", "label": "Number of Rooms"},
                {"name": "stairs_count", "type": "number", "label": "Number of Stairs"},
                {"name": "subfloor_type", "type": "select", "label": "Subfloor Type", "options": ["Plywood", "OSB", "Concrete", "Existing Flooring"]}
            ]
        },
        {
            "id": "new_materials",
            "title": "New Flooring Materials",
            "fields": [
                {"name": "product_brand", "type": "text", "label": "Product Brand"},
                {"name": "product_name", "type": "text", "label": "Product Name/Line"},
                {"name": "sqft_installed", "type": "number", "label": "Square Feet Installed"},
                {"name": "floorscore_certified", "type": "boolean", "label": "FloorScore Certified"},
                {"name": "greenguard_certified", "type": "boolean", "label": "GREENGUARD Certified"},
                {"name": "fsc_certified", "type": "boolean", "label": "FSC Certified (wood)", "showIf": "flooring_type === Hardwood || flooring_type === Engineered Wood || flooring_type === Bamboo"},
                {"name": "recycled_content_percent", "type": "number", "label": "Recycled Content (%)"},
                {"name": "voc_emissions", "type": "select", "label": "VOC Emissions Level", "options": ["Ultra Low VOC", "Low VOC", "Standard", "Unknown"]},
                {"name": "made_in_usa", "type": "boolean", "label": "Made in USA"},
                {"name": "warranty_years", "type": "number", "label": "Warranty (years)"}
            ]
        },
        {
            "id": "underlayment",
            "title": "Underlayment & Preparation",
            "fields": [
                {"name": "underlayment_type", "type": "select", "label": "Underlayment Type", "options": ["None", "Foam", "Cork", "Rubber", "Felt", "Combination"]},
                {"name": "underlayment_sqft", "type": "number", "label": "Underlayment (sq ft)"},
                {"name": "moisture_barrier", "type": "boolean", "label": "Moisture Barrier Installed"},
                {"name": "leveling_compound_lbs", "type": "number", "label": "Leveling Compound (lbs)"},
                {"name": "adhesive_type", "type": "select", "label": "Adhesive Type", "options": ["None (floating)", "Low-VOC Adhesive", "Standard Adhesive", "Pressure Sensitive"]},
                {"name": "adhesive_gallons", "type": "number", "label": "Adhesive (gallons)", "step": 0.25}
            ]
        },
        {
            "id": "old_flooring",
            "title": "Old Flooring Removal",
            "showIf": "service_category === Replacement",
            "fields": [
                {"name": "old_flooring_removed", "type": "boolean", "label": "Old Flooring Removed"},
                {"name": "old_flooring_type", "type": "select", "label": "Old Flooring Type", "showIf": "old_flooring_removed === true", "options": ["Hardwood", "Carpet", "Vinyl", "Tile", "Laminate", "Linoleum", "Other"]},
                {"name": "old_flooring_sqft", "type": "number", "label": "Old Flooring Removed (sq ft)", "showIf": "old_flooring_removed === true"},
                {"name": "old_flooring_weight_lbs", "type": "number", "label": "Old Flooring Weight (lbs)", "showIf": "old_flooring_removed === true"},
                {"name": "asbestos_testing", "type": "boolean", "label": "Asbestos Testing Performed", "helperText": "Required for pre-1980 vinyl/linoleum"},
                {"name": "asbestos_found", "type": "boolean", "label": "Asbestos Found", "showIf": "asbestos_testing === true"},
                {"name": "asbestos_abatement", "type": "file", "label": "Asbestos Abatement Certificate", "showIf": "asbestos_found === true"}
            ]
        },
        {
            "id": "waste_recycling",
            "title": "Waste & Recycling",
            "fields": [
                {"name": "total_waste_lbs", "type": "number", "label": "Total Waste Generated (lbs)"},
                {"name": "recycled_lbs", "type": "number", "label": "Material Recycled (lbs)"},
                {"name": "recycling_type", "type": "multiselect", "label": "Materials Recycled", "options": ["Carpet", "Carpet Pad", "Wood", "Cardboard/Packaging", "Metal"]},
                {"name": "carpet_recycling_program", "type": "boolean", "label": "Carpet Sent to Recycling Program", "showIf": "old_flooring_type === Carpet"},
                {"name": "landfill_lbs", "type": "number", "label": "Sent to Landfill (lbs)"},
                {"name": "packaging_recycled", "type": "boolean", "label": "Packaging Recycled"}
            ]
        },
        {
            "id": "refinishing",
            "title": "Refinishing Details",
            "showIf": "service_category === Refinishing",
            "fields": [
                {"name": "sanding_required", "type": "boolean", "label": "Sanding Required"},
                {"name": "dust_containment_used", "type": "boolean", "label": "Dust Containment System Used"},
                {"name": "stain_type", "type": "select", "label": "Stain Type", "options": ["None", "Oil-Based", "Water-Based", "Gel Stain"]},
                {"name": "stain_gallons", "type": "number", "label": "Stain (gallons)", "step": 0.25},
                {"name": "finish_type", "type": "select", "label": "Finish Type", "options": ["Water-Based Polyurethane", "Oil-Based Polyurethane", "Hard Wax Oil", "Penetrating Oil", "UV-Cured"]},
                {"name": "finish_gallons", "type": "number", "label": "Finish (gallons)", "step": 0.25},
                {"name": "low_voc_products", "type": "boolean", "label": "Low-VOC Products Used"},
                {"name": "coats_applied", "type": "number", "label": "Coats Applied"}
            ]
        }
    ]
}'::jsonb
FROM verticals WHERE slug = 'flooring';

-- =============================================
-- WINDOW INSTALLATION VERTICAL
-- =============================================
INSERT INTO vertical_form_config (vertical_id, form_config)
SELECT id, '{
    "sections": [
        {
            "id": "service_type",
            "title": "Service Type",
            "fields": [
                {"name": "service_category", "type": "select", "label": "Service Category", "required": true, "options": ["Full Replacement", "Insert Replacement", "New Construction", "Repair", "Glass Only"]},
                {"name": "window_count", "type": "number", "label": "Number of Windows", "required": true}
            ]
        },
        {
            "id": "window_details",
            "title": "Window Details",
            "fields": [
                {"name": "window_type", "type": "select", "label": "Window Type", "options": ["Double-Hung", "Single-Hung", "Casement", "Awning", "Sliding", "Picture", "Bay/Bow", "Skylight", "Custom"]},
                {"name": "frame_material", "type": "select", "label": "Frame Material", "options": ["Vinyl", "Fiberglass", "Aluminum", "Wood", "Composite", "Clad Wood"]},
                {"name": "glass_type", "type": "select", "label": "Glass Type", "options": ["Double Pane", "Triple Pane", "Single Pane", "Laminated", "Tempered"]},
                {"name": "low_e_coating", "type": "boolean", "label": "Low-E Coating"},
                {"name": "argon_filled", "type": "boolean", "label": "Argon/Gas Filled"},
                {"name": "u_factor", "type": "number", "label": "U-Factor", "step": 0.01, "helperText": "Lower is better (0.20-0.40 typical)"},
                {"name": "shgc", "type": "number", "label": "Solar Heat Gain Coefficient", "step": 0.01, "helperText": "0-1 scale"},
                {"name": "energy_star", "type": "boolean", "label": "ENERGY STAR Certified"},
                {"name": "nfrc_certified", "type": "boolean", "label": "NFRC Certified"}
            ]
        },
        {
            "id": "dimensions",
            "title": "Window Dimensions",
            "fields": [
                {"name": "total_sqft", "type": "number", "label": "Total Window Area (sq ft)"},
                {"name": "windows_by_size", "type": "window_list", "label": "Windows by Size", "fields": [
                    {"name": "width_inches", "type": "number"},
                    {"name": "height_inches", "type": "number"},
                    {"name": "quantity", "type": "number"}
                ]}
            ]
        },
        {
            "id": "old_windows",
            "title": "Old Windows Removed",
            "showIf": "service_category === Full Replacement || service_category === Insert Replacement",
            "fields": [
                {"name": "old_frame_material", "type": "select", "label": "Old Frame Material", "options": ["Vinyl", "Aluminum", "Wood", "Steel", "Unknown"]},
                {"name": "old_glass_type", "type": "select", "label": "Old Glass Type", "options": ["Single Pane", "Double Pane", "Unknown"]},
                {"name": "old_u_factor", "type": "number", "label": "Old U-Factor (estimated)", "step": 0.01},
                {"name": "old_window_age_years", "type": "number", "label": "Old Window Age (years)"},
                {"name": "lead_paint_present", "type": "boolean", "label": "Lead Paint Present"},
                {"name": "lead_safe_practices", "type": "boolean", "label": "Lead-Safe Practices Used", "showIf": "lead_paint_present === true"}
            ]
        },
        {
            "id": "waste_recycling",
            "title": "Waste & Recycling",
            "fields": [
                {"name": "old_windows_recycled", "type": "boolean", "label": "Old Windows Recycled"},
                {"name": "glass_recycled_lbs", "type": "number", "label": "Glass Recycled (lbs)"},
                {"name": "metal_recycled_lbs", "type": "number", "label": "Metal Recycled (lbs)"},
                {"name": "wood_recycled_lbs", "type": "number", "label": "Wood Recycled (lbs)"},
                {"name": "vinyl_recycled_lbs", "type": "number", "label": "Vinyl Recycled (lbs)"},
                {"name": "landfill_lbs", "type": "number", "label": "Sent to Landfill (lbs)"},
                {"name": "packaging_recycled", "type": "boolean", "label": "Packaging Recycled"}
            ]
        },
        {
            "id": "installation",
            "title": "Installation Details",
            "fields": [
                {"name": "insulation_added", "type": "boolean", "label": "Insulation Added Around Frames"},
                {"name": "spray_foam_oz", "type": "number", "label": "Spray Foam Used (oz)"},
                {"name": "caulking_tubes", "type": "number", "label": "Caulking Tubes Used"},
                {"name": "trim_replaced", "type": "boolean", "label": "Interior Trim Replaced"},
                {"name": "exterior_trim_replaced", "type": "boolean", "label": "Exterior Trim Replaced"},
                {"name": "flashing_installed", "type": "boolean", "label": "Flashing Installed"}
            ]
        },
        {
            "id": "energy_impact",
            "title": "Energy Impact",
            "fields": [
                {"name": "estimated_heating_savings_percent", "type": "number", "label": "Estimated Heating Savings (%)"},
                {"name": "estimated_cooling_savings_percent", "type": "number", "label": "Estimated Cooling Savings (%)"},
                {"name": "estimated_annual_kwh_savings", "type": "number", "label": "Estimated Annual Energy Savings (kWh)"},
                {"name": "estimated_annual_cost_savings", "type": "number", "label": "Estimated Annual Cost Savings ($)"},
                {"name": "utility_rebate_eligible", "type": "boolean", "label": "Utility Rebate Eligible"},
                {"name": "tax_credit_eligible", "type": "boolean", "label": "Federal Tax Credit Eligible"}
            ]
        }
    ]
}'::jsonb
FROM verticals WHERE slug = 'window-installation';

-- =============================================
-- LOCKSMITH VERTICAL
-- =============================================
INSERT INTO vertical_form_config (vertical_id, form_config)
SELECT id, '{
    "sections": [
        {
            "id": "service_type",
            "title": "Service Type",
            "fields": [
                {"name": "service_category", "type": "select", "label": "Service Category", "required": true, "options": ["Lock Installation", "Lock Repair", "Rekey", "Lockout Service", "Key Duplication", "Safe Service", "Access Control", "Automotive"]},
                {"name": "property_type", "type": "select", "label": "Property Type", "options": ["Residential", "Commercial", "Automotive", "Industrial"]}
            ]
        },
        {
            "id": "lock_details",
            "title": "Lock Details",
            "fields": [
                {"name": "lock_type", "type": "multiselect", "label": "Lock Types Serviced", "options": ["Deadbolt", "Knob Lock", "Lever Handle", "Mortise Lock", "Rim Lock", "Padlock", "Smart Lock", "Keypad Lock", "Card Access", "Biometric"]},
                {"name": "lock_brand", "type": "text", "label": "Lock Brand"},
                {"name": "lock_grade", "type": "select", "label": "Lock Grade", "options": ["Grade 1 (Commercial)", "Grade 2 (Light Commercial)", "Grade 3 (Residential)", "Unknown"]},
                {"name": "locks_installed", "type": "number", "label": "Locks Installed"},
                {"name": "locks_repaired", "type": "number", "label": "Locks Repaired"},
                {"name": "locks_rekeyed", "type": "number", "label": "Locks Rekeyed"}
            ]
        },
        {
            "id": "smart_locks",
            "title": "Smart Lock Installation",
            "showIf": "lock_type includes Smart Lock || lock_type includes Keypad Lock || lock_type includes Biometric",
            "fields": [
                {"name": "smart_lock_brand", "type": "text", "label": "Smart Lock Brand"},
                {"name": "smart_lock_model", "type": "text", "label": "Smart Lock Model"},
                {"name": "battery_type", "type": "select", "label": "Battery Type", "options": ["AA", "AAA", "CR123A", "Rechargeable", "Hardwired"]},
                {"name": "wifi_connected", "type": "boolean", "label": "WiFi Connected"},
                {"name": "home_automation_compatible", "type": "boolean", "label": "Home Automation Compatible"}
            ]
        },
        {
            "id": "keys",
            "title": "Keys",
            "fields": [
                {"name": "keys_made", "type": "number", "label": "Keys Made/Duplicated"},
                {"name": "key_type", "type": "select", "label": "Key Type", "options": ["Standard", "High Security", "Restricted", "Transponder", "Smart Key", "Fob"]},
                {"name": "key_material", "type": "select", "label": "Key Material", "options": ["Brass", "Nickel Silver", "Steel", "Plastic/Electronic"]}
            ]
        },
        {
            "id": "old_hardware",
            "title": "Old Hardware Disposal",
            "fields": [
                {"name": "old_locks_removed", "type": "number", "label": "Old Locks Removed"},
                {"name": "old_hardware_recycled", "type": "boolean", "label": "Old Hardware Recycled"},
                {"name": "metal_recycled_lbs", "type": "number", "label": "Metal Recycled (lbs)", "step": 0.1},
                {"name": "electronic_waste", "type": "boolean", "label": "Electronic Waste Generated"},
                {"name": "ewaste_properly_disposed", "type": "boolean", "label": "E-Waste Properly Disposed", "showIf": "electronic_waste === true"}
            ]
        },
        {
            "id": "automotive",
            "title": "Automotive Service",
            "showIf": "service_category === Automotive",
            "fields": [
                {"name": "vehicle_make", "type": "text", "label": "Vehicle Make"},
                {"name": "vehicle_model", "type": "text", "label": "Vehicle Model"},
                {"name": "vehicle_year", "type": "number", "label": "Vehicle Year"},
                {"name": "key_programming", "type": "boolean", "label": "Key Programming Required"},
                {"name": "ignition_service", "type": "boolean", "label": "Ignition Service"}
            ]
        }
    ]
}'::jsonb
FROM verticals WHERE slug = 'locksmith';

-- =============================================
-- CARPET CLEANING VERTICAL
-- =============================================
INSERT INTO vertical_form_config (vertical_id, form_config)
SELECT id, '{
    "sections": [
        {
            "id": "service_type",
            "title": "Service Type",
            "fields": [
                {"name": "service_category", "type": "select", "label": "Service Category", "required": true, "options": ["Steam Cleaning", "Dry Cleaning", "Encapsulation", "Bonnet Cleaning", "Shampoo", "Stain Treatment", "Pet Treatment", "Commercial"]},
                {"name": "property_type", "type": "select", "label": "Property Type", "options": ["Residential", "Commercial", "Multi-Family", "Hospitality"]}
            ]
        },
        {
            "id": "area_details",
            "title": "Area Details",
            "fields": [
                {"name": "total_sqft", "type": "number", "label": "Total Area Cleaned (sq ft)", "required": true},
                {"name": "rooms_cleaned", "type": "number", "label": "Rooms Cleaned"},
                {"name": "stairs_cleaned", "type": "number", "label": "Stairs Cleaned"},
                {"name": "carpet_type", "type": "select", "label": "Carpet Type", "options": ["Cut Pile", "Loop Pile", "Cut-Loop", "Berber", "Frieze", "Commercial Grade"]},
                {"name": "carpet_material", "type": "select", "label": "Carpet Material", "options": ["Nylon", "Polyester", "Olefin", "Wool", "Triexta", "Blend", "Unknown"]}
            ]
        },
        {
            "id": "cleaning_products",
            "title": "Cleaning Products",
            "fields": [
                {"name": "pre_spray_oz", "type": "number", "label": "Pre-Spray Solution (oz)"},
                {"name": "cleaning_solution_oz", "type": "number", "label": "Main Cleaning Solution (oz)"},
                {"name": "spot_treatment_oz", "type": "number", "label": "Spot Treatment (oz)"},
                {"name": "deodorizer_oz", "type": "number", "label": "Deodorizer (oz)"},
                {"name": "protectant_oz", "type": "number", "label": "Carpet Protectant (oz)"},
                {"name": "green_seal_certified", "type": "boolean", "label": "Green Seal Certified Products"},
                {"name": "epa_safer_choice", "type": "boolean", "label": "EPA Safer Choice Products"},
                {"name": "fragrance_free", "type": "boolean", "label": "Fragrance-Free Products"},
                {"name": "enzyme_based", "type": "boolean", "label": "Enzyme-Based Cleaners"}
            ]
        },
        {
            "id": "water_usage",
            "title": "Water Usage",
            "fields": [
                {"name": "water_used_gallons", "type": "number", "label": "Fresh Water Used (gallons)"},
                {"name": "water_extracted_gallons", "type": "number", "label": "Water Extracted (gallons)"},
                {"name": "wastewater_disposed", "type": "select", "label": "Wastewater Disposal", "options": ["Sanitary Sewer", "Holding Tank", "Treatment Facility", "On-Site Treatment"]},
                {"name": "hot_water_used", "type": "boolean", "label": "Hot Water Extraction"},
                {"name": "water_temp_f", "type": "number", "label": "Water Temperature (°F)", "showIf": "hot_water_used === true"}
            ]
        },
        {
            "id": "equipment",
            "title": "Equipment Used",
            "fields": [
                {"name": "equipment_type", "type": "select", "label": "Primary Equipment", "options": ["Truck Mount", "Portable Extractor", "Dry Compound Machine", "Encapsulation Machine", "Rotary/Bonnet"]},
                {"name": "truck_mount_fuel_gallons", "type": "number", "label": "Truck Mount Fuel (gallons)", "showIf": "equipment_type === Truck Mount", "step": 0.1},
                {"name": "hepa_vacuum_used", "type": "boolean", "label": "HEPA Vacuum Used"},
                {"name": "air_movers_used", "type": "number", "label": "Air Movers Used"},
                {"name": "dehumidifier_used", "type": "boolean", "label": "Dehumidifier Used"}
            ]
        },
        {
            "id": "iaq",
            "title": "Indoor Air Quality",
            "fields": [
                {"name": "allergen_treatment", "type": "boolean", "label": "Allergen Treatment Applied"},
                {"name": "antimicrobial_treatment", "type": "boolean", "label": "Antimicrobial Treatment Applied"},
                {"name": "drying_time_hours", "type": "number", "label": "Expected Drying Time (hours)"},
                {"name": "ventilation_recommended", "type": "boolean", "label": "Ventilation Recommended"}
            ]
        },
        {
            "id": "upholstery",
            "title": "Upholstery Cleaning",
            "fields": [
                {"name": "upholstery_cleaned", "type": "boolean", "label": "Upholstery Also Cleaned"},
                {"name": "upholstery_pieces", "type": "number", "label": "Upholstery Pieces", "showIf": "upholstery_cleaned === true"},
                {"name": "upholstery_sqft", "type": "number", "label": "Upholstery Area (sq ft)", "showIf": "upholstery_cleaned === true"}
            ]
        }
    ]
}'::jsonb
FROM verticals WHERE slug = 'carpet-cleaning';

-- =============================================
-- TREE SERVICE VERTICAL
-- =============================================
INSERT INTO vertical_form_config (vertical_id, form_config)
SELECT id, '{
    "sections": [
        {
            "id": "service_type",
            "title": "Service Type",
            "fields": [
                {"name": "service_category", "type": "multiselect", "label": "Services Performed", "required": true, "options": ["Tree Removal", "Tree Trimming/Pruning", "Stump Grinding", "Stump Removal", "Emergency Service", "Cabling/Bracing", "Disease Treatment", "Tree Planting", "Arborist Consultation"]}
            ]
        },
        {
            "id": "tree_details",
            "title": "Tree Details",
            "fields": [
                {"name": "tree_species", "type": "text", "label": "Tree Species"},
                {"name": "tree_count", "type": "number", "label": "Number of Trees"},
                {"name": "avg_height_ft", "type": "number", "label": "Average Tree Height (ft)"},
                {"name": "avg_diameter_inches", "type": "number", "label": "Average Trunk Diameter (inches)"},
                {"name": "tree_condition", "type": "select", "label": "Tree Condition", "options": ["Healthy", "Diseased", "Dead", "Storm Damaged", "Hazardous"]}
            ]
        },
        {
            "id": "removal_details",
            "title": "Removal Details",
            "showIf": "service_category includes Tree Removal",
            "fields": [
                {"name": "trees_removed", "type": "number", "label": "Trees Removed"},
                {"name": "reason_for_removal", "type": "select", "label": "Reason for Removal", "options": ["Dead/Dying", "Storm Damage", "Disease", "Construction", "Hazard", "Customer Request", "Utility Clearance"]},
                {"name": "permit_required", "type": "boolean", "label": "Removal Permit Required"},
                {"name": "permit_number", "type": "text", "label": "Permit Number", "showIf": "permit_required === true"},
                {"name": "protected_species", "type": "boolean", "label": "Protected Species"},
                {"name": "mitigation_required", "type": "boolean", "label": "Tree Mitigation Required", "showIf": "protected_species === true"}
            ]
        },
        {
            "id": "equipment_fuel",
            "title": "Equipment & Fuel",
            "fields": [
                {"name": "chainsaw_gas_gallons", "type": "number", "label": "Chainsaw Fuel (gallons)", "step": 0.1},
                {"name": "chipper_gas_gallons", "type": "number", "label": "Chipper Fuel (gallons)", "step": 0.1},
                {"name": "stump_grinder_gas_gallons", "type": "number", "label": "Stump Grinder Fuel (gallons)", "step": 0.1},
                {"name": "truck_diesel_gallons", "type": "number", "label": "Truck/Equipment Diesel (gallons)", "step": 0.1},
                {"name": "aerial_lift_used", "type": "boolean", "label": "Aerial Lift Used"},
                {"name": "crane_used", "type": "boolean", "label": "Crane Used"}
            ]
        },
        {
            "id": "wood_waste",
            "title": "Wood & Debris",
            "fields": [
                {"name": "wood_tons", "type": "number", "label": "Wood Generated (tons)", "step": 0.1},
                {"name": "brush_yards", "type": "number", "label": "Brush/Branches (cubic yards)"},
                {"name": "wood_destination", "type": "select", "label": "Wood Destination", "options": ["Firewood (customer)", "Firewood (donated)", "Lumber Mill", "Biomass Facility", "Mulch/Chips", "Landfill"]},
                {"name": "brush_destination", "type": "select", "label": "Brush Destination", "options": ["Chipped On-Site", "Composting Facility", "Municipal Yard Waste", "Biomass Facility", "Landfill"]},
                {"name": "mulch_left_onsite", "type": "boolean", "label": "Mulch Left On-Site"},
                {"name": "mulch_yards_left", "type": "number", "label": "Mulch Left (cubic yards)", "showIf": "mulch_left_onsite === true"}
            ]
        },
        {
            "id": "stump_service",
            "title": "Stump Service",
            "showIf": "service_category includes Stump Grinding || service_category includes Stump Removal",
            "fields": [
                {"name": "stumps_ground", "type": "number", "label": "Stumps Ground"},
                {"name": "avg_stump_diameter", "type": "number", "label": "Average Stump Diameter (inches)"},
                {"name": "grinding_depth_inches", "type": "number", "label": "Grinding Depth (inches)"},
                {"name": "grindings_removed", "type": "boolean", "label": "Grindings Removed"},
                {"name": "grindings_yards", "type": "number", "label": "Grindings (cubic yards)"},
                {"name": "backfill_added", "type": "boolean", "label": "Backfill/Topsoil Added"}
            ]
        },
        {
            "id": "planting",
            "title": "Tree Planting",
            "showIf": "service_category includes Tree Planting",
            "fields": [
                {"name": "trees_planted", "type": "number", "label": "Trees Planted"},
                {"name": "species_planted", "type": "text", "label": "Species Planted"},
                {"name": "native_species", "type": "boolean", "label": "Native Species"},
                {"name": "caliper_inches", "type": "number", "label": "Caliper Size (inches)"},
                {"name": "container_size", "type": "select", "label": "Container Size", "options": ["1 gallon", "5 gallon", "15 gallon", "24\" box", "36\" box", "B&B (Balled & Burlapped)"]},
                {"name": "carbon_sequestration_annual_lbs", "type": "number", "label": "Est. Annual CO2 Sequestration (lbs)", "computed": true}
            ]
        },
        {
            "id": "environmental_impact",
            "title": "Environmental Impact",
            "fields": [
                {"name": "carbon_released_tons", "type": "number", "label": "Est. Carbon Released (tons)", "helperText": "From tree removal", "computed": true},
                {"name": "habitat_assessment", "type": "boolean", "label": "Wildlife Habitat Assessment Done"},
                {"name": "nesting_season", "type": "boolean", "label": "Nesting Season Considerations"},
                {"name": "erosion_control", "type": "boolean", "label": "Erosion Control Measures Taken"}
            ]
        }
    ]
}'::jsonb
FROM verticals WHERE slug = 'tree-service';

RAISE NOTICE 'Additional vertical form configurations completed';
