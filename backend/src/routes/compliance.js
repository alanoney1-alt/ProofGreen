const express = require('express');
const router = express.Router();
const { supabase } = require('../utils/supabase');
const { authenticate, authorize } = require('../middleware/auth');
const { logger } = require('../utils/logger');
const complianceService = require('../services/complianceService');
const formService = require('../services/formService');

// GET /api/compliance/status - Get company compliance overview
router.get('/status', authenticate, async (req, res) => {
  try {
    const compliance = await complianceService.calculateCompanyCompliance(req.companyId);

    // Get recent jobs with ESG scores
    const { data: recentJobs } = await supabase
      .from('jobs')
      .select(`
        id,
        title,
        status,
        vertical_id,
        created_at,
        verticals (name, slug)
      `)
      .eq('company_id', req.companyId)
      .order('created_at', { ascending: false })
      .limit(10);

    // Calculate ESG scores for recent jobs
    const jobsWithScores = await Promise.all(
      (recentJobs || []).map(async (job) => {
        const esgScore = await complianceService.calculateJobESGScore(job.id);
        return {
          ...job,
          esgScore
        };
      })
    );

    // Get expiring items
    const expiringItems = await complianceService.getExpiringItems(req.companyId, 30);

    res.json({
      compliance,
      recentJobs: jobsWithScores,
      expiringItems,
      summary: {
        overallScore: compliance.overallScore,
        trend: compliance.trend,
        contractReady: compliance.overallScore >= 70,
        actionRequired: expiringItems.length > 0
      }
    });
  } catch (error) {
    logger.error('Get compliance status error:', error);
    res.status(500).json({ error: 'Failed to fetch compliance status' });
  }
});

// GET /api/compliance/requirements/:verticalId - Get requirements for a vertical
router.get('/requirements/:verticalId', authenticate, async (req, res) => {
  try {
    const { verticalId } = req.params;

    const requirements = await complianceService.getRequirements(verticalId, req.companyId);

    // Get company's current compliance status for these requirements
    const { data: complianceStatus } = await supabase
      .from('compliance_status')
      .select('*')
      .eq('company_id', req.companyId)
      .eq('vertical_id', verticalId);

    // Merge requirements with compliance status
    const enrichedRequirements = requirements.map(req => {
      const status = complianceStatus?.find(s => s.requirement_id === req.id);
      return {
        ...req,
        companyStatus: status ? {
          compliant: status.compliant,
          lastChecked: status.last_checked,
          notes: status.notes,
          documentId: status.document_id
        } : null
      };
    });

    // Group by requirement type
    const grouped = enrichedRequirements.reduce((acc, req) => {
      const type = req.requirement_type;
      if (!acc[type]) acc[type] = [];
      acc[type].push(req);
      return acc;
    }, {});

    res.json({
      verticalId,
      requirements: enrichedRequirements,
      grouped,
      summary: {
        total: enrichedRequirements.length,
        compliant: enrichedRequirements.filter(r => r.companyStatus?.compliant).length,
        pending: enrichedRequirements.filter(r => !r.companyStatus).length
      }
    });
  } catch (error) {
    logger.error('Get requirements error:', error);
    res.status(500).json({ error: 'Failed to fetch requirements' });
  }
});

// POST /api/compliance/check-readiness - Check contract readiness
router.post('/check-readiness', authenticate, async (req, res) => {
  try {
    const { contractType, verticalId } = req.body;

    if (!contractType || !verticalId) {
      return res.status(400).json({ error: 'contractType and verticalId are required' });
    }

    const readiness = await complianceService.checkContractReadiness(
      req.companyId,
      contractType,
      verticalId
    );

    // Get detailed gap analysis
    const gaps = readiness.missingRequirements.map(req => ({
      requirement: req.name,
      type: req.requirement_type,
      priority: req.priority || 'medium',
      estimatedEffort: getEstimatedEffort(req),
      actionItems: getActionItems(req)
    }));

    res.json({
      ready: readiness.ready,
      score: readiness.score,
      minimumRequired: readiness.minimumRequired,
      gaps,
      recommendations: generateRecommendations(readiness, contractType),
      timeline: estimateComplianceTimeline(gaps)
    });
  } catch (error) {
    logger.error('Check readiness error:', error);
    res.status(500).json({ error: 'Failed to check contract readiness' });
  }
});

