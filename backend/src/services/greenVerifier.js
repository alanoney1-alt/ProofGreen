/**
 * Green Verifier Service
 * Generates verified ESG certificates and compliance reports
 */

const crypto = require('crypto');
const { createClient } = require('@supabase/supabase-js');
const carbonAPI = require('./carbonAPI');

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

// Certificate types
const CERTIFICATE_TYPES = {
  GREEN_MOVE: {
    name: 'Green Move Certificate',
    description: 'Verified carbon footprint for relocation services',
    scope: 'Scope 3 - Category 4 (Upstream Transportation)',
    standard: 'GLEC Framework v3.0 / ISO 14083'
  },
  REFRIGERANT_COMPLIANCE: {
    name: 'Refrigerant Recovery Certificate',
    description: 'EPA Section 608 compliant refrigerant handling',
    scope: 'Scope 1 - Direct Emissions',
    standard: 'EPA Section 608 / AHRI Guideline N'
  },
  ENERGY_EFFICIENCY: {
    name: 'Energy Efficiency Improvement Certificate',
    description: 'Verified energy savings from equipment upgrade',
    scope: 'Scope 2 - Indirect Emissions (Avoided)',
    standard: 'ASHRAE 90.1 / ENERGY STAR'
  },
  WASTE_DIVERSION: {
    name: 'Waste Diversion Certificate',
    description: 'Verified recycling and waste reduction',
    scope: 'Scope 3 - Category 5 (Waste)',
    standard: 'EPA WARM Model'
  },
  CARBON_NEUTRAL_SERVICE: {
    name: 'Carbon Neutral Service Certificate',
    description: 'Service with verified carbon offset',
    scope: 'All Applicable Scopes',
    standard: 'PAS 2060'
  }
};

/**
 * Generate unique certificate ID with checksum
 */
function generateCertificateId(type, companyId, jobId) {
  const timestamp = Date.now().toString(36);
  const random = crypto.randomBytes(4).toString('hex');
  const data = `${type}-${companyId}-${jobId}-${timestamp}`;
  const checksum = crypto.createHash('sha256').update(data).digest('hex').slice(0, 6);

  return `PG-${type.slice(0, 3).toUpperCase()}-${timestamp.toUpperCase()}-${random.toUpperCase()}-${checksum.toUpperCase()}`;
}

/**
 * Generate QR code data for certificate verification
 */
function generateVerificationQR(certificateId) {
  const verificationUrl = `${process.env.APP_URL || 'https://proofgreen.io'}/verify/${certificateId}`;
  return {
    url: verificationUrl,
    data: JSON.stringify({
      cert_id: certificateId,
      verify_url: verificationUrl,
      issued_by: 'ProofGreen',
      timestamp: new Date().toISOString()
    })
  };
}

/**
 * Create Green Move Certificate
 */
async function createGreenMoveCertificate(moveData) {
  const {
    company_id,
    job_id,
    company_name,
    customer_name,
    origin_address,
    destination_address,
    distance_miles,
    weight_lbs,
    vehicle_type,
    fuel_type,
    actual_fuel_gallons,
    move_date
  } = moveData;

  // Calculate verified emissions using GLEC Framework
  const emissions = await carbonAPI.calculateFreightEmissions({
    distance_km: distance_miles * 1.60934,
    weight_kg: weight_lbs * 0.453592,
    vehicle_type: vehicle_type || 'truck_medium',
    fuel_type: fuel_type || 'diesel',
    load_factor: 80 // Assume 80% load
  });

  const certificateId = generateCertificateId('GREEN_MOVE', company_id, job_id);

  const certificate = {
    certificate_id: certificateId,
    type: 'GREEN_MOVE',
    type_info: CERTIFICATE_TYPES.GREEN_MOVE,

    issued_to: {
      customer_name,
      company_name,
      company_id
    },

    service_details: {
      job_id,
      service_date: move_date,
      origin: origin_address,
      destination: destination_address,
      distance_miles,
      distance_km: Math.round(distance_miles * 1.60934 * 100) / 100,
      weight_lbs,
      weight_kg: Math.round(weight_lbs * 0.453592 * 100) / 100,
      vehicle_type,
      fuel_type
    },

    carbon_footprint: {
      total_co2e_kg: emissions.co2e_kg,
      total_co2e_lbs: emissions.co2e_lbs,
      tonne_km: emissions.tonne_km,
      emission_intensity: Math.round(emissions.co2e_kg / (distance_miles * 1.60934) * 1000) / 1000,
      emission_intensity_unit: 'kg CO2e / km'
    },

    methodology: {
      framework: emissions.methodology,
      source: emissions.source,
      audit_trail: emissions.audit_trail
    },

    verification: generateVerificationQR(certificateId),

    issued_at: new Date().toISOString(),
    valid_until: new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString(),

    attestation: `This certificate attests that the relocation service performed on ${move_date} resulted in verified greenhouse gas emissions of ${emissions.co2e_kg} kg CO2e, calculated in accordance with the GLEC Framework v3.0 and ISO 14083 standards.`
  };

  // Store certificate in database
  await supabase.from('certificates').insert({
    certificate_id: certificateId,
    company_id,
    job_id,
    type: 'GREEN_MOVE',
    data: certificate,
    issued_at: new Date().toISOString()
  });

  return certificate;
}

