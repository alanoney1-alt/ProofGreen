/**
 * Mileage Calculator Service
 * Calculates distance and emissions for service trips
 */

// Emission factors (lbs CO2 per gallon)
const FUEL_EMISSION_FACTORS = {
  gasoline: 19.6,
  diesel: 22.4,
  electric: 0, // Emissions depend on grid
  hybrid: 14.7, // Estimated average
  cng: 14.3,
  propane: 12.7
};

// Average MPG by vehicle type
const DEFAULT_MPG = {
  car: { gasoline: 30, diesel: 35, electric: 100, hybrid: 45 },
  van: { gasoline: 20, diesel: 24, electric: 80, hybrid: 28 },
  pickup: { gasoline: 18, diesel: 22, electric: 70, hybrid: 25 },
  box_truck_16ft: { gasoline: 10, diesel: 12 },
  box_truck_20ft: { gasoline: 8, diesel: 10 },
  box_truck_26ft: { gasoline: 6, diesel: 8 },
  semi: { diesel: 6 }
};

/**
 * Calculate distance between two addresses using geocoding
 * In production, this would use Google Maps, Mapbox, or similar API
 */
async function calculateDistance(originAddress, destinationAddress) {
  // For demo purposes, estimate based on zip codes or return placeholder
  // In production, integrate with Google Maps Distance Matrix API

  try {
    // Check if we have coordinates
    if (originAddress.lat && originAddress.lng && destinationAddress.lat && destinationAddress.lng) {
      return haversineDistance(
        originAddress.lat, originAddress.lng,
        destinationAddress.lat, destinationAddress.lng
      );
    }

    // Placeholder: In production, call geocoding API
    // For now, return estimate based on input
    console.log('Distance calculation requires geocoding API integration');
    return null;
  } catch (error) {
    console.error('Distance calculation error:', error);
    throw error;
  }
}

/**
 * Haversine formula for distance between two coordinates
 */
function haversineDistance(lat1, lon1, lat2, lon2) {
  const R = 3959; // Earth's radius in miles
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat/2) * Math.sin(dLat/2) +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
    Math.sin(dLon/2) * Math.sin(dLon/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c;
}

function toRad(deg) {
  return deg * (Math.PI / 180);
}

/**
 * Calculate fuel consumption and emissions for a trip
 */
function calculateTripEmissions(distanceMiles, vehicleType, fuelType, customMpg = null) {
  const mpg = customMpg || DEFAULT_MPG[vehicleType]?.[fuelType] || 20;
  const emissionFactor = FUEL_EMISSION_FACTORS[fuelType] || FUEL_EMISSION_FACTORS.gasoline;

  const fuelUsedGallons = distanceMiles / mpg;
  const co2EmissionsLbs = fuelUsedGallons * emissionFactor;

  return {
    distanceMiles,
    fuelUsedGallons: Math.round(fuelUsedGallons * 1000) / 1000,
    co2EmissionsLbs: Math.round(co2EmissionsLbs * 100) / 100,
    mpgUsed: mpg,
    fuelType,
    vehicleType
  };
}

/**
 * Calculate emissions for a complete service job with multiple trips
 */
function calculateJobTripEmissions(trips) {
  let totalDistance = 0;
  let totalFuel = 0;
  let totalCO2 = 0;

  const tripDetails = trips.map(trip => {
    const result = calculateTripEmissions(
      trip.distanceMiles,
      trip.vehicleType,
      trip.fuelType,
      trip.mpg
    );

    totalDistance += result.distanceMiles;
    totalFuel += result.fuelUsedGallons;
    totalCO2 += result.co2EmissionsLbs;

    return {
      ...trip,
      ...result
    };
  });

  return {
    trips: tripDetails,
    totals: {
      distanceMiles: Math.round(totalDistance * 100) / 100,
      fuelUsedGallons: Math.round(totalFuel * 1000) / 1000,
      co2EmissionsLbs: Math.round(totalCO2 * 100) / 100
    }
  };
}

/**
 * Estimate annual mileage impact for recurring service
 */
function estimateAnnualMileageImpact(tripDistanceMiles, frequency, vehicleType, fuelType) {
  const tripsPerYear = {
    weekly: 52,
    biweekly: 26,
    monthly: 12,
    quarterly: 4,
    annual: 1
  };

  const annualTrips = tripsPerYear[frequency] || 1;
  const annualDistance = tripDistanceMiles * annualTrips * 2; // Round trip

  const emissions = calculateTripEmissions(annualDistance, vehicleType, fuelType);

  return {
    frequency,
    tripsPerYear: annualTrips,
    annualDistanceMiles: annualDistance,
    annualFuelGallons: emissions.fuelUsedGallons,
    annualCO2Lbs: emissions.co2EmissionsLbs
  };
}

/**
 * Calculate carbon offset needed for trip
 */
function calculateCarbonOffset(co2EmissionsLbs) {
  // Average cost per ton of CO2 offset: $10-50
  const co2Tons = co2EmissionsLbs / 2000;
  const offsetCostLow = co2Tons * 10;
  const offsetCostHigh = co2Tons * 50;

  // Trees needed (1 tree absorbs ~48 lbs CO2/year)
  const treesNeeded = Math.ceil(co2EmissionsLbs / 48);

  return {
    co2Tons: Math.round(co2Tons * 1000) / 1000,
    offsetCostRange: {
      low: Math.round(offsetCostLow * 100) / 100,
      high: Math.round(offsetCostHigh * 100) / 100
    },
    treesEquivalent: treesNeeded
  };
}

module.exports = {
  calculateDistance,
  calculateTripEmissions,
  calculateJobTripEmissions,
  estimateAnnualMileageImpact,
  calculateCarbonOffset,
  FUEL_EMISSION_FACTORS,
  DEFAULT_MPG
};
