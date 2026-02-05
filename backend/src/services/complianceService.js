const { supabase } = require('../utils/supabase');
const { logger } = require('../utils/logger');

/**
 * ESG Score Calculation Constants
 */
const SCORING_CONFIG = {
  environmental: {
    weight: 0.4,
    components: {
      diversion_rate: { max_points: 40, threshold: 75 }, // 75%+ = full points
      carbon_tracking: { max_points: 30 },
      documentation: { max_points: 30 }
    }
  },
  social: {
    weight: 0.3,
    components: {
      safety_record: { max_points: 50 },
      training: { max_points: 30 },
      community_impact: { max_points: 20 }
    }
  },
  governance: {
    weight: 0.3,
    components: {
      insurance: { max_points: 40 },
      licenses: { max_points: 40 },
      certifications: { max_points: 20 }
    }
  }
};

// Carbon emission factors
const CARBON_FACTORS = {
  gasoline_per_gallon: 19.6, // lbs CO2 per gallon
  diesel_per_gallon: 22.4,
  electricity_per_kwh: 0.855, // lbs CO2 per kWh (US average)
  natural_gas_per_therm: 11.7
};

/**
 * Calculate ESG scores for a specific job
 */
async function calculateJobESGScore(jobId) {
  try {
    // Fetch job with all related data
    const { data: job, error: jobError } = await supabase
      .from('jobs')
      .select(`
        *,
        verticals (*),
        job_items (*),
        vertical_esg_data (*),
        esg_documents (*)
      `)
      .eq('id', jobId)
      .single();

    if (jobError || !job) {
      throw new Error('Job not found');
    }

    const esgData = job.vertical_esg_data?.[0]?.data || {};
    const documents = job.esg_documents || [];

    // Calculate Environmental Score
    let environmentalScore = 0;

    // Diversion rate component (40 points max)
    const totalWeight = job.total_weight_lbs || esgData.total_weight_lbs || 0;
    const recycledWeight = job.recycled_weight_lbs || esgData.recycled_weight_lbs || 0;
    const donatedWeight = job.donated_weight_lbs || esgData.donated_weight_lbs || 0;
    const diversionRate = totalWeight > 0
      ? ((recycledWeight + donatedWeight) / totalWeight) * 100
      : 0;

    // Scale diversion rate: 75%+ = 40 points, linear below
    const diversionPoints = Math.min(40, (diversionRate / 75) * 40);
    environmentalScore += diversionPoints;

    // Carbon tracking component (30 points max)
    const hasCarbonData = esgData.fuel_gallons || esgData.carbon_emissions_lbs;
    if (hasCarbonData) {
      environmentalScore += 30;
    }

    // Documentation component (30 points max)
    const requiredDocs = ['weight_ticket', 'recycling_receipt'];
    const uploadedDocTypes = documents.map(d => d.document_type);
    const docsComplete = requiredDocs.filter(d => uploadedDocTypes.includes(d)).length;
    const docPoints = (docsComplete / requiredDocs.length) * 30;
    environmentalScore += docPoints;

    // Calculate Social Score (simplified for job level)
    let socialScore = 70; // Base score

    // Donation impact adds to social score
    if (donatedWeight > 0) {
      socialScore += Math.min(30, (donatedWeight / 100) * 5);
    }

    // Calculate Governance Score (simplified for job level)
    let governanceScore = 80; // Base score, adjusted at company level

    // Calculate Overall Score
    const overallScore = Math.round(
      (environmentalScore * 0.4) +
      (socialScore * 0.3) +
      (governanceScore * 0.3)
    );

    // Get requirements for this vertical
    const { data: requirements } = await supabase
      .from('esg_requirements')
      .select('*')
      .eq('vertical_id', job.vertical_id)
      .eq('is_active', true);

    // Check which requirements are met
    const missingRequirements = checkRequirementsMet(requirements || [], esgData, documents);

    // Determine contract readiness
    const mandatoryMissing = missingRequirements.filter(r => r.is_mandatory);
    const contractReady = mandatoryMissing.length === 0;

    // Store or update vertical_esg_data
    const esgRecord = {
      job_id: jobId,
      vertical_id: job.vertical_id,
      company_id: job.company_id,
      data: {
        ...esgData,
        diversion_rate: diversionRate,
        total_weight_lbs: totalWeight,
        recycled_weight_lbs: recycledWeight,
        donated_weight_lbs: donatedWeight,
        landfill_weight_lbs: job.landfill_weight_lbs || esgData.landfill_weight_lbs || 0
      },
      environmental_score: Math.round(environmentalScore),
      social_score: Math.round(socialScore),
      governance_score: Math.round(governanceScore),
      overall_esg_score: overallScore,
      contract_ready: contractReady,
      missing_requirements: missingRequirements,
      updated_at: new Date().toISOString()
    };

    // Upsert the ESG data
    if (job.vertical_esg_data?.[0]?.id) {
      await supabase
        .from('vertical_esg_data')
        .update(esgRecord)
        .eq('id', job.vertical_esg_data[0].id);
    } else {
      await supabase
        .from('vertical_esg_data')
        .insert(esgRecord);
    }

    // Update job with ESG score
    await supabase
      .from('jobs')
      .update({
        esg_score: overallScore,
        diversion_rate: diversionRate
      })
      .eq('id', jobId);

    logger.info(`Calculated ESG score for job ${jobId}: ${overallScore}`);

    return {
      jobId,
      environmental_score: Math.round(environmentalScore),
      social_score: Math.round(socialScore),
      governance_score: Math.round(governanceScore),
      overall_esg_score: overallScore,
      diversion_rate: diversionRate,
      contract_ready: contractReady,
      missing_requirements: missingRequirements
    };
  } catch (error) {
    logger.error('Calculate job ESG score error:', error);
    throw error;
  }
}

