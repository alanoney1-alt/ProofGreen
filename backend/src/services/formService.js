const { supabase } = require('../utils/supabase');
const { logger } = require('../utils/logger');
const { CARBON_FACTORS } = require('./complianceService');

/**
 * Get dynamic form fields for a vertical
 */
async function getFormFields(verticalId) {
  try {
    // Get form configuration from database
    const { data: fields, error } = await supabase
      .from('vertical_form_config')
      .select('*')
      .eq('vertical_id', verticalId)
      .eq('is_active', true)
      .order('display_order');

    if (error) throw error;

    // Transform to frontend-friendly format
    return (fields || []).map(field => ({
      name: field.field_key,
      type: field.field_type,
      label: field.label,
      placeholder: field.placeholder,
      helpText: field.help_text,
      required: field.is_required,
      validation: field.validation_rules || {},
      options: field.options || [],
      group: field.field_group,
      calculationFormula: field.calculation_formula,
      requirementId: field.requirement_id
    }));
  } catch (error) {
    logger.error('Get form fields error:', error);
    // Return fallback fields if database fetch fails
    return getDefaultFormFields(verticalId);
  }
}

/**
 * Get form fields by vertical slug
 */
async function getFormFieldsBySlug(verticalSlug) {
  try {
    const { data: vertical } = await supabase
      .from('verticals')
      .select('id')
      .eq('slug', verticalSlug)
      .single();

    if (!vertical) {
      return getDefaultFormFieldsBySlug(verticalSlug);
    }

    return getFormFields(vertical.id);
  } catch (error) {
    logger.error('Get form fields by slug error:', error);
    return getDefaultFormFieldsBySlug(verticalSlug);
  }
}

/**
 * Default form fields when database is not available
 */
