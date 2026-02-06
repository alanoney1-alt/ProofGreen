/**
 * ProofGreen Autonomous ESG Agent
 *
 * This agent automatically processes job photos to:
 * 1. Analyze photos using GPT-4 Vision
 * 2. Identify job type based on detected items
 * 3. Calculate carbon offset and ESG metrics
 * 4. Check and award milestones
 * 5. Generate ESG reports
 */

const OpenAI = require('openai');
const Anthropic = require('@anthropic-ai/sdk');
const { supabase } = require('../utils/supabase');
const { logger } = require('../utils/logger');
const complianceService = require('../services/complianceService');
const formService = require('../services/formService');
const {
  calculateConfidenceScore,
  assessImageQuality,
  formatConfidenceForDisplay
} = require('../services/confidenceService');

// Lazy-initialized AI clients (avoids crash if keys missing)
let openai = null;
let anthropic = null;

function getOpenAI() {
  if (!openai) {
    if (!process.env.OPENAI_API_KEY) {
      throw new Error('OPENAI_API_KEY environment variable is required for AI analysis');
    }
    openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  }
  return openai;
}

function getAnthropic() {
  if (!anthropic) {
    if (!process.env.ANTHROPIC_API_KEY) {
      throw new Error('ANTHROPIC_API_KEY environment variable is required for AI analysis');
    }
    anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  }
  return anthropic;
}

/**
 * Main entry point - process a job photo through the autonomous agent
 */
async function processJobPhoto(jobId, photoBase64, companyId) {
  const executionId = await logAgentExecution(jobId, companyId, 'esg_agent', 'processJobPhoto', { jobId });

  try {
    logger.info(`Starting AI processing for job ${jobId}`);

    // Step 1: Analyze photo
    const analysisResult = await analyzePhoto(photoBase64, jobId, companyId);
    logger.info(`Photo analysis complete: ${analysisResult.items.length} items detected`);

    // Step 2: Identify job type
    const jobTypeResult = await identifyJobType(analysisResult.items, jobId, companyId);
    logger.info(`Job type identified: ${jobTypeResult.job_type} (${jobTypeResult.confidence * 100}% confidence)`);

    // Step 3: Save items and calculate carbon
    const carbonResult = await calculateCarbon(jobId, analysisResult.items, companyId);
    logger.info(`Carbon calculation complete: ${carbonResult.carbon_offset_lbs} lbs CO2 offset`);

    // Step 4: Check milestones
    const milestoneResult = await checkMilestones(companyId, jobId);
    logger.info(`Milestone check complete: ${milestoneResult.new_milestones.length} new milestones achieved`);

    // Step 5: Generate report
    const reportResult = await generateReport(jobId, companyId);
    logger.info(`Report generated: ${reportResult.report_id}`);

    // Step 6: Check ESG compliance
    const complianceResult = await checkESGCompliance(jobId, companyId, jobTypeResult.vertical_id);
    logger.info(`ESG compliance check complete: score ${complianceResult.esgScore.overall}`);

    // Mark job as AI processed
    await supabase
      .from('jobs')
      .update({
        ai_processed: true,
        ai_processed_at: new Date().toISOString(),
        ai_confidence: analysisResult.confidence,
        vertical_id: jobTypeResult.vertical_id,
        esg_score: complianceResult.esgScore.overall
      })
      .eq('id', jobId);

    await completeAgentExecution(executionId, 'completed', {
      items_detected: analysisResult.items.length,
      job_type: jobTypeResult.job_type,
      carbon_offset: carbonResult.carbon_offset_lbs,
      new_milestones: milestoneResult.new_milestones.length,
      report_id: reportResult.report_id,
      esg_score: complianceResult.esgScore.overall,
      compliance_status: complianceResult.complianceStatus
    });

    return {
      success: true,
      analysis: analysisResult,
      jobType: jobTypeResult,
      carbon: carbonResult,
      milestones: milestoneResult,
      report: reportResult,
      compliance: complianceResult
    };
  } catch (error) {
    logger.error('Agent processing error:', error);
    await completeAgentExecution(executionId, 'failed', null, error.message);
    throw error;
  }
}

/**
 * Function 1: Analyze photo using GPT-4 Vision
 */
