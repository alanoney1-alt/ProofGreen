/**
 * Multi-Agent Orchestrator
 * Coordinates specialized AI agents for ESG automation
 */

const Anthropic = require('@anthropic-ai/sdk');
const carbonAPI = require('./carbonAPI');
const cvSurveyAgent = require('./cvSurveyAgent');
const greenVerifier = require('./greenVerifier');
const taxCreditMatcher = require('./taxCreditMatcher');
const { createClient } = require('@supabase/supabase-js');

// Lazy-initialized Anthropic client
let anthropic = null;
function getAnthropic() {
  if (!anthropic) {
    if (!process.env.ANTHROPIC_API_KEY) {
      throw new Error('ANTHROPIC_API_KEY required for agent orchestration');
    }
    anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  }
  return anthropic;
}

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

/**
 * Agent Types and their capabilities
 */
const AGENT_TYPES = {
  INTAKE: {
    name: 'Intake Agent',
    description: 'Handles customer inquiries, quotes, and scheduling',
    capabilities: [
      'cv_survey',
      'instant_quote',
      'scheduling',
      'customer_questions',
      'lead_qualification'
    ]
  },
  OPS: {
    name: 'Operations Agent',
    description: 'Optimizes routes, manages fleet, tracks efficiency',
    capabilities: [
      'route_optimization',
      'fleet_tracking',
      'fuel_monitoring',
      'schedule_optimization',
      'resource_allocation'
    ]
  },
  VERIFIER: {
    name: 'Green Verifier Agent',
    description: 'Generates certificates, calculates emissions, ensures compliance',
    capabilities: [
      'carbon_calculation',
      'certificate_generation',
      'compliance_checking',
      'esg_reporting',
      'audit_preparation'
    ]
  },
  TAX: {
    name: 'Tax Credit Agent',
    description: 'Identifies tax credits, tracks deductions, prepares documentation',
    capabilities: [
      'credit_identification',
      'deduction_tracking',
      'documentation_generation',
      'roi_calculation',
      'incentive_alerts'
    ]
  }
};

/**
 * Main orchestrator - routes requests to appropriate agents
 */
async function orchestrate(request) {
  const {
    type,
    action,
    data,
    company_id,
    user_id,
    conversation_history
  } = request;

  // Log the request
  const executionId = await logExecution(company_id, type, action, 'started');

  try {
    let result;

    switch (type) {
      case 'INTAKE':
        result = await handleIntakeRequest(action, data, conversation_history);
        break;

      case 'OPS':
        result = await handleOpsRequest(action, data, company_id);
        break;

      case 'VERIFIER':
        result = await handleVerifierRequest(action, data, company_id);
        break;

      case 'TAX':
        result = await handleTaxRequest(action, data, company_id);
        break;

      case 'CHAT':
        // General chat - determine which agent should handle
        result = await routeToAgent(data.message, data.context, company_id);
        break;

      default:
        throw new Error(`Unknown agent type: ${type}`);
    }

    await updateExecution(executionId, 'completed', result);
    return result;

  } catch (error) {
    await updateExecution(executionId, 'failed', { error: error.message });
    throw error;
  }
}

/**
 * Intake Agent Handler
 */
async function handleIntakeRequest(action, data, conversationHistory) {
  switch (action) {
    case 'cv_survey':
      // Process images and generate quote
      const surveyResult = await cvSurveyAgent.analyzeHomeSurvey(data.images);

      if (surveyResult.rooms.length > 0 && data.move_details) {
        const quote = cvSurveyAgent.generateMovingQuote(surveyResult, data.move_details);
        return {
          survey: surveyResult,
          quote,
          agent: 'INTAKE',
          action: 'cv_survey'
        };
      }

      return { survey: surveyResult, agent: 'INTAKE', action: 'cv_survey' };

    case 'instant_quote':
      // Generate quote from provided inventory data
      const { inventory, move_details } = data;

      // Calculate totals from inventory
      let totalWeight = 0;
      let totalVolume = 0;
      const items = [];

      for (const item of inventory) {
        const furnitureData = cvSurveyAgent.FURNITURE_DATABASE[item.type] || {
          weight_lbs: 50,
          cubic_ft: 10
        };

        totalWeight += furnitureData.weight_lbs * (item.quantity || 1);
        totalVolume += furnitureData.cubic_ft * (item.quantity || 1);
        items.push({
          ...item,
          weight_lbs: furnitureData.weight_lbs * (item.quantity || 1),
          cubic_ft: furnitureData.cubic_ft * (item.quantity || 1)
        });
      }

      const mockSurvey = {
        totals: { weight_lbs: totalWeight, cubic_ft: totalVolume },
        special_items: items.filter(i => i.special),
        all_hazards: [],
        truck_recommendation: determineTruckSize(totalVolume)
      };

      const instantQuote = cvSurveyAgent.generateMovingQuote(mockSurvey, move_details);
      return { quote: instantQuote, agent: 'INTAKE', action: 'instant_quote' };

    case 'chat':
      // Handle customer chat with context-aware responses
      return await handleCustomerChat(data.message, conversationHistory, data.context);

    default:
      throw new Error(`Unknown intake action: ${action}`);
  }
}

