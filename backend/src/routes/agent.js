const express = require('express');
const router = express.Router();
const multer = require('multer');
const { body, validationResult } = require('express-validator');
const { supabase } = require('../utils/supabase');
const { authenticate } = require('../middleware/auth');
const { logger } = require('../utils/logger');
const {
  processJobPhoto,
  analyzePhoto,
  identifyJobType,
  calculateCarbon,
  checkMilestones,
  generateReport,
  checkESGCompliance
} = require('../agents/esgAgent');

// Configure multer for photo uploads
const storage = multer.memoryStorage();
const upload = multer({
  storage,
  limits: { fileSize: 10 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    if (file.mimetype.startsWith('image/')) {
      cb(null, true);
    } else {
      cb(new Error('Only image files are allowed'));
    }
  }
});

// POST /api/agent/process
// Full autonomous processing pipeline
router.post('/process', authenticate, upload.single('photo'), async (req, res) => {
  try {
    const { jobId } = req.body;
    let photoBase64;

    if (req.file) {
      photoBase64 = req.file.buffer.toString('base64');
    } else if (req.body.photoBase64) {
      photoBase64 = req.body.photoBase64;
    } else {
      return res.status(400).json({ error: 'Photo is required' });
    }

    if (!jobId) {
      return res.status(400).json({ error: 'Job ID is required' });
    }

    // Verify job belongs to company
    const { data: job } = await supabase
      .from('jobs')
      .select('id')
      .eq('id', jobId)
      .eq('company_id', req.companyId)
      .single();

    if (!job) {
      return res.status(404).json({ error: 'Job not found' });
    }

    // Check AI analysis limits
    const { data: subscription } = await supabase
      .from('subscriptions')
      .select('pricing_plans(ai_analysis_limit)')
      .eq('company_id', req.companyId)
      .in('status', ['active', 'trialing'])
      .single();

    if (subscription?.pricing_plans?.ai_analysis_limit) {
      const { count } = await supabase
        .from('agent_executions')
        .select('*', { count: 'exact', head: true })
        .eq('company_id', req.companyId)
        .eq('function_name', 'processJobPhoto')
        .gte('started_at', new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString());

      if (count >= subscription.pricing_plans.ai_analysis_limit) {
        return res.status(403).json({ error: 'Monthly AI analysis limit reached for your plan' });
      }
    }

    // Process asynchronously
    processJobPhoto(jobId, photoBase64, req.companyId)
      .then(result => {
        logger.info(`Job ${jobId} processing completed successfully`);
      })
      .catch(error => {
        logger.error(`Job ${jobId} processing failed:`, error);
      });

    res.json({
      message: 'Processing started',
      jobId,
      status: 'processing'
    });
  } catch (error) {
    logger.error('Agent process error:', error);
    res.status(500).json({ error: 'Failed to start processing' });
  }
});

// POST /api/agent/analyze-photo
// Step 1 only: Analyze a photo
router.post('/analyze-photo', authenticate, upload.single('photo'), async (req, res) => {
  try {
    let photoBase64;

    if (req.file) {
      photoBase64 = req.file.buffer.toString('base64');
    } else if (req.body.photoBase64) {
      photoBase64 = req.body.photoBase64;
    } else {
      return res.status(400).json({ error: 'Photo is required' });
    }

    const result = await analyzePhoto(photoBase64, req.body.jobId, req.companyId);

    res.json({
      success: true,
      ...result
    });
  } catch (error) {
    logger.error('Photo analysis error:', error);
    res.status(500).json({ error: 'Photo analysis failed' });
  }
});

// POST /api/agent/identify-job-type
// Step 2: Identify job type from items
router.post('/identify-job-type', authenticate, [
  body('items').isArray({ min: 1 })
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const { items, jobId } = req.body;
    const result = await identifyJobType(items, jobId, req.companyId);

    res.json({
      success: true,
      ...result
    });
  } catch (error) {
    logger.error('Job type identification error:', error);
    res.status(500).json({ error: 'Job type identification failed' });
  }
});

