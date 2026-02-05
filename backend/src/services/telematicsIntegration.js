/**
 * Telematics Integration Service
 * Integrates with Samsara, Geotab, Verizon Connect, and Fleetio
 */

const { createClient } = require('@supabase/supabase-js');
const carbonAPI = require('./carbonAPI');

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

// Provider configurations
const PROVIDERS = {
  samsara: {
    name: 'Samsara',
    baseUrl: 'https://api.samsara.com',
    version: 'v1',
    authType: 'bearer'
  },
  geotab: {
    name: 'Geotab',
    baseUrl: 'https://my.geotab.com/apiv1',
    authType: 'basic'
  },
  verizon: {
    name: 'Verizon Connect',
    baseUrl: 'https://fim.api.us.fleetmatics.com',
    authType: 'oauth2'
  },
  fleetio: {
    name: 'Fleetio',
    baseUrl: 'https://secure.fleetio.com/api',
    version: 'v1',
    authType: 'api_key'
  }
};

/**
 * Get integration credentials for a company
 */
async function getCredentials(companyId, provider) {
  const { data } = await supabase
    .from('integrations')
    .select('*')
    .eq('company_id', companyId)
    .eq('type', provider)
    .single();

  return data?.credentials;
}

/**
 * Samsara API Client
 */
class SamsaraClient {
  constructor(apiKey) {
    this.apiKey = apiKey;
    this.baseUrl = PROVIDERS.samsara.baseUrl;
  }

  async request(endpoint, method = 'GET', body = null) {
    const url = `${this.baseUrl}/${endpoint}`;

    const options = {
      method,
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json'
      }
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    const response = await fetch(url, options);
    return response.json();
  }

  async getVehicles() {
    const result = await this.request('fleet/vehicles');
    return result.data?.map(v => ({
      external_id: v.id,
      name: v.name,
      vin: v.vin,
      make: v.make,
      model: v.model,
      year: v.year,
      license_plate: v.licensePlate,
      odometer_miles: v.odometerMeters ? v.odometerMeters / 1609.34 : null,
      fuel_type: this.mapFuelType(v.fuelType),
      status: v.vehicleStatus
    })) || [];
  }

  async getVehicleLocations() {
    const result = await this.request('fleet/vehicles/locations');
    return result.data?.map(v => ({
      external_id: v.id,
      latitude: v.location?.latitude,
      longitude: v.location?.longitude,
      heading: v.location?.heading,
      speed_mph: v.location?.speedMilesPerHour,
      recorded_at: v.location?.time
    })) || [];
  }

  async getTrips(vehicleId, startTime, endTime) {
    const params = new URLSearchParams({
      vehicleId,
      startTime: startTime.toISOString(),
      endTime: endTime.toISOString()
    });

    const result = await this.request(`fleet/trips?${params}`);
    return result.trips?.map(t => ({
      trip_id: t.id,
      external_vehicle_id: vehicleId,
      start_time: t.startTime,
      end_time: t.endTime,
      distance_miles: t.distanceMeters / 1609.34,
      duration_minutes: Math.round((new Date(t.endTime) - new Date(t.startTime)) / 60000),
      start_location: t.startLocation,
      end_location: t.endLocation,
      fuel_consumed_gallons: t.fuelConsumedMl ? t.fuelConsumedMl / 3785.41 : null,
      idle_time_minutes: t.idleDurationMs ? Math.round(t.idleDurationMs / 60000) : 0
    })) || [];
  }

  async getFuelUsage(vehicleId, startTime, endTime) {
    const params = new URLSearchParams({
      vehicleIds: vehicleId,
      startTime: startTime.toISOString(),
      endTime: endTime.toISOString()
    });

    const result = await this.request(`fleet/vehicles/stats/fuel?${params}`);
    return result.data?.[0];
  }

  async getDriverBehavior(vehicleId, startTime, endTime) {
    const params = new URLSearchParams({
      vehicleIds: vehicleId,
      startTime: startTime.toISOString(),
      endTime: endTime.toISOString()
    });

    const result = await this.request(`fleet/vehicles/stats/safety?${params}`);

    if (result.data?.[0]) {
      const stats = result.data[0];
      return {
        harsh_braking: stats.harshBrakingCount || 0,
        harsh_acceleration: stats.harshAccelerationCount || 0,
        speeding_duration_minutes: Math.round((stats.speedingDurationMs || 0) / 60000),
        safety_score: stats.safetyScore
      };
    }

    return null;
  }

  mapFuelType(type) {
    const mapping = {
      'diesel': 'diesel',
      'unleaded': 'gasoline',
      'electric': 'electric',
      'hybrid': 'hybrid',
      'cng': 'cng'
    };
    return mapping[type?.toLowerCase()] || 'gasoline';
  }
}

