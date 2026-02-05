/**
 * Tax Credit Matcher Service
 * Identifies and calculates applicable tax credits and incentives
 * for ESG-related equipment and services
 */

const { createClient } = require('@supabase/supabase-js');

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

// Federal Tax Credits Database (2024-2026)
const FEDERAL_TAX_CREDITS = {
  // Section 45W - Commercial Clean Vehicle Credit
  '45W': {
    name: 'Commercial Clean Vehicle Credit',
    section: 'IRC Section 45W',
    description: 'Credit for purchase of qualified commercial clean vehicles',
    effective_dates: { start: '2023-01-01', end: '2032-12-31' },
    vehicle_types: ['electric', 'plug_in_hybrid', 'fuel_cell'],
    credit_calculation: (vehicle) => {
      // Credit = lesser of 15% of vehicle cost OR incremental cost over comparable ICE vehicle
      // Max: $7,500 for vehicles < 14,000 lbs GVWR, $40,000 for heavier
      const maxCredit = vehicle.gvwr_lbs < 14000 ? 7500 : 40000;
      const calculatedCredit = Math.min(vehicle.purchase_price * 0.15, vehicle.incremental_cost || maxCredit);
      return Math.min(calculatedCredit, maxCredit);
    },
    requirements: [
      'Vehicle must be acquired for use in trade or business',
      'Must meet EPA emission standards',
      'Battery capacity minimum 7 kWh (or 4 kWh for vehicles < 14,000 lbs)',
      'Not for personal use',
      'Not acquired for resale'
    ],
    documentation_needed: [
      'Purchase invoice/agreement',
      'Vehicle VIN',
      'Battery capacity certification',
      'Business use attestation'
    ]
  },

  // Section 48C - Advanced Energy Project Credit
  '48C': {
    name: 'Advanced Energy Project Credit',
    section: 'IRC Section 48C',
    description: 'Credit for investment in clean energy manufacturing and recycling projects',
    effective_dates: { start: '2023-01-01', end: '2032-12-31' },
    credit_rate: 0.30, // 30% investment credit
    credit_rate_base: 0.06, // 6% without prevailing wage
    qualifying_projects: [
      'Clean energy manufacturing equipment',
      'Energy storage systems',
      'Grid modernization equipment',
      'Recycling equipment for battery materials',
      'Equipment for reducing GHG emissions'
    ],
    requirements: [
      'Must receive DOE allocation',
      'Prevailing wage requirements for 30% rate',
      'Apprenticeship requirements',
      'Located in energy community (bonus)'
    ]
  },

  // Section 179D - Energy Efficient Commercial Buildings Deduction
  '179D': {
    name: 'Energy Efficient Commercial Buildings Deduction',
    section: 'IRC Section 179D',
    description: 'Deduction for energy efficient improvements to commercial buildings',
    effective_dates: { start: '2006-01-01', end: '2032-12-31' },
    max_deduction_per_sqft: 5.00, // Up to $5/sq ft
    min_deduction_per_sqft: 0.50,
    qualifying_systems: ['HVAC', 'lighting', 'building_envelope'],
    efficiency_requirements: {
      minimum_improvement: 25, // 25% energy reduction
      bonus_threshold: 50 // 50% for max deduction
    },
    credit_calculation: (building) => {
      const baseDeduction = building.sqft * 0.50;
      const maxDeduction = building.sqft * 5.00;

      if (building.efficiency_improvement >= 50) {
        return maxDeduction;
      } else if (building.efficiency_improvement >= 25) {
        const incrementalRate = (building.efficiency_improvement - 25) / 25 * 4.50;
        return building.sqft * (0.50 + incrementalRate);
      }
      return 0;
    }
  },

  // Section 25C - Energy Efficient Home Improvement Credit (for installers to promote)
  '25C': {
    name: 'Energy Efficient Home Improvement Credit',
    section: 'IRC Section 25C',
    description: 'Residential credit for energy efficient equipment (customer benefit)',
    effective_dates: { start: '2023-01-01', end: '2032-12-31' },
    annual_limit: 3200,
    qualifying_improvements: {
      heat_pumps: { credit_rate: 0.30, max_credit: 2000 },
      heat_pump_water_heaters: { credit_rate: 0.30, max_credit: 2000 },
      biomass_stoves: { credit_rate: 0.30, max_credit: 2000 },
      insulation: { credit_rate: 0.30, max_credit: 1200 },
      windows: { credit_rate: 0.30, max_credit: 600 },
      doors: { credit_rate: 0.30, max_credit: 500 },
      electrical_panel: { credit_rate: 0.30, max_credit: 600 },
      home_energy_audits: { credit_rate: 0.30, max_credit: 150 }
    },
    energy_star_required: true
  },

  // Section 30D - Clean Vehicle Credit (for fleet vehicles)
  '30D': {
    name: 'New Clean Vehicle Credit',
    section: 'IRC Section 30D',
    description: 'Credit for new qualified plug-in electric vehicles',
    effective_dates: { start: '2023-01-01', end: '2032-12-31' },
    max_credit: 7500,
    credit_components: {
      critical_minerals: 3750, // Battery components sourced domestically
      battery_components: 3750 // Battery assembled in North America
    },
    price_caps: {
      van: 80000,
      suv: 80000,
      pickup: 80000,
      other: 55000
    }
  }
};

