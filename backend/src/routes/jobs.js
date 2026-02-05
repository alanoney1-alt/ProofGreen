const express = require('express');
const router = express.Router();
const { body, query, validationResult } = require('express-validator');
const multer = require('multer');
const { supabase } = require('../utils/supabase');
const { authenticate } = require('../middleware/auth');
const { logger } = require('../utils/logger');
const { processJobPhoto } = require('../agents/esgAgent');

// Configure multer for photo uploads
const storage = multer.memoryStorage();
const upload = multer({
  storage,
  limits: { fileSize: 10 * 1024 * 1024 }, // 10MB limit
  fileFilter: (req, file, cb) => {
    if (file.mimetype.startsWith('image/')) {
      cb(null, true);
    } else {
      cb(new Error('Only image files are allowed'));
    }
  }
});

// GET /api/jobs
router.get('/', authenticate, [
  query('status').optional().isIn(['pending', 'in_progress', 'completed', 'cancelled']),
  query('limit').optional().isInt({ min: 1, max: 100 }),
  query('offset').optional().isInt({ min: 0 })
], async (req, res) => {
  try {
    const { status, limit = 20, offset = 0, startDate, endDate, verticalId } = req.query;

    let queryBuilder = supabase
      .from('jobs')
      .select(`
        *,
        verticals (*),
        job_items (*)
      `, { count: 'exact' })
      .eq('company_id', req.companyId)
      .order('created_at', { ascending: false })
      .range(offset, offset + limit - 1);

    if (status) {
      queryBuilder = queryBuilder.eq('status', status);
    }

    if (startDate) {
      queryBuilder = queryBuilder.gte('scheduled_date', startDate);
    }

    if (endDate) {
      queryBuilder = queryBuilder.lte('scheduled_date', endDate);
    }

    if (verticalId) {
      queryBuilder = queryBuilder.eq('vertical_id', verticalId);
    }

    const { data: jobs, error, count } = await queryBuilder;

    if (error) {
      logger.error('Jobs fetch error:', error);
      return res.status(500).json({ error: 'Failed to fetch jobs' });
    }

    res.json({
      jobs,
      pagination: {
        total: count,
        limit: parseInt(limit),
        offset: parseInt(offset)
      }
    });
  } catch (error) {
    logger.error('Get jobs error:', error);
    res.status(500).json({ error: 'Failed to fetch jobs' });
  }
});

// GET /api/jobs/:id
router.get('/:id', authenticate, async (req, res) => {
  try {
    const { id } = req.params;

    const { data: job, error } = await supabase
      .from('jobs')
      .select(`
        *,
        verticals (*),
        job_items (*),
        users (id, first_name, last_name, email),
        esg_reports (*)
      `)
      .eq('id', id)
      .eq('company_id', req.companyId)
      .single();

    if (error || !job) {
      return res.status(404).json({ error: 'Job not found' });
    }

    res.json({ job });
  } catch (error) {
    logger.error('Get job error:', error);
    res.status(500).json({ error: 'Failed to fetch job' });
  }
});

// POST /api/jobs
router.post('/', authenticate, [
  body('title').trim().notEmpty(),
  body('customerName').optional().trim(),
  body('scheduledDate').optional().isISO8601()
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    // Check subscription limits
    const { data: subscription } = await supabase
      .from('subscriptions')
      .select('pricing_plans(job_limit)')
      .eq('company_id', req.companyId)
      .in('status', ['active', 'trialing'])
      .single();

    if (subscription?.pricing_plans?.job_limit) {
      const { count } = await supabase
        .from('jobs')
        .select('*', { count: 'exact', head: true })
        .eq('company_id', req.companyId)
        .gte('created_at', new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString());

      if (count >= subscription.pricing_plans.job_limit) {
        return res.status(403).json({ error: 'Monthly job limit reached for your plan' });
      }
    }

    // Generate job number
    const { count: jobCount } = await supabase
      .from('jobs')
      .select('*', { count: 'exact', head: true })
      .eq('company_id', req.companyId);

    const jobNumber = `JOB-${String(jobCount + 1).padStart(5, '0')}`;

    const jobData = {
      company_id: req.companyId,
      job_number: jobNumber,
      title: req.body.title,
      description: req.body.description,
      vertical_id: req.body.verticalId,
      assigned_user_id: req.body.assignedUserId || req.user.id,
      customer_name: req.body.customerName,
      customer_email: req.body.customerEmail,
      customer_phone: req.body.customerPhone,
      address_line1: req.body.addressLine1,
      address_line2: req.body.addressLine2,
      city: req.body.city,
      state: req.body.state,
      zip_code: req.body.zipCode,
      scheduled_date: req.body.scheduledDate,
      scheduled_time_start: req.body.scheduledTimeStart,
      scheduled_time_end: req.body.scheduledTimeEnd,
      estimated_cost: req.body.estimatedCost,
      notes: req.body.notes,
      status: 'pending'
    };

    const { data: job, error } = await supabase
      .from('jobs')
      .insert(jobData)
      .select(`
        *,
        verticals (*)
      `)
      .single();

    if (error) {
      logger.error('Job creation error:', error);
      return res.status(500).json({ error: 'Failed to create job' });
    }

    logger.info(`Job created: ${job.job_number} for company ${req.companyId}`);

    res.status(201).json({ job });
  } catch (error) {
    logger.error('Create job error:', error);
    res.status(500).json({ error: 'Failed to create job' });
  }
});

