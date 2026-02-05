/**
 * Telematics and Route Optimization API Routes
 */

const express = require('express');
const router = express.Router();
const telematicsIntegration = require('../services/telematicsIntegration');
const routeOptimizer = require('../services/routeOptimizer');

// ==========================================
// TELEMATICS ENDPOINTS
// ==========================================

/**
 * Get supported telematics providers
 */
router.get('/providers', (req, res) => {
  res.json({
    success: true,
    providers: Object.entries(telematicsIntegration.PROVIDERS).map(([key, value]) => ({
      id: key,
      ...value
    }))
  });
});

/**
 * Sync vehicles from telematics provider
 */
router.post('/sync/vehicles', async (req, res) => {
  try {
    const { company_id, provider } = req.body;

    if (!company_id || !provider) {
      return res.status(400).json({
        success: false,
        error: 'company_id and provider are required'
      });
    }

    const result = await telematicsIntegration.syncVehicles(company_id, provider);
    res.json({ success: true, ...result });
  } catch (error) {
    console.error('Vehicle sync error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Sync trip data from telematics
 */
router.post('/sync/trips', async (req, res) => {
  try {
    const { company_id, provider, start_date, end_date } = req.body;

    if (!company_id || !provider) {
      return res.status(400).json({
        success: false,
        error: 'company_id and provider are required'
      });
    }

    const startTime = start_date ? new Date(start_date) : new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
    const endTime = end_date ? new Date(end_date) : new Date();

    const result = await telematicsIntegration.syncTrips(company_id, provider, startTime, endTime);
    res.json({ success: true, ...result });
  } catch (error) {
    console.error('Trip sync error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get live fleet status
 */
router.get('/fleet/:companyId', async (req, res) => {
  try {
    const { provider } = req.query;
    const result = await telematicsIntegration.getFleetStatus(
      req.params.companyId,
      provider || 'demo'
    );
    res.json({ success: true, ...result });
  } catch (error) {
    console.error('Fleet status error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get fleet emissions summary
 */
router.get('/emissions/:companyId', async (req, res) => {
  try {
    const { start_date, end_date } = req.query;

    const startDate = start_date || new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
    const endDate = end_date || new Date().toISOString();

    const result = await telematicsIntegration.getFleetEmissionsSummary(
      req.params.companyId,
      startDate,
      endDate
    );

    res.json({ success: true, ...result });
  } catch (error) {
    console.error('Emissions summary error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// ==========================================
// ROUTE OPTIMIZATION ENDPOINTS
// ==========================================

/**
 * Optimize route for jobs
 */
router.post('/optimize', async (req, res) => {
  try {
    const {
      company_id,
      jobs,
      start_location,
      return_to_start,
      vehicle_type,
      fuel_type
    } = req.body;

    if (!company_id || !jobs?.length) {
      return res.status(400).json({
        success: false,
        error: 'company_id and jobs array are required'
      });
    }

    const result = await routeOptimizer.optimizeRoute(company_id, jobs, {
      startLocation: start_location,
      returnToStart: return_to_start !== false,
      vehicleType: vehicle_type || 'van',
      fuelType: fuel_type || 'gasoline'
    });

    res.json({ success: true, ...result });
  } catch (error) {
    console.error('Route optimization error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get optimized daily schedule
 */
router.get('/daily-schedule/:companyId/:date', async (req, res) => {
  try {
    const result = await routeOptimizer.getDailyOptimizedSchedule(
      req.params.companyId,
      req.params.date
    );

    res.json({ success: true, ...result });
  } catch (error) {
    console.error('Daily schedule error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Analyze empty miles
 */
router.post('/empty-miles', async (req, res) => {
  try {
    const { company_id, start_date, end_date } = req.body;

    if (!company_id) {
      return res.status(400).json({
        success: false,
        error: 'company_id is required'
      });
    }

    const startDate = start_date || new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
    const endDate = end_date || new Date().toISOString();

    const result = await routeOptimizer.analyzeEmptyMiles(company_id, startDate, endDate);
    res.json({ success: true, ...result });
  } catch (error) {
    console.error('Empty miles analysis error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Calculate distance between two points
 */
router.post('/distance', (req, res) => {
  try {
    const { origin, destination } = req.body;

    if (!origin?.latitude || !destination?.latitude) {
      return res.status(400).json({
        success: false,
        error: 'origin and destination coordinates required'
      });
    }

    const distance = routeOptimizer.calculateDistance(
      origin.latitude,
      origin.longitude,
      destination.latitude,
      destination.longitude
    );

    const travelTime = routeOptimizer.estimateTravelTime(distance);

    res.json({
      success: true,
      distance_miles: Math.round(distance * 100) / 100,
      estimated_time_minutes: travelTime,
      estimated_time_formatted: routeOptimizer.formatDuration(travelTime)
    });
  } catch (error) {
    console.error('Distance calculation error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get vehicle efficiency data
 */
router.get('/vehicle-efficiency', (req, res) => {
  res.json({
    success: true,
    fuel_efficiency: routeOptimizer.FUEL_EFFICIENCY,
    vehicle_capacities: routeOptimizer.VEHICLE_CAPACITIES
  });
});

module.exports = router;