// GET /api/compliance/report - Generate compliance report
router.get('/report', authenticate, async (req, res) => {
  try {
    const { format, verticalId, dateRange } = req.query;

    const report = await complianceService.generateComplianceReport(
      req.companyId,
      verticalId || null
    );

    // Add historical data if date range specified
    if (dateRange) {
      const { data: historicalScores } = await supabase
        .from('jobs')
        .select('created_at, esg_score')
        .eq('company_id', req.companyId)
        .not('esg_score', 'is', null)
        .gte('created_at', getDateFromRange(dateRange))
        .order('created_at', { ascending: true });

      report.historicalScores = historicalScores || [];
      report.trend = calculateTrend(historicalScores || []);
    }

    // Get certifications
    const { data: certifications } = await supabase
      .from('certifications')
      .select('*')
      .eq('company_id', req.companyId)
      .order('expires_at', { ascending: true });

    report.certifications = certifications || [];

    if (format === 'pdf') {
      // Return PDF generation endpoint hint
      res.json({
        ...report,
        pdfUrl: `/api/reports/compliance/pdf?companyId=${req.companyId}`
      });
    } else {
      res.json(report);
    }
  } catch (error) {
    logger.error('Generate report error:', error);
    res.status(500).json({ error: 'Failed to generate compliance report' });
  }
});

// GET /api/compliance/score/:jobId - Get ESG score for a specific job
router.get('/score/:jobId', authenticate, async (req, res) => {
  try {
    const { jobId } = req.params;

    // Verify job belongs to company
    const { data: job } = await supabase
      .from('jobs')
      .select('*, verticals(name, slug)')
      .eq('id', jobId)
      .eq('company_id', req.companyId)
      .single();

    if (!job) {
      return res.status(404).json({ error: 'Job not found' });
    }

    const esgScore = await complianceService.calculateJobESGScore(jobId);

    res.json({
      jobId,
      jobTitle: job.title,
      vertical: job.verticals?.name,
      esgScore,
      breakdown: {
        environmental: esgScore.breakdown?.environmental || 0,
        social: esgScore.breakdown?.social || 0,
        governance: esgScore.breakdown?.governance || 0
      },
      factors: esgScore.factors || [],
      recommendations: generateJobRecommendations(esgScore, job.verticals?.slug)
    });
  } catch (error) {
    logger.error('Get job ESG score error:', error);
    res.status(500).json({ error: 'Failed to calculate ESG score' });
  }
});

// POST /api/compliance/esg-data - Store vertical-specific ESG data
router.post('/esg-data', authenticate, async (req, res) => {
  try {
    const { jobId, verticalSlug, formData } = req.body;

    if (!jobId || !verticalSlug || !formData) {
      return res.status(400).json({ error: 'jobId, verticalSlug, and formData are required' });
    }

    // Validate form data
    const validation = formService.validateFormData(formData, verticalSlug);
    if (!validation.valid) {
      return res.status(400).json({
        error: 'Invalid form data',
        validationErrors: validation.errors
      });
    }

    // Process form submission (calculates derived fields)
    const processedData = formService.processFormSubmission(formData, verticalSlug);

    // Store ESG data
    const result = await complianceService.storeVerticalESGData(
      jobId,
      verticalSlug,
      processedData
    );

    // Recalculate job ESG score
    const newScore = await complianceService.calculateJobESGScore(jobId);

    // Update job with new ESG score
    await supabase
      .from('jobs')
      .update({ esg_score: newScore.overall })
      .eq('id', jobId);

    res.json({
      success: true,
      esgData: result,
      newScore,
      message: 'ESG data stored and score updated'
    });
  } catch (error) {
    logger.error('Store ESG data error:', error);
    res.status(500).json({ error: 'Failed to store ESG data' });
  }
});

