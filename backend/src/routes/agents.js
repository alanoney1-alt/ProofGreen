/**
 * Agent API Routes
 * Multi-agent orchestration endpoints
 */

const express = require('express');
const router = express.Router();
const multer = require('multer');
const agentOrchestrator = require('../services/agentOrchestrator');
const cvSurveyAgent = require('../services/cvSurveyAgent');
const carbonAPI = require('../services/carbonAPI');
const greenVerifier = require('../services/greenVerifier');
const taxCreditMatcher = require('../services/taxCreditMatcher');

// Configure multer for image uploads
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024 }
});

// ==========================================
// ORCHESTRATOR ENDPOINT
// ==========================================

/**
 * Main orchestrator endpoint - routes to appropriate agent
 */
router.post('/orchestrate', async (req, res) => {
  try {
    const result = await agentOrchestrator.orchestrate(req.body);
    res.json({ success: true, ...result });
  } catch (error) {
    console.error('Orchestrator error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get available agents and their capabilities
 */
router.get('/available', (req, res) => {
  res.json({
    success: true,
    agents: agentOrchestrator.AGENT_TYPES
  });
});

// ==========================================
// INTAKE AGENT ENDPOINTS
// ==========================================

/**
 * Analyze room images for moving survey
 */
router.post('/intake/survey', upload.array('images', 20), async (req, res) => {
  try {
    const images = req.files.map(file => ({
      base64: file.buffer.toString('base64'),
      mimeType: file.mimetype,
      roomType: req.body[`room_${file.originalname}`] || 'unknown'
    }));

    const surveyResult = await cvSurveyAgent.analyzeHomeSurvey(images);

    // Generate quote if move details provided
    let quote = null;
    if (req.body.origin_address && req.body.destination_address) {
      quote = cvSurveyAgent.generateMovingQuote(surveyResult, {
        origin_address: req.body.origin_address,
        destination_address: req.body.destination_address,
        distance_miles: parseFloat(req.body.distance_miles) || 50,
        move_date: req.body.move_date,
        floor_origin: parseInt(req.body.floor_origin) || 1,
        floor_destination: parseInt(req.body.floor_destination) || 1,
        has_elevator_origin: req.body.has_elevator_origin === 'true',
        has_elevator_destination: req.body.has_elevator_destination === 'true'
      });
    }

    res.json({
      success: true,
      survey: surveyResult,
      quote
    });
  } catch (error) {
    console.error('Survey error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Analyze single room image
 */
router.post('/intake/analyze-room', upload.single('image'), async (req, res) => {
  try {
    const base64 = req.file.buffer.toString('base64');
    const result = await cvSurveyAgent.analyzeRoomImage(
      base64,
      req.file.mimetype,
      req.body.room_type
    );

    res.json({ success: true, analysis: result });
  } catch (error) {
    console.error('Room analysis error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Analyze equipment image
 */
router.post('/intake/analyze-equipment', upload.single('image'), async (req, res) => {
  try {
    const base64 = req.file.buffer.toString('base64');
    const result = await cvSurveyAgent.analyzeEquipmentImage(
      base64,
      req.body.equipment_type || 'unknown',
      req.file.mimetype
    );

    res.json({ success: true, ...result });
  } catch (error) {
    console.error('Equipment analysis error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Generate instant quote from inventory
 */
router.post('/intake/quote', async (req, res) => {
  try {
    const result = await agentOrchestrator.handleIntakeRequest(
      'instant_quote',
      req.body,
      null
    );

    res.json({ success: true, ...result });
  } catch (error) {
    console.error('Quote error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Customer chat endpoint
 */
router.post('/intake/chat', async (req, res) => {
  try {
    const { message, history, context } = req.body;

    const result = await agentOrchestrator.handleIntakeRequest(
      'chat',
      { message, context },
      history
    );

    res.json({ success: true, ...result });
  } catch (error) {
    console.error('Chat error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// ==========================================
// OPS AGENT ENDPOINTS
// ==========================================

/**
 * Optimize route
 */
router.post('/ops/optimize-route', async (req, res) => {
  try {
    const result = await agentOrchestrator.handleOpsRequest(
      'optimize_route',
      req.body,
      req.body.company_id
    );

    res.json({ success: true, ...result });
  } catch (error) {
    console.error('Route optimization error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get fleet status
 */
router.get('/ops/fleet/:companyId', async (req, res) => {
  try {
    const result = await agentOrchestrator.handleOpsRequest(
      'track_fleet',
      {},
      req.params.companyId
    );

    res.json({ success: true, ...result });
  } catch (error) {
    console.error('Fleet tracking error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Analyze empty miles
 */
router.post('/ops/empty-miles', async (req, res) => {
  try {
    const result = await agentOrchestrator.handleOpsRequest(
      'empty_miles_analysis',
      req.body,
      req.body.company_id
    );

    res.json({ success: true, ...result });
  } catch (error) {
    console.error('Empty miles analysis error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// ==========================================
// GREEN VERIFIER ENDPOINTS
// ==========================================

/**
 * Calculate job emissions
 */
router.post('/verifier/calculate', async (req, res) => {
  try {
    const emissions = await carbonAPI.calculateJobEmissions(req.body);
    res.json({ success: true, emissions });
  } catch (error) {
    console.error('Emissions calculation error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Calculate freight emissions
 */
router.post('/verifier/freight', async (req, res) => {
  try {
    const emissions = await carbonAPI.calculateFreightEmissions(req.body);
    res.json({ success: true, emissions });
  } catch (error) {
    console.error('Freight calculation error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Generate certificate
 */
router.post('/verifier/certificate', async (req, res) => {
  try {
    const result = await agentOrchestrator.handleVerifierRequest(
      'generate_certificate',
      req.body,
      req.body.company_id
    );

    res.json({ success: true, ...result });
  } catch (error) {
    console.error('Certificate generation error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Verify certificate
 */
router.get('/verifier/verify/:certificateId', async (req, res) => {
  try {
    const verification = await greenVerifier.verifyCertificate(req.params.certificateId);
    res.json({ success: true, ...verification });
  } catch (error) {
    console.error('Certificate verification error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get company certificates
 */
router.get('/verifier/certificates/:companyId', async (req, res) => {
  try {
    const certificates = await greenVerifier.getCompanyCertificates(req.params.companyId);
    res.json({ success: true, certificates });
  } catch (error) {
    console.error('Get certificates error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Generate annual ESG report
 */
router.get('/verifier/annual-report/:companyId/:year', async (req, res) => {
  try {
    const report = await greenVerifier.generateAnnualESGReport(
      req.params.companyId,
      parseInt(req.params.year)
    );

    res.json({ success: true, report });
  } catch (error) {
    console.error('Annual report error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get emission factors reference
 */
router.get('/verifier/emission-factors', (req, res) => {
  res.json({
    success: true,
    factors: carbonAPI.getEmissionFactors()
  });
});

// ==========================================
// TAX CREDIT ENDPOINTS
// ==========================================

/**
 * Analyze company for tax credits
 */
router.get('/tax/analyze/:companyId', async (req, res) => {
  try {
    const analysis = await taxCreditMatcher.analyzeCompanyForCredits(
      req.params.companyId,
      parseInt(req.query.year) || new Date().getFullYear()
    );

    res.json({ success: true, analysis });
  } catch (error) {
    console.error('Tax analysis error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Calculate specific credit
 */
router.post('/tax/calculate', (req, res) => {
  try {
    const { credit_type, transaction } = req.body;
    const credit = taxCreditMatcher.calculateCredit(credit_type, transaction);

    res.json({ success: true, credit });
  } catch (error) {
    console.error('Credit calculation error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Generate tax credit report
 */
router.get('/tax/report/:companyId', async (req, res) => {
  try {
    const report = await taxCreditMatcher.generateTaxCreditReport(
      req.params.companyId,
      parseInt(req.query.year) || new Date().getFullYear()
    );

    res.json({ success: true, report });
  } catch (error) {
    console.error('Tax report error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get available credits for equipment type
 */
router.get('/tax/equipment-credits/:equipmentType', (req, res) => {
  try {
    const credits = taxCreditMatcher.getCreditsForEquipment(req.params.equipmentType);
    res.json({ success: true, credits });
  } catch (error) {
    console.error('Equipment credits error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get available federal credits
 */
router.get('/tax/federal-credits', (req, res) => {
  res.json({
    success: true,
    credits: taxCreditMatcher.FEDERAL_TAX_CREDITS
  });
});

/**
 * Get state incentives
 */
router.get('/tax/state-incentives/:state', (req, res) => {
  const incentives = taxCreditMatcher.STATE_INCENTIVES[req.params.state.toUpperCase()];

  res.json({
    success: true,
    state: req.params.state.toUpperCase(),
    incentives: incentives || {}
  });
});

module.exports = router;
