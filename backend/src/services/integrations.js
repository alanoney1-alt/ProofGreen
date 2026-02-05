/**
 * External Integrations Service
 * Handles connections to ServiceTitan, QuickBooks, Fleet GPS, etc.
 */

const { createClient } = require('@supabase/supabase-js');

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

/**
 * Integration Providers Configuration
 */
const PROVIDERS = {
  servicetitan: {
    name: 'ServiceTitan',
    type: 'field_service',
    authType: 'oauth2',
    baseUrl: 'https://api.servicetitan.io',
    scopes: ['jobs', 'customers', 'invoices', 'inventory'],
    dataMapping: {
      jobs: {
        externalField: 'id',
        localField: 'external_job_id',
        fields: ['jobNumber', 'customerId', 'locationId', 'businessUnitId', 'jobType', 'summary', 'completedOn']
      },
      materials: {
        externalField: 'id',
        localField: 'external_material_id',
        fields: ['name', 'code', 'cost', 'quantity', 'unit']
      }
    }
  },
  housecall_pro: {
    name: 'Housecall Pro',
    type: 'field_service',
    authType: 'oauth2',
    baseUrl: 'https://api.housecallpro.com',
    scopes: ['jobs', 'customers', 'invoices'],
    dataMapping: {
      jobs: {
        externalField: 'id',
        localField: 'external_job_id',
        fields: ['work_status', 'scheduled_start', 'scheduled_end', 'customer', 'address', 'total_amount']
      }
    }
  },
  jobber: {
    name: 'Jobber',
    type: 'field_service',
    authType: 'oauth2',
    baseUrl: 'https://api.getjobber.com',
    scopes: ['jobs', 'clients', 'invoices', 'quotes'],
    dataMapping: {
      jobs: {
        externalField: 'id',
        localField: 'external_job_id',
        fields: ['title', 'instructions', 'start_at', 'end_at', 'client', 'property']
      }
    }
  },
  quickbooks: {
    name: 'QuickBooks Online',
    type: 'accounting',
    authType: 'oauth2',
    baseUrl: 'https://quickbooks.api.intuit.com',
    scopes: ['com.intuit.quickbooks.accounting'],
    dataMapping: {
      invoices: {
        externalField: 'Id',
        localField: 'external_invoice_id',
        fields: ['DocNumber', 'TxnDate', 'TotalAmt', 'Line', 'CustomerRef']
      },
      items: {
        externalField: 'Id',
        localField: 'external_item_id',
        fields: ['Name', 'Description', 'UnitPrice', 'Type', 'PurchaseCost']
      },
      vendors: {
        externalField: 'Id',
        localField: 'external_vendor_id',
        fields: ['DisplayName', 'PrimaryEmailAddr', 'PrimaryPhone']
      }
    }
  },
  samsara: {
    name: 'Samsara Fleet',
    type: 'fleet_gps',
    authType: 'api_key',
    baseUrl: 'https://api.samsara.com',
    dataMapping: {
      vehicles: {
        externalField: 'id',
        localField: 'external_vehicle_id',
        fields: ['name', 'vin', 'make', 'model', 'year', 'licensePlate']
      },
      trips: {
        externalField: 'id',
        localField: 'external_trip_id',
        fields: ['startTime', 'endTime', 'startLocation', 'endLocation', 'distanceMeters', 'fuelConsumedMl']
      }
    }
  },
  verizon_connect: {
    name: 'Verizon Connect',
    type: 'fleet_gps',
    authType: 'oauth2',
    baseUrl: 'https://fim.api.verizonconnect.com',
    dataMapping: {
      vehicles: {
        externalField: 'vehicleId',
        localField: 'external_vehicle_id',
        fields: ['name', 'vin', 'licensePlate', 'fuelType', 'odometer']
      },
      trips: {
        externalField: 'tripId',
        localField: 'external_trip_id',
        fields: ['startTime', 'endTime', 'startAddress', 'endAddress', 'mileage', 'fuelUsed']
      }
    }
  },
  fleetio: {
    name: 'Fleetio',
    type: 'fleet_management',
    authType: 'api_key',
    baseUrl: 'https://secure.fleetio.com/api',
    dataMapping: {
      vehicles: {
        externalField: 'id',
        localField: 'external_vehicle_id',
        fields: ['name', 'vin', 'make', 'model', 'year', 'license_plate', 'fuel_type', 'current_meter_value']
      },
      fuel_entries: {
        externalField: 'id',
        localField: 'external_fuel_id',
        fields: ['date', 'vehicle_id', 'gallons', 'total_amount', 'odometer']
      }
    }
  }
};