/**
 * Check which requirements are met based on data and documents
 */
function checkRequirementsMet(requirements, esgData, documents) {
  const missing = [];
  const docTypes = documents.map(d => d.document_type);

  for (const req of requirements) {
    let isMet = false;

    switch (req.requirement_type) {
      case 'documentation':
        // Check if corresponding document is uploaded
        const docKey = req.requirement_key;
        isMet = docTypes.some(t =>
          t.toLowerCase().includes(docKey.replace('_', ' ')) ||
          t.toLowerCase().includes(docKey)
        );
        break;

      case 'calculation':
        // Check if relevant data exists
        if (req.requirement_key === 'diversion_rate') {
          isMet = esgData.total_weight_lbs > 0;
        } else if (req.requirement_key === 'carbon_tracking') {
          isMet = !!esgData.fuel_gallons || !!esgData.carbon_emissions_lbs;
        } else if (req.requirement_key === 'energy_savings' || req.requirement_key === 'energy_efficiency') {
          isMet = !!esgData.old_unit_seer && !!esgData.new_unit_seer;
        } else if (req.requirement_key === 'water_savings') {
          isMet = !!esgData.water_savings_gallons;
        } else {
          isMet = !!esgData[req.requirement_key];
        }
        break;

      case 'certification':
        // Check if certification document exists
        isMet = docTypes.some(t =>
          t.toLowerCase().includes('cert') ||
          t.toLowerCase().includes(req.requirement_key)
        );
        break;

      case 'measurement':
        // Check if measurement data exists
        isMet = !!esgData[req.requirement_key];
        break;
    }

    if (!isMet) {
      missing.push({
        id: req.id,
        name: req.requirement_name,
        key: req.requirement_key,
        type: req.requirement_type,
        is_mandatory: req.is_mandatory,
        help_text: req.help_text
      });
    }
  }

  return missing;
}

/**
 * Calculate company-wide compliance status
 */