// GET /api/compliance/form-fields/:verticalSlug - Get form fields for a vertical
router.get('/form-fields/:verticalSlug', authenticate, async (req, res) => {
  try {
    const { verticalSlug } = req.params;

    const fields = formService.getFormFieldsBySlug(verticalSlug);

    if (!fields || fields.length === 0) {
      return res.status(404).json({ error: 'No form fields found for this vertical' });
    }

    // Group fields by section
    const sections = fields.reduce((acc, field) => {
      const section = field.section || 'general';
      if (!acc[section]) acc[section] = [];
      acc[section].push(field);
      return acc;
    }, {});

    res.json({
      verticalSlug,
      fields,
      sections,
      totalFields: fields.length,
      requiredFields: fields.filter(f => f.required).length
    });
  } catch (error) {
    logger.error('Get form fields error:', error);
    res.status(500).json({ error: 'Failed to fetch form fields' });
  }
});

// PUT /api/compliance/requirement/:requirementId - Update requirement compliance status
router.put('/requirement/:requirementId', authenticate, authorize('owner', 'admin', 'manager'), async (req, res) => {
  try {
    const { requirementId } = req.params;
    const { compliant, notes, documentId, verticalId } = req.body;

    const statusRecord = {
      company_id: req.companyId,
      requirement_id: requirementId,
      vertical_id: verticalId,
      compliant,
      notes,
      document_id: documentId || null,
      last_checked: new Date().toISOString(),
      checked_by: req.user.id
    };

    const { data: status, error } = await supabase
      .from('compliance_status')
      .upsert(statusRecord, {
        onConflict: 'company_id,requirement_id'
      })
      .select()
      .single();

    if (error) {
      logger.error('Update compliance status error:', error);
      return res.status(500).json({ error: 'Failed to update compliance status' });
    }

    res.json({
      status,
      message: 'Compliance status updated'
    });
  } catch (error) {
    logger.error('Update requirement error:', error);
    res.status(500).json({ error: 'Failed to update requirement' });
  }
});

// POST /api/compliance/certification - Add a certification
router.post('/certification', authenticate, authorize('owner', 'admin', 'manager'), async (req, res) => {
  try {
    const {
      certificationName,
      certificationNumber,
      issuedBy,
      issuedAt,
      expiresAt,
      documentId,
      verticalId
    } = req.body;

    if (!certificationName || !issuedBy) {
      return res.status(400).json({ error: 'certificationName and issuedBy are required' });
    }

    const { data: certification, error } = await supabase
      .from('certifications')
      .insert({
        company_id: req.companyId,
        certification_name: certificationName,
        certification_number: certificationNumber,
        issued_by: issuedBy,
        issued_at: issuedAt || new Date().toISOString(),
        expires_at: expiresAt,
        document_id: documentId,
        vertical_id: verticalId,
        verified: false
      })
      .select()
      .single();

    if (error) {
      logger.error('Add certification error:', error);
      return res.status(500).json({ error: 'Failed to add certification' });
    }

    logger.info(`Certification added: ${certificationName} for company ${req.companyId}`);

    res.status(201).json({
      certification,
      message: 'Certification added successfully'
    });
  } catch (error) {
    logger.error('Add certification error:', error);
    res.status(500).json({ error: 'Failed to add certification' });
  }
});

// GET /api/compliance/certifications - Get company certifications
router.get('/certifications', authenticate, async (req, res) => {
  try {
    const { status, verticalId } = req.query;

    let query = supabase
      .from('certifications')
      .select('*')
      .eq('company_id', req.companyId)
      .order('expires_at', { ascending: true });

    if (verticalId) {
      query = query.eq('vertical_id', verticalId);
    }

    const { data: certifications, error } = await query;

    if (error) {
      return res.status(500).json({ error: 'Failed to fetch certifications' });
    }

    // Categorize by status
    const now = new Date();
    const thirtyDaysFromNow = new Date();
    thirtyDaysFromNow.setDate(thirtyDaysFromNow.getDate() + 30);

    const categorized = {
      active: [],
      expiringSoon: [],
      expired: []
    };

    certifications.forEach(cert => {
      if (!cert.expires_at) {
        categorized.active.push(cert);
      } else {
        const expiresAt = new Date(cert.expires_at);
        if (expiresAt < now) {
          categorized.expired.push(cert);
        } else if (expiresAt < thirtyDaysFromNow) {
          categorized.expiringSoon.push(cert);
        } else {
          categorized.active.push(cert);
        }
      }
    });

    // Filter by status if specified
    let filtered = certifications;
    if (status === 'active') filtered = categorized.active;
    else if (status === 'expiring') filtered = categorized.expiringSoon;
    else if (status === 'expired') filtered = categorized.expired;

    res.json({
      certifications: filtered,
      summary: {
        total: certifications.length,
        active: categorized.active.length,
        expiringSoon: categorized.expiringSoon.length,
        expired: categorized.expired.length
      }
    });
  } catch (error) {
    logger.error('Get certifications error:', error);
    res.status(500).json({ error: 'Failed to fetch certifications' });
  }
});