/**
 * Operations Agent Handler
 */
async function handleOpsRequest(action, data, companyId) {
  switch (action) {
    case 'optimize_route':
      // Multi-stop route optimization
      const { stops, vehicle, start_location, end_location } = data;

      // Calculate optimal order (simplified TSP)
      const optimizedRoute = optimizeStopOrder(stops, start_location, end_location);

      // Calculate emissions for route
      const routeEmissions = await carbonAPI.calculateFreightEmissions({
        distance_km: optimizedRoute.total_distance_km,
        weight_kg: data.cargo_weight_kg || 1000,
        vehicle_type: vehicle.type,
        fuel_type: vehicle.fuel_type,
        load_factor: data.load_factor || 80
      });

      return {
        optimized_route: optimizedRoute,
        emissions: routeEmissions,
        savings: {
          distance_saved_km: (data.original_distance_km || optimizedRoute.total_distance_km * 1.15) - optimizedRoute.total_distance_km,
          estimated_fuel_saved: routeEmissions.co2e_kg * 0.15 / 2.68, // Approx liters
          estimated_co2_saved_kg: routeEmissions.co2e_kg * 0.15
        },
        agent: 'OPS',
        action: 'optimize_route'
      };

    case 'track_fleet':
      // Get fleet status and emissions
      const { data: vehicles } = await supabase
        .from('vehicles')
        .select('*, service_trips(*)')
        .eq('company_id', companyId);

      const fleetSummary = {
        total_vehicles: vehicles?.length || 0,
        by_fuel_type: {},
        total_miles_today: 0,
        total_co2_today_lbs: 0
      };

      for (const vehicle of vehicles || []) {
        fleetSummary.by_fuel_type[vehicle.fuel_type] =
          (fleetSummary.by_fuel_type[vehicle.fuel_type] || 0) + 1;

        // Sum today's trips
        const todayTrips = (vehicle.service_trips || []).filter(t =>
          t.start_time && new Date(t.start_time).toDateString() === new Date().toDateString()
        );

        for (const trip of todayTrips) {
          fleetSummary.total_miles_today += trip.distance_miles || 0;
          fleetSummary.total_co2_today_lbs += trip.co2_emissions_lbs || 0;
        }
      }

      return {
        fleet_summary: fleetSummary,
        vehicles: vehicles?.map(v => ({
          id: v.id,
          name: `${v.year} ${v.make} ${v.model}`,
          fuel_type: v.fuel_type,
          current_odometer: v.current_odometer,
          trips_today: v.service_trips?.length || 0
        })),
        agent: 'OPS',
        action: 'track_fleet'
      };

    case 'empty_miles_analysis':
      // Analyze empty/deadhead miles
      const { data: trips } = await supabase
        .from('service_trips')
        .select('*')
        .eq('vehicle_id', data.vehicle_id)
        .gte('start_time', data.start_date)
        .lte('end_time', data.end_date);

      let totalMiles = 0;
      let loadedMiles = 0;
      let emptyMiles = 0;

      for (const trip of trips || []) {
        totalMiles += trip.distance_miles || 0;
        if (trip.trip_type === 'to_job' || trip.trip_type === 'between_jobs') {
          loadedMiles += trip.distance_miles || 0;
        } else {
          emptyMiles += trip.distance_miles || 0;
        }
      }

      const emptyMilesPercent = totalMiles > 0 ? (emptyMiles / totalMiles * 100) : 0;

      return {
        analysis: {
          total_miles: totalMiles,
          loaded_miles: loadedMiles,
          empty_miles: emptyMiles,
          empty_miles_percent: Math.round(emptyMilesPercent * 10) / 10,
          industry_benchmark: 35, // Typical is 35% empty
          performance: emptyMilesPercent < 35 ? 'above_average' : 'below_average'
        },
        recommendations: emptyMilesPercent > 35 ? [
          'Consider route consolidation to reduce deadhead miles',
          'Look for backhaul opportunities',
          'Adjust scheduling to minimize return trips'
        ] : [
          'Empty miles below industry average - good performance',
          'Continue monitoring for optimization opportunities'
        ],
        agent: 'OPS',
        action: 'empty_miles_analysis'
      };

    default:
      throw new Error(`Unknown ops action: ${action}`);
  }
}

