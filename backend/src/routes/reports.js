const express = require('express');
const router = express.Router();
const { body, query } = require('express-validator');
const { supabase } = require('../utils/supabase');
const { authenticate } = require('../middleware/auth');
const { logger } = require('../utils/logger');
const { v4: uuidv4 } = require('uuid');

// GET /api/reports
router.get('/', authenticate, [
  query('type').optional().isIn(['job', 'weekly', 'monthly', 'quarterly', 'annual', 'custom']),
  query('limit').optional().isInt({ min: 1, max: 100 })
], async (req, res) => {
  try {
    const { type, limit = 20, offset = 0 } = req.query;

    let queryBuilder = supabase
      .from('esg_reports')
      .select('*', { count: 'exact' })
      .eq('company_id', req.companyId)
      .order('generated_at', { ascending: false })
      .range(offset, offset + limit - 1);

    if (type) {
      queryBuilder = queryBuilder.eq('report_type', type);
    }

    const { data: reports, error, count } = await queryBuilder;

    if (error) {
      return res.status(500).json({ error: 'Failed to fetch reports' });
    }

    res.json({
      reports,
      pagination: { total: count, limit: parseInt(limit), offset: parseInt(offset) }
    });
  } catch (error) {
    logger.error('Get reports error:', error);
    res.status(500).json({ error: 'Failed to fetch reports' });
  }
});

// GET /api/reports/:id
router.get('/:id', authenticate, async (req, res) => {
  try {
    const { id } = req.params;

    const { data: report, error } = await supabase
      .from('esg_reports')
      .select(`
        *,
        jobs (*)
      `)
      .eq('id', id)
      .eq('company_id', req.companyId)
      .single();

    if (error || !report) {
      return res.status(404).json({ error: 'Report not found' });
    }

    // Increment view count
    await supabase
      .from('esg_reports')
      .update({
        viewed_count: (report.viewed_count || 0) + 1,
        last_viewed_at: new Date().toISOString()
      })
      .eq('id', id);

    res.json({ report });
  } catch (error) {
    logger.error('Get report error:', error);
    res.status(500).json({ error: 'Failed to fetch report' });
  }
});

// GET /api/reports/public/:token
router.get('/public/:token', async (req, res) => {
  try {
    const { token } = req.params;

    const { data: report, error } = await supabase
      .from('esg_reports')
      .select(`
        *,
        companies (name, logo_url)
      `)
      .eq('public_token', token)
      .eq('is_public', true)
      .single();

    if (error || !report) {
      return res.status(404).json({ error: 'Report not found or not public' });
    }

    // Increment view count
    await supabase
      .from('esg_reports')
      .update({
        viewed_count: (report.viewed_count || 0) + 1,
        last_viewed_at: new Date().toISOString()
      })
      .eq('id', report.id);

    res.json({ report });
  } catch (error) {
    logger.error('Get public report error:', error);
    res.status(500).json({ error: 'Failed to fetch report' });
  }
});

// POST /api/reports/generate/job/:jobId
router.post('/generate/job/:jobId', authenticate, async (req, res) => {
  try {
    const { jobId } = req.params;

    // Fetch job with items
    const { data: job, error: jobError } = await supabase
      .from('jobs')
      .select(`
        *,
        verticals (*),
        job_items (*),
        companies (*)
      `)
      .eq('id', jobId)
      .eq('company_id', req.companyId)
      .single();

    if (jobError || !job) {
      return res.status(404).json({ error: 'Job not found' });
    }

    // Generate report data
    const reportData = generateJobReportData(job);

    // Create report record
    const publicToken = uuidv4();
    const { data: report, error } = await supabase
      .from('esg_reports')
      .insert({
        company_id: req.companyId,
        job_id: jobId,
        report_type: 'job',
        title: `ESG Report - ${job.job_number}`,
        period_start: job.scheduled_date,
        period_end: job.completed_at?.split('T')[0] || job.scheduled_date,
        summary: reportData.summary,
        metrics_snapshot: reportData.metrics,
        report_data: reportData,
        file_format: 'json',
        public_token: publicToken
      })
      .select()
      .single();

    if (error) {
      logger.error('Report creation error:', error);
      return res.status(500).json({ error: 'Failed to generate report' });
    }

    res.status(201).json({
      report,
      publicUrl: `/reports/public/${publicToken}`
    });
  } catch (error) {
    logger.error('Generate job report error:', error);
    res.status(500).json({ error: 'Failed to generate report' });
  }
});