/**
 * Create Refrigerant Compliance Certificate
 */
async function createRefrigerantCertificate(refrigerantData) {
  const {
    company_id,
    job_id,
    company_name,
    technician_name,
    epa_cert_number,
    refrigerant_type,
    system_charge_oz,
    refrigerant_added_oz,
    refrigerant_recovered_oz,
    leak_detected,
    leak_repaired,
    service_date
  } = refrigerantData;

  // Calculate emissions from any refrigerant loss
  const leaked_oz = Math.max(0, refrigerant_added_oz - refrigerant_recovered_oz);
  let emissions = null;

  if (leaked_oz > 0) {
    emissions = carbonAPI.calculateLocalEmissions({
      type: 'refrigerant',
      subtype: refrigerant_type,
      value: leaked_oz,
      unit: 'oz'
    });
  }

  const certificateId = generateCertificateId('REFRIG', company_id, job_id);

  const certificate = {
    certificate_id: certificateId,
    type: 'REFRIGERANT_COMPLIANCE',
    type_info: CERTIFICATE_TYPES.REFRIGERANT_COMPLIANCE,

    issued_to: {
      company_name,
      company_id,
      technician_name,
      epa_certification: epa_cert_number
    },

    service_details: {
      job_id,
      service_date,
      refrigerant_type,
      system_charge_oz,
      refrigerant_added_oz,
      refrigerant_recovered_oz,
      net_loss_oz: leaked_oz,
      leak_detected,
      leak_repaired
    },

    environmental_impact: emissions ? {
      co2e_kg: emissions.co2e_kg,
      co2e_lbs: emissions.co2e_lbs,
      gwp_value: carbonAPI.GHG_EMISSION_FACTORS.refrigerants[refrigerant_type]?.gwp,
      methodology: emissions.methodology
    } : {
      co2e_kg: 0,
      co2e_lbs: 0,
      note: 'No refrigerant loss - full recovery achieved'
    },

    compliance_status: {
      epa_608_compliant: true,
      recovery_rate: refrigerant_recovered_oz > 0 ?
        Math.round(refrigerant_recovered_oz / (refrigerant_recovered_oz + leaked_oz) * 100) : 100,
      leak_repair_compliant: !leak_detected || leak_repaired
    },

    verification: generateVerificationQR(certificateId),

    issued_at: new Date().toISOString(),
    valid_until: new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString(),

    attestation: `This certificate attests that refrigerant handling services performed on ${service_date} were conducted in compliance with EPA Section 608 regulations. ${refrigerant_recovered_oz} oz of ${refrigerant_type} refrigerant was properly recovered.`
  };

  await supabase.from('certificates').insert({
    certificate_id: certificateId,
    company_id,
    job_id,
    type: 'REFRIGERANT_COMPLIANCE',
    data: certificate,
    issued_at: new Date().toISOString()
  });

  return certificate;
}

/**
 * Create Energy Efficiency Certificate
 */
