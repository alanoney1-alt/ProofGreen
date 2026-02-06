/**
 * Computer Vision Survey Agent
 * Analyzes photos/video to estimate inventory for moving companies
 * and identify equipment for service companies
 */

const Anthropic = require('@anthropic-ai/sdk');

// Lazy-initialized Anthropic client
let anthropic = null;
function getAnthropic() {
  if (!anthropic) {
    if (!process.env.ANTHROPIC_API_KEY) {
      throw new Error('ANTHROPIC_API_KEY required for CV survey');
    }
    anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  }
  return anthropic;
}

// Standard furniture weights and volumes (for moving estimation)
const FURNITURE_DATABASE = {
  // Living Room
  'sofa_3seat': { weight_lbs: 280, cubic_ft: 70, category: 'living_room' },
  'sofa_2seat': { weight_lbs: 180, cubic_ft: 45, category: 'living_room' },
  'sectional_sofa': { weight_lbs: 450, cubic_ft: 120, category: 'living_room' },
  'recliner': { weight_lbs: 150, cubic_ft: 35, category: 'living_room' },
  'armchair': { weight_lbs: 80, cubic_ft: 25, category: 'living_room' },
  'coffee_table': { weight_lbs: 60, cubic_ft: 15, category: 'living_room' },
  'end_table': { weight_lbs: 30, cubic_ft: 8, category: 'living_room' },
  'entertainment_center': { weight_lbs: 200, cubic_ft: 60, category: 'living_room' },
  'tv_65inch': { weight_lbs: 55, cubic_ft: 12, category: 'living_room' },
  'tv_55inch': { weight_lbs: 40, cubic_ft: 8, category: 'living_room' },
  'bookshelf_large': { weight_lbs: 150, cubic_ft: 40, category: 'living_room' },
  'bookshelf_small': { weight_lbs: 60, cubic_ft: 20, category: 'living_room' },
  'piano_upright': { weight_lbs: 500, cubic_ft: 50, category: 'living_room', special: true },
  'piano_grand': { weight_lbs: 900, cubic_ft: 150, category: 'living_room', special: true },

  // Bedroom
  'bed_king': { weight_lbs: 200, cubic_ft: 80, category: 'bedroom' },
  'bed_queen': { weight_lbs: 160, cubic_ft: 60, category: 'bedroom' },
  'bed_full': { weight_lbs: 120, cubic_ft: 45, category: 'bedroom' },
  'bed_twin': { weight_lbs: 80, cubic_ft: 30, category: 'bedroom' },
  'mattress_king': { weight_lbs: 130, cubic_ft: 50, category: 'bedroom' },
  'mattress_queen': { weight_lbs: 100, cubic_ft: 40, category: 'bedroom' },
  'dresser_large': { weight_lbs: 200, cubic_ft: 50, category: 'bedroom' },
  'dresser_small': { weight_lbs: 100, cubic_ft: 25, category: 'bedroom' },
  'nightstand': { weight_lbs: 40, cubic_ft: 8, category: 'bedroom' },
  'wardrobe': { weight_lbs: 250, cubic_ft: 80, category: 'bedroom' },
  'chest_of_drawers': { weight_lbs: 120, cubic_ft: 30, category: 'bedroom' },

  // Dining Room
  'dining_table_large': { weight_lbs: 200, cubic_ft: 45, category: 'dining' },
  'dining_table_small': { weight_lbs: 100, cubic_ft: 25, category: 'dining' },
  'dining_chair': { weight_lbs: 20, cubic_ft: 6, category: 'dining' },
  'china_cabinet': { weight_lbs: 300, cubic_ft: 70, category: 'dining' },
  'buffet': { weight_lbs: 200, cubic_ft: 50, category: 'dining' },

  // Kitchen
  'refrigerator_large': { weight_lbs: 300, cubic_ft: 30, category: 'kitchen' },
  'refrigerator_small': { weight_lbs: 180, cubic_ft: 20, category: 'kitchen' },
  'stove_range': { weight_lbs: 200, cubic_ft: 25, category: 'kitchen' },
  'dishwasher': { weight_lbs: 125, cubic_ft: 15, category: 'kitchen' },
  'microwave': { weight_lbs: 35, cubic_ft: 3, category: 'kitchen' },
  'kitchen_table': { weight_lbs: 80, cubic_ft: 20, category: 'kitchen' },

  // Office
  'desk_large': { weight_lbs: 150, cubic_ft: 40, category: 'office' },
  'desk_small': { weight_lbs: 80, cubic_ft: 25, category: 'office' },
  'office_chair': { weight_lbs: 45, cubic_ft: 15, category: 'office' },
  'filing_cabinet': { weight_lbs: 100, cubic_ft: 12, category: 'office' },
  'computer_desktop': { weight_lbs: 30, cubic_ft: 4, category: 'office' },
  'computer_monitor': { weight_lbs: 15, cubic_ft: 3, category: 'office' },

  // Misc
  'washer': { weight_lbs: 175, cubic_ft: 20, category: 'laundry' },
  'dryer': { weight_lbs: 125, cubic_ft: 20, category: 'laundry' },
  'treadmill': { weight_lbs: 250, cubic_ft: 40, category: 'fitness', special: true },
  'elliptical': { weight_lbs: 200, cubic_ft: 35, category: 'fitness', special: true },
  'pool_table': { weight_lbs: 800, cubic_ft: 100, category: 'recreation', special: true },
  'safe_large': { weight_lbs: 500, cubic_ft: 15, category: 'misc', special: true },
  'safe_small': { weight_lbs: 150, cubic_ft: 5, category: 'misc', special: true },

  // Boxes (standard)
  'box_small': { weight_lbs: 25, cubic_ft: 1.5, category: 'boxes' },
  'box_medium': { weight_lbs: 35, cubic_ft: 3, category: 'boxes' },
  'box_large': { weight_lbs: 50, cubic_ft: 4.5, category: 'boxes' },
  'box_wardrobe': { weight_lbs: 40, cubic_ft: 10, category: 'boxes' }
};