async function analyzePhoto(photoBase64, jobId, companyId) {
  const executionId = await logAgentExecution(jobId, companyId, 'vision_agent', 'analyzePhoto', {});

  try {
    // Get vertical-specific prompt if available
    const { data: job } = await supabase
      .from('jobs')
      .select('vertical_id')
      .eq('id', jobId)
      .single();

    let customPrompt = '';
    if (job?.vertical_id) {
      const { data: promptData } = await supabase
        .from('vertical_ai_prompts')
        .select('prompt_template, focus_items')
        .eq('vertical_id', job.vertical_id)
        .eq('prompt_type', 'photo_analysis')
        .single();

      if (promptData) {
        customPrompt = promptData.prompt_template;
      }
    }

    const systemPrompt = `You are an expert ESG (Environmental, Social, Governance) analyst specializing in waste management and recycling for home service businesses.

Your task is to analyze photos from service jobs and identify all items present, estimate their weights, and categorize them for proper disposal tracking.

${customPrompt || 'Analyze the image and identify all items that can be tracked for sustainability metrics.'}

For each item, provide:
1. Name (specific item name)
2. Category (one of: furniture, electronics, metal, construction, hvac, roofing, appliance, yard, general)
3. Subcategory (more specific type within category)
4. Estimated weight in pounds
5. Whether it's recyclable
6. Recommended disposal method (recycled, donated, landfill, hazardous, compost, reused)

Respond ONLY with valid JSON in this exact format:
{
  "items": [
    {
      "name": "item name",
      "category": "category",
      "subcategory": "subcategory",
      "weight_lbs": 50,
      "recyclable": true,
      "disposal_method": "recycled"
    }
  ],
  "scene_description": "Brief description of the scene",
  "confidence": 0.85
}`;

    const response = await getOpenAI().chat.completions.create({
      model: 'gpt-4o',
      messages: [
        {
          role: 'system',
          content: systemPrompt
        },
        {
          role: 'user',
          content: [
            {
              type: 'text',
              text: 'Analyze this image and identify all items for ESG tracking. Estimate weights and categorize each item.'
            },
            {
              type: 'image_url',
              image_url: {
                url: `data:image/jpeg;base64,${photoBase64}`,
                detail: 'high'
              }
            }
          ]
        }
      ],
      max_tokens: 2000,
      temperature: 0.3
    });

    const content = response.choices[0].message.content;

    // Parse JSON from response
    let rawResult;
    try {
      // Try to extract JSON from markdown code blocks if present
      const jsonMatch = content.match(/```(?:json)?\s*([\s\S]*?)```/) || [null, content];
      rawResult = JSON.parse(jsonMatch[1].trim());
    } catch (parseError) {
      logger.error('Failed to parse GPT response:', content);
      rawResult = {
        items: [],
        scene_description: 'Unable to parse response',
        confidence: 0
      };
    }

    // Calculate comprehensive confidence score
    const imageMetadata = assessImageQuality(
      Buffer.from(photoBase64, 'base64'),
      'image/jpeg'
    );

    const confidenceResult = calculateConfidenceScore(rawResult, imageMetadata);
    const displayConfidence = formatConfidenceForDisplay(confidenceResult);

    // Enhanced result with confidence scoring
    const result = {
      items: rawResult.items,
      scene_description: rawResult.scene_description,
      // AI's raw confidence
      raw_confidence: rawResult.confidence,
      // Comprehensive confidence assessment
      confidence: {
        score: confidenceResult.score,
        level: confidenceResult.level,
        factors: confidenceResult.factors,
        warnings: confidenceResult.warnings,
        needsReview: confidenceResult.needsReview,
        recommendations: confidenceResult.recommendations
      },
      // Display-ready confidence data
      display: displayConfidence.display,
      // CRITICAL: Always require user verification
      userMustVerify: true,
      // AI suggestions for user to verify/modify
      aiSuggestions: rawResult.items,
      // Metadata for tracking
      metadata: confidenceResult.metadata,
      // Next step guidance
      next_step: confidenceResult.needsReview ?
        'manual_review_required' : 'confirm_and_submit'
    };

    await completeAgentExecution(executionId, 'completed', result, null, response.usage?.total_tokens);

    return result;
  } catch (error) {
    await completeAgentExecution(executionId, 'failed', null, error.message);
    throw error;
  }
}