function getDefaultFormFieldsBySlug(verticalSlug) {
  const formConfigs = {
    junk_removal: [
      { name: 'total_weight_lbs', type: 'number', label: 'Total Weight (lbs)', required: true, validation: { min: 0 }, group: 'weight', helpText: 'AI can estimate from photo. Enter actual weight from scale if available.' },
      { name: 'recycled_weight_lbs', type: 'number', label: 'Recycled Weight (lbs)', required: true, validation: { min: 0 }, group: 'weight', helpText: 'Weight of materials sent to recycling facilities.' },
      { name: 'donated_weight_lbs', type: 'number', label: 'Donated Weight (lbs)', required: false, validation: { min: 0 }, group: 'weight', helpText: 'Weight of items donated to charity.' },
      { name: 'landfill_weight_lbs', type: 'number', label: 'Landfill Weight (lbs)', required: true, validation: { min: 0 }, group: 'weight', helpText: 'Weight of materials sent to landfill.' },
      { name: 'recycling_center', type: 'text', label: 'Recycling Center Name', required: true, group: 'documentation', helpText: 'Name and location of recycling facility used.' },
      { name: 'weight_ticket_url', type: 'file', label: 'Weight Ticket', required: true, validation: { accept: 'image/*,application/pdf' }, group: 'documentation', helpText: 'Scan or photo of weight ticket from recycling center.' },
      { name: 'donation_receipt_url', type: 'file', label: 'Donation Receipt', required: false, validation: { accept: 'image/*,application/pdf' }, group: 'documentation', helpText: 'Receipt from charity for donated items.' },
      { name: 'fuel_gallons', type: 'number', label: 'Fuel Used (gallons)', required: true, validation: { min: 0, step: 0.1 }, group: 'carbon', helpText: 'Total fuel consumed for this job.' },
      { name: 'miles_driven', type: 'number', label: 'Miles Driven', required: true, validation: { min: 0 }, group: 'carbon', helpText: 'Total miles driven for this job (round trip).' },
      { name: 'carbon_emissions_lbs', type: 'calculated', label: 'Carbon Emissions (lbs CO2)', group: 'carbon', calculationFormula: 'fuel_gallons * 19.6' },
      { name: 'diversion_rate', type: 'calculated', label: 'Diversion Rate (%)', group: 'metrics', calculationFormula: '((recycled_weight_lbs + donated_weight_lbs) / total_weight_lbs) * 100' }
    ],

    hvac: [
      { name: 'refrigerant_type', type: 'select', label: 'Refrigerant Type', required: true, options: ['R-22', 'R-410A', 'R-32', 'R-134a', 'R-404A', 'R-407C', 'Other'], group: 'refrigerant', helpText: 'Type of refrigerant in the system.' },
      { name: 'refrigerant_recovered_lbs', type: 'number', label: 'Refrigerant Recovered (lbs)', required: true, validation: { min: 0, step: 0.1 }, group: 'refrigerant', helpText: 'Amount of refrigerant recovered during service.' },
      { name: 'epa_cert_number', type: 'text', label: 'EPA 608 Certification Number', required: true, validation: { pattern: '[A-Za-z0-9-]+' }, group: 'certification', helpText: 'Your EPA Section 608 certification number.' },
      { name: 'old_unit_seer', type: 'number', label: 'Old Unit SEER Rating', required: false, validation: { min: 6, max: 30 }, group: 'efficiency', helpText: 'SEER rating of unit being replaced.' },
      { name: 'new_unit_seer', type: 'number', label: 'New Unit SEER Rating', required: false, validation: { min: 13, max: 30 }, group: 'efficiency', helpText: 'SEER rating of new unit installed.' },
      { name: 'btu_capacity', type: 'number', label: 'System BTU Capacity', required: false, validation: { min: 0 }, group: 'efficiency', helpText: 'Cooling capacity of the system.' },
      { name: 'unit_weight_lbs', type: 'number', label: 'Old Unit Weight (lbs)', required: false, validation: { min: 0 }, group: 'weight', helpText: 'Weight of removed HVAC unit for recycling.' },
      { name: 'disposal_manifest_url', type: 'file', label: 'Refrigerant Disposal Manifest', required: true, validation: { accept: 'image/*,application/pdf' }, group: 'documentation', helpText: 'EPA-compliant disposal documentation.' },
      { name: 'energy_savings_kwh', type: 'calculated', label: 'Est. Annual Energy Savings (kWh)', group: 'metrics', calculationFormula: 'btu_capacity * ((1/old_unit_seer - 1/new_unit_seer)) * 1000 / 1000' },
      { name: 'carbon_offset_lbs', type: 'calculated', label: 'Carbon Offset (lbs CO2/year)', group: 'metrics', calculationFormula: 'energy_savings_kwh * 0.855' }
    ],

    roofing: [
      { name: 'roof_area_sqft', type: 'number', label: 'Roof Area (sq ft)', required: true, validation: { min: 0 }, group: 'measurements', helpText: 'Total roof area for the project.' },
      { name: 'material_type', type: 'select', label: 'Primary Roofing Material', required: true, options: ['Asphalt Shingles', 'Metal', 'Tile', 'Wood Shake', 'Slate', 'Flat/TPO', 'EPDM', 'Other'], group: 'materials', helpText: 'Main roofing material removed/installed.' },
      { name: 'old_material_weight_lbs', type: 'number', label: 'Removed Material Weight (lbs)', required: true, validation: { min: 0 }, group: 'weight', helpText: 'Total weight of old roofing materials removed.' },
      { name: 'recycled_weight_lbs', type: 'number', label: 'Recycled Weight (lbs)', required: true, validation: { min: 0 }, group: 'weight', helpText: 'Weight of materials sent to recycling.' },
      { name: 'landfill_weight_lbs', type: 'number', label: 'Landfill Weight (lbs)', required: true, validation: { min: 0 }, group: 'weight', helpText: 'Weight of materials sent to landfill.' },
      { name: 'metal_recycled_lbs', type: 'number', label: 'Metal Recycled (lbs)', required: false, validation: { min: 0 }, group: 'weight', helpText: 'Weight of metal (flashing, gutters) recycled.' },
      { name: 'recycling_receipt_url', type: 'file', label: 'Recycling Weight Ticket', required: true, validation: { accept: 'image/*,application/pdf' }, group: 'documentation', helpText: 'Weight ticket from recycling facility.' },
      { name: 'is_cool_roof', type: 'checkbox', label: 'Energy Star Cool Roof', required: false, group: 'certification', helpText: 'Check if cool roof materials were installed.' },
      { name: 'sri_value', type: 'number', label: 'Solar Reflectance Index (SRI)', required: false, validation: { min: 0, max: 150 }, group: 'certification', helpText: 'SRI value of installed roofing.' },
      { name: 'diversion_rate', type: 'calculated', label: 'Diversion Rate (%)', group: 'metrics', calculationFormula: '(recycled_weight_lbs / old_material_weight_lbs) * 100' }
    ],

    cleaning: [
      { name: 'area_sqft', type: 'number', label: 'Area Cleaned (sq ft)', required: true, validation: { min: 0 }, group: 'measurements', helpText: 'Total area cleaned.' },
      { name: 'cleaning_type', type: 'select', label: 'Cleaning Type', required: true, options: ['Regular Maintenance', 'Deep Clean', 'Post-Construction', 'Move In/Out', 'Specialty'], group: 'service', helpText: 'Type of cleaning service performed.' },
      { name: 'green_products_count', type: 'number', label: 'Green Products Used', required: true, validation: { min: 0 }, group: 'products', helpText: 'EPA Safer Choice or Green Seal certified products.' },
      { name: 'total_products_count', type: 'number', label: 'Total Products Used', required: true, validation: { min: 1 }, group: 'products', helpText: 'Total number of cleaning products used.' },
      { name: 'water_gallons', type: 'number', label: 'Water Used (gallons)', required: false, validation: { min: 0 }, group: 'resources', helpText: 'Estimated water consumption.' },
      { name: 'sds_uploaded', type: 'checkbox', label: 'Safety Data Sheets on File', required: true, group: 'compliance', helpText: 'Confirm SDS available for all products.' },
      { name: 'product_list_url', type: 'file', label: 'Product List Document', required: false, validation: { accept: 'application/pdf,image/*' }, group: 'documentation', helpText: 'List of products used with certifications.' },
      { name: 'green_product_percentage', type: 'calculated', label: 'Green Product Percentage (%)', group: 'metrics', calculationFormula: '(green_products_count / total_products_count) * 100' }
    ],

    landscaping: [
      { name: 'area_sqft', type: 'number', label: 'Area Serviced (sq ft)', required: true, validation: { min: 0 }, group: 'measurements', helpText: 'Total area of landscape service.' },
      { name: 'service_type', type: 'select', label: 'Service Type', required: true, options: ['Maintenance', 'Installation', 'Irrigation', 'Tree Service', 'Hardscape', 'Other'], group: 'service', helpText: 'Type of landscaping service.' },
      { name: 'water_gallons', type: 'number', label: 'Water Used (gallons)', required: true, validation: { min: 0 }, group: 'resources', helpText: 'Total irrigation water used.' },
      { name: 'pesticide_applied', type: 'checkbox', label: 'Pesticides Applied', required: true, group: 'compliance', helpText: 'Were any pesticides applied?' },
      { name: 'pesticide_type', type: 'text', label: 'Pesticide Product Name', required: false, group: 'compliance', helpText: 'Name of pesticide product used.' },
      { name: 'pesticide_amount', type: 'text', label: 'Amount Applied', required: false, group: 'compliance', helpText: 'Amount and unit (e.g., 2 oz/1000 sqft).' },
      { name: 'native_plants_count', type: 'number', label: 'Native Plants Installed', required: false, validation: { min: 0 }, group: 'plants', helpText: 'Number of native plants installed.' },
      { name: 'total_plants_count', type: 'number', label: 'Total Plants Installed', required: false, validation: { min: 0 }, group: 'plants', helpText: 'Total plants installed.' },
      { name: 'green_waste_lbs', type: 'number', label: 'Green Waste (lbs)', required: false, validation: { min: 0 }, group: 'waste', helpText: 'Weight of green waste collected.' },
      { name: 'composted_lbs', type: 'number', label: 'Composted (lbs)', required: false, validation: { min: 0 }, group: 'waste', helpText: 'Weight sent to composting.' },
      { name: 'native_plant_percentage', type: 'calculated', label: 'Native Plant Percentage (%)', group: 'metrics', calculationFormula: '(native_plants_count / total_plants_count) * 100' }
    ],

    plumbing: [
      { name: 'service_type', type: 'select', label: 'Service Type', required: true, options: ['Repair', 'Installation', 'Replacement', 'Inspection', 'Emergency', 'Other'], group: 'service', helpText: 'Type of plumbing service.' },
      { name: 'fixture_type', type: 'select', label: 'Fixture Type', required: false, options: ['Toilet', 'Faucet', 'Showerhead', 'Water Heater', 'Pipe', 'Other'], group: 'fixture', helpText: 'Type of fixture worked on.' },
      { name: 'old_gpm', type: 'number', label: 'Old Flow Rate (GPM)', required: false, validation: { min: 0, step: 0.1 }, group: 'efficiency', helpText: 'Old fixture flow rate in gallons per minute.' },
      { name: 'new_gpm', type: 'number', label: 'New Flow Rate (GPM)', required: false, validation: { min: 0, step: 0.1 }, group: 'efficiency', helpText: 'New fixture flow rate in gallons per minute.' },
      { name: 'is_watersense', type: 'checkbox', label: 'WaterSense Certified', required: false, group: 'certification', helpText: 'Is the new fixture WaterSense certified?' },
      { name: 'copper_recycled_lbs', type: 'number', label: 'Copper Recycled (lbs)', required: false, validation: { min: 0 }, group: 'recycling', helpText: 'Weight of copper pipe recycled.' },
      { name: 'brass_recycled_lbs', type: 'number', label: 'Brass Recycled (lbs)', required: false, validation: { min: 0 }, group: 'recycling', helpText: 'Weight of brass fixtures recycled.' },
      { name: 'recycling_receipt_url', type: 'file', label: 'Metal Recycling Receipt', required: false, validation: { accept: 'image/*,application/pdf' }, group: 'documentation', helpText: 'Receipt from scrap metal recycler.' },
      { name: 'daily_uses', type: 'number', label: 'Estimated Daily Uses', required: false, validation: { min: 0 }, group: 'efficiency', helpText: 'Estimated uses per day for calculation.' },
      { name: 'water_savings_gallons', type: 'calculated', label: 'Annual Water Savings (gallons)', group: 'metrics', calculationFormula: '(old_gpm - new_gpm) * daily_uses * 365' }
    ],

    electrical: [
      { name: 'service_type', type: 'select', label: 'Service Type', required: true, options: ['Lighting Upgrade', 'Panel Work', 'Solar Installation', 'EV Charger', 'Repair', 'Other'], group: 'service', helpText: 'Type of electrical service.' },
      { name: 'old_wattage', type: 'number', label: 'Old Wattage (total)', required: false, validation: { min: 0 }, group: 'efficiency', helpText: 'Total wattage of old lighting/equipment.' },
      { name: 'new_wattage', type: 'number', label: 'New Wattage (total)', required: false, validation: { min: 0 }, group: 'efficiency', helpText: 'Total wattage of new lighting/equipment.' },
      { name: 'hours_per_day', type: 'number', label: 'Hours Used Per Day', required: false, validation: { min: 0, max: 24 }, group: 'efficiency', helpText: 'Average hours of daily operation.' },
      { name: 'is_led', type: 'checkbox', label: 'LED Lighting Installed', required: false, group: 'certification', helpText: 'Were LED lights installed?' },
      { name: 'is_energy_star', type: 'checkbox', label: 'Energy Star Equipment', required: false, group: 'certification', helpText: 'Is equipment Energy Star rated?' },
      { name: 'solar_kw', type: 'number', label: 'Solar System Size (kW)', required: false, validation: { min: 0 }, group: 'solar', helpText: 'Size of solar installation in kilowatts.' },
      { name: 'ewaste_recycled_lbs', type: 'number', label: 'E-Waste Recycled (lbs)', required: false, validation: { min: 0 }, group: 'recycling', helpText: 'Weight of electronic waste recycled.' },
      { name: 'ewaste_receipt_url', type: 'file', label: 'E-Waste Receipt', required: false, validation: { accept: 'image/*,application/pdf' }, group: 'documentation', helpText: 'Receipt from certified e-waste recycler.' },
      { name: 'energy_savings_kwh', type: 'calculated', label: 'Annual Energy Savings (kWh)', group: 'metrics', calculationFormula: '((old_wattage - new_wattage) * hours_per_day * 365) / 1000' },
      { name: 'carbon_offset_lbs', type: 'calculated', label: 'Carbon Offset (lbs CO2/year)', group: 'metrics', calculationFormula: 'energy_savings_kwh * 0.855' }
    ],

    demolition: [
      { name: 'project_type', type: 'select', label: 'Demolition Type', required: true, options: ['Full Structure', 'Partial/Interior', 'Selective', 'Deconstruction', 'Other'], group: 'project', helpText: 'Type of demolition project.' },
      { name: 'total_weight_tons', type: 'number', label: 'Total Material Weight (tons)', required: true, validation: { min: 0 }, group: 'weight', helpText: 'Total weight of all materials.' },
      { name: 'concrete_recycled_tons', type: 'number', label: 'Concrete Recycled (tons)', required: false, validation: { min: 0 }, group: 'materials', helpText: 'Concrete sent to recycling.' },
      { name: 'metal_recycled_tons', type: 'number', label: 'Metal Recycled (tons)', required: false, validation: { min: 0 }, group: 'materials', helpText: 'Metal sent to recycling.' },
      { name: 'wood_recycled_tons', type: 'number', label: 'Wood Recycled (tons)', required: false, validation: { min: 0 }, group: 'materials', helpText: 'Wood sent to recycling/reuse.' },
      { name: 'drywall_recycled_tons', type: 'number', label: 'Drywall Recycled (tons)', required: false, validation: { min: 0 }, group: 'materials', helpText: 'Drywall sent to recycling.' },
      { name: 'landfill_tons', type: 'number', label: 'Landfill (tons)', required: true, validation: { min: 0 }, group: 'materials', helpText: 'Materials sent to landfill.' },
      { name: 'has_hazmat', type: 'checkbox', label: 'Hazardous Materials Present', required: true, group: 'compliance', helpText: 'Were any hazardous materials encountered?' },
      { name: 'hazmat_type', type: 'text', label: 'Hazmat Type', required: false, group: 'compliance', helpText: 'Type of hazardous material (asbestos, lead, etc.).' },
      { name: 'hazmat_manifest_url', type: 'file', label: 'Hazmat Disposal Manifest', required: false, validation: { accept: 'image/*,application/pdf' }, group: 'documentation', helpText: 'EPA disposal manifest.' },
      { name: 'recycling_receipts_url', type: 'file', label: 'Recycling Receipts', required: true, validation: { accept: 'image/*,application/pdf' }, group: 'documentation', helpText: 'Weight tickets from recycling facilities.' },
      { name: 'diversion_rate', type: 'calculated', label: 'Diversion Rate (%)', group: 'metrics', calculationFormula: '((total_weight_tons - landfill_tons) / total_weight_tons) * 100' }
    ]
  };

  return formConfigs[verticalSlug] || [];
}