/**
 * Green Verifier Agent Handler
 */
async function handleVerifierRequest(action, data, companyId) {
  switch (action) {
    case 'calculate_emissions':
      const emissions = await carbonAPI.calculateJobEmissions(data);
      return { emissions, agent: 'VERIFIER', action: 'calculate_emissions' };

    case 'generate_certificate':
      let certificate;

      switch (data.certificate_type) {
        case 'GREEN_MOVE':
          certificate = await greenVerifier.createGreenMoveCertificate({
            company_id: companyId,
            ...data
          });
          break;

        case 'REFRIGERANT':
          certificate = await greenVerifier.createRefrigerantCertificate({
            company_id: companyId,
            ...data
          });
          break;

        case 'EFFICIENCY':
          certificate = await greenVerifier.createEfficiencyCertificate({
            company_id: companyId,
            ...data
          });
          break;

        case 'WASTE':
          certificate = await greenVerifier.createWasteDiversionCertificate({
            company_id: companyId,
            ...data
          });
          break;

        default:
          throw new Error(`Unknown certificate type: ${data.certificate_type}`);
      }

      return { certificate, agent: 'VERIFIER', action: 'generate_certificate' };

    case 'verify_certificate':
      const verification = await greenVerifier.verifyCertificate(data.certificate_id);
      return { verification, agent: 'VERIFIER', action: 'verify_certificate' };

    case 'annual_report':
      const report = await greenVerifier.generateAnnualESGReport(companyId, data.year);
      return { report, agent: 'VERIFIER', action: 'annual_report' };

    default:
      throw new Error(`Unknown verifier action: ${action}`);
  }
}

/**
 * Tax Credit Agent Handler
 */
async function handleTaxRequest(action, data, companyId) {
  switch (action) {
    case 'analyze_credits':
      const analysis = await taxCreditMatcher.analyzeCompanyForCredits(
        companyId,
        data.tax_year || new Date().getFullYear()
      );
      return { analysis, agent: 'TAX', action: 'analyze_credits' };

    case 'calculate_credit':
      const credit = taxCreditMatcher.calculateCredit(data.credit_type, data.transaction);
      return { credit, agent: 'TAX', action: 'calculate_credit' };

    case 'generate_report':
      const taxReport = await taxCreditMatcher.generateTaxCreditReport(
        companyId,
        data.tax_year || new Date().getFullYear()
      );
      return { report: taxReport, agent: 'TAX', action: 'generate_report' };

    case 'equipment_credits':
      const equipmentCredits = taxCreditMatcher.getCreditsForEquipment(data.equipment_type);
      return { credits: equipmentCredits, agent: 'TAX', action: 'equipment_credits' };

    default:
      throw new Error(`Unknown tax action: ${action}`);
  }
}

/**
 * Route general chat to appropriate agent
 */
async function routeToAgent(message, context, companyId) {
  // Use Claude to determine intent and route
  const routingPrompt = `Analyze this user message and determine which specialized agent should handle it.

User message: "${message}"
Context: ${JSON.stringify(context || {})}

Available agents:
1. INTAKE - Customer inquiries, quotes, scheduling, surveys
2. OPS - Route optimization, fleet tracking, efficiency
3. VERIFIER - Carbon calculations, certificates, compliance
4. TAX - Tax credits, deductions, incentives

Respond with JSON:
{
  "agent": "INTAKE|OPS|VERIFIER|TAX",
  "action": "specific_action_to_take",
  "confidence": 0.0-1.0,
  "extracted_data": {}
}`;

  const response = await getAnthropic().messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 1000,
    messages: [{ role: 'user', content: routingPrompt }]
  });

  const routingResult = JSON.parse(response.content[0].text.match(/\{[\s\S]*\}/)[0]);

  // Route to appropriate agent
  const request = {
    type: routingResult.agent,
    action: routingResult.action,
    data: { ...routingResult.extracted_data, message },
    company_id: companyId
  };

  return await orchestrate(request);
}