/**
 * Function 2: Identify job type based on detected items
 */
async function identifyJobType(itemsDetected, jobId, companyId) {
  const executionId = await logAgentExecution(jobId, companyId, 'classification_agent', 'identifyJobType', { items: itemsDetected });

  try {
    // Count items by category
    const categoryCounts = {};
    itemsDetected.forEach(item => {
      const cat = item.category || 'general';
      categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;
    });

    // Map categories to verticals
    const categoryToVertical = {
      'hvac': 'hvac',
      'roofing': 'roofing',
      'construction': 'demolition',
      'furniture': 'junk_removal',
      'appliance': 'appliance_repair',
      'electronics': 'junk_removal',
      'metal': 'junk_removal',
      'yard': 'landscaping',
      'general': 'junk_removal'
    };

    // Find dominant category
    let dominantCategory = 'general';
    let maxCount = 0;
    Object.entries(categoryCounts).forEach(([cat, count]) => {
      if (count > maxCount) {
        maxCount = count;
        dominantCategory = cat;
      }
    });

    const verticalSlug = categoryToVertical[dominantCategory] || 'junk_removal';

    // Get vertical ID from database
    const { data: vertical } = await supabase
      .from('verticals')
      .select('id, name')
      .eq('slug', verticalSlug)
      .single();

    const result = {
      job_type: verticalSlug,
      vertical_id: vertical?.id,
      vertical_name: vertical?.name || verticalSlug,
      confidence: maxCount / itemsDetected.length,
      category_breakdown: categoryCounts
    };

    await completeAgentExecution(executionId, 'completed', result);

    return result;
  } catch (error) {
    await completeAgentExecution(executionId, 'failed', null, error.message);
    throw error;
  }
}

/**
 * Function 3: Calculate carbon offset and update job metrics
 */
async function calculateCarbon(jobId, items, companyId) {
  const executionId = await logAgentExecution(jobId, companyId, 'carbon_agent', 'calculateCarbon', { item_count: items.length });

  try {
    // Fetch carbon factors from database
    const { data: carbonFactors } = await supabase
      .from('carbon_factors')
      .select('*');

    // Create lookup map
    const factorMap = {};
    carbonFactors?.forEach(cf => {
      const key = `${cf.category}:${cf.subcategory || ''}`;
      factorMap[key] = cf;
    });

    // Calculate metrics for each item
    let totalWeight = 0;
    let recycledWeight = 0;
    let donatedWeight = 0;
    let landfillWeight = 0;
    let totalCarbonOffset = 0;

    const processedItems = items.map(item => {
      const weight = item.weight_lbs || 0;
      totalWeight += weight;

      // Get carbon factor
      const factor = factorMap[`${item.category}:${item.subcategory || ''}`] ||
                     factorMap[`${item.category}:`] ||
                     { landfill_factor: 1.0, recycle_factor: 0.3, reuse_factor: 0.1 };

      let carbonOffset = 0;
      const disposal = item.disposal_method || 'landfill';

      switch (disposal) {
        case 'recycled':
          recycledWeight += weight;
          carbonOffset = weight * (factor.landfill_factor - factor.recycle_factor);
          break;
        case 'donated':
        case 'reused':
          donatedWeight += weight;
          carbonOffset = weight * (factor.landfill_factor - factor.reuse_factor);
          break;
        case 'landfill':
        default:
          landfillWeight += weight;
          carbonOffset = 0;
      }

      totalCarbonOffset += carbonOffset;

      return {
        ...item,
        carbon_offset_lbs: carbonOffset,
        carbon_factor_id: factor.id
      };
    });

    // Calculate rates and score
    const diversionRate = totalWeight > 0
      ? ((recycledWeight + donatedWeight) / totalWeight) * 100
      : 0;

    const recycleRate = totalWeight > 0
      ? (recycledWeight / totalWeight) * 100
      : 0;

    const esgScore = Math.min(100, Math.round(
      (diversionRate * 0.4) +
      (Math.min(totalCarbonOffset / 100, 100) * 0.3) +
      (recycleRate * 0.3)
    ));

    // Save items to database
    const itemRecords = processedItems.map(item => ({
      job_id: jobId,
      name: item.name,
      category: item.category,
      subcategory: item.subcategory,
      weight_lbs: item.weight_lbs,
      disposal_method: item.disposal_method,
      carbon_offset_lbs: item.carbon_offset_lbs,
      detected_by_ai: true,
      ai_confidence: 0.85
    }));

    // Clear existing AI-detected items and insert new ones
    await supabase
      .from('job_items')
      .delete()
      .eq('job_id', jobId)
      .eq('detected_by_ai', true);

    if (itemRecords.length > 0) {
      await supabase
        .from('job_items')
        .insert(itemRecords);
    }

    // Update job with calculated metrics
    await supabase
      .from('jobs')
      .update({
        total_weight_lbs: totalWeight,
        recycled_weight_lbs: recycledWeight,
        donated_weight_lbs: donatedWeight,
        landfill_weight_lbs: landfillWeight,
        carbon_offset_lbs: totalCarbonOffset,
        diversion_rate: diversionRate,
        esg_score: esgScore
      })
      .eq('id', jobId);

    const result = {
      total_weight_lbs: totalWeight,
      recycled_weight_lbs: recycledWeight,
      donated_weight_lbs: donatedWeight,
      landfill_weight_lbs: landfillWeight,
      carbon_offset_lbs: totalCarbonOffset,
      diversion_rate: diversionRate,
      esg_score: esgScore,
      items_processed: processedItems.length
    };

    await completeAgentExecution(executionId, 'completed', result);

    return result;
  } catch (error) {
    await completeAgentExecution(executionId, 'failed', null, error.message);
    throw error;
  }
}