// POST /api/reports/generate/period
router.post('/generate/period', authenticate, [
  body('reportType').isIn(['weekly', 'monthly', 'quarterly', 'annual', 'custom']),
  body('startDate').isISO8601(),
  body('endDate').isISO8601()
], async (req, res) => {
  try {
    const { reportType, startDate, endDate, title } = req.body;

    // Fetch company info
    const { data: company } = await supabase
      .from('companies')
      .select('*')
      .eq('id', req.companyId)
      .single();

    // Fetch all jobs in period
    const { data: jobs } = await supabase
      .from('jobs')
      .select(`
        *,
        verticals (*),
        job_items (*)
      `)
      .eq('company_id', req.companyId)
      .eq('status', 'completed')
      .gte('completed_at', startDate)
      .lte('completed_at', endDate);

    // Generate period report data
    const reportData = generatePeriodReportData(company, jobs || [], startDate, endDate);

    // Create report record
    const publicToken = uuidv4();
    const reportTitle = title || `${reportType.charAt(0).toUpperCase() + reportType.slice(1)} ESG Report - ${new Date(startDate).toLocaleDateString()} to ${new Date(endDate).toLocaleDateString()}`;

    const { data: report, error } = await supabase
      .from('esg_reports')
      .insert({
        company_id: req.companyId,
        report_type: reportType,
        title: reportTitle,
        period_start: startDate,
        period_end: endDate,
        summary: reportData.summary,
        metrics_snapshot: reportData.metrics,
        report_data: reportData,
        file_format: 'json',
        public_token: publicToken
      })
      .select()
      .single();

    if (error) {
      logger.error('Report creation error:', error);
      return res.status(500).json({ error: 'Failed to generate report' });
    }

    res.status(201).json({
      report,
      publicUrl: `/reports/public/${publicToken}`
    });
  } catch (error) {
    logger.error('Generate period report error:', error);
    res.status(500).json({ error: 'Failed to generate report' });
  }
});

// PUT /api/reports/:id/share
router.put('/:id/share', authenticate, async (req, res) => {
  try {
    const { id } = req.params;
    const { isPublic } = req.body;

    const { data: report, error } = await supabase
      .from('esg_reports')
      .update({ is_public: isPublic })
      .eq('id', id)
      .eq('company_id', req.companyId)
      .select()
      .single();

    if (error || !report) {
      return res.status(404).json({ error: 'Report not found' });
    }

    res.json({
      report,
      publicUrl: isPublic ? `/reports/public/${report.public_token}` : null
    });
  } catch (error) {
    logger.error('Share report error:', error);
    res.status(500).json({ error: 'Failed to update report sharing' });
  }
});

// DELETE /api/reports/:id
router.delete('/:id', authenticate, async (req, res) => {
  try {
    const { id } = req.params;

    const { error } = await supabase
      .from('esg_reports')
      .delete()
      .eq('id', id)
      .eq('company_id', req.companyId);

    if (error) {
      return res.status(500).json({ error: 'Failed to delete report' });
    }

    res.json({ message: 'Report deleted successfully' });
  } catch (error) {
    logger.error('Delete report error:', error);
    res.status(500).json({ error: 'Failed to delete report' });
  }
});