function getDefaultFormFields(verticalId) {
  // Return basic common fields
  return [
    { name: 'notes', type: 'text', label: 'Notes', required: false, group: 'general' }
  ];
}

/**
 * Calculate derived/computed field values
 */
function calculateDerivedFields(data, verticalSlug) {
  const calculations = {
    // Diversion rate calculation
    diversion_rate: () => {
      const total = parseFloat(data.total_weight_lbs || data.old_material_weight_lbs || data.total_weight_tons * 2000) || 0;
      const recycled = parseFloat(data.recycled_weight_lbs || 0);
      const donated = parseFloat(data.donated_weight_lbs || 0);
      if (total === 0) return 0;
      return ((recycled + donated) / total) * 100;
    },

    // Carbon emissions from fuel
    carbon_emissions_lbs: () => {
      const gallons = parseFloat(data.fuel_gallons) || 0;
      return gallons * CARBON_FACTORS.gasoline_per_gallon;
    },

    // Energy savings from SEER improvement (HVAC)
    energy_savings_kwh: () => {
      const oldSeer = parseFloat(data.old_unit_seer) || 0;
      const newSeer = parseFloat(data.new_unit_seer) || 0;
      const btu = parseFloat(data.btu_capacity) || 0;
      const hours = parseFloat(data.hours_per_day) || 8;

      if (verticalSlug === 'hvac' && oldSeer && newSeer && btu) {
        // Simplified calculation: BTU * hours * days * (1/oldSEER - 1/newSEER) / 1000
        return (btu * hours * 365 * (1/oldSeer - 1/newSeer)) / 1000;
      }

      // For electrical upgrades
      const oldWattage = parseFloat(data.old_wattage) || 0;
      const newWattage = parseFloat(data.new_wattage) || 0;
      if (oldWattage && newWattage) {
        return ((oldWattage - newWattage) * hours * 365) / 1000;
      }

      return 0;
    },

    // Carbon offset from energy savings
    carbon_offset_lbs: () => {
      const energySavings = calculations.energy_savings_kwh();
      return energySavings * CARBON_FACTORS.electricity_per_kwh;
    },

    // Water savings
    water_savings_gallons: () => {
      const oldGpm = parseFloat(data.old_gpm) || 0;
      const newGpm = parseFloat(data.new_gpm) || 0;
      const dailyUses = parseFloat(data.daily_uses) || 10;
      if (oldGpm && newGpm) {
        return (oldGpm - newGpm) * dailyUses * 365;
      }
      return 0;
    },

    // Green product percentage
    green_product_percentage: () => {
      const green = parseFloat(data.green_products_count) || 0;
      const total = parseFloat(data.total_products_count) || 0;
      if (total === 0) return 0;
      return (green / total) * 100;
    },

    // Native plant percentage
    native_plant_percentage: () => {
      const native = parseFloat(data.native_plants_count) || 0;
      const total = parseFloat(data.total_plants_count) || 0;
      if (total === 0) return 0;
      return (native / total) * 100;
    }
  };

  // Calculate all derived values
  const derived = {};
  for (const [key, calc] of Object.entries(calculations)) {
    try {
      const value = calc();
      if (!isNaN(value) && isFinite(value)) {
        derived[key] = Math.round(value * 100) / 100; // Round to 2 decimal places
      }
    } catch (e) {
      // Skip failed calculations
    }
  }

  return derived;
}