/**
 * Analyze room image to identify furniture and estimate move size
 */
async function analyzeRoomImage(imageBase64, mimeType = 'image/jpeg', roomType = 'unknown') {
  const prompt = `You are an expert moving estimator. Analyze this room photo and identify all furniture and large items.

For EACH item you can see, provide:
1. Item type (match to standard furniture names like: sofa_3seat, bed_king, dresser_large, etc.)
2. Estimated condition (excellent, good, fair, poor)
3. Any special handling needs (fragile, oversized, heavy, disassembly required)
4. Confidence level (high, medium, low)

Room type hint: ${roomType}

Respond in JSON format:
{
  "room_type": "living_room|bedroom|dining|kitchen|office|garage|other",
  "items": [
    {
      "item_type": "standard_furniture_name",
      "description": "brief description with color/material",
      "quantity": 1,
      "condition": "excellent|good|fair|poor",
      "special_handling": ["fragile", "heavy", "disassembly", "oversized"],
      "confidence": "high|medium|low"
    }
  ],
  "estimated_boxes": {
    "small": 0,
    "medium": 0,
    "large": 0
  },
  "notes": "any important observations",
  "hazards": ["stairs", "narrow_doorway", "no_elevator", etc.]
}`;

  try {
    const response = await getAnthropic().messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 4096,
      messages: [
        {
          role: 'user',
          content: [
            {
              type: 'image',
              source: {
                type: 'base64',
                media_type: mimeType,
                data: imageBase64
              }
            },
            {
              type: 'text',
              text: prompt
            }
          ]
        }
      ]
    });

    const content = response.content[0].text;

    // Parse JSON response
    const jsonMatch = content.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      const analysis = JSON.parse(jsonMatch[0]);

      // Calculate weights and volumes
      let totalWeight = 0;
      let totalVolume = 0;
      const itemizedList = [];

      for (const item of analysis.items) {
        const furnitureData = FURNITURE_DATABASE[item.item_type] || {
          weight_lbs: 50,
          cubic_ft: 10,
          category: 'misc'
        };

        const itemTotal = {
          ...item,
          weight_lbs: furnitureData.weight_lbs * item.quantity,
          cubic_ft: furnitureData.cubic_ft * item.quantity,
          special: furnitureData.special || false
        };

        totalWeight += itemTotal.weight_lbs;
        totalVolume += itemTotal.cubic_ft;
        itemizedList.push(itemTotal);
      }

      // Add box estimates
      const boxes = analysis.estimated_boxes || {};
      totalWeight += (boxes.small || 0) * 25;
      totalWeight += (boxes.medium || 0) * 35;
      totalWeight += (boxes.large || 0) * 50;
      totalVolume += (boxes.small || 0) * 1.5;
      totalVolume += (boxes.medium || 0) * 3;
      totalVolume += (boxes.large || 0) * 4.5;

      return {
        success: true,
        room_type: analysis.room_type,
        items: itemizedList,
        boxes: analysis.estimated_boxes,
        totals: {
          weight_lbs: totalWeight,
          cubic_ft: totalVolume
        },
        special_items: itemizedList.filter(i => i.special || i.special_handling?.length > 0),
        hazards: analysis.hazards || [],
        notes: analysis.notes
      };
    }

    throw new Error('Failed to parse room analysis');
  } catch (error) {
    console.error('Room analysis error:', error);
    return {
      success: false,
      error: error.message
    };
  }
}