/**
 * Function 4: Check and award milestones
 */
async function checkMilestones(companyId, jobId) {
  const executionId = await logAgentExecution(jobId, companyId, 'milestone_agent', 'checkMilestones', {});

  try {
    // Get company's total metrics from all completed jobs
    const { data: jobs } = await supabase
      .from('jobs')
      .select('total_weight_lbs, recycled_weight_lbs, donated_weight_lbs, carbon_offset_lbs')
      .eq('company_id', companyId)
      .eq('status', 'completed');

    const totals = jobs?.reduce((acc, job) => ({
      totalWeight: acc.totalWeight + (job.total_weight_lbs || 0),
      diverted: acc.diverted + (job.recycled_weight_lbs || 0) + (job.donated_weight_lbs || 0),
      carbon: acc.carbon + (job.carbon_offset_lbs || 0),
      count: acc.count + 1
    }), { totalWeight: 0, diverted: 0, carbon: 0, count: 0 }) || { totalWeight: 0, diverted: 0, carbon: 0, count: 0 };

    const diversionRate = totals.totalWeight > 0
      ? (totals.diverted / totals.totalWeight) * 100
      : 0;

    // Get all milestones for this company
    const { data: milestones } = await supabase
      .from('milestones')
      .select('*')
      .eq('company_id', companyId)
      .eq('achieved', false);

    const newlyAchieved = [];

    for (const milestone of (milestones || [])) {
      let currentValue = 0;

      switch (milestone.milestone_type) {
        case 'tons_diverted':
          currentValue = totals.diverted;
          break;
        case 'carbon_saved':
          currentValue = totals.carbon;
          break;
        case 'jobs_completed':
          currentValue = totals.count;
          break;
        case 'diversion_rate':
          currentValue = diversionRate;
          break;
      }

      // Check if milestone is achieved
      if (currentValue >= milestone.threshold_value) {
        await supabase
          .from('milestones')
          .update({
            achieved: true,
            achieved_at: new Date().toISOString(),
            current_value: currentValue
          })
          .eq('id', milestone.id);

        newlyAchieved.push({
          id: milestone.id,
          name: milestone.name,
          milestone_type: milestone.milestone_type,
          threshold_value: milestone.threshold_value,
          current_value: currentValue,
          points: milestone.points
        });
      } else {
        // Update progress
        await supabase
          .from('milestones')
          .update({ current_value: currentValue })
          .eq('id', milestone.id);
      }
    }

    const result = {
      new_milestones: newlyAchieved,
      current_totals: totals,
      diversion_rate: diversionRate
    };

    await completeAgentExecution(executionId, 'completed', result);

    return result;
  } catch (error) {
    await completeAgentExecution(executionId, 'failed', null, error.message);
    throw error;
  }
}

/**
 * Function 5: Generate ESG report for the job
 */