async function calculateCompanyCompliance(companyId, periodStart = null, periodEnd = null) {
  try {
    // Default to current month
    const now = new Date();
    const start = periodStart || new Date(now.getFullYear(), now.getMonth(), 1);
    const end = periodEnd || new Date(now.getFullYear(), now.getMonth() + 1, 0);

    // Fetch all completed jobs in period
    const { data: jobs, error: jobsError } = await supabase
      .from('jobs')
      .select(`
        *,
        vertical_esg_data (*)
      `)
      .eq('company_id', companyId)
      .eq('status', 'completed')
      .gte('completed_at', start.toISOString())
      .lte('completed_at', end.toISOString());

    if (jobsError) throw jobsError;

    // Fetch company documents
    const { data: documents } = await supabase
      .from('esg_documents')
      .select('*')
      .eq('company_id', companyId);

    // Fetch company certifications
    const { data: certifications } = await supabase
      .from('certifications')
      .select('*')
      .eq('company_id', companyId)
      .eq('is_active', true);

    // Aggregate metrics from jobs
    const totals = jobs?.reduce((acc, job) => ({
      totalWeight: acc.totalWeight + (job.total_weight_lbs || 0),
      recycledWeight: acc.recycledWeight + (job.recycled_weight_lbs || 0),
      donatedWeight: acc.donatedWeight + (job.donated_weight_lbs || 0),
      landfillWeight: acc.landfillWeight + (job.landfill_weight_lbs || 0),
      carbonOffset: acc.carbonOffset + (job.carbon_offset_lbs || 0),
      esgScoreSum: acc.esgScoreSum + (job.esg_score || 0),
      jobCount: acc.jobCount + 1
    }), {
      totalWeight: 0,
      recycledWeight: 0,
      donatedWeight: 0,
      landfillWeight: 0,
      carbonOffset: 0,
      esgScoreSum: 0,
      jobCount: 0
    }) || {};

    // Calculate company-wide scores
    const diversionRate = totals.totalWeight > 0
      ? ((totals.recycledWeight + totals.donatedWeight) / totals.totalWeight) * 100
      : 0;

    // Environmental Score
    let environmentalScore = 0;
    environmentalScore += Math.min(40, (diversionRate / 75) * 40);
    environmentalScore += Math.min(30, (documents?.length || 0) * 3);
    environmentalScore += totals.carbonOffset > 0 ? 30 : 0;

    // Social Score
    let socialScore = 70;
    if (totals.donatedWeight > 0) {
      socialScore += Math.min(30, totals.donatedWeight / 1000 * 10);
    }

    // Governance Score
    let governanceScore = 0;

    // Check insurance (40 points)
    const hasInsurance = documents?.some(d =>
      d.document_type === 'insurance_cert' &&
      (!d.expires_at || new Date(d.expires_at) > new Date())
    );
    if (hasInsurance) governanceScore += 40;

    // Check licenses (40 points)
    const licenses = documents?.filter(d => d.document_type === 'license') || [];
    governanceScore += Math.min(40, licenses.length * 10);

    // Check certifications (20 points)
    const activeCerts = certifications?.filter(c =>
      !c.expiry_date || new Date(c.expiry_date) > new Date()
    ) || [];
    governanceScore += Math.min(20, activeCerts.length * 5);

    // Overall Score
    const overallScore = Math.round(
      (environmentalScore * 0.4) +
      (socialScore * 0.3) +
      (governanceScore * 0.3)
    );

    // Check document expiration
    const thirtyDaysFromNow = new Date();
    thirtyDaysFromNow.setDate(thirtyDaysFromNow.getDate() + 30);

    const docsExpiringSoon = documents?.filter(d =>
      d.expires_at && new Date(d.expires_at) <= thirtyDaysFromNow
    ).length || 0;

    // Determine contract readiness
    const insuranceCurrent = hasInsurance;
    const licensesCurrent = licenses.length > 0;
    const certificationsCurrent = activeCerts.length > 0;
    const allDocsCurrent = docsExpiringSoon === 0;

    const contractReady = insuranceCurrent && diversionRate >= 50;

    // Calculate carbon emissions from all jobs
    let totalCarbonEmissions = 0;
    for (const job of jobs || []) {
      const esgData = job.vertical_esg_data?.[0]?.data || {};
      if (esgData.fuel_gallons) {
        totalCarbonEmissions += esgData.fuel_gallons * CARBON_FACTORS.gasoline_per_gallon;
      }
    }

    // Create or update compliance status
    const statusRecord = {
      company_id: companyId,
      period_type: 'monthly',
      period_start: start.toISOString().split('T')[0],
      period_end: end.toISOString().split('T')[0],
      environmental_score: Math.round(environmentalScore),
      social_score: Math.round(socialScore),
      governance_score: Math.round(governanceScore),
      overall_esg_score: overallScore,
      total_jobs: totals.jobCount,
      diversion_rate: diversionRate,
      carbon_emissions_lbs: totalCarbonEmissions,
      carbon_offset_lbs: totals.carbonOffset,
      net_carbon_lbs: totalCarbonEmissions - totals.carbonOffset,
      docs_uploaded: documents?.length || 0,
      docs_verified: documents?.filter(d => d.verified).length || 0,
      docs_expiring_soon: docsExpiringSoon,
      all_docs_current: allDocsCurrent,
      insurance_current: insuranceCurrent,
      licenses_current: licensesCurrent,
      certifications_current: certificationsCurrent,
      contract_ready: contractReady,
      contract_ready_reason: !contractReady
        ? (!insuranceCurrent ? 'Insurance not current' : 'Diversion rate below 50%')
        : null,
      metrics_breakdown: {
        weight: totals,
        documents: {
          total: documents?.length || 0,
          verified: documents?.filter(d => d.verified).length || 0,
          byType: groupDocumentsByType(documents || [])
        },
        certifications: activeCerts.map(c => c.certification_name)
      },
      last_calculated_at: new Date().toISOString()
    };

    // Upsert compliance status
    await supabase
      .from('compliance_status')
      .upsert(statusRecord, {
        onConflict: 'company_id,period_type,period_start'
      });

    logger.info(`Updated compliance status for company ${companyId}: ESG ${overallScore}`);

    return statusRecord;
  } catch (error) {
    logger.error('Calculate company compliance error:', error);
    throw error;
  }
}