/**
 * Handle customer chat with context
 */
async function handleCustomerChat(message, history, context) {
  const systemPrompt = `You are a helpful customer service agent for a home service company.
You can help with:
- Providing quotes for services
- Answering questions about scheduling
- Explaining services and pricing
- Discussing environmental benefits and certifications

Be friendly, professional, and concise. If you need more information to provide a quote, ask for it.

Context about this customer:
${JSON.stringify(context || {})}`;

  const messages = [
    ...(history || []).map(h => ({
      role: h.role,
      content: h.content
    })),
    { role: 'user', content: message }
  ];

  const response = await getAnthropic().messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 1000,
    system: systemPrompt,
    messages
  });

  return {
    response: response.content[0].text,
    agent: 'INTAKE',
    action: 'chat'
  };
}

/**
 * Helper: Determine truck size from volume
 */
function determineTruckSize(cubicFt) {
  if (cubicFt <= 400) {
    return { size: '16ft', capacity_cubic_ft: 450, crew_size: 2, estimated_hours: Math.ceil(cubicFt / 100) };
  } else if (cubicFt <= 800) {
    return { size: '20ft', capacity_cubic_ft: 850, crew_size: 2, estimated_hours: Math.ceil(cubicFt / 80) };
  } else if (cubicFt <= 1200) {
    return { size: '26ft', capacity_cubic_ft: 1400, crew_size: 3, estimated_hours: Math.ceil(cubicFt / 70) };
  } else {
    return { size: 'Multiple trucks', truck_count: Math.ceil(cubicFt / 1200), crew_size: 4, estimated_hours: Math.ceil(cubicFt / 60) };
  }
}

/**
 * Helper: Optimize stop order (simplified nearest neighbor)
 */
function optimizeStopOrder(stops, startLocation, endLocation) {
  // Simplified optimization - in production use OSRM or Google Routes API
  const ordered = [];
  const remaining = [...stops];
  let current = startLocation;
  let totalDistance = 0;

  while (remaining.length > 0) {
    // Find nearest stop
    let nearestIdx = 0;
    let nearestDist = Infinity;

    for (let i = 0; i < remaining.length; i++) {
      const dist = calculateDistance(current, remaining[i]);
      if (dist < nearestDist) {
        nearestDist = dist;
        nearestIdx = i;
      }
    }

    ordered.push(remaining[nearestIdx]);
    current = remaining[nearestIdx];
    totalDistance += nearestDist;
    remaining.splice(nearestIdx, 1);
  }

  // Add distance to end location
  totalDistance += calculateDistance(current, endLocation);

  return {
    stops: ordered,
    total_distance_km: Math.round(totalDistance * 100) / 100,
    stop_count: ordered.length
  };
}

/**
 * Helper: Calculate distance between coordinates
 */
function calculateDistance(point1, point2) {
  if (!point1?.lat || !point2?.lat) return 10; // Default 10km if no coords

  const R = 6371; // Earth's radius in km
  const dLat = (point2.lat - point1.lat) * Math.PI / 180;
  const dLon = (point2.lng - point1.lng) * Math.PI / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(point1.lat * Math.PI / 180) * Math.cos(point2.lat * Math.PI / 180) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

/**
 * Log agent execution
 */
async function logExecution(companyId, agentType, action, status) {
  const { data } = await supabase
    .from('agent_executions')
    .insert({
      company_id: companyId,
      agent_type: agentType,
      action,
      status,
      started_at: new Date().toISOString()
    })
    .select()
    .single();

  return data?.id;
}

/**
 * Update execution status
 */
async function updateExecution(executionId, status, result) {
  if (!executionId) return;

  await supabase
    .from('agent_executions')
    .update({
      status,
      result,
      completed_at: new Date().toISOString()
    })
    .eq('id', executionId);
}

module.exports = {
  AGENT_TYPES,
  orchestrate,
  handleIntakeRequest,
  handleOpsRequest,
  handleVerifierRequest,
  handleTaxRequest,
  routeToAgent
};
