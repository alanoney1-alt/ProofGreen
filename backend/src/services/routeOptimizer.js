/**
 * Route Optimization Engine
 * Optimizes service routes for fuel efficiency and reduced emissions
 */

const { createClient } = require('@supabase/supabase-js');
const carbonAPI = require('./carbonAPI');

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

// Vehicle capacity defaults
const VEHICLE_CAPACITIES = {
  car: { weight_lbs: 500, volume_cuft: 15 },
  van: { weight_lbs: 2000, volume_cuft: 200 },
  pickup: { weight_lbs: 1500, volume_cuft: 80 },
  box_truck_16ft: { weight_lbs: 5000, volume_cuft: 800 },
  box_truck_20ft: { weight_lbs: 7000, volume_cuft: 1100 },
  box_truck_26ft: { weight_lbs: 10000, volume_cuft: 1700 },
  semi: { weight_lbs: 45000, volume_cuft: 3000 }
};

// Average speeds by road type (mph)
const AVERAGE_SPEEDS = {
  highway: 55,
  urban: 25,
  suburban: 35,
  rural: 45
};

// Fuel efficiency by vehicle type (mpg)
const FUEL_EFFICIENCY = {
  car: { gasoline: 28, diesel: 32, hybrid: 45, electric: 100 },
  van: { gasoline: 18, diesel: 22, hybrid: 28, electric: 80 },
  pickup: { gasoline: 16, diesel: 20, hybrid: 24, electric: 70 },
  box_truck_16ft: { gasoline: 10, diesel: 12 },
  box_truck_20ft: { gasoline: 8, diesel: 10 },
  box_truck_26ft: { gasoline: 6, diesel: 8 },
  semi: { diesel: 6 }
};

/**
 * Calculate distance between two coordinates using Haversine formula
 */