async function generateReport(jobId, companyId) {
  const executionId = await logAgentExecution(jobId, companyId, 'report_agent', 'generateReport', {});

  try {
    // Fetch complete job data
    const { data: job } = await supabase
      .from('jobs')
      .select(`
        *,
        verticals (*),
        job_items (*),
        companies (*)
      `)
      .eq('id', jobId)
      .single();

    if (!job) {
      throw new Error('Job not found');
    }

    // Use Claude to generate a professional summary
    let summary;
    try {
      const summaryResponse = await getAnthropic().messages.create({
        model: 'claude-sonnet-4-20250514',
        max_tokens: 500,
        messages: [
          {
            role: 'user',
            content: `Generate a professional 2-3 sentence ESG report summary for this job:

Job: ${job.title || job.job_number}
Service Type: ${job.verticals?.name || 'General Service'}
Total Weight: ${job.total_weight_lbs || 0} lbs
Recycled: ${job.recycled_weight_lbs || 0} lbs
Donated: ${job.donated_weight_lbs || 0} lbs
Landfill: ${job.landfill_weight_lbs || 0} lbs
Carbon Offset: ${job.carbon_offset_lbs || 0} lbs CO2
Diversion Rate: ${job.diversion_rate?.toFixed(1) || 0}%
ESG Score: ${job.esg_score || 0}/100

Items processed: ${job.job_items?.map(i => i.name).join(', ') || 'None recorded'}

Write a professional summary highlighting the environmental impact. Be specific with numbers.`
          }
        ]
      });

      summary = summaryResponse.content[0].text;
    } catch (aiError) {
      logger.warn('Claude summary generation failed, using fallback:', aiError.message);
      summary = `This job processed ${job.total_weight_lbs?.toFixed(0) || 0} lbs of material with a ${job.diversion_rate?.toFixed(1) || 0}% diversion rate, offsetting approximately ${job.carbon_offset_lbs?.toFixed(0) || 0} lbs of CO2 emissions.`;
    }

    // Create report
    const { v4: uuidv4 } = require('uuid');
    const publicToken = uuidv4();

    const reportData = {
      job: {
        id: job.id,
        jobNumber: job.job_number,
        title: job.title,
        completedAt: job.completed_at,
        customerName: job.customer_name,
        location: `${job.city || ''}, ${job.state || ''}`
      },
      company: {
        name: job.companies?.name,
        logo: job.companies?.logo_url
      },
      metrics: {
        totalWeight: job.total_weight_lbs,
        recycledWeight: job.recycled_weight_lbs,
        donatedWeight: job.donated_weight_lbs,
        landfillWeight: job.landfill_weight_lbs,
        carbonOffset: job.carbon_offset_lbs,
        diversionRate: job.diversion_rate,
        esgScore: job.esg_score
      },
      environmental: {
        treesEquivalent: Math.round((job.carbon_offset_lbs || 0) / 48),
        milesEquivalent: Math.round((job.carbon_offset_lbs || 0) / 0.89),
        gallonsGasEquivalent: Math.round((job.carbon_offset_lbs || 0) / 19.6)
      },
      items: job.job_items?.map(item => ({
        name: item.name,
        category: item.category,
        weight: item.weight_lbs,
        disposalMethod: item.disposal_method,
        carbonOffset: item.carbon_offset_lbs
      })) || [],
      summary,
      generatedAt: new Date().toISOString()
    };

    const { data: report, error } = await supabase
      .from('esg_reports')
      .insert({
        company_id: companyId,
        job_id: jobId,
        report_type: 'job',
        title: `ESG Report - ${job.job_number}`,
        period_start: job.scheduled_date,
        period_end: job.completed_at?.split('T')[0] || new Date().toISOString().split('T')[0],
        summary,
        metrics_snapshot: reportData.metrics,
        report_data: reportData,
        file_format: 'json',
        public_token: publicToken
      })
      .select()
      .single();

    if (error) {
      throw error;
    }

    const result = {
      report_id: report.id,
      public_token: publicToken,
      public_url: `/reports/public/${publicToken}`,
      summary
    };

    await completeAgentExecution(executionId, 'completed', result);

    return result;
  } catch (error) {
    await completeAgentExecution(executionId, 'failed', null, error.message);
    throw error;
  }
}