/**
 * Validate form data against field rules
 */
function validateFormData(data, fields) {
  const errors = [];

  for (const field of fields) {
    const value = data[field.name];

    // Check required
    if (field.required && (value === undefined || value === null || value === '')) {
      errors.push({
        field: field.name,
        message: `${field.label} is required`
      });
      continue;
    }

    // Skip validation if not required and empty
    if (value === undefined || value === null || value === '') continue;

    const rules = field.validation || {};

    // Number validation
    if (field.type === 'number') {
      const numValue = parseFloat(value);
      if (isNaN(numValue)) {
        errors.push({
          field: field.name,
          message: `${field.label} must be a number`
        });
        continue;
      }
      if (rules.min !== undefined && numValue < rules.min) {
        errors.push({
          field: field.name,
          message: `${field.label} must be at least ${rules.min}`
        });
      }
      if (rules.max !== undefined && numValue > rules.max) {
        errors.push({
          field: field.name,
          message: `${field.label} must be at most ${rules.max}`
        });
      }
    }

    // Pattern validation
    if (rules.pattern && typeof value === 'string') {
      const regex = new RegExp(rules.pattern);
      if (!regex.test(value)) {
        errors.push({
          field: field.name,
          message: `${field.label} format is invalid`
        });
      }
    }

    // Select validation
    if (field.type === 'select' && field.options && field.options.length > 0) {
      if (!field.options.includes(value)) {
        errors.push({
          field: field.name,
          message: `${field.label} must be one of: ${field.options.join(', ')}`
        });
      }
    }
  }

  return {
    isValid: errors.length === 0,
    errors
  };
}