/**
 * Get integration configuration for a provider
 */
function getProviderConfig(providerId) {
  return PROVIDERS[providerId] || null;
}

/**
 * List available integrations
 */
function listAvailableIntegrations() {
  return Object.entries(PROVIDERS).map(([id, config]) => ({
    id,
    name: config.name,
    type: config.type,
    authType: config.authType
  }));
}

/**
 * Save integration credentials for a company
 */
async function saveIntegration(companyId, providerId, credentials) {
  const config = getProviderConfig(providerId);
  if (!config) {
    throw new Error(`Unknown provider: ${providerId}`);
  }

  const { data, error } = await supabase
    .from('integrations')
    .upsert({
      company_id: companyId,
      provider: providerId,
      status: 'active',
      access_token: credentials.accessToken,
      refresh_token: credentials.refreshToken,
      token_expires_at: credentials.expiresAt,
      field_mappings: config.dataMapping,
      updated_at: new Date().toISOString()
    }, {
      onConflict: 'company_id,provider'
    })
    .select()
    .single();

  if (error) throw error;
  return data;
}

/**
 * Get company's active integrations
 */
async function getCompanyIntegrations(companyId) {
  const { data, error } = await supabase
    .from('integrations')
    .select('*')
    .eq('company_id', companyId);

  if (error) throw error;

  return data.map(int => ({
    ...int,
    providerConfig: PROVIDERS[int.provider],
    access_token: undefined, // Don't expose tokens
    refresh_token: undefined
  }));
}

/**
 * Sync data from an integration
 * This is a framework - actual implementation depends on provider APIs
 */
async function syncIntegration(integrationId, syncType = 'incremental') {
  const { data: integration, error } = await supabase
    .from('integrations')
    .select('*')
    .eq('id', integrationId)
    .single();

  if (error) throw error;
  if (!integration) throw new Error('Integration not found');

  const config = PROVIDERS[integration.provider];
  if (!config) throw new Error('Unknown provider');

  // Log sync start
  const { data: syncLog } = await supabase
    .from('integration_sync_logs')
    .insert({
      integration_id: integrationId,
      sync_type: syncType,
      status: 'started',
      started_at: new Date().toISOString()
    })
    .select()
    .single();

  try {
    // In production, this would call the actual provider API
    // For now, return a placeholder
    const results = {
      provider: integration.provider,
      syncType,
      recordsSynced: 0,
      recordsFailed: 0,
      message: `Sync framework ready. Implement ${config.name} API calls.`
    };

    // Update sync log
    await supabase
      .from('integration_sync_logs')
      .update({
        status: 'completed',
        records_synced: results.recordsSynced,
        records_failed: results.recordsFailed,
        completed_at: new Date().toISOString()
      })
      .eq('id', syncLog.id);

    // Update integration last sync
    await supabase
      .from('integrations')
      .update({
        last_sync_at: new Date().toISOString()
      })
      .eq('id', integrationId);

    return results;

  } catch (syncError) {
    // Log error
    await supabase
      .from('integration_sync_logs')
      .update({
        status: 'failed',
        error_message: syncError.message,
        completed_at: new Date().toISOString()
      })
      .eq('id', syncLog.id);

    throw syncError;
  }
}

/**
 * Map external data to ProofGreen format
 */
function mapExternalData(providerId, dataType, externalData) {
  const config = PROVIDERS[providerId];
  if (!config || !config.dataMapping[dataType]) {
    throw new Error(`No mapping for ${providerId}/${dataType}`);
  }

  const mapping = config.dataMapping[dataType];
  const mappedData = {};

  mapping.fields.forEach(field => {
    if (externalData[field] !== undefined) {
      mappedData[field] = externalData[field];
    }
  });

  mappedData[mapping.localField] = externalData[mapping.externalField];

  return mappedData;
}

/**
 * Import jobs from external system
 */