// DELETE /api/compliance/certification/:id - Delete a certification
router.delete('/certification/:id', authenticate, authorize('owner', 'admin'), async (req, res) => {
  try {
    const { id } = req.params;

    const { error } = await supabase
      .from('certifications')
      .delete()
      .eq('id', id)
      .eq('company_id', req.companyId);

    if (error) {
      return res.status(500).json({ error: 'Failed to delete certification' });
    }

    res.json({ message: 'Certification deleted successfully' });
  } catch (error) {
    logger.error('Delete certification error:', error);
    res.status(500).json({ error: 'Failed to delete certification' });
  }
});

// GET /api/compliance/analytics - Get compliance analytics
router.get('/analytics', authenticate, async (req, res) => {
  try {
    const { period = '30' } = req.query;
    const daysBack = parseInt(period);

    const startDate = new Date();
    startDate.setDate(startDate.getDate() - daysBack);

    // Get jobs with ESG scores in period
    const { data: jobs } = await supabase
      .from('jobs')
      .select('id, created_at, esg_score, vertical_id, verticals(name)')
      .eq('company_id', req.companyId)
      .gte('created_at', startDate.toISOString())
      .not('esg_score', 'is', null)
      .order('created_at', { ascending: true });

    // Calculate analytics
    const scores = (jobs || []).map(j => j.esg_score);
    const avgScore = scores.length > 0
      ? scores.reduce((a, b) => a + b, 0) / scores.length
      : 0;

    // Score distribution
    const distribution = {
      excellent: scores.filter(s => s >= 80).length,
      good: scores.filter(s => s >= 60 && s < 80).length,
      fair: scores.filter(s => s >= 40 && s < 60).length,
      needsWork: scores.filter(s => s < 40).length
    };

    // By vertical
    const byVertical = (jobs || []).reduce((acc, job) => {
      const vertical = job.verticals?.name || 'Unknown';
      if (!acc[vertical]) {
        acc[vertical] = { count: 0, totalScore: 0 };
      }
      acc[vertical].count++;
      acc[vertical].totalScore += job.esg_score;
      return acc;
    }, {});

    Object.keys(byVertical).forEach(v => {
      byVertical[v].avgScore = byVertical[v].totalScore / byVertical[v].count;
    });

    // Trend over time (weekly)
    const weeklyTrend = [];
    const weekMs = 7 * 24 * 60 * 60 * 1000;
    for (let i = 0; i < Math.ceil(daysBack / 7); i++) {
      const weekStart = new Date(startDate.getTime() + i * weekMs);
      const weekEnd = new Date(weekStart.getTime() + weekMs);
      const weekJobs = (jobs || []).filter(j => {
        const date = new Date(j.created_at);
        return date >= weekStart && date < weekEnd;
      });
      const weekScores = weekJobs.map(j => j.esg_score);
      weeklyTrend.push({
        week: i + 1,
        startDate: weekStart.toISOString().split('T')[0],
        avgScore: weekScores.length > 0
          ? weekScores.reduce((a, b) => a + b, 0) / weekScores.length
          : null,
        jobCount: weekJobs.length
      });
    }

    res.json({
      period: `${daysBack} days`,
      analytics: {
        totalJobs: jobs?.length || 0,
        averageScore: Math.round(avgScore * 10) / 10,
        highestScore: scores.length > 0 ? Math.max(...scores) : 0,
        lowestScore: scores.length > 0 ? Math.min(...scores) : 0,
        distribution,
        byVertical,
        weeklyTrend
      }
    });
  } catch (error) {
    logger.error('Get analytics error:', error);
    res.status(500).json({ error: 'Failed to fetch analytics' });
  }
});

