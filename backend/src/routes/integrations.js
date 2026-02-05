/**
 * External Integrations API Routes
 * ServiceTitan, QuickBooks, Fleet GPS, etc.
 */

const express = require('express');
const router = express.Router();
const integrations = require('../services/integrations');

/**
 * List available integrations
 */
router.get('/available', (req, res) => {
  try {
    const available = integrations.listAvailableIntegrations();
    res.json({ success: true, integrations: available });
  } catch (error) {
    console.error('List integrations error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get provider configuration
 */
router.get('/provider/:providerId', (req, res) => {
  try {
    const config = integrations.getProviderConfig(req.params.providerId);

    if (!config) {
      return res.status(404).json({
        success: false,
        error: 'Provider not found'
      });
    }

    // Don't expose sensitive fields
    const safeConfig = {
      name: config.name,
      type: config.type,
      authType: config.authType,
      scopes: config.scopes,
      dataMapping: Object.keys(config.dataMapping)
    };

    res.json({ success: true, provider: safeConfig });
  } catch (error) {
    console.error('Provider config error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get company's active integrations
 */
router.get('/company/:companyId', async (req, res) => {
  try {
    const companyIntegrations = await integrations.getCompanyIntegrations(
      req.params.companyId
    );

    res.json({ success: true, integrations: companyIntegrations });
  } catch (error) {
    console.error('Company integrations error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get OAuth authorization URL
 */
router.post('/oauth/authorize', (req, res) => {
  try {
    const { providerId, redirectUri, state } = req.body;

    if (!providerId || !redirectUri) {
      return res.status(400).json({
        success: false,
        error: 'providerId and redirectUri are required'
      });
    }

    const authUrl = integrations.getAuthorizationUrl(
      providerId,
      redirectUri,
      state || Math.random().toString(36).substring(7)
    );

    res.json({ success: true, authorizationUrl: authUrl });
  } catch (error) {
    console.error('OAuth authorize error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Save integration credentials
 */
router.post('/connect', async (req, res) => {
  try {
    const { companyId, providerId, credentials } = req.body;

    if (!companyId || !providerId || !credentials) {
      return res.status(400).json({
        success: false,
        error: 'companyId, providerId, and credentials are required'
      });
    }

    const integration = await integrations.saveIntegration(
      companyId,
      providerId,
      credentials
    );

    res.json({ success: true, integration });
  } catch (error) {
    console.error('Connect integration error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Sync data from integration
 */
router.post('/sync/:integrationId', async (req, res) => {
  try {
    const { syncType = 'incremental' } = req.body;

    const result = await integrations.syncIntegration(
      req.params.integrationId,
      syncType
    );

    res.json({ success: true, result });
  } catch (error) {
    console.error('Sync integration error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Import jobs from external system
 */
router.post('/import/jobs', async (req, res) => {
  try {
    const { companyId, providerId, jobs } = req.body;

    if (!companyId || !providerId || !jobs) {
      return res.status(400).json({
        success: false,
        error: 'companyId, providerId, and jobs array are required'
      });
    }

    const result = await integrations.importJobs(companyId, providerId, jobs);

    res.json({
      success: true,
      imported: result.length,
      jobs: result
    });
  } catch (error) {
    console.error('Import jobs error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Import fleet/vehicle data
 */
router.post('/import/fleet', async (req, res) => {
  try {
    const { companyId, providerId, fleetData } = req.body;

    if (!companyId || !providerId || !fleetData) {
      return res.status(400).json({
        success: false,
        error: 'companyId, providerId, and fleetData are required'
      });
    }

    const result = await integrations.importFleetData(companyId, providerId, fleetData);

    res.json({ success: true, result });
  } catch (error) {
    console.error('Import fleet error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Webhook endpoint for provider callbacks
 */
router.post('/webhook/:providerId', async (req, res) => {
  try {
    const { providerId } = req.params;
    const payload = req.body;

    console.log(`Webhook received from ${providerId}:`, JSON.stringify(payload).substring(0, 500));

    // In production, process the webhook based on provider
    // For now, just acknowledge receipt

    res.json({ success: true, received: true });
  } catch (error) {
    console.error('Webhook error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Disconnect integration
 */
router.delete('/:integrationId', async (req, res) => {
  try {
    const { createClient } = require('@supabase/supabase-js');
    const supabase = createClient(
      process.env.SUPABASE_URL,
      process.env.SUPABASE_SERVICE_KEY
    );

    const { error } = await supabase
      .from('integrations')
      .update({
        status: 'disconnected',
        access_token: null,
        refresh_token: null,
        updated_at: new Date().toISOString()
      })
      .eq('id', req.params.integrationId);

    if (error) throw error;

    res.json({ success: true, disconnected: true });
  } catch (error) {
    console.error('Disconnect error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

module.exports = router;