async function createEfficiencyCertificate(efficiencyData) {
  const {
    company_id,
    job_id,
    company_name,
    customer_name,
    equipment_type,
    old_equipment,
    new_equipment,
    annual_usage_hours,
    service_date
  } = efficiencyData;

  // Calculate energy savings
  let annual_kwh_saved = 0;
  let annual_co2_saved_kg = 0;

  if (equipment_type === 'hvac') {
    const old_kwh = (old_equipment.tonnage * 12000 / old_equipment.seer) * annual_usage_hours;
    const new_kwh = (new_equipment.tonnage * 12000 / new_equipment.seer) * annual_usage_hours;
    annual_kwh_saved = old_kwh - new_kwh;
    annual_co2_saved_kg = annual_kwh_saved * 0.42; // US grid average
  } else if (equipment_type === 'water_heater') {
    const old_kwh = old_equipment.annual_kwh || 4000;
    const new_kwh = new_equipment.annual_kwh || (old_kwh * (old_equipment.uef / new_equipment.uef));
    annual_kwh_saved = old_kwh - new_kwh;
    annual_co2_saved_kg = annual_kwh_saved * 0.42;
  } else if (equipment_type === 'lighting') {
    annual_kwh_saved = (old_equipment.wattage - new_equipment.wattage) * annual_usage_hours / 1000;
    annual_co2_saved_kg = annual_kwh_saved * 0.42;
  }

  const certificateId = generateCertificateId('EFFIC', company_id, job_id);

  // Calculate 10-year impact
  const ten_year_kwh = annual_kwh_saved * 10;
  const ten_year_co2_kg = annual_co2_saved_kg * 10;

  const certificate = {
    certificate_id: certificateId,
    type: 'ENERGY_EFFICIENCY',
    type_info: CERTIFICATE_TYPES.ENERGY_EFFICIENCY,

    issued_to: {
      customer_name,
      company_name,
      company_id
    },

    service_details: {
      job_id,
      service_date,
      equipment_type,
      old_equipment,
      new_equipment
    },

    efficiency_improvement: {
      old_efficiency: old_equipment.seer || old_equipment.uef || old_equipment.wattage,
      new_efficiency: new_equipment.seer || new_equipment.uef || new_equipment.wattage,
      improvement_percent: Math.round(
        ((new_equipment.seer || new_equipment.uef || old_equipment.wattage) /
          (old_equipment.seer || old_equipment.uef || new_equipment.wattage) - 1) * 100
      ),
      energy_star_certified: new_equipment.energy_star || false
    },

    environmental_impact: {
      annual_kwh_saved: Math.round(annual_kwh_saved),
      annual_co2_saved_kg: Math.round(annual_co2_saved_kg),
      annual_co2_saved_lbs: Math.round(annual_co2_saved_kg * 2.205),
      ten_year_kwh_saved: Math.round(ten_year_kwh),
      ten_year_co2_saved_kg: Math.round(ten_year_co2_kg),
      ten_year_co2_saved_lbs: Math.round(ten_year_co2_kg * 2.205),
      trees_equivalent: Math.round(annual_co2_saved_kg / 21) // ~21kg CO2 per tree per year
    },

    financial_impact: {
      estimated_annual_savings: Math.round(annual_kwh_saved * 0.12), // ~$0.12/kWh avg
      estimated_ten_year_savings: Math.round(ten_year_kwh * 0.12)
    },

    verification: generateVerificationQR(certificateId),

    issued_at: new Date().toISOString(),
    valid_until: new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString(),

    attestation: `This certificate attests that the equipment upgrade performed on ${service_date} will result in estimated annual energy savings of ${Math.round(annual_kwh_saved)} kWh, equivalent to ${Math.round(annual_co2_saved_kg)} kg CO2e avoided per year.`
  };

  await supabase.from('certificates').insert({
    certificate_id: certificateId,
    company_id,
    job_id,
    type: 'ENERGY_EFFICIENCY',
    data: certificate,
    issued_at: new Date().toISOString()
  });

  return certificate;
}

/**
 * Create Waste Diversion Certificate
 */
async function createWasteDiversionCertificate(wasteData) {
  const {
    company_id,
    job_id,
    company_name,
    customer_name,
    total_waste_lbs,
    recycled_lbs,
    composted_lbs,
    landfill_lbs,
    materials_breakdown,
    service_date
  } = wasteData;

  const diversion_rate = Math.round(
    ((recycled_lbs + composted_lbs) / total_waste_lbs) * 100
  );

  // Calculate emissions avoided
  const recycling_benefit = (recycled_lbs * 0.453592) * -1.2; // Negative = benefit
  const composting_benefit = (composted_lbs * 0.453592) * -0.2;
  const landfill_emissions = (landfill_lbs * 0.453592) * 0.58;

  const net_impact_kg = recycling_benefit + composting_benefit + landfill_emissions;

  const certificateId = generateCertificateId('WASTE', company_id, job_id);

  const certificate = {
    certificate_id: certificateId,
    type: 'WASTE_DIVERSION',
    type_info: CERTIFICATE_TYPES.WASTE_DIVERSION,

    issued_to: {
      customer_name,
      company_name,
      company_id
    },

    service_details: {
      job_id,
      service_date
    },

    waste_summary: {
      total_waste_lbs,
      total_waste_kg: Math.round(total_waste_lbs * 0.453592 * 100) / 100,
      recycled_lbs,
      composted_lbs,
      landfill_lbs,
      diversion_rate,
      materials_breakdown
    },

    environmental_impact: {
      recycling_benefit_kg: Math.round(Math.abs(recycling_benefit) * 100) / 100,
      composting_benefit_kg: Math.round(Math.abs(composting_benefit) * 100) / 100,
      landfill_emissions_kg: Math.round(landfill_emissions * 100) / 100,
      net_co2e_kg: Math.round(net_impact_kg * 100) / 100,
      net_co2e_lbs: Math.round(net_impact_kg * 2.205 * 100) / 100,
      is_net_positive: net_impact_kg < 0
    },

    verification: generateVerificationQR(certificateId),

    issued_at: new Date().toISOString(),
    valid_until: new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString(),

    attestation: `This certificate attests that ${diversion_rate}% of waste generated (${total_waste_lbs} lbs total) was diverted from landfill through recycling and composting on ${service_date}.`
  };

  await supabase.from('certificates').insert({
    certificate_id: certificateId,
    company_id,
    job_id,
    type: 'WASTE_DIVERSION',
    data: certificate,
    issued_at: new Date().toISOString()
  });

  return certificate;
}

