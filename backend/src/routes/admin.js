const express = require('express');
const router = express.Router();
const { supabase } = require('../utils/supabase');
const { authenticate, authorize } = require('../middleware/auth');
const { logger } = require('../utils/logger');

// All admin routes require authentication and admin/owner role
router.use(authenticate);
router.use(authorize('admin', 'owner'));

// GET /api/admin/stats
// Platform-wide statistics
router.get('/stats', async (req, res) => {
  try {
    // Get counts
    const [companiesResult, usersResult, jobsResult, subscriptionsResult] = await Promise.all([
      supabase.from('companies').select('*', { count: 'exact', head: true }),
      supabase.from('users').select('*', { count: 'exact', head: true }),
      supabase.from('jobs').select('*', { count: 'exact', head: true }),
      supabase.from('subscriptions').select('*', { count: 'exact', head: true }).eq('status', 'active')
    ]);

    // Get metrics aggregates
    const { data: metricsData } = await supabase
      .from('jobs')
      .select('total_weight_lbs, recycled_weight_lbs, donated_weight_lbs, carbon_offset_lbs')
      .eq('status', 'completed');

    const totals = metricsData?.reduce((acc, job) => ({
      totalWeight: acc.totalWeight + (job.total_weight_lbs || 0),
      recycledWeight: acc.recycledWeight + (job.recycled_weight_lbs || 0),
      donatedWeight: acc.donatedWeight + (job.donated_weight_lbs || 0),
      carbonOffset: acc.carbonOffset + (job.carbon_offset_lbs || 0)
    }), { totalWeight: 0, recycledWeight: 0, donatedWeight: 0, carbonOffset: 0 }) || {};

    // Get revenue by plan
    const { data: subscriptions } = await supabase
      .from('subscriptions')
      .select('billing_cycle, pricing_plans(price_monthly, price_yearly)')
      .eq('status', 'active');

    const mrr = subscriptions?.reduce((acc, sub) => {
      if (sub.billing_cycle === 'monthly') {
        return acc + (sub.pricing_plans?.price_monthly || 0);
      } else {
        return acc + ((sub.pricing_plans?.price_yearly || 0) / 12);
      }
    }, 0) || 0;

    res.json({
      stats: {
        companies: companiesResult.count || 0,
        users: usersResult.count || 0,
        jobs: jobsResult.count || 0,
        activeSubscriptions: subscriptionsResult.count || 0
      },
      metrics: {
        totalWeight: totals.totalWeight,
        recycledWeight: totals.recycledWeight,
        donatedWeight: totals.donatedWeight,
        carbonOffset: totals.carbonOffset,
        diversionRate: totals.totalWeight > 0
          ? ((totals.recycledWeight + totals.donatedWeight) / totals.totalWeight) * 100
          : 0
      },
      revenue: {
        mrr,
        arr: mrr * 12
      }
    });
  } catch (error) {
    logger.error('Admin stats error:', error);
    res.status(500).json({ error: 'Failed to fetch admin stats' });
  }
});

// GET /api/admin/companies
// List all companies with pagination
router.get('/companies', async (req, res) => {
  try {
    const { limit = 20, offset = 0, search, status } = req.query;

    let query = supabase
      .from('companies')
      .select(`
        *,
        users(count),
        jobs(count),
        subscriptions(*, pricing_plans(*))
      `, { count: 'exact' })
      .order('created_at', { ascending: false })
      .range(offset, parseInt(offset) + parseInt(limit) - 1);

    if (search) {
      query = query.or(`name.ilike.%${search}%,email.ilike.%${search}%`);
    }

    if (status === 'active') {
      query = query.eq('is_active', true);
    } else if (status === 'inactive') {
      query = query.eq('is_active', false);
    }

    const { data: companies, error, count } = await query;

    if (error) {
      return res.status(500).json({ error: 'Failed to fetch companies' });
    }

    res.json({
      companies,
      pagination: {
        total: count,
        limit: parseInt(limit),
        offset: parseInt(offset)
      }
    });
  } catch (error) {
    logger.error('Admin companies error:', error);
    res.status(500).json({ error: 'Failed to fetch companies' });
  }
});