async function importJobs(companyId, providerId, jobs) {
  const mappedJobs = jobs.map(job => mapExternalData(providerId, 'jobs', job));

  // Transform to ProofGreen job format
  const proofGreenJobs = mappedJobs.map(job => ({
    company_id: companyId,
    external_job_id: job.external_job_id,
    external_source: providerId,
    // Map other fields based on provider
    status: 'imported',
    imported_at: new Date().toISOString()
  }));

  const { data, error } = await supabase
    .from('jobs')
    .upsert(proofGreenJobs, {
      onConflict: 'company_id,external_job_id'
    })
    .select();

  if (error) throw error;
  return data;
}

/**
 * Import vehicle/trip data from fleet system
 */
async function importFleetData(companyId, providerId, fleetData) {
  const results = {
    vehiclesImported: 0,
    tripsImported: 0,
    errors: []
  };

  // Import vehicles
  if (fleetData.vehicles) {
    for (const vehicle of fleetData.vehicles) {
      try {
        const { error } = await supabase
          .from('vehicles')
          .upsert({
            company_id: companyId,
            external_vehicle_id: vehicle.id,
            external_source: providerId,
            make: vehicle.make,
            model: vehicle.model,
            year: vehicle.year,
            vin: vehicle.vin,
            license_plate: vehicle.licensePlate,
            fuel_type: vehicle.fuelType || 'gasoline',
            current_odometer: vehicle.odometer,
            updated_at: new Date().toISOString()
          }, {
            onConflict: 'company_id,vin'
          });

        if (error) throw error;
        results.vehiclesImported++;
      } catch (err) {
        results.errors.push({ type: 'vehicle', id: vehicle.id, error: err.message });
      }
    }
  }

  // Import trips
  if (fleetData.trips) {
    for (const trip of fleetData.trips) {
      try {
        // Calculate emissions from trip data
        const distanceMiles = trip.distanceMeters ? trip.distanceMeters / 1609.34 : trip.mileage || 0;
        const fuelGallons = trip.fuelConsumedMl ? trip.fuelConsumedMl / 3785.41 : trip.fuelUsed || 0;
        const co2Lbs = fuelGallons * 19.6; // Gasoline emission factor

        const { error } = await supabase
          .from('service_trips')
          .insert({
            vehicle_id: trip.vehicleId,
            origin_address: trip.startAddress || trip.startLocation,
            destination_address: trip.endAddress || trip.endLocation,
            distance_miles: distanceMiles,
            fuel_used_gallons: fuelGallons,
            co2_emissions_lbs: co2Lbs,
            start_time: trip.startTime,
            end_time: trip.endTime,
            external_trip_id: trip.id,
            external_source: providerId
          });

        if (error) throw error;
        results.tripsImported++;
      } catch (err) {
        results.errors.push({ type: 'trip', id: trip.id, error: err.message });
      }
    }
  }

  return results;
}

/**
 * Generate OAuth authorization URL
 */
function getAuthorizationUrl(providerId, redirectUri, state) {
  const config = PROVIDERS[providerId];
  if (!config || config.authType !== 'oauth2') {
    throw new Error(`OAuth not supported for ${providerId}`);
  }

  // These would be configured per provider
  const oauthConfigs = {
    servicetitan: {
      authUrl: 'https://auth.servicetitan.io/connect/authorize',
      clientId: process.env.SERVICETITAN_CLIENT_ID
    },
    quickbooks: {
      authUrl: 'https://appcenter.intuit.com/connect/oauth2',
      clientId: process.env.QUICKBOOKS_CLIENT_ID
    },
    housecall_pro: {
      authUrl: 'https://api.housecallpro.com/oauth/authorize',
      clientId: process.env.HOUSECALLPRO_CLIENT_ID
    },
    jobber: {
      authUrl: 'https://api.getjobber.com/api/oauth/authorize',
      clientId: process.env.JOBBER_CLIENT_ID
    }
  };

  const oauth = oauthConfigs[providerId];
  if (!oauth || !oauth.clientId) {
    throw new Error(`OAuth not configured for ${providerId}`);
  }

  const params = new URLSearchParams({
    client_id: oauth.clientId,
    redirect_uri: redirectUri,
    response_type: 'code',
    scope: config.scopes.join(' '),
    state
  });

  return `${oauth.authUrl}?${params.toString()}`;
}

module.exports = {
  PROVIDERS,
  getProviderConfig,
  listAvailableIntegrations,
  saveIntegration,
  getCompanyIntegrations,
  syncIntegration,
  mapExternalData,
  importJobs,
  importFleetData,
  getAuthorizationUrl
};