// PUT /api/jobs/:id
router.put('/:id', authenticate, async (req, res) => {
  try {
    const { id } = req.params;

    // Verify job belongs to company
    const { data: existingJob } = await supabase
      .from('jobs')
      .select('id, status')
      .eq('id', id)
      .eq('company_id', req.companyId)
      .single();

    if (!existingJob) {
      return res.status(404).json({ error: 'Job not found' });
    }

    const updates = {};
    const allowedFields = [
      'title', 'description', 'status', 'vertical_id', 'assigned_user_id',
      'customer_name', 'customer_email', 'customer_phone',
      'address_line1', 'address_line2', 'city', 'state', 'zip_code',
      'scheduled_date', 'scheduled_time_start', 'scheduled_time_end',
      'estimated_cost', 'final_cost', 'notes'
    ];

    allowedFields.forEach(field => {
      const camelField = field.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
      if (req.body[camelField] !== undefined) {
        updates[field] = req.body[camelField];
      }
    });

    // Handle status change to completed
    if (updates.status === 'completed' && existingJob.status !== 'completed') {
      updates.completed_at = new Date().toISOString();
    }

    const { data: job, error } = await supabase
      .from('jobs')
      .update(updates)
      .eq('id', id)
      .select(`
        *,
        verticals (*),
        job_items (*)
      `)
      .single();

    if (error) {
      logger.error('Job update error:', error);
      return res.status(500).json({ error: 'Failed to update job' });
    }

    res.json({ job });
  } catch (error) {
    logger.error('Update job error:', error);
    res.status(500).json({ error: 'Failed to update job' });
  }
});

// POST /api/jobs/:id/photos
router.post('/:id/photos', authenticate, upload.array('photos', 10), async (req, res) => {
  try {
    const { id } = req.params;
    const { photoType = 'before' } = req.body;

    if (!req.files || req.files.length === 0) {
      return res.status(400).json({ error: 'No photos uploaded' });
    }

    // Verify job belongs to company
    const { data: job } = await supabase
      .from('jobs')
      .select('*')
      .eq('id', id)
      .eq('company_id', req.companyId)
      .single();

    if (!job) {
      return res.status(404).json({ error: 'Job not found' });
    }

    // Convert files to base64 for storage
    const photos = req.files.map(file => ({
      data: file.buffer.toString('base64'),
      mimeType: file.mimetype,
      filename: file.originalname,
      uploadedAt: new Date().toISOString()
    }));

    // Update job with photos
    const photoField = photoType === 'after' ? 'after_photos' : 'before_photos';
    const existingPhotos = job[photoField] || [];
    const updatedPhotos = [...existingPhotos, ...photos];

    await supabase
      .from('jobs')
      .update({ [photoField]: updatedPhotos })
      .eq('id', id);

    // Trigger AI processing for the first photo
    if (photos.length > 0) {
      // Process asynchronously
      processJobPhoto(id, photos[0].data, req.companyId)
        .catch(err => logger.error('Photo processing error:', err));
    }

    res.json({
      message: 'Photos uploaded successfully',
      photoCount: photos.length,
      processing: true
    });
  } catch (error) {
    logger.error('Photo upload error:', error);
    res.status(500).json({ error: 'Failed to upload photos' });
  }
});