/**
 * Analyze multiple room images for complete home survey
 */
async function analyzeHomeSurvey(images) {
  const results = {
    rooms: [],
    totals: {
      weight_lbs: 0,
      cubic_ft: 0,
      item_count: 0
    },
    special_items: [],
    all_hazards: new Set(),
    truck_recommendation: null,
    estimated_labor_hours: 0,
    boxes_needed: {
      small: 0,
      medium: 0,
      large: 0,
      wardrobe: 0
    }
  };

  // Analyze each room
  for (const image of images) {
    const roomResult = await analyzeRoomImage(
      image.base64,
      image.mimeType,
      image.roomType
    );

    if (roomResult.success) {
      results.rooms.push(roomResult);
      results.totals.weight_lbs += roomResult.totals.weight_lbs;
      results.totals.cubic_ft += roomResult.totals.cubic_ft;
      results.totals.item_count += roomResult.items.length;

      results.special_items.push(...roomResult.special_items);

      roomResult.hazards.forEach(h => results.all_hazards.add(h));

      if (roomResult.boxes) {
        results.boxes_needed.small += roomResult.boxes.small || 0;
        results.boxes_needed.medium += roomResult.boxes.medium || 0;
        results.boxes_needed.large += roomResult.boxes.large || 0;
      }
    }
  }

  // Determine truck size recommendation
  const cubicFt = results.totals.cubic_ft;
  if (cubicFt <= 400) {
    results.truck_recommendation = {
      size: '16ft',
      capacity_cubic_ft: 450,
      crew_size: 2,
      estimated_hours: Math.ceil(cubicFt / 100)
    };
  } else if (cubicFt <= 800) {
    results.truck_recommendation = {
      size: '20ft',
      capacity_cubic_ft: 850,
      crew_size: 2,
      estimated_hours: Math.ceil(cubicFt / 80)
    };
  } else if (cubicFt <= 1200) {
    results.truck_recommendation = {
      size: '26ft',
      capacity_cubic_ft: 1400,
      crew_size: 3,
      estimated_hours: Math.ceil(cubicFt / 70)
    };
  } else {
    results.truck_recommendation = {
      size: 'Multiple 26ft trucks',
      truck_count: Math.ceil(cubicFt / 1200),
      capacity_cubic_ft: 1400,
      crew_size: 4,
      estimated_hours: Math.ceil(cubicFt / 60)
    };
  }

  // Add 20% for special items/hazards
  if (results.special_items.length > 0 || results.all_hazards.size > 0) {
    results.truck_recommendation.estimated_hours = Math.ceil(
      results.truck_recommendation.estimated_hours * 1.2
    );
  }

  results.estimated_labor_hours = results.truck_recommendation.estimated_hours;
  results.all_hazards = Array.from(results.all_hazards);

  return results;
}

/**
 * Analyze equipment nameplate/label image
 */
async function analyzeEquipmentImage(imageBase64, equipmentType, mimeType = 'image/jpeg') {
  const prompt = `Analyze this ${equipmentType} equipment image/nameplate. Extract all visible specifications.

Look for:
- Brand/Manufacturer
- Model number
- Serial number
- Capacity (tons, BTU, gallons, etc.)
- Efficiency ratings (SEER, EER, AFUE, etc.)
- Refrigerant type and charge
- Electrical specs (voltage, amps)
- Manufacturing date
- Certifications (ENERGY STAR, UL, etc.)
- Any warning labels or hazard information

Respond in JSON:
{
  "equipment_type": "${equipmentType}",
  "brand": "",
  "model_number": "",
  "serial_number": "",
  "manufacturing_date": "",
  "specifications": {
    "capacity": {"value": 0, "unit": ""},
    "efficiency": {"rating_type": "", "value": 0},
    "refrigerant": {"type": "", "charge_oz": 0},
    "electrical": {"voltage": "", "amperage": 0, "wattage": 0}
  },
  "certifications": [],
  "age_estimate_years": 0,
  "condition_assessment": "excellent|good|fair|poor|unknown",
  "esg_relevant": {
    "energy_star": false,
    "refrigerant_gwp": 0,
    "estimated_annual_kwh": 0
  },
  "notes": ""
}`;

  try {
    const response = await getAnthropic().messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 4096,
      messages: [
        {
          role: 'user',
          content: [
            {
              type: 'image',
              source: {
                type: 'base64',
                media_type: mimeType,
                data: imageBase64
              }
            },
            {
              type: 'text',
              text: prompt
            }
          ]
        }
      ]
    });

    const content = response.content[0].text;
    const jsonMatch = content.match(/\{[\s\S]*\}/);

    if (jsonMatch) {
      return {
        success: true,
        equipment: JSON.parse(jsonMatch[0])
      };
    }

    throw new Error('Failed to parse equipment analysis');
  } catch (error) {
    console.error('Equipment analysis error:', error);
    return {
      success: false,
      error: error.message
    };
  }
}