/**
 * Group documents by type
 */
function groupDocumentsByType(documents) {
  return documents.reduce((acc, doc) => {
    acc[doc.document_type] = (acc[doc.document_type] || 0) + 1;
    return acc;
  }, {});
}

/**
 * Check contract readiness against specific requirements
 */
async function checkContractReadiness(companyId, contractRequirements = {}) {
  try {
    // Get current compliance status
    const { data: status } = await supabase
      .from('compliance_status')
      .select('*')
      .eq('company_id', companyId)
      .order('period_start', { ascending: false })
      .limit(1)
      .single();

    // Get company documents
    const { data: documents } = await supabase
      .from('esg_documents')
      .select('*')
      .eq('company_id', companyId);

    // Get certifications
    const { data: certifications } = await supabase
      .from('certifications')
      .select('*')
      .eq('company_id', companyId)
      .eq('is_active', true);

    const checklist = [];
    let allPassed = true;

    // Default contract requirements if not specified
    const requirements = {
      min_diversion_rate: contractRequirements.min_diversion_rate || 75,
      min_esg_score: contractRequirements.min_esg_score || 70,
      require_insurance: contractRequirements.require_insurance !== false,
      required_certifications: contractRequirements.required_certifications || [],
      required_documents: contractRequirements.required_documents || []
    };

    // Check diversion rate
    const diversionPassed = (status?.diversion_rate || 0) >= requirements.min_diversion_rate;
    checklist.push({
      requirement: `Minimum ${requirements.min_diversion_rate}% diversion rate`,
      status: diversionPassed ? 'passed' : 'failed',
      current: `${(status?.diversion_rate || 0).toFixed(1)}%`,
      required: `${requirements.min_diversion_rate}%`
    });
    if (!diversionPassed) allPassed = false;

    // Check ESG score
    const esgPassed = (status?.overall_esg_score || 0) >= requirements.min_esg_score;
    checklist.push({
      requirement: `Minimum ESG score of ${requirements.min_esg_score}`,
      status: esgPassed ? 'passed' : 'failed',
      current: status?.overall_esg_score || 0,
      required: requirements.min_esg_score
    });
    if (!esgPassed) allPassed = false;

    // Check insurance
    if (requirements.require_insurance) {
      const insurancePassed = status?.insurance_current || false;
      checklist.push({
        requirement: 'Current insurance documentation',
        status: insurancePassed ? 'passed' : 'failed',
        current: insurancePassed ? 'On file' : 'Missing/Expired'
      });
      if (!insurancePassed) allPassed = false;
    }

    // Check required certifications
    const certNames = certifications?.map(c => c.certification_name.toLowerCase()) || [];
    for (const reqCert of requirements.required_certifications) {
      const hasCert = certNames.some(c => c.includes(reqCert.toLowerCase()));
      checklist.push({
        requirement: `${reqCert} certification`,
        status: hasCert ? 'passed' : 'failed',
        current: hasCert ? 'Certified' : 'Not found'
      });
      if (!hasCert) allPassed = false;
    }

    // Check required documents
    const docTypes = documents?.map(d => d.document_type) || [];
    for (const reqDoc of requirements.required_documents) {
      const hasDoc = docTypes.includes(reqDoc);
      checklist.push({
        requirement: `${reqDoc.replace(/_/g, ' ')} documentation`,
        status: hasDoc ? 'passed' : 'failed',
        current: hasDoc ? 'On file' : 'Missing'
      });
      if (!hasDoc) allPassed = false;
    }

    return {
      ready: allPassed,
      checklist,
      current_scores: {
        esg_score: status?.overall_esg_score || 0,
        diversion_rate: status?.diversion_rate || 0,
        environmental: status?.environmental_score || 0,
        social: status?.social_score || 0,
        governance: status?.governance_score || 0
      },
      missing: checklist.filter(c => c.status === 'failed').map(c => c.requirement)
    };
  } catch (error) {
    logger.error('Check contract readiness error:', error);
    throw error;
  }
}