// POST /api/jobs/:id/items
router.post('/:id/items', authenticate, [
  body('items').isArray({ min: 1 })
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const { id } = req.params;
    const { items } = req.body;

    // Verify job belongs to company
    const { data: job } = await supabase
      .from('jobs')
      .select('id')
      .eq('id', id)
      .eq('company_id', req.companyId)
      .single();

    if (!job) {
      return res.status(404).json({ error: 'Job not found' });
    }

    // Prepare items for insertion
    const itemRecords = items.map(item => ({
      job_id: id,
      name: item.name,
      category: item.category,
      subcategory: item.subcategory,
      quantity: item.quantity || 1,
      weight_lbs: item.weightLbs,
      disposal_method: item.disposalMethod,
      detected_by_ai: item.detectedByAi || false,
      ai_confidence: item.aiConfidence,
      notes: item.notes
    }));

    const { data: createdItems, error } = await supabase
      .from('job_items')
      .insert(itemRecords)
      .select();

    if (error) {
      logger.error('Items creation error:', error);
      return res.status(500).json({ error: 'Failed to add items' });
    }

    // Recalculate job metrics
    await recalculateJobMetrics(id);

    res.status(201).json({ items: createdItems });
  } catch (error) {
    logger.error('Add items error:', error);
    res.status(500).json({ error: 'Failed to add items' });
  }
});

// DELETE /api/jobs/:id/items/:itemId
router.delete('/:id/items/:itemId', authenticate, async (req, res) => {
  try {
    const { id, itemId } = req.params;

    // Verify job belongs to company
    const { data: job } = await supabase
      .from('jobs')
      .select('id')
      .eq('id', id)
      .eq('company_id', req.companyId)
      .single();

    if (!job) {
      return res.status(404).json({ error: 'Job not found' });
    }

    await supabase
      .from('job_items')
      .delete()
      .eq('id', itemId)
      .eq('job_id', id);

    // Recalculate job metrics
    await recalculateJobMetrics(id);

    res.json({ message: 'Item deleted successfully' });
  } catch (error) {
    logger.error('Delete item error:', error);
    res.status(500).json({ error: 'Failed to delete item' });
  }
});

// Helper function to recalculate job metrics
async function recalculateJobMetrics(jobId) {
  try {
    // Fetch all items for the job
    const { data: items } = await supabase
      .from('job_items')
      .select('*')
      .eq('job_id', jobId);

    if (!items || items.length === 0) {
      return;
    }

    // Calculate totals
    let totalWeight = 0;
    let recycledWeight = 0;
    let landfillWeight = 0;
    let donatedWeight = 0;
    let carbonOffset = 0;

    for (const item of items) {
      const weight = (item.weight_lbs || 0) * (item.quantity || 1);
      totalWeight += weight;

      switch (item.disposal_method) {
        case 'recycled':
          recycledWeight += weight;
          break;
        case 'donated':
        case 'reused':
          donatedWeight += weight;
          break;
        case 'landfill':
        default:
          landfillWeight += weight;
      }

      // Get carbon factor
      const { data: carbonFactor } = await supabase
        .from('carbon_factors')
        .select('*')
        .eq('category', item.category)
        .eq('subcategory', item.subcategory)
        .single();

      if (carbonFactor) {
        let factor = carbonFactor.landfill_factor;
        if (item.disposal_method === 'recycled') {
          factor = carbonFactor.landfill_factor - carbonFactor.recycle_factor;
        } else if (item.disposal_method === 'donated' || item.disposal_method === 'reused') {
          factor = carbonFactor.landfill_factor - carbonFactor.reuse_factor;
        }
        carbonOffset += weight * factor;
      }
    }

    const diversionRate = totalWeight > 0
      ? ((recycledWeight + donatedWeight) / totalWeight) * 100
      : 0;

    const esgScore = Math.min(100, Math.round(
      (diversionRate * 0.4) +
      (Math.min(carbonOffset / 100, 100) * 0.3) +
      ((recycledWeight / Math.max(totalWeight, 1)) * 100 * 0.3)
    ));

    // Update job
    await supabase
      .from('jobs')
      .update({
        total_weight_lbs: totalWeight,
        recycled_weight_lbs: recycledWeight,
        landfill_weight_lbs: landfillWeight,
        donated_weight_lbs: donatedWeight,
        carbon_offset_lbs: carbonOffset,
        diversion_rate: diversionRate,
        esg_score: esgScore
      })
      .eq('id', jobId);

  } catch (error) {
    logger.error('Recalculate metrics error:', error);
  }
}

module.exports = router;