function calculateDistance(lat1, lon1, lat2, lon2) {
  const R = 3959; // Earth's radius in miles
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;

  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

/**
 * Estimate travel time between two points
 */
function estimateTravelTime(distanceMiles, roadType = 'suburban') {
  const speed = AVERAGE_SPEEDS[roadType] || AVERAGE_SPEEDS.suburban;
  return Math.round(distanceMiles / speed * 60); // Returns minutes
}

/**
 * Build distance matrix for a set of locations
 */
function buildDistanceMatrix(locations) {
  const n = locations.length;
  const matrix = [];

  for (let i = 0; i < n; i++) {
    matrix[i] = [];
    for (let j = 0; j < n; j++) {
      if (i === j) {
        matrix[i][j] = 0;
      } else {
        matrix[i][j] = calculateDistance(
          locations[i].latitude,
          locations[i].longitude,
          locations[j].latitude,
          locations[j].longitude
        );
      }
    }
  }

  return matrix;
}

/**
 * Nearest neighbor algorithm for initial route
 */
function nearestNeighborRoute(distanceMatrix, startIndex = 0) {
  const n = distanceMatrix.length;
  const visited = new Set([startIndex]);
  const route = [startIndex];
  let current = startIndex;

  while (visited.size < n) {
    let nearestDist = Infinity;
    let nearestIdx = -1;

    for (let i = 0; i < n; i++) {
      if (!visited.has(i) && distanceMatrix[current][i] < nearestDist) {
        nearestDist = distanceMatrix[current][i];
        nearestIdx = i;
      }
    }

    if (nearestIdx !== -1) {
      visited.add(nearestIdx);
      route.push(nearestIdx);
      current = nearestIdx;
    }
  }

  return route;
}

/**
 * 2-opt improvement for route optimization
 */
function twoOptImprove(route, distanceMatrix) {
  let improved = true;
  let bestRoute = [...route];
  let bestDistance = calculateRouteDistance(bestRoute, distanceMatrix);

  while (improved) {
    improved = false;

    for (let i = 1; i < route.length - 1; i++) {
      for (let j = i + 1; j < route.length; j++) {
        const newRoute = twoOptSwap(bestRoute, i, j);
        const newDistance = calculateRouteDistance(newRoute, distanceMatrix);

        if (newDistance < bestDistance) {
          bestRoute = newRoute;
          bestDistance = newDistance;
          improved = true;
        }
      }
    }
  }

  return bestRoute;
}

/**
 * Perform 2-opt swap
 */
function twoOptSwap(route, i, j) {
  const newRoute = route.slice(0, i);
  const reversed = route.slice(i, j + 1).reverse();
  const remaining = route.slice(j + 1);

  return [...newRoute, ...reversed, ...remaining];
}

/**
 * Calculate total route distance
 */
function calculateRouteDistance(route, distanceMatrix) {
  let total = 0;
  for (let i = 0; i < route.length - 1; i++) {
    total += distanceMatrix[route[i]][route[i + 1]];
  }
  // Add return to start
  total += distanceMatrix[route[route.length - 1]][route[0]];
  return total;
}

/**
 * Optimize route for a set of jobs
 */
async function optimizeRoute(companyId, jobs, options = {}) {
  const {
    startLocation,
    returnToStart = true,
    vehicleType = 'van',
    fuelType = 'gasoline',
    maxStops = 20,
    timeWindows = false,
    prioritizeEco = true
  } = options;

  // Prepare locations
  const locations = [];

  // Add start location (depot)
  if (startLocation) {
    locations.push({
      id: 'depot',
      type: 'depot',
      name: 'Start Location',
      latitude: startLocation.latitude,
      longitude: startLocation.longitude,
      duration_minutes: 0
    });
  }

  // Add job locations
  for (const job of jobs.slice(0, maxStops)) {
    if (job.latitude && job.longitude) {
      locations.push({
        id: job.id,
        type: 'job',
        name: job.customer_name || `Job ${job.id}`,
        address: job.service_address,
        latitude: parseFloat(job.latitude),
        longitude: parseFloat(job.longitude),
        duration_minutes: job.estimated_duration || 60,
        time_window: job.time_window,
        priority: job.priority || 'normal'
      });
    }
  }

  if (locations.length < 2) {
    return { error: 'Need at least 2 locations to optimize' };
  }

  // Build distance matrix
  const distanceMatrix = buildDistanceMatrix(locations);

  // Get initial route using nearest neighbor
  let route = nearestNeighborRoute(distanceMatrix, 0);

  // Improve with 2-opt
  route = twoOptImprove(route, distanceMatrix);

  // Build optimized route with details
  const optimizedRoute = [];
  let totalDistance = 0;
  let totalDuration = 0;
  let previousLocation = null;

  for (let i = 0; i < route.length; i++) {
    const locIdx = route[i];
    const location = locations[locIdx];

    let legDistance = 0;
    let legDuration = 0;

    if (previousLocation) {
      legDistance = distanceMatrix[route[i - 1]][locIdx];
      legDuration = estimateTravelTime(legDistance);
      totalDistance += legDistance;
      totalDuration += legDuration;
    }

    // Add service time
    totalDuration += location.duration_minutes;

    optimizedRoute.push({
      stop_number: optimizedRoute.length + 1,
      location_id: location.id,
      location_type: location.type,
      name: location.name,
      address: location.address,
      coordinates: {
        latitude: location.latitude,
        longitude: location.longitude
      },
      distance_from_previous: Math.round(legDistance * 100) / 100,
      drive_time_minutes: legDuration,
      service_duration_minutes: location.duration_minutes,
      cumulative_distance: Math.round(totalDistance * 100) / 100,
      cumulative_time: totalDuration
    });

    previousLocation = location;
  }

  // Add return leg if needed
  if (returnToStart && route.length > 1) {
    const returnDistance = distanceMatrix[route[route.length - 1]][0];
    const returnTime = estimateTravelTime(returnDistance);
    totalDistance += returnDistance;
    totalDuration += returnTime;

    optimizedRoute.push({
      stop_number: optimizedRoute.length + 1,
      location_id: 'depot',
      location_type: 'return',
      name: 'Return to Start',
      distance_from_previous: Math.round(returnDistance * 100) / 100,
      drive_time_minutes: returnTime,
      service_duration_minutes: 0,
      cumulative_distance: Math.round(totalDistance * 100) / 100,
      cumulative_time: totalDuration
    });
  }

  // Calculate fuel and emissions
  const mpg = FUEL_EFFICIENCY[vehicleType]?.[fuelType] || 15;
  const fuelGallons = totalDistance / mpg;

  const emissions = carbonAPI.calculateLocalEmissions({
    type: 'transport',
    subtype: `${vehicleType}_${fuelType}`,
    value: fuelGallons,
    unit: 'gallons'
  });

  // Compare with non-optimized (original order)
  const originalDistance = calculateRouteDistance(
    Array.from({ length: locations.length }, (_, i) => i),
    distanceMatrix
  );
  const distanceSaved = originalDistance - totalDistance;
  const fuelSaved = distanceSaved / mpg;
  const emissionsSaved = fuelSaved * (carbonAPI.GHG_EMISSION_FACTORS.fuels[fuelType]?.factor || 8.89);

  const result = {
    optimized_route: optimizedRoute,

    summary: {
      total_stops: optimizedRoute.length - (returnToStart ? 1 : 0),
      total_distance_miles: Math.round(totalDistance * 100) / 100,
      total_duration_minutes: totalDuration,
      total_duration_formatted: formatDuration(totalDuration),
      estimated_fuel_gallons: Math.round(fuelGallons * 100) / 100,
      estimated_co2_lbs: Math.round(emissions.co2e_lbs * 100) / 100,
      estimated_co2_kg: Math.round(emissions.co2e_kg * 100) / 100
    },

    savings: {
      distance_saved_miles: Math.round(distanceSaved * 100) / 100,
      distance_saved_percent: Math.round(distanceSaved / originalDistance * 100 * 10) / 10,
      fuel_saved_gallons: Math.round(fuelSaved * 100) / 100,
      co2_saved_lbs: Math.round(emissionsSaved * 100) / 100,
      original_distance_miles: Math.round(originalDistance * 100) / 100
    },

    vehicle: {
      type: vehicleType,
      fuel_type: fuelType,
      mpg: mpg
    }
  };

  // Store optimization result
  await supabase.from('route_optimizations').insert({
    company_id: companyId,
    date: new Date().toISOString().split('T')[0],
    job_ids: jobs.map(j => j.id),
    start_location: startLocation,
    optimized_routes: result,
    total_distance_miles: totalDistance,
    total_duration_minutes: totalDuration,
    estimated_fuel_gallons: fuelGallons,
    estimated_co2_lbs: emissions.co2e_lbs,
    original_distance_miles: originalDistance,
    distance_saved_miles: distanceSaved,
    distance_saved_percent: distanceSaved / originalDistance * 100,
    fuel_saved_gallons: fuelSaved,
    co2_saved_lbs: emissionsSaved
  });

  return result;
}

/**
 * Analyze empty miles for fleet
 */
async function analyzeEmptyMiles(companyId, startDate, endDate) {
  // Get all trips for the period
  const { data: trips } = await supabase
    .from('fleet_telematics')
    .select(`
      *,
      vehicle:vehicles(id, name, vehicle_type, fuel_type)
    `)
    .eq('company_id', companyId)
    .gte('recorded_at', startDate)
    .lte('recorded_at', endDate)
    .order('recorded_at');

  // Get jobs for the same period
  const { data: jobs } = await supabase
    .from('jobs')
    .select('*')
    .eq('company_id', companyId)
    .gte('scheduled_date', startDate)
    .lte('scheduled_date', endDate);

  let totalMiles = 0;
  let loadedMiles = 0;
  let emptyMiles = 0;

  // Simple analysis - compare trip distances with job-related travel
  const jobLocations = new Map();
  for (const job of jobs || []) {
    if (job.latitude && job.longitude) {
      jobLocations.set(job.id, {
        latitude: parseFloat(job.latitude),
        longitude: parseFloat(job.longitude)
      });
    }
  }

  for (const trip of trips || []) {
    const distance = trip.trip_distance_miles || 0;
    totalMiles += distance;

    // Simplified: assume 70% of miles are loaded (serving jobs)
    // In production, this would match trip endpoints to job locations
    loadedMiles += distance * 0.7;
    emptyMiles += distance * 0.3;
  }

  // Identify backhaul opportunities
  const backhaulOpportunities = identifyBackhaulOpportunities(jobs || []);

  const emptyMilePercent = totalMiles > 0 ? (emptyMiles / totalMiles) * 100 : 0;

  // Calculate potential savings
  const reductionTarget = 0.25; // 25% reduction in empty miles
  const potentialSavings = emptyMiles * reductionTarget;
  const avgMpg = 12;
  const fuelSavings = potentialSavings / avgMpg;
  const co2Savings = fuelSavings * 8.89;

  return {
    period: { start: startDate, end: endDate },

    summary: {
      total_miles: Math.round(totalMiles * 100) / 100,
      loaded_miles: Math.round(loadedMiles * 100) / 100,
      empty_miles: Math.round(emptyMiles * 100) / 100,
      empty_mile_percent: Math.round(emptyMilePercent * 10) / 10,
      trips_analyzed: trips?.length || 0
    },

    benchmarks: {
      industry_average_empty_percent: 35,
      best_in_class_empty_percent: 20,
      your_performance: emptyMilePercent < 25 ? 'excellent' :
        emptyMilePercent < 35 ? 'good' : 'needs_improvement'
    },

    improvement_potential: {
      target_empty_percent: Math.max(20, emptyMilePercent - 10),
      potential_miles_saved: Math.round(potentialSavings * 100) / 100,
      potential_fuel_saved_gallons: Math.round(fuelSavings * 100) / 100,
      potential_co2_saved_lbs: Math.round(co2Savings * 100) / 100,
      potential_cost_saved: Math.round(fuelSavings * 3.5 * 100) / 100 // $3.50/gal
    },

    backhaul_opportunities: backhaulOpportunities,

    recommendations: generateEmptyMileRecommendations(emptyMilePercent, backhaulOpportunities)
  };
}

/**
 * Identify potential backhaul opportunities
 */
function identifyBackhaulOpportunities(jobs) {
  const opportunities = [];

  // Group jobs by date
  const jobsByDate = {};
  for (const job of jobs) {
    const date = job.scheduled_date;
    if (!jobsByDate[date]) jobsByDate[date] = [];
    jobsByDate[date].push(job);
  }

  // Look for jobs in similar areas on same day
  for (const [date, dayJobs] of Object.entries(jobsByDate)) {
    if (dayJobs.length < 2) continue;

    // Find clusters of jobs
    for (let i = 0; i < dayJobs.length; i++) {
      for (let j = i + 1; j < dayJobs.length; j++) {
        if (dayJobs[i].latitude && dayJobs[j].latitude) {
          const distance = calculateDistance(
            parseFloat(dayJobs[i].latitude),
            parseFloat(dayJobs[i].longitude),
            parseFloat(dayJobs[j].latitude),
            parseFloat(dayJobs[j].longitude)
          );

          if (distance < 5) { // Within 5 miles
            opportunities.push({
              date,
              job1: dayJobs[i].id,
              job2: dayJobs[j].id,
              distance_between: Math.round(distance * 10) / 10,
              potential_savings: 'Combine trips for these nearby jobs'
            });
          }
        }
      }
    }
  }

  return opportunities.slice(0, 10); // Return top 10
}

/**
 * Generate recommendations for reducing empty miles
 */
function generateEmptyMileRecommendations(emptyPercent, opportunities) {
  const recommendations = [];

  if (emptyPercent > 30) {
    recommendations.push({
      priority: 'high',
      category: 'route_optimization',
      suggestion: 'Implement daily route optimization to reduce deadhead miles',
      potential_impact: '15-25% reduction in empty miles'
    });
  }

  if (opportunities.length > 0) {
    recommendations.push({
      priority: 'high',
      category: 'job_clustering',
      suggestion: `${opportunities.length} backhaul opportunities identified - schedule nearby jobs together`,
      potential_impact: '10-15% reduction in empty miles'
    });
  }

  recommendations.push({
    priority: 'medium',
    category: 'scheduling',
    suggestion: 'Use geographic clustering when scheduling new jobs',
    potential_impact: '5-10% reduction in empty miles'
  });

  recommendations.push({
    priority: 'medium',
    category: 'telematics',
    suggestion: 'Enable real-time route adjustments based on live traffic',
    potential_impact: '3-5% reduction in fuel consumption'
  });

  if (emptyPercent > 40) {
    recommendations.push({
      priority: 'high',
      category: 'territory_design',
      suggestion: 'Consider redesigning service territories to reduce cross-territory travel',
      potential_impact: '20-30% reduction in empty miles'
    });
  }

  return recommendations;
}

/**
 * Format duration in hours and minutes
 */
function formatDuration(minutes) {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hours}h ${mins}m`;
}

/**
 * Get optimized schedule for a date
 */
async function getDailyOptimizedSchedule(companyId, date) {
  // Get jobs for the date
  const { data: jobs } = await supabase
    .from('jobs')
    .select('*')
    .eq('company_id', companyId)
    .eq('scheduled_date', date)
    .in('status', ['scheduled', 'assigned']);

  if (!jobs?.length) {
    return { message: 'No jobs scheduled for this date' };
  }

  // Get company's default depot location
  const { data: company } = await supabase
    .from('companies')
    .select('latitude, longitude, address')
    .eq('id', companyId)
    .single();

  const startLocation = company?.latitude ? {
    latitude: parseFloat(company.latitude),
    longitude: parseFloat(company.longitude),
    address: company.address
  } : null;

  // Optimize the route
  return optimizeRoute(companyId, jobs, {
    startLocation,
    returnToStart: true,
    vehicleType: 'van',
    fuelType: 'gasoline'
  });
}

module.exports = {
  VEHICLE_CAPACITIES,
  FUEL_EFFICIENCY,
  calculateDistance,
  estimateTravelTime,
  buildDistanceMatrix,
  optimizeRoute,
  analyzeEmptyMiles,
  getDailyOptimizedSchedule,
  formatDuration
};