/**
 * Function 6: Check ESG compliance and store vertical-specific data
 */
async function checkESGCompliance(jobId, companyId, verticalId) {
  const executionId = await logAgentExecution(jobId, companyId, 'compliance_agent', 'checkESGCompliance', { jobId, verticalId });

  try {
    // Get job details with items
    const { data: job } = await supabase
      .from('jobs')
      .select(`
        *,
        verticals (id, name, slug),
        job_items (*)
      `)
      .eq('id', jobId)
      .single();

    if (!job) {
      throw new Error('Job not found');
    }

    const verticalSlug = job.verticals?.slug || 'junk_removal';

    // Auto-populate ESG data from job items
    const esgData = generateESGDataFromJob(job, verticalSlug);

    // Store vertical-specific ESG data
    await complianceService.storeVerticalESGData(jobId, verticalSlug, esgData);

    // Calculate ESG score for this job
    const esgScore = await complianceService.calculateJobESGScore(jobId);

    // Get company's overall compliance status
    const companyCompliance = await complianceService.calculateCompanyCompliance(companyId);

    // Check contract readiness for various contract types
    const governmentReadiness = verticalId
      ? await complianceService.checkContractReadiness(companyId, 'government', verticalId)
      : { ready: false, score: 0 };

    const commercialReadiness = verticalId
      ? await complianceService.checkContractReadiness(companyId, 'commercial', verticalId)
      : { ready: false, score: 0 };

    // Get expiring certifications/documents
    const expiringItems = await complianceService.getExpiringItems(companyId, 30);

    // Generate compliance recommendations using AI
    const recommendations = await generateComplianceRecommendations(
      job,
      esgScore,
      companyCompliance,
      expiringItems
    );

    const result = {
      esgScore,
      esgData,
      complianceStatus: {
        jobScore: esgScore.overall,
        companyScore: companyCompliance.overallScore,
        governmentContractReady: governmentReadiness.ready,
        commercialContractReady: commercialReadiness.ready,
        governmentReadinessScore: governmentReadiness.score,
        commercialReadinessScore: commercialReadiness.score
      },
      expiringItems: expiringItems.slice(0, 5), // Top 5 expiring items
      recommendations,
      breakdown: esgScore.breakdown
    };

    await completeAgentExecution(executionId, 'completed', result);

    return result;
  } catch (error) {
    await completeAgentExecution(executionId, 'failed', null, error.message);
    logger.error('ESG compliance check error:', error);
    // Return default values on error
    return {
      esgScore: { overall: 0, breakdown: { environmental: 0, social: 0, governance: 0 } },
      complianceStatus: {
        jobScore: 0,
        companyScore: 0,
        governmentContractReady: false,
        commercialContractReady: false
      },
      expiringItems: [],
      recommendations: []
    };
  }
}

/**
 * Helper: Generate ESG data from job items and metrics
 */