// GET /api/admin/companies/:id
// Get single company details
router.get('/companies/:id', async (req, res) => {
  try {
    const { id } = req.params;

    const { data: company, error } = await supabase
      .from('companies')
      .select(`
        *,
        users(*),
        company_verticals(*, verticals(*)),
        subscriptions(*, pricing_plans(*)),
        jobs(id, status, created_at)
      `)
      .eq('id', id)
      .single();

    if (error || !company) {
      return res.status(404).json({ error: 'Company not found' });
    }

    // Get metrics for this company
    const { data: jobs } = await supabase
      .from('jobs')
      .select('total_weight_lbs, recycled_weight_lbs, donated_weight_lbs, carbon_offset_lbs, esg_score')
      .eq('company_id', id)
      .eq('status', 'completed');

    const metrics = jobs?.reduce((acc, job) => ({
      totalWeight: acc.totalWeight + (job.total_weight_lbs || 0),
      recycledWeight: acc.recycledWeight + (job.recycled_weight_lbs || 0),
      donatedWeight: acc.donatedWeight + (job.donated_weight_lbs || 0),
      carbonOffset: acc.carbonOffset + (job.carbon_offset_lbs || 0),
      totalEsgScore: acc.totalEsgScore + (job.esg_score || 0),
      jobCount: acc.jobCount + 1
    }), { totalWeight: 0, recycledWeight: 0, donatedWeight: 0, carbonOffset: 0, totalEsgScore: 0, jobCount: 0 });

    res.json({
      company,
      metrics: {
        ...metrics,
        averageEsgScore: metrics.jobCount > 0 ? Math.round(metrics.totalEsgScore / metrics.jobCount) : 0,
        diversionRate: metrics.totalWeight > 0
          ? ((metrics.recycledWeight + metrics.donatedWeight) / metrics.totalWeight) * 100
          : 0
      }
    });
  } catch (error) {
    logger.error('Admin company detail error:', error);
    res.status(500).json({ error: 'Failed to fetch company' });
  }
});

// PUT /api/admin/companies/:id
// Update company
router.put('/companies/:id', async (req, res) => {
  try {
    const { id } = req.params;
    const updates = {};

    const allowedFields = ['name', 'is_active', 'onboarding_completed'];
    allowedFields.forEach(field => {
      if (req.body[field] !== undefined) {
        updates[field] = req.body[field];
      }
    });

    const { data: company, error } = await supabase
      .from('companies')
      .update(updates)
      .eq('id', id)
      .select()
      .single();

    if (error || !company) {
      return res.status(500).json({ error: 'Failed to update company' });
    }

    logger.info(`Admin updated company ${id}`, { updates, adminId: req.user.id });

    res.json({ company });
  } catch (error) {
    logger.error('Admin update company error:', error);
    res.status(500).json({ error: 'Failed to update company' });
  }
});

// GET /api/admin/users
// List all users
router.get('/users', async (req, res) => {
  try {
    const { limit = 20, offset = 0, search, companyId } = req.query;

    let query = supabase
      .from('users')
      .select(`
        *,
        companies(id, name)
      `, { count: 'exact' })
      .order('created_at', { ascending: false })
      .range(offset, parseInt(offset) + parseInt(limit) - 1);

    if (search) {
      query = query.or(`email.ilike.%${search}%,first_name.ilike.%${search}%,last_name.ilike.%${search}%`);
    }

    if (companyId) {
      query = query.eq('company_id', companyId);
    }

    const { data: users, error, count } = await query;

    if (error) {
      return res.status(500).json({ error: 'Failed to fetch users' });
    }

    // Remove password hashes from response
    const safeUsers = users.map(({ password_hash, ...user }) => user);

    res.json({
      users: safeUsers,
      pagination: {
        total: count,
        limit: parseInt(limit),
        offset: parseInt(offset)
      }
    });
  } catch (error) {
    logger.error('Admin users error:', error);
    res.status(500).json({ error: 'Failed to fetch users' });
  }
});

// PUT /api/admin/users/:id
// Update user
router.put('/users/:id', async (req, res) => {
  try {
    const { id } = req.params;
    const updates = {};

    const allowedFields = ['is_active', 'role', 'email_verified'];
    allowedFields.forEach(field => {
      if (req.body[field] !== undefined) {
        updates[field] = req.body[field];
      }
    });

    const { data: user, error } = await supabase
      .from('users')
      .update(updates)
      .eq('id', id)
      .select('id, email, first_name, last_name, role, is_active')
      .single();

    if (error || !user) {
      return res.status(500).json({ error: 'Failed to update user' });
    }

    logger.info(`Admin updated user ${id}`, { updates, adminId: req.user.id });

    res.json({ user });
  } catch (error) {
    logger.error('Admin update user error:', error);
    res.status(500).json({ error: 'Failed to update user' });
  }
});