// POST /api/agent/calculate-carbon
// Step 3: Calculate carbon metrics
router.post('/calculate-carbon', authenticate, [
  body('jobId').notEmpty(),
  body('items').isArray({ min: 1 })
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const { jobId, items } = req.body;

    // Verify job belongs to company
    const { data: job } = await supabase
      .from('jobs')
      .select('id')
      .eq('id', jobId)
      .eq('company_id', req.companyId)
      .single();

    if (!job) {
      return res.status(404).json({ error: 'Job not found' });
    }

    const result = await calculateCarbon(jobId, items, req.companyId);

    res.json({
      success: true,
      ...result
    });
  } catch (error) {
    logger.error('Carbon calculation error:', error);
    res.status(500).json({ error: 'Carbon calculation failed' });
  }
});

// POST /api/agent/check-milestones
// Step 4: Check milestones
router.post('/check-milestones', authenticate, async (req, res) => {
  try {
    const result = await checkMilestones(req.companyId, req.body.jobId);

    res.json({
      success: true,
      ...result
    });
  } catch (error) {
    logger.error('Milestone check error:', error);
    res.status(500).json({ error: 'Milestone check failed' });
  }
});

// POST /api/agent/generate-report
// Step 5: Generate report
router.post('/generate-report', authenticate, [
  body('jobId').notEmpty()
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const { jobId } = req.body;

    // Verify job belongs to company
    const { data: job } = await supabase
      .from('jobs')
      .select('id')
      .eq('id', jobId)
      .eq('company_id', req.companyId)
      .single();

    if (!job) {
      return res.status(404).json({ error: 'Job not found' });
    }

    const result = await generateReport(jobId, req.companyId);

    res.json({
      success: true,
      ...result
    });
  } catch (error) {
    logger.error('Report generation error:', error);
    res.status(500).json({ error: 'Report generation failed' });
  }
});

// POST /api/agent/check-esg-compliance
// Step 6: Check ESG compliance
router.post('/check-esg-compliance', authenticate, [
  body('jobId').notEmpty()
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const { jobId } = req.body;

    // Verify job belongs to company
    const { data: job } = await supabase
      .from('jobs')
      .select('id, vertical_id')
      .eq('id', jobId)
      .eq('company_id', req.companyId)
      .single();

    if (!job) {
      return res.status(404).json({ error: 'Job not found' });
    }

    const result = await checkESGCompliance(jobId, req.companyId, job.vertical_id);

    res.json({
      success: true,
      ...result
    });
  } catch (error) {
    logger.error('ESG compliance check error:', error);
    res.status(500).json({ error: 'ESG compliance check failed' });
  }
});

// GET /api/agent/executions
// Get agent execution history
router.get('/executions', authenticate, async (req, res) => {
  try {
    const { jobId, limit = 50 } = req.query;

    let query = supabase
      .from('agent_executions')
      .select('*')
      .eq('company_id', req.companyId)
      .order('started_at', { ascending: false })
      .limit(limit);

    if (jobId) {
      query = query.eq('job_id', jobId);
    }

    const { data: executions, error } = await query;

    if (error) {
      return res.status(500).json({ error: 'Failed to fetch executions' });
    }

    res.json({ executions });
  } catch (error) {
    logger.error('Get executions error:', error);
    res.status(500).json({ error: 'Failed to fetch executions' });
  }
});

// GET /api/agent/status/:jobId
// Get processing status for a job
router.get('/status/:jobId', authenticate, async (req, res) => {
  try {
    const { jobId } = req.params;

    // Verify job belongs to company
    const { data: job } = await supabase
      .from('jobs')
      .select('id, ai_processed, ai_processed_at, ai_confidence')
      .eq('id', jobId)
      .eq('company_id', req.companyId)
      .single();

    if (!job) {
      return res.status(404).json({ error: 'Job not found' });
    }

    // Get latest execution
    const { data: execution } = await supabase
      .from('agent_executions')
      .select('*')
      .eq('job_id', jobId)
      .eq('function_name', 'processJobPhoto')
      .order('started_at', { ascending: false })
      .limit(1)
      .single();

    res.json({
      jobId,
      processed: job.ai_processed,
      processedAt: job.ai_processed_at,
      confidence: job.ai_confidence,
      latestExecution: execution
    });
  } catch (error) {
    logger.error('Get status error:', error);
    res.status(500).json({ error: 'Failed to fetch status' });
  }
});

module.exports = router;