/**
 * Get requirements for a vertical
 */
async function getRequirements(verticalId) {
  try {
    const { data: requirements, error } = await supabase
      .from('esg_requirements')
      .select('*')
      .eq('vertical_id', verticalId)
      .eq('is_active', true)
      .order('display_order');

    if (error) throw error;

    return requirements || [];
  } catch (error) {
    logger.error('Get requirements error:', error);
    throw error;
  }
}

/**
 * Generate compliance report data
 */
async function generateComplianceReport(companyId, periodType = 'monthly') {
  try {
    // Get company info
    const { data: company } = await supabase
      .from('companies')
      .select('*')
      .eq('id', companyId)
      .single();

    // Get latest compliance status
    const { data: status } = await supabase
      .from('compliance_status')
      .select('*')
      .eq('company_id', companyId)
      .eq('period_type', periodType)
      .order('period_start', { ascending: false })
      .limit(1)
      .single();

    // Get certifications
    const { data: certifications } = await supabase
      .from('certifications')
      .select('*')
      .eq('company_id', companyId)
      .eq('is_active', true);

    // Get recent jobs for this period
    const { data: jobs } = await supabase
      .from('jobs')
      .select('*')
      .eq('company_id', companyId)
      .eq('status', 'completed')
      .order('completed_at', { ascending: false })
      .limit(20);

    // Calculate environmental equivalents
    const carbonOffset = status?.carbon_offset_lbs || 0;
    const treesEquivalent = Math.round(carbonOffset / 48);
    const milesEquivalent = Math.round(carbonOffset / 0.89);
    const gallonsGasEquivalent = Math.round(carbonOffset / 19.6);

    return {
      company: {
        name: company.name,
        id: company.id
      },
      period: {
        type: periodType,
        start: status?.period_start,
        end: status?.period_end
      },
      scores: {
        overall: status?.overall_esg_score || 0,
        environmental: status?.environmental_score || 0,
        social: status?.social_score || 0,
        governance: status?.governance_score || 0
      },
      metrics: {
        total_jobs: status?.total_jobs || 0,
        diversion_rate: status?.diversion_rate || 0,
        carbon_offset_lbs: carbonOffset,
        carbon_emissions_lbs: status?.carbon_emissions_lbs || 0,
        net_carbon_lbs: status?.net_carbon_lbs || 0
      },
      environmental_impact: {
        trees_equivalent: treesEquivalent,
        miles_equivalent: milesEquivalent,
        gallons_gas_equivalent: gallonsGasEquivalent
      },
      compliance: {
        contract_ready: status?.contract_ready || false,
        insurance_current: status?.insurance_current || false,
        licenses_current: status?.licenses_current || false,
        certifications_current: status?.certifications_current || false,
        docs_expiring_soon: status?.docs_expiring_soon || 0
      },
      certifications: certifications?.map(c => ({
        name: c.certification_name,
        issuer: c.issuing_organization,
        expiry: c.expiry_date
      })) || [],
      recent_jobs: jobs?.map(j => ({
        job_number: j.job_number,
        title: j.title,
        esg_score: j.esg_score,
        diversion_rate: j.diversion_rate,
        completed_at: j.completed_at
      })) || [],
      generated_at: new Date().toISOString()
    };
  } catch (error) {
    logger.error('Generate compliance report error:', error);
    throw error;
  }
}