// GET /api/admin/subscriptions
// List all subscriptions
router.get('/subscriptions', async (req, res) => {
  try {
    const { limit = 20, offset = 0, status } = req.query;

    let query = supabase
      .from('subscriptions')
      .select(`
        *,
        companies(id, name, email),
        pricing_plans(*)
      `, { count: 'exact' })
      .order('created_at', { ascending: false })
      .range(offset, parseInt(offset) + parseInt(limit) - 1);

    if (status) {
      query = query.eq('status', status);
    }

    const { data: subscriptions, error, count } = await query;

    if (error) {
      return res.status(500).json({ error: 'Failed to fetch subscriptions' });
    }

    res.json({
      subscriptions,
      pagination: {
        total: count,
        limit: parseInt(limit),
        offset: parseInt(offset)
      }
    });
  } catch (error) {
    logger.error('Admin subscriptions error:', error);
    res.status(500).json({ error: 'Failed to fetch subscriptions' });
  }
});

// PUT /api/admin/subscriptions/:id
// Update subscription (e.g., extend trial, change plan)
router.put('/subscriptions/:id', async (req, res) => {
  try {
    const { id } = req.params;
    const { planId, status, trialEnd } = req.body;

    const updates = {};
    if (planId) updates.plan_id = planId;
    if (status) updates.status = status;
    if (trialEnd) updates.trial_end = trialEnd;

    const { data: subscription, error } = await supabase
      .from('subscriptions')
      .update(updates)
      .eq('id', id)
      .select(`
        *,
        pricing_plans(*)
      `)
      .single();

    if (error || !subscription) {
      return res.status(500).json({ error: 'Failed to update subscription' });
    }

    logger.info(`Admin updated subscription ${id}`, { updates, adminId: req.user.id });

    res.json({ subscription });
  } catch (error) {
    logger.error('Admin update subscription error:', error);
    res.status(500).json({ error: 'Failed to update subscription' });
  }
});

// GET /api/admin/agent-executions
// View AI agent execution logs
router.get('/agent-executions', async (req, res) => {
  try {
    const { limit = 50, offset = 0, status, companyId } = req.query;

    let query = supabase
      .from('agent_executions')
      .select(`
        *,
        companies(id, name),
        jobs(id, job_number)
      `, { count: 'exact' })
      .order('started_at', { ascending: false })
      .range(offset, parseInt(offset) + parseInt(limit) - 1);

    if (status) {
      query = query.eq('status', status);
    }

    if (companyId) {
      query = query.eq('company_id', companyId);
    }

    const { data: executions, error, count } = await query;

    if (error) {
      return res.status(500).json({ error: 'Failed to fetch executions' });
    }

    res.json({
      executions,
      pagination: {
        total: count,
        limit: parseInt(limit),
        offset: parseInt(offset)
      }
    });
  } catch (error) {
    logger.error('Admin agent executions error:', error);
    res.status(500).json({ error: 'Failed to fetch agent executions' });
  }
});

// GET /api/admin/activity
// Recent platform activity
router.get('/activity', async (req, res) => {
  try {
    const { limit = 50 } = req.query;

    // Get recent jobs
    const { data: recentJobs } = await supabase
      .from('jobs')
      .select('id, job_number, title, status, created_at, companies(name)')
      .order('created_at', { ascending: false })
      .limit(parseInt(limit));

    // Get recent signups
    const { data: recentUsers } = await supabase
      .from('users')
      .select('id, email, first_name, last_name, created_at, companies(name)')
      .order('created_at', { ascending: false })
      .limit(parseInt(limit));

    // Get recent milestones achieved
    const { data: recentMilestones } = await supabase
      .from('milestones')
      .select('id, name, achieved_at, companies(name)')
      .eq('achieved', true)
      .order('achieved_at', { ascending: false })
      .limit(parseInt(limit));

    // Combine and sort by date
    const activity = [
      ...recentJobs.map(j => ({
        type: 'job',
        title: `New job: ${j.job_number}`,
        description: j.title,
        company: j.companies?.name,
        timestamp: j.created_at
      })),
      ...recentUsers.map(u => ({
        type: 'signup',
        title: 'New user',
        description: `${u.first_name} ${u.last_name} (${u.email})`,
        company: u.companies?.name,
        timestamp: u.created_at
      })),
      ...recentMilestones.map(m => ({
        type: 'milestone',
        title: 'Milestone achieved',
        description: m.name,
        company: m.companies?.name,
        timestamp: m.achieved_at
      }))
    ]
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
      .slice(0, parseInt(limit));

    res.json({ activity });
  } catch (error) {
    logger.error('Admin activity error:', error);
    res.status(500).json({ error: 'Failed to fetch activity' });
  }
});

module.exports = router;