function generateESGDataFromJob(job, verticalSlug) {
  const items = job.job_items || [];
  const totalWeight = job.total_weight_lbs || 0;
  const recycledWeight = job.recycled_weight_lbs || 0;
  const donatedWeight = job.donated_weight_lbs || 0;

  // Base ESG data applicable to all verticals
  const baseData = {
    total_weight_lbs: totalWeight,
    diverted_weight_lbs: recycledWeight + donatedWeight,
    diversion_rate: totalWeight > 0 ? ((recycledWeight + donatedWeight) / totalWeight) * 100 : 0,
    carbon_offset_lbs: job.carbon_offset_lbs || 0,
    job_date: job.completed_at || job.scheduled_date,
    items_count: items.length
  };

  // Vertical-specific data generation
  const verticalSpecificData = {
    junk_removal: () => ({
      ...baseData,
      recycled_weight_lbs: recycledWeight,
      donated_weight_lbs: donatedWeight,
      landfill_weight_lbs: job.landfill_weight_lbs || 0,
      donation_value_usd: estimateDonationValue(items.filter(i => i.disposal_method === 'donated')),
      recyclable_categories: [...new Set(items.filter(i => i.recyclable).map(i => i.category))]
    }),

    hvac: () => ({
      ...baseData,
      refrigerant_type: extractFromItems(items, 'refrigerant') || 'Unknown',
      refrigerant_lbs_recovered: estimateRefrigerantRecovered(items),
      old_seer_rating: 10, // Default, should be captured in form
      new_seer_rating: 16, // Default estimate
      equipment_recycled: items.some(i => i.category === 'hvac' && i.disposal_method === 'recycled')
    }),

    roofing: () => ({
      ...baseData,
      shingles_recycled_lbs: items.filter(i => i.subcategory?.includes('shingle')).reduce((sum, i) => sum + (i.weight_lbs || 0), 0),
      metal_recycled_lbs: items.filter(i => i.category === 'metal').reduce((sum, i) => sum + (i.weight_lbs || 0), 0),
      cool_roof_installed: false, // Should be captured in form
      energy_star_rated: false // Should be captured in form
    }),

    cleaning: () => ({
      ...baseData,
      green_products_used: true, // Default assumption
      green_product_percentage: 75,
      water_usage_gallons: estimateWaterUsage(job),
      square_footage_cleaned: job.square_footage || 0
    }),

    landscaping: () => ({
      ...baseData,
      organic_waste_composted_lbs: items.filter(i => i.disposal_method === 'compost').reduce((sum, i) => sum + (i.weight_lbs || 0), 0),
      native_plants_installed: 0, // Should be captured in form
      chemical_free: true,
      water_efficient_irrigation: false
    }),

    plumbing: () => ({
      ...baseData,
      water_savings_gallons_per_year: estimateWaterSavings(job),
      low_flow_fixtures_installed: 0,
      pipe_material_recycled_lbs: items.filter(i => i.category === 'metal').reduce((sum, i) => sum + (i.weight_lbs || 0), 0),
      lead_free_materials: true
    }),

    electrical: () => ({
      ...baseData,
      energy_savings_kwh_per_year: estimateEnergySavings(job),
      led_fixtures_installed: 0,
      copper_recycled_lbs: items.filter(i => i.subcategory?.includes('copper')).reduce((sum, i) => sum + (i.weight_lbs || 0), 0),
      smart_controls_installed: false
    }),

    demolition: () => ({
      ...baseData,
      concrete_recycled_lbs: items.filter(i => i.subcategory?.includes('concrete')).reduce((sum, i) => sum + (i.weight_lbs || 0), 0),
      metal_recycled_lbs: items.filter(i => i.category === 'metal').reduce((sum, i) => sum + (i.weight_lbs || 0), 0),
      wood_recycled_lbs: items.filter(i => i.subcategory?.includes('wood')).reduce((sum, i) => sum + (i.weight_lbs || 0), 0),
      hazmat_properly_disposed: true,
      deconstruction_vs_demolition: 'demolition'
    })
  };

  const generator = verticalSpecificData[verticalSlug] || verticalSpecificData.junk_removal;
  return generator();
}

/**
 * Helper: Estimate donation value from donated items
 */
function estimateDonationValue(donatedItems) {
  const valuationRates = {
    furniture: 50,
    electronics: 30,
    appliance: 75,
    general: 20
  };

  return donatedItems.reduce((total, item) => {
    const rate = valuationRates[item.category] || valuationRates.general;
    return total + (item.weight_lbs || 0) * (rate / 100);
  }, 0);
}

/**
 * Helper: Extract specific data from items
 */
function extractFromItems(items, keyword) {
  const item = items.find(i =>
    i.name?.toLowerCase().includes(keyword) ||
    i.subcategory?.toLowerCase().includes(keyword)
  );
  return item?.name || null;
}

/**
 * Helper: Estimate refrigerant recovered
 */
function estimateRefrigerantRecovered(items) {
  const hvacItems = items.filter(i => i.category === 'hvac');
  // Rough estimate: 2-5 lbs per unit
  return hvacItems.length * 3;
}

/**
 * Helper: Estimate water usage for cleaning jobs
 */
function estimateWaterUsage(job) {
  const sqft = job.square_footage || 1000;
  // Rough estimate: 0.1 gallons per sq ft
  return sqft * 0.1;
}

/**
 * Helper: Estimate water savings for plumbing jobs
 */
function estimateWaterSavings(job) {
  // Rough estimate based on fixture replacements
  return 5000; // gallons per year default
}

/**
 * Helper: Estimate energy savings for electrical jobs
 */
function estimateEnergySavings(job) {
  // Rough estimate based on LED replacements
  return 500; // kWh per year default
}