// Helper functions
function getEstimatedEffort(requirement) {
  const effortMap = {
    documentation: 'Low - Upload required document',
    certification: 'Medium - Obtain certification',
    equipment: 'High - Equipment purchase/upgrade needed',
    training: 'Medium - Complete required training',
    process: 'Medium - Implement process changes'
  };
  return effortMap[requirement.requirement_type] || 'Medium';
}

function getActionItems(requirement) {
  const actions = {
    documentation: ['Locate or obtain required document', 'Upload to system', 'Verify document validity'],
    certification: ['Research certification requirements', 'Complete application process', 'Upload certificate'],
    equipment: ['Evaluate current equipment', 'Research compliant options', 'Plan procurement'],
    training: ['Identify required training', 'Schedule training sessions', 'Document completion'],
    process: ['Review current processes', 'Implement required changes', 'Document new procedures']
  };
  return actions[requirement.requirement_type] || ['Review requirement', 'Take necessary action'];
}

function generateRecommendations(readiness, contractType) {
  const recommendations = [];

  if (readiness.score < 50) {
    recommendations.push({
      priority: 'high',
      message: 'Significant compliance gaps exist. Focus on documentation requirements first.'
    });
  }

  if (readiness.missingRequirements.some(r => r.requirement_type === 'certification')) {
    recommendations.push({
      priority: 'medium',
      message: 'Missing certifications detected. Begin certification process early as these take time.'
    });
  }

  if (contractType === 'government') {
    recommendations.push({
      priority: 'high',
      message: 'Government contracts require strict compliance. Ensure all documentation is current and verified.'
    });
  }

  if (readiness.score >= 70 && readiness.score < 85) {
    recommendations.push({
      priority: 'medium',
      message: 'Close to full compliance. Address remaining gaps to maximize contract opportunities.'
    });
  }

  return recommendations;
}

function estimateComplianceTimeline(gaps) {
  const estimates = gaps.map(gap => {
    switch (gap.priority) {
      case 'high': return 14;
      case 'medium': return 7;
      default: return 3;
    }
  });

  const maxDays = estimates.length > 0 ? Math.max(...estimates) : 0;

  return {
    estimatedDays: maxDays,
    message: maxDays === 0
      ? 'Already compliant'
      : `Estimated ${maxDays} days to full compliance`
  };
}

function generateJobRecommendations(esgScore, verticalSlug) {
  const recommendations = [];

  if (esgScore.breakdown?.environmental < 60) {
    recommendations.push('Improve waste diversion rates and recycling practices');
  }

  if (esgScore.breakdown?.social < 60) {
    recommendations.push('Focus on charitable donations and community impact');
  }

  if (esgScore.breakdown?.governance < 60) {
    recommendations.push('Ensure proper documentation and certifications are in place');
  }

  if (esgScore.overall >= 80) {
    recommendations.push('Excellent ESG performance! Consider pursuing ESG certifications.');
  }

  return recommendations;
}

function getDateFromRange(range) {
  const now = new Date();
  switch (range) {
    case '7d': now.setDate(now.getDate() - 7); break;
    case '30d': now.setDate(now.getDate() - 30); break;
    case '90d': now.setDate(now.getDate() - 90); break;
    case '1y': now.setFullYear(now.getFullYear() - 1); break;
    default: now.setDate(now.getDate() - 30);
  }
  return now.toISOString();
}

function calculateTrend(scores) {
  if (scores.length < 2) return 'stable';

  const recent = scores.slice(-5);
  const older = scores.slice(0, 5);

  const recentAvg = recent.reduce((a, b) => a + (b.esg_score || 0), 0) / recent.length;
  const olderAvg = older.reduce((a, b) => a + (b.esg_score || 0), 0) / older.length;

  if (recentAvg > olderAvg + 5) return 'improving';
  if (recentAvg < olderAvg - 5) return 'declining';
  return 'stable';
}

module.exports = router;