/**
 * Store vertical-specific ESG data
 */
async function storeVerticalESGData(jobId, verticalId, companyId, data) {
  try {
    // Check if record exists
    const { data: existing } = await supabase
      .from('vertical_esg_data')
      .select('id')
      .eq('job_id', jobId)
      .single();

    const record = {
      job_id: jobId,
      vertical_id: verticalId,
      company_id: companyId,
      data,
      updated_at: new Date().toISOString()
    };

    if (existing) {
      await supabase
        .from('vertical_esg_data')
        .update(record)
        .eq('id', existing.id);
    } else {
      await supabase
        .from('vertical_esg_data')
        .insert(record);
    }

    // Trigger ESG score calculation
    return calculateJobESGScore(jobId);
  } catch (error) {
    logger.error('Store vertical ESG data error:', error);
    throw error;
  }
}

/**
 * Get expiring documents/certifications
 */
async function getExpiringItems(companyId, daysAhead = 30) {
  try {
    const futureDate = new Date();
    futureDate.setDate(futureDate.getDate() + daysAhead);

    // Get expiring documents
    const { data: documents } = await supabase
      .from('esg_documents')
      .select('*')
      .eq('company_id', companyId)
      .not('expires_at', 'is', null)
      .lte('expires_at', futureDate.toISOString())
      .gte('expires_at', new Date().toISOString());

    // Get expiring certifications
    const { data: certifications } = await supabase
      .from('certifications')
      .select('*')
      .eq('company_id', companyId)
      .eq('is_active', true)
      .not('expiry_date', 'is', null)
      .lte('expiry_date', futureDate.toISOString())
      .gte('expiry_date', new Date().toISOString());

    return {
      documents: documents || [],
      certifications: certifications || [],
      total: (documents?.length || 0) + (certifications?.length || 0)
    };
  } catch (error) {
    logger.error('Get expiring items error:', error);
    throw error;
  }
}

module.exports = {
  calculateJobESGScore,
  calculateCompanyCompliance,
  checkContractReadiness,
  getRequirements,
  generateComplianceReport,
  storeVerticalESGData,
  getExpiringItems,
  checkRequirementsMet,
  CARBON_FACTORS,
  SCORING_CONFIG
};