// State incentive programs (sample - would need full database)
const STATE_INCENTIVES = {
  CA: {
    'HVIP': {
      name: 'Hybrid and Zero-Emission Truck and Bus Voucher Incentive Project',
      max_voucher: 120000,
      vehicle_types: ['truck', 'bus', 'van'],
      fuel_types: ['electric', 'fuel_cell']
    },
    'SGIP': {
      name: 'Self-Generation Incentive Program',
      description: 'Rebates for energy storage systems',
      rate_per_kwh: 150 // Varies by technology and sector
    }
  },
  NY: {
    'NYSERDA_EV': {
      name: 'NYSERDA EV Make-Ready Program',
      description: 'Incentives for EV charging infrastructure',
      max_incentive: 100000
    }
  },
  TX: {
    'TERP': {
      name: 'Texas Emissions Reduction Plan',
      description: 'Grants for replacing older diesel equipment',
      max_grant: 400000
    }
  }
};

/**
 * Analyze company activities and identify applicable credits
 */
async function analyzeCompanyForCredits(companyId, taxYear) {
  const results = {
    company_id: companyId,
    tax_year: taxYear,
    analysis_date: new Date().toISOString(),
    federal_credits: [],
    state_incentives: [],
    total_potential_value: 0,
    documentation_status: 'incomplete'
  };

  // Get company data
  const { data: company } = await supabase
    .from('companies')
    .select('*, vehicles(*), jobs(*)')
    .eq('id', companyId)
    .single();

  if (!company) {
    return { error: 'Company not found' };
  }

  // Check for clean vehicles (45W)
  const cleanVehicles = (company.vehicles || []).filter(
    v => ['electric', 'plug_in_hybrid', 'fuel_cell'].includes(v.fuel_type)
  );

  if (cleanVehicles.length > 0) {
    let totalVehicleCredits = 0;
    const vehicleCredits = cleanVehicles.map(v => {
      const credit = FEDERAL_TAX_CREDITS['45W'].credit_calculation({
        purchase_price: v.purchase_price || 50000,
        gvwr_lbs: v.gvwr_lbs || 10000,
        incremental_cost: v.incremental_cost
      });
      totalVehicleCredits += credit;
      return {
        vehicle: `${v.year} ${v.make} ${v.model}`,
        vin: v.vin,
        estimated_credit: credit
      };
    });

    results.federal_credits.push({
      credit_type: '45W',
      credit_info: FEDERAL_TAX_CREDITS['45W'],
      qualifying_items: vehicleCredits,
      total_estimated_credit: totalVehicleCredits,
      documentation_needed: FEDERAL_TAX_CREDITS['45W'].documentation_needed,
      next_steps: [
        'Verify vehicle battery capacity meets requirements',
        'Confirm vehicle is used exclusively for business',
        'Gather purchase documentation',
        'File Form 8936 with tax return'
      ]
    });

    results.total_potential_value += totalVehicleCredits;
  }

  // Analyze jobs for energy efficiency improvements (179D / 25C promotion)
  const { data: jobs } = await supabase
    .from('jobs')
    .select('*')
    .eq('company_id', companyId)
    .gte('created_at', `${taxYear}-01-01`)
    .lte('created_at', `${taxYear}-12-31`);

  // Count ENERGY STAR equipment installations
  const energyStarInstalls = (jobs || []).filter(j =>
    j.job_data?.new_equipment?.energy_star ||
    j.job_data?.energy_star === true
  );

  if (energyStarInstalls.length > 0) {
    // These are customer credits - company can use for marketing
    results.customer_credit_opportunities = {
      credit_type: '25C',
      description: 'Your customers may qualify for tax credits on these installations',
      qualifying_jobs: energyStarInstalls.length,
      marketing_value: 'Promote customer savings to win more business',
      customer_benefit_estimate: energyStarInstalls.length * 1500, // Avg credit
      action_items: [
        'Provide customers with ENERGY STAR certification documentation',
        'Include tax credit information in invoices',
        'Create marketing materials highlighting customer savings'
      ]
    };
  }

  // Check for commercial building work (179D)
  const commercialJobs = (jobs || []).filter(j =>
    j.job_data?.property_type === 'Commercial' ||
    j.job_data?.building_type === 'commercial'
  );

  if (commercialJobs.length > 0) {
    results.federal_credits.push({
      credit_type: '179D',
      credit_info: FEDERAL_TAX_CREDITS['179D'],
      potential_projects: commercialJobs.length,
      note: 'Energy modeling required to determine exact deduction',
      estimated_value_range: {
        low: commercialJobs.length * 5000,
        high: commercialJobs.length * 25000
      },
      next_steps: [
        'Identify commercial projects with 25%+ energy improvement',
        'Engage qualified energy modeler for certification',
        'Obtain building owner allocation letter',
        'Document prevailing wage compliance if applicable'
      ]
    });

    results.total_potential_value += commercialJobs.length * 10000; // Conservative estimate
  }

  // State incentives check (based on company state)
  const companyState = company.state || extractState(company.address);
  if (companyState && STATE_INCENTIVES[companyState]) {
    const statePrograms = STATE_INCENTIVES[companyState];

    for (const [programId, program] of Object.entries(statePrograms)) {
      results.state_incentives.push({
        state: companyState,
        program_id: programId,
        program_name: program.name,
        description: program.description,
        max_incentive: program.max_voucher || program.max_incentive || program.max_grant,
        eligibility: 'Review required'
      });
    }
  }

  // Generate recommendations
  results.recommendations = generateRecommendations(results);

  return results;
}