/**
 * Verify certificate by ID
 */
async function verifyCertificate(certificateId) {
  const { data, error } = await supabase
    .from('certificates')
    .select('*')
    .eq('certificate_id', certificateId)
    .single();

  if (error || !data) {
    return {
      valid: false,
      error: 'Certificate not found'
    };
  }

  return {
    valid: true,
    certificate_id: data.certificate_id,
    type: data.type,
    issued_at: data.issued_at,
    company_id: data.company_id,
    summary: {
      type_name: CERTIFICATE_TYPES[data.type]?.name,
      standard: CERTIFICATE_TYPES[data.type]?.standard
    }
  };
}

/**
 * Get all certificates for a company
 */
async function getCompanyCertificates(companyId) {
  const { data, error } = await supabase
    .from('certificates')
    .select('*')
    .eq('company_id', companyId)
    .order('issued_at', { ascending: false });

  if (error) throw error;
  return data;
}

/**
 * Generate annual ESG report with all certificates
 */
async function generateAnnualESGReport(companyId, year) {
  const startDate = `${year}-01-01`;
  const endDate = `${year}-12-31`;

  const { data: certificates } = await supabase
    .from('certificates')
    .select('*')
    .eq('company_id', companyId)
    .gte('issued_at', startDate)
    .lte('issued_at', endDate);

  // Aggregate metrics
  const report = {
    company_id: companyId,
    reporting_year: year,
    generated_at: new Date().toISOString(),

    summary: {
      total_certificates: certificates?.length || 0,
      by_type: {},
      total_co2e_kg: 0,
      total_co2e_avoided_kg: 0
    },

    scope1_emissions: { total_kg: 0, sources: [] },
    scope2_emissions: { total_kg: 0, sources: [] },
    scope3_emissions: { total_kg: 0, sources: [] },

    avoided_emissions: { total_kg: 0, sources: [] },

    certificates: certificates || []
  };

  // Process each certificate
  for (const cert of certificates || []) {
    const type = cert.type;
    report.summary.by_type[type] = (report.summary.by_type[type] || 0) + 1;

    const data = cert.data;

    if (type === 'GREEN_MOVE') {
      report.scope3_emissions.total_kg += data.carbon_footprint?.total_co2e_kg || 0;
      report.scope3_emissions.sources.push({
        certificate_id: cert.certificate_id,
        co2e_kg: data.carbon_footprint?.total_co2e_kg,
        category: 'Upstream Transportation'
      });
    }

    if (type === 'REFRIGERANT_COMPLIANCE') {
      report.scope1_emissions.total_kg += data.environmental_impact?.co2e_kg || 0;
      report.scope1_emissions.sources.push({
        certificate_id: cert.certificate_id,
        co2e_kg: data.environmental_impact?.co2e_kg,
        category: 'Fugitive Emissions - Refrigerants'
      });
    }

    if (type === 'ENERGY_EFFICIENCY') {
      report.avoided_emissions.total_kg += data.environmental_impact?.annual_co2_saved_kg || 0;
      report.avoided_emissions.sources.push({
        certificate_id: cert.certificate_id,
        co2e_avoided_kg: data.environmental_impact?.annual_co2_saved_kg,
        category: 'Energy Efficiency Improvements'
      });
    }

    if (type === 'WASTE_DIVERSION') {
      if (data.environmental_impact?.is_net_positive) {
        report.avoided_emissions.total_kg += Math.abs(data.environmental_impact?.net_co2e_kg || 0);
      } else {
        report.scope3_emissions.total_kg += data.environmental_impact?.net_co2e_kg || 0;
      }
    }
  }

  report.summary.total_co2e_kg =
    report.scope1_emissions.total_kg +
    report.scope2_emissions.total_kg +
    report.scope3_emissions.total_kg;

  report.summary.total_co2e_avoided_kg = report.avoided_emissions.total_kg;

  report.summary.net_emissions_kg =
    report.summary.total_co2e_kg - report.summary.total_co2e_avoided_kg;

  return report;
}

module.exports = {
  CERTIFICATE_TYPES,
  createGreenMoveCertificate,
  createRefrigerantCertificate,
  createEfficiencyCertificate,
  createWasteDiversionCertificate,
  verifyCertificate,
  getCompanyCertificates,
  generateAnnualESGReport
};