// Helper function to generate job report data
function generateJobReportData(job) {
  const items = job.job_items || [];

  // Group items by category
  const byCategory = {};
  items.forEach(item => {
    const cat = item.category || 'general';
    if (!byCategory[cat]) {
      byCategory[cat] = { items: [], totalWeight: 0, recycledWeight: 0 };
    }
    const weight = (item.weight_lbs || 0) * (item.quantity || 1);
    byCategory[cat].items.push(item);
    byCategory[cat].totalWeight += weight;
    if (item.disposal_method === 'recycled' || item.disposal_method === 'donated') {
      byCategory[cat].recycledWeight += weight;
    }
  });

  const metrics = {
    totalWeight: job.total_weight_lbs || 0,
    recycledWeight: job.recycled_weight_lbs || 0,
    donatedWeight: job.donated_weight_lbs || 0,
    landfillWeight: job.landfill_weight_lbs || 0,
    carbonOffset: job.carbon_offset_lbs || 0,
    diversionRate: job.diversion_rate || 0,
    esgScore: job.esg_score || 0,
    itemCount: items.length
  };

  const summary = `This job processed ${metrics.totalWeight.toFixed(0)} lbs of material with a ${metrics.diversionRate.toFixed(1)}% diversion rate, offsetting ${metrics.carbonOffset.toFixed(0)} lbs of CO2 emissions.`;

  return {
    job: {
      id: job.id,
      jobNumber: job.job_number,
      title: job.title,
      customerName: job.customer_name,
      completedAt: job.completed_at,
      address: `${job.city || ''}, ${job.state || ''}`
    },
    company: {
      name: job.companies?.name,
      logo: job.companies?.logo_url
    },
    vertical: job.verticals?.name,
    metrics,
    byCategory: Object.entries(byCategory).map(([category, data]) => ({
      category,
      itemCount: data.items.length,
      totalWeight: data.totalWeight,
      recycledWeight: data.recycledWeight,
      diversionRate: data.totalWeight > 0 ? (data.recycledWeight / data.totalWeight) * 100 : 0
    })),
    items: items.map(item => ({
      name: item.name,
      category: item.category,
      weight: item.weight_lbs,
      quantity: item.quantity,
      disposalMethod: item.disposal_method
    })),
    summary,
    generatedAt: new Date().toISOString()
  };
}

// Helper function to generate period report data
function generatePeriodReportData(company, jobs, startDate, endDate) {
  const metrics = {
    totalJobs: jobs.length,
    totalWeight: 0,
    recycledWeight: 0,
    donatedWeight: 0,
    landfillWeight: 0,
    carbonOffset: 0,
    averageEsgScore: 0
  };

  jobs.forEach(job => {
    metrics.totalWeight += job.total_weight_lbs || 0;
    metrics.recycledWeight += job.recycled_weight_lbs || 0;
    metrics.donatedWeight += job.donated_weight_lbs || 0;
    metrics.landfillWeight += job.landfill_weight_lbs || 0;
    metrics.carbonOffset += job.carbon_offset_lbs || 0;
  });

  metrics.diversionRate = metrics.totalWeight > 0
    ? ((metrics.recycledWeight + metrics.donatedWeight) / metrics.totalWeight) * 100
    : 0;

  metrics.averageEsgScore = jobs.length > 0
    ? Math.round(jobs.reduce((sum, j) => sum + (j.esg_score || 0), 0) / jobs.length)
    : 0;

  // Environmental equivalents
  metrics.treesEquivalent = Math.round(metrics.carbonOffset / 48);
  metrics.milesEquivalent = Math.round(metrics.carbonOffset / 0.89);
  metrics.tonsFromLandfill = (metrics.recycledWeight + metrics.donatedWeight) / 2000;

  // By vertical breakdown
  const byVertical = {};
  jobs.forEach(job => {
    const vertical = job.verticals?.name || 'Other';
    if (!byVertical[vertical]) {
      byVertical[vertical] = { jobs: 0, totalWeight: 0, carbonOffset: 0 };
    }
    byVertical[vertical].jobs++;
    byVertical[vertical].totalWeight += job.total_weight_lbs || 0;
    byVertical[vertical].carbonOffset += job.carbon_offset_lbs || 0;
  });

  const summary = `During this period, ${company.name} completed ${metrics.totalJobs} jobs, processing ${metrics.totalWeight.toFixed(0)} lbs of material with a ${metrics.diversionRate.toFixed(1)}% diversion rate. This effort offset ${metrics.carbonOffset.toFixed(0)} lbs of CO2 emissions, equivalent to planting ${metrics.treesEquivalent} trees.`;

  return {
    company: {
      name: company.name,
      logo: company.logo_url
    },
    period: {
      start: startDate,
      end: endDate
    },
    metrics,
    byVertical: Object.entries(byVertical).map(([vertical, data]) => ({
      vertical,
      ...data
    })),
    topJobs: jobs
      .sort((a, b) => (b.esg_score || 0) - (a.esg_score || 0))
      .slice(0, 5)
      .map(j => ({
        jobNumber: j.job_number,
        title: j.title,
        esgScore: j.esg_score,
        totalWeight: j.total_weight_lbs
      })),
    summary,
    generatedAt: new Date().toISOString()
  };
}

module.exports = router;