/**
 * Generate instant moving quote from survey
 */
function generateMovingQuote(surveyResults, moveDetails) {
  const {
    origin_address,
    destination_address,
    distance_miles,
    move_date,
    floor_origin,
    floor_destination,
    has_elevator_origin,
    has_elevator_destination
  } = moveDetails;

  // Base rates (per hour, varies by market)
  const BASE_RATE_PER_HOUR = 150; // 2-person crew
  const ADDITIONAL_MOVER_RATE = 40; // per additional mover per hour
  const TRUCK_RATE_PER_MILE = 1.50;

  // Calculate labor
  const crew_size = surveyResults.truck_recommendation.crew_size;
  const labor_hours = surveyResults.estimated_labor_hours;
  const additional_movers = Math.max(0, crew_size - 2);

  const labor_cost = (BASE_RATE_PER_HOUR + (additional_movers * ADDITIONAL_MOVER_RATE)) * labor_hours;

  // Calculate travel
  const travel_cost = distance_miles * TRUCK_RATE_PER_MILE * 2; // Round trip

  // Stair/elevator charges
  let stair_charge = 0;
  if (!has_elevator_origin && floor_origin > 1) {
    stair_charge += 75 * (floor_origin - 1);
  }
  if (!has_elevator_destination && floor_destination > 1) {
    stair_charge += 75 * (floor_destination - 1);
  }

  // Special item charges
  let special_charges = 0;
  for (const item of surveyResults.special_items) {
    if (item.item_type.includes('piano')) special_charges += 300;
    else if (item.item_type.includes('pool_table')) special_charges += 250;
    else if (item.item_type.includes('safe')) special_charges += 150;
    else if (item.item_type.includes('treadmill')) special_charges += 75;
    else special_charges += 50;
  }

  // Packing materials estimate
  const packing_materials = {
    small_boxes: surveyResults.boxes_needed.small * 4,
    medium_boxes: surveyResults.boxes_needed.medium * 5,
    large_boxes: surveyResults.boxes_needed.large * 7,
    packing_paper: Math.ceil(surveyResults.totals.item_count * 2),
    tape: Math.ceil(surveyResults.boxes_needed.medium / 10) * 8,
    total: 0
  };
  packing_materials.total =
    packing_materials.small_boxes +
    packing_materials.medium_boxes +
    packing_materials.large_boxes +
    packing_materials.packing_paper +
    packing_materials.tape;

  const subtotal = labor_cost + travel_cost + stair_charge + special_charges;
  const tax = subtotal * 0.08; // Varies by state
  const total = subtotal + tax;

  // Carbon footprint estimate
  const fuel_gallons = distance_miles / 8; // ~8 mpg for moving truck
  const co2_lbs = fuel_gallons * 22.4; // Diesel emission factor

  return {
    quote_id: `MQ-${Date.now()}`,
    generated_at: new Date().toISOString(),
    valid_until: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),

    move_details: {
      origin: origin_address,
      destination: destination_address,
      distance_miles,
      move_date,
      estimated_weight_lbs: surveyResults.totals.weight_lbs,
      estimated_volume_cubic_ft: surveyResults.totals.cubic_ft,
      truck_size: surveyResults.truck_recommendation.size,
      crew_size,
      estimated_hours: labor_hours
    },

    pricing: {
      labor: labor_cost,
      travel: travel_cost,
      stair_charges: stair_charge,
      special_items: special_charges,
      subtotal,
      tax,
      total,
      packing_materials_optional: packing_materials.total
    },

    carbon_footprint: {
      estimated_fuel_gallons: Math.round(fuel_gallons * 10) / 10,
      estimated_co2_lbs: Math.round(co2_lbs),
      offset_cost: Math.round(co2_lbs / 2000 * 15 * 100) / 100 // ~$15/ton
    },

    special_items: surveyResults.special_items.map(i => i.item_type),
    hazards: surveyResults.all_hazards,

    disclaimer: 'This quote is an estimate based on visual analysis. Final price may vary based on actual inventory, access conditions, and services required.'
  };
}

module.exports = {
  analyzeRoomImage,
  analyzeHomeSurvey,
  analyzeEquipmentImage,
  generateMovingQuote,
  FURNITURE_DATABASE
};