/**
 * Process and enrich form submission
 */
function processFormSubmission(data, verticalSlug) {
  // Calculate derived fields
  const derived = calculateDerivedFields(data, verticalSlug);

  // Merge with original data
  return {
    ...data,
    ...derived,
    _processed_at: new Date().toISOString(),
    _vertical: verticalSlug
  };
}

/**
 * Get field groups for organizing form UI
 */
function getFieldGroups(verticalSlug) {
  const groups = {
    junk_removal: ['weight', 'documentation', 'carbon', 'metrics'],
    hvac: ['refrigerant', 'certification', 'efficiency', 'weight', 'documentation', 'metrics'],
    roofing: ['measurements', 'materials', 'weight', 'documentation', 'certification', 'metrics'],
    cleaning: ['measurements', 'service', 'products', 'resources', 'compliance', 'documentation', 'metrics'],
    landscaping: ['measurements', 'service', 'resources', 'compliance', 'plants', 'waste', 'metrics'],
    plumbing: ['service', 'fixture', 'efficiency', 'certification', 'recycling', 'documentation', 'metrics'],
    electrical: ['service', 'efficiency', 'certification', 'solar', 'recycling', 'documentation', 'metrics'],
    demolition: ['project', 'weight', 'materials', 'compliance', 'documentation', 'metrics']
  };

  return groups[verticalSlug] || ['general'];
}

module.exports = {
  getFormFields,
  getFormFieldsBySlug,
  getDefaultFormFieldsBySlug,
  calculateDerivedFields,
  validateFormData,
  processFormSubmission,
  getFieldGroups
};