/**
 * Geotab API Client
 */
class GeotabClient {
  constructor(database, username, password) {
    this.database = database;
    this.username = username;
    this.password = password;
    this.sessionId = null;
  }

  async authenticate() {
    const response = await fetch(`${PROVIDERS.geotab.baseUrl}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        method: 'Authenticate',
        params: {
          database: this.database,
          userName: this.username,
          password: this.password
        }
      })
    });

    const result = await response.json();
    this.sessionId = result.result?.credentials?.sessionId;
    return this.sessionId;
  }

  async call(method, params = {}) {
    if (!this.sessionId) {
      await this.authenticate();
    }

    const response = await fetch(`${PROVIDERS.geotab.baseUrl}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        method,
        params: {
          ...params,
          credentials: {
            database: this.database,
            sessionId: this.sessionId,
            userName: this.username
          }
        }
      })
    });

    return response.json();
  }

  async getVehicles() {
    const result = await this.call('Get', {
      typeName: 'Device',
      resultsLimit: 1000
    });

    return result.result?.map(d => ({
      external_id: d.id,
      name: d.name,
      vin: d.vehicleIdentificationNumber,
      license_plate: d.licensePlate,
      serial_number: d.serialNumber,
      odometer_miles: d.odometerOffset
    })) || [];
  }

  async getVehicleLocations() {
    const result = await this.call('Get', {
      typeName: 'DeviceStatusInfo'
    });

    return result.result?.map(s => ({
      external_id: s.device?.id,
      latitude: s.latitude,
      longitude: s.longitude,
      speed_mph: s.speed * 0.621371,
      recorded_at: s.dateTime
    })) || [];
  }

  async getTrips(deviceId, startTime, endTime) {
    const result = await this.call('Get', {
      typeName: 'Trip',
      search: {
        deviceSearch: { id: deviceId },
        fromDate: startTime.toISOString(),
        toDate: endTime.toISOString()
      }
    });

    return result.result?.map(t => ({
      trip_id: t.id,
      external_vehicle_id: deviceId,
      start_time: t.start,
      end_time: t.stop,
      distance_miles: t.distance * 0.621371,
      duration_minutes: t.drivingDuration ? Math.round(t.drivingDuration / 60) : 0,
      idle_time_minutes: t.idlingDuration ? Math.round(t.idlingDuration / 60) : 0
    })) || [];
  }
}

/**
 * Fleetio API Client
 */
class FleetioClient {
  constructor(accountToken, apiKey) {
    this.accountToken = accountToken;
    this.apiKey = apiKey;
    this.baseUrl = `${PROVIDERS.fleetio.baseUrl}/${PROVIDERS.fleetio.version}`;
  }