/**
 * Calculate specific credit for a transaction
 */
function calculateCredit(creditType, transactionData) {
  const creditConfig = FEDERAL_TAX_CREDITS[creditType];

  if (!creditConfig) {
    return { error: 'Unknown credit type' };
  }

  let calculatedCredit = 0;
  let documentation = [];

  switch (creditType) {
    case '45W':
      calculatedCredit = creditConfig.credit_calculation(transactionData);
      documentation = creditConfig.documentation_needed;
      break;

    case '179D':
      calculatedCredit = creditConfig.credit_calculation(transactionData);
      documentation = [
        'Energy modeling study',
        'Qualified certification',
        'Building owner allocation letter'
      ];
      break;

    case '25C':
      const improvement = creditConfig.qualifying_improvements[transactionData.improvement_type];
      if (improvement) {
        calculatedCredit = Math.min(
          transactionData.cost * improvement.credit_rate,
          improvement.max_credit
        );
      }
      documentation = [
        'Purchase receipt',
        'ENERGY STAR certification',
        'Installation documentation'
      ];
      break;

    case '30D':
      // Check price cap
      const priceCap = creditConfig.price_caps[transactionData.vehicle_type] ||
        creditConfig.price_caps.other;

      if (transactionData.purchase_price <= priceCap) {
        calculatedCredit = creditConfig.max_credit;
        // Reduce if missing domestic content requirements
        if (!transactionData.critical_minerals_domestic) {
          calculatedCredit -= creditConfig.credit_components.critical_minerals;
        }
        if (!transactionData.battery_north_america) {
          calculatedCredit -= creditConfig.credit_components.battery_components;
        }
      }
      break;
  }

  return {
    credit_type: creditType,
    credit_name: creditConfig.name,
    calculated_credit: Math.round(calculatedCredit * 100) / 100,
    documentation_required: documentation,
    filing_requirements: {
      form: creditType === '45W' || creditType === '30D' ? 'Form 8936' :
        creditType === '179D' ? 'Form 7205' : 'Form 5695',
      deadline: `April 15, ${new Date().getFullYear() + 1} (or extension)`
    }
  };
}