/**
 * Generate AI-powered compliance recommendations
 */
async function generateComplianceRecommendations(job, esgScore, companyCompliance, expiringItems) {
  try {
    const prompt = `Based on this ESG data, provide 3-5 specific, actionable recommendations to improve compliance:

Job ESG Score: ${esgScore.overall}/100
- Environmental: ${esgScore.breakdown?.environmental || 0}/100
- Social: ${esgScore.breakdown?.social || 0}/100
- Governance: ${esgScore.breakdown?.governance || 0}/100

Company Overall Score: ${companyCompliance.overallScore}/100
Expiring Certifications/Documents: ${expiringItems.length}

Service Type: ${job.verticals?.name || 'General'}
Diversion Rate: ${job.diversion_rate?.toFixed(1) || 0}%
Carbon Offset: ${job.carbon_offset_lbs?.toFixed(0) || 0} lbs

Return a JSON array of recommendations with format:
[{"priority": "high/medium/low", "category": "environmental/social/governance", "recommendation": "specific action", "impact": "expected improvement"}]`;

    const response = await getAnthropic().messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 500,
      messages: [{ role: 'user', content: prompt }]
    });

    const content = response.content[0].text;
    const jsonMatch = content.match(/\[[\s\S]*\]/);

    if (jsonMatch) {
      return JSON.parse(jsonMatch[0]);
    }

    return getDefaultRecommendations(esgScore);
  } catch (error) {
    logger.warn('AI recommendations generation failed:', error.message);
    return getDefaultRecommendations(esgScore);
  }
}

/**
 * Get default recommendations based on scores
 */
function getDefaultRecommendations(esgScore) {
  const recommendations = [];

  if (esgScore.breakdown?.environmental < 60) {
    recommendations.push({
      priority: 'high',
      category: 'environmental',
      recommendation: 'Increase waste diversion rate by partnering with more recycling facilities',
      impact: 'Could improve environmental score by 15-20 points'
    });
  }

  if (esgScore.breakdown?.social < 60) {
    recommendations.push({
      priority: 'medium',
      category: 'social',
      recommendation: 'Establish relationships with local charities for item donations',
      impact: 'Could improve social score by 10-15 points'
    });
  }

  if (esgScore.breakdown?.governance < 60) {
    recommendations.push({
      priority: 'high',
      category: 'governance',
      recommendation: 'Ensure all required certifications and documentation are current',
      impact: 'Could improve governance score by 20+ points'
    });
  }

  if (esgScore.overall >= 70) {
    recommendations.push({
      priority: 'low',
      category: 'governance',
      recommendation: 'Consider pursuing third-party ESG certification to validate your practices',
      impact: 'Increased credibility for government contracts'
    });
  }

  return recommendations;
}

/**
 * Helper: Log agent execution start
 */
async function logAgentExecution(jobId, companyId, agentType, functionName, inputData) {
  try {
    const { data } = await supabase
      .from('agent_executions')
      .insert({
        job_id: jobId,
        company_id: companyId,
        agent_type: agentType,
        function_name: functionName,
        input_data: inputData,
        status: 'running',
        started_at: new Date().toISOString()
      })
      .select()
      .single();

    return data?.id;
  } catch (error) {
    logger.error('Failed to log agent execution:', error);
    return null;
  }
}

/**
 * Helper: Complete agent execution log
 */
async function completeAgentExecution(executionId, status, outputData, errorMessage, tokensUsed) {
  if (!executionId) return;

  try {
    const startedAt = await supabase
      .from('agent_executions')
      .select('started_at')
      .eq('id', executionId)
      .single();

    const executionTime = startedAt?.data?.started_at
      ? new Date().getTime() - new Date(startedAt.data.started_at).getTime()
      : null;

    await supabase
      .from('agent_executions')
      .update({
        status,
        output_data: outputData,
        error_message: errorMessage,
        completed_at: new Date().toISOString(),
        execution_time_ms: executionTime,
        tokens_used: tokensUsed
      })
      .eq('id', executionId);
  } catch (error) {
    logger.error('Failed to complete agent execution log:', error);
  }
}

module.exports = {
  processJobPhoto,
  analyzePhoto,
  identifyJobType,
  calculateCarbon,
  checkMilestones,
  generateReport,
  checkESGCompliance
};