  async request(endpoint, method = 'GET', body = null) {
    const url = `${this.baseUrl}/${endpoint}`;

    const options = {
      method,
      headers: {
        'Authorization': `Token token=${this.apiKey}`,
        'Account-Token': this.accountToken,
        'Content-Type': 'application/json'
      }
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    const response = await fetch(url, options);
    return response.json();
  }

  async getVehicles() {
    const result = await this.request('vehicles');
    return result.map(v => ({
      external_id: v.id.toString(),
      name: v.name,
      vin: v.vin,
      make: v.make,
      model: v.model,
      year: v.year,
      license_plate: v.license_plate,
      odometer_miles: v.current_meter_value,
      fuel_type: v.fuel_type_name?.toLowerCase(),
      status: v.vehicle_status_name
    }));
  }

  async getFuelEntries(vehicleId, startTime, endTime) {
    const params = new URLSearchParams({
      'q[vehicle_id_eq]': vehicleId,
      'q[date_gteq]': startTime.toISOString().split('T')[0],
      'q[date_lteq]': endTime.toISOString().split('T')[0]
    });

    const result = await this.request(`fuel_entries?${params}`);
    return result.map(f => ({
      date: f.date,
      gallons: f.us_gallons,
      cost: f.cost_per_gallon,
      total_cost: f.total_amount,
      odometer_miles: f.meter_value
    }));
  }

  async getServiceEntries(vehicleId) {
    const params = new URLSearchParams({
      'q[vehicle_id_eq]': vehicleId
    });

    const result = await this.request(`service_entries?${params}`);
    return result;
  }
}

/**
 * Sync vehicles from telematics provider
 */
async function syncVehicles(companyId, provider) {
  const credentials = await getCredentials(companyId, provider);

  if (!credentials) {
    throw new Error(`No ${provider} credentials configured`);
  }

  let client;
  let vehicles = [];

  switch (provider) {
    case 'samsara':
      client = new SamsaraClient(credentials.api_key);
      vehicles = await client.getVehicles();
      break;

    case 'geotab':
      client = new GeotabClient(credentials.database, credentials.username, credentials.password);
      vehicles = await client.getVehicles();
      break;

    case 'fleetio':
      client = new FleetioClient(credentials.account_token, credentials.api_key);
      vehicles = await client.getVehicles();
      break;

    default:
      throw new Error(`Unsupported provider: ${provider}`);
  }

  // Upsert vehicles to database
  const results = [];
  for (const vehicle of vehicles) {
    const { data, error } = await supabase
      .from('vehicles')
      .upsert({
        company_id: companyId,
        external_id: vehicle.external_id,
        telematics_provider: provider,
        name: vehicle.name,
        vin: vehicle.vin,
        make: vehicle.make,
        model: vehicle.model,
        year: vehicle.year,
        license_plate: vehicle.license_plate,
        fuel_type: vehicle.fuel_type,
        current_odometer_miles: vehicle.odometer_miles,
        synced_at: new Date().toISOString()
      }, {
        onConflict: 'company_id,external_id'
      })
      .select()
      .single();

    if (data) results.push(data);
  }

  return {
    provider,
    synced: results.length,
    vehicles: results
  };
}

/**
 * Sync trip data from telematics
 */
async function syncTrips(companyId, provider, startTime, endTime) {
  const credentials = await getCredentials(companyId, provider);

  if (!credentials) {
    throw new Error(`No ${provider} credentials configured`);
  }

  // Get company vehicles
  const { data: vehicles } = await supabase
    .from('vehicles')
    .select('id, external_id')
    .eq('company_id', companyId)
    .eq('telematics_provider', provider);

  if (!vehicles?.length) {
    return { synced: 0, message: 'No vehicles found' };
  }

  let client;
  switch (provider) {
    case 'samsara':
      client = new SamsaraClient(credentials.api_key);
      break;
    case 'geotab':
      client = new GeotabClient(credentials.database, credentials.username, credentials.password);
      break;
    default:
      throw new Error(`Trip sync not supported for ${provider}`);
  }

  const allTrips = [];

  for (const vehicle of vehicles) {
    const trips = await client.getTrips(vehicle.external_id, startTime, endTime);

    for (const trip of trips) {
      // Calculate emissions for this trip
      let emissions = null;
      if (trip.distance_miles > 0) {
        emissions = carbonAPI.calculateLocalEmissions({
          type: 'transport',
          subtype: 'van_delivery', // Will use vehicle-specific type when available
          value: trip.distance_miles,
          unit: 'miles'
        });
      }

      const { data } = await supabase
        .from('fleet_telematics')
        .insert({
          company_id: companyId,
          vehicle_id: vehicle.id,
          provider,
          external_vehicle_id: vehicle.external_id,
          trip_id: trip.trip_id,
          trip_start_time: trip.start_time,
          trip_end_time: trip.end_time,
          trip_distance_miles: trip.distance_miles,
          trip_duration_minutes: trip.duration_minutes,
          fuel_consumed_gallons: trip.fuel_consumed_gallons,
          idle_time_minutes: trip.idle_time_minutes,
          recorded_at: trip.start_time,
          raw_data: {
            ...trip,
            emissions: emissions ? {
              co2e_kg: emissions.co2e_kg,
              co2e_lbs: emissions.co2e_lbs
            } : null
          }
        })
        .select()
        .single();

      if (data) allTrips.push(data);
    }
  }

  return {
    provider,
    synced: allTrips.length,
    date_range: {
      start: startTime,
      end: endTime
    }
  };
}

/**
 * Get live fleet status
 */
async function getFleetStatus(companyId, provider) {
  const credentials = await getCredentials(companyId, provider);

  if (!credentials) {
    // Return mock data for demo
    return getMockFleetStatus(companyId);
  }

  let client;
  switch (provider) {
    case 'samsara':
      client = new SamsaraClient(credentials.api_key);
      break;
    case 'geotab':
      client = new GeotabClient(credentials.database, credentials.username, credentials.password);
      break;
    default:
      return getMockFleetStatus(companyId);
  }

  const locations = await client.getVehicleLocations();

  // Enrich with database info
  const { data: vehicles } = await supabase
    .from('vehicles')
    .select('*')
    .eq('company_id', companyId);

  const enrichedLocations = locations.map(loc => {
    const vehicle = vehicles?.find(v => v.external_id === loc.external_id);
    return {
      ...loc,
      vehicle_name: vehicle?.name,
      vehicle_id: vehicle?.id,
      fuel_type: vehicle?.fuel_type
    };
  });

  return {
    provider,
    timestamp: new Date().toISOString(),
    vehicles: enrichedLocations
  };
}

/**
 * Generate mock fleet status for demo
 */
function getMockFleetStatus(companyId) {
  const mockVehicles = [
    {
      external_id: 'demo-1',
      vehicle_name: 'Service Van #1',
      latitude: 34.0522,
      longitude: -118.2437,
      speed_mph: 35,
      status: 'moving',
      current_job: 'JOB-2024-001',
      driver: 'John Smith'
    },
    {
      external_id: 'demo-2',
      vehicle_name: 'Service Van #2',
      latitude: 34.0195,
      longitude: -118.4912,
      speed_mph: 0,
      status: 'at_job',
      current_job: 'JOB-2024-002',
      driver: 'Jane Doe'
    },
    {
      external_id: 'demo-3',
      vehicle_name: 'Box Truck #1',
      latitude: 34.1478,
      longitude: -118.1445,
      speed_mph: 55,
      status: 'returning',
      current_job: null,
      driver: 'Bob Wilson'
    }
  ];

  return {
    provider: 'demo',
    timestamp: new Date().toISOString(),
    vehicles: mockVehicles,
    summary: {
      total_vehicles: 3,
      moving: 2,
      idle: 0,
      at_job: 1,
      offline: 0
    }
  };
}

/**
 * Calculate fleet emissions summary
 */
async function getFleetEmissionsSummary(companyId, startDate, endDate) {
  const { data: telematicsData } = await supabase
    .from('fleet_telematics')
    .select(`
      trip_distance_miles,
      fuel_consumed_gallons,
      idle_time_minutes,
      vehicle:vehicles(fuel_type, vehicle_type)
    `)
    .eq('company_id', companyId)
    .gte('recorded_at', startDate)
    .lte('recorded_at', endDate);

  if (!telematicsData?.length) {
    return {
      period: { start: startDate, end: endDate },
      total_distance_miles: 0,
      total_fuel_gallons: 0,
      total_co2e_kg: 0,
      total_co2e_lbs: 0,
      trips_count: 0
    };
  }

  let totalDistance = 0;
  let totalFuel = 0;
  let totalCO2 = 0;
  let totalIdle = 0;

  for (const trip of telematicsData) {
    totalDistance += trip.trip_distance_miles || 0;
    totalFuel += trip.fuel_consumed_gallons || 0;
    totalIdle += trip.idle_time_minutes || 0;

    // Calculate emissions
    if (trip.trip_distance_miles > 0) {
      const fuelType = trip.vehicle?.fuel_type || 'gasoline';
      const emissionFactor = carbonAPI.GHG_EMISSION_FACTORS.fuels[fuelType]?.factor || 8.89;

      let fuelUsed = trip.fuel_consumed_gallons;
      if (!fuelUsed && trip.trip_distance_miles) {
        // Estimate fuel from distance using average MPG
        const avgMpg = fuelType === 'diesel' ? 8 : 10;
        fuelUsed = trip.trip_distance_miles / avgMpg;
      }

      totalCO2 += fuelUsed * emissionFactor * 0.453592; // Convert lbs to kg
    }
  }

  // Calculate idle emissions (assuming 0.5 gal/hr idle consumption)
  const idleHours = totalIdle / 60;
  const idleFuel = idleHours * 0.5;
  const idleCO2 = idleFuel * 8.89 * 0.453592;

  return {
    period: { start: startDate, end: endDate },
    total_distance_miles: Math.round(totalDistance * 100) / 100,
    total_fuel_gallons: Math.round(totalFuel * 100) / 100,
    estimated_fuel_gallons: Math.round((totalFuel || totalDistance / 10) * 100) / 100,
    total_idle_minutes: Math.round(totalIdle),
    idle_fuel_gallons: Math.round(idleFuel * 100) / 100,
    total_co2e_kg: Math.round((totalCO2 + idleCO2) * 100) / 100,
    total_co2e_lbs: Math.round((totalCO2 + idleCO2) * 2.205 * 100) / 100,
    trips_count: telematicsData.length,
    efficiency_metrics: {
      avg_miles_per_trip: Math.round(totalDistance / telematicsData.length * 100) / 100,
      idle_percentage: totalIdle > 0 ? Math.round(idleHours / (totalDistance / 35) * 100) : 0, // Assuming 35mph avg
      co2_per_mile: totalDistance > 0 ? Math.round((totalCO2 + idleCO2) / totalDistance * 1000) / 1000 : 0
    }
  };
}

module.exports = {
  PROVIDERS,
  SamsaraClient,
  GeotabClient,
  FleetioClient,
  syncVehicles,
  syncTrips,
  getFleetStatus,
  getMockFleetStatus,
  getFleetEmissionsSummary
};