/**
 * Generate prioritized recommendations
 */
function generateRecommendations(analysisResults) {
  const recommendations = [];

  // Sort credits by value
  const allCredits = [
    ...analysisResults.federal_credits,
    ...(analysisResults.state_incentives || [])
  ].sort((a, b) =>
    (b.total_estimated_credit || b.max_incentive || 0) -
    (a.total_estimated_credit || a.max_incentive || 0)
  );

  if (allCredits.length === 0) {
    recommendations.push({
      priority: 'medium',
      action: 'Consider Clean Vehicle Purchase',
      description: 'Electric or plug-in hybrid vehicles qualify for up to $40,000 in tax credits per vehicle',
      potential_value: 40000,
      timeline: 'Before year-end for current tax year benefit'
    });
  } else {
    for (const credit of allCredits.slice(0, 3)) {
      recommendations.push({
        priority: 'high',
        action: `Claim ${credit.credit_type || credit.program_id} Credit`,
        description: credit.credit_info?.description || credit.description,
        potential_value: credit.total_estimated_credit || credit.max_incentive,
        next_steps: credit.next_steps || ['Gather documentation', 'Consult tax professional']
      });
    }
  }

  // Always recommend documentation
  recommendations.push({
    priority: 'medium',
    action: 'Maintain ESG Documentation',
    description: 'Proper documentation of energy-efficient installations supports future tax credit claims',
    items: [
      'Keep ENERGY STAR certifications for all equipment',
      'Document vehicle usage logs',
      'Retain all installation invoices and permits'
    ]
  });

  return recommendations;
}

/**
 * Generate tax credit report for CPA
 */
async function generateTaxCreditReport(companyId, taxYear) {
  const analysis = await analyzeCompanyForCredits(companyId, taxYear);

  const report = {
    report_type: 'Tax Credit Analysis',
    prepared_for: companyId,
    tax_year: taxYear,
    generated_date: new Date().toISOString(),

    executive_summary: {
      total_potential_credits: analysis.total_potential_value,
      federal_credits_identified: analysis.federal_credits.length,
      state_incentives_identified: analysis.state_incentives.length,
      recommended_actions: analysis.recommendations.length
    },

    federal_credits: analysis.federal_credits.map(credit => ({
      ...credit,
      irs_reference: credit.credit_info?.section,
      form_required: credit.credit_type === '45W' ? 'Form 8936' : 'See instructions',
      substantiation_requirements: credit.documentation_needed
    })),

    state_incentives: analysis.state_incentives,

    customer_opportunities: analysis.customer_credit_opportunities,

    recommendations: analysis.recommendations,

    disclaimer: `This report is for informational purposes only and does not constitute tax advice.
Consult a qualified tax professional before claiming any credits. Tax laws change frequently
and individual circumstances vary. ProofGreen makes no warranty regarding the accuracy of
credit calculations or eligibility determinations.`,

    prepared_by: 'ProofGreen Tax Credit Analyzer',
    version: '1.0'
  };

  return report;
}

/**
 * Helper to extract state from address
 */
function extractState(address) {
  if (!address) return null;

  const statePatterns = /\b([A-Z]{2})\s+\d{5}/;
  const match = address.match(statePatterns);
  return match ? match[1] : null;
}

/**
 * Get available credits for a specific equipment type
 */
function getCreditsForEquipment(equipmentType) {
  const applicable = [];

  // Check 25C (residential)
  const homeCredits = FEDERAL_TAX_CREDITS['25C'].qualifying_improvements;
  for (const [type, config] of Object.entries(homeCredits)) {
    if (type.includes(equipmentType) || equipmentType.includes(type)) {
      applicable.push({
        credit: '25C',
        for: 'Residential customer',
        max_credit: config.max_credit,
        rate: `${config.credit_rate * 100}%`
      });
    }
  }

  // Check for commercial applicability
  if (['HVAC', 'lighting', 'insulation', 'windows'].includes(equipmentType)) {
    applicable.push({
      credit: '179D',
      for: 'Commercial buildings',
      max_credit: 'Up to $5/sq ft',
      requirements: '25%+ energy reduction'
    });
  }

  return applicable;
}

module.exports = {
  FEDERAL_TAX_CREDITS,
  STATE_INCENTIVES,
  analyzeCompanyForCredits,
  calculateCredit,
  generateTaxCreditReport,
  getCreditsForEquipment
};
