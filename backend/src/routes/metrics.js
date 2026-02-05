const express = require('express');
const router = express.Router();
const { query } = require('express-validator');
const { supabase } = require('../utils/supabase');
const { authenticate } = require('../middleware/auth');
const { logger } = require('../utils/logger');

// GET /api/metrics/dashboard
router.get('/dashboard', authenticate, async (req, res) => {
  try {
    const companyId = req.companyId;

    // Fetch all completed jobs for the company
    const { data: jobs } = await supabase
      .from('jobs')
      .select('*')
      .eq('company_id', companyId)
      .eq('status', 'completed');

    // Calculate aggregate metrics
    const metrics = {
      totalJobs: jobs?.length || 0,
      totalWeight: 0,
      recycledWeight: 0,
      donatedWeight: 0,
      landfillWeight: 0,
      carbonOffset: 0,
      diversionRate: 0,
      averageEsgScore: 0
    };

    if (jobs && jobs.length > 0) {
      jobs.forEach(job => {
        metrics.totalWeight += job.total_weight_lbs || 0;
        metrics.recycledWeight += job.recycled_weight_lbs || 0;
        metrics.donatedWeight += job.donated_weight_lbs || 0;
        metrics.landfillWeight += job.landfill_weight_lbs || 0;
        metrics.carbonOffset += job.carbon_offset_lbs || 0;
      });

      metrics.diversionRate = metrics.totalWeight > 0
        ? ((metrics.recycledWeight + metrics.donatedWeight) / metrics.totalWeight * 100)
        : 0;

      const totalEsgScore = jobs.reduce((sum, job) => sum + (job.esg_score || 0), 0);
      metrics.averageEsgScore = Math.round(totalEsgScore / jobs.length);
    }

    // Calculate environmental equivalents
    metrics.treesEquivalent = Math.round(metrics.carbonOffset / 48); // ~48 lbs CO2 per tree/year
    metrics.milesEquivalent = Math.round(metrics.carbonOffset / 0.89); // ~0.89 lbs CO2 per mile driven
    metrics.tonsFromLandfill = metrics.totalWeight / 2000;

    // Get recent activity
    const { data: recentJobs } = await supabase
      .from('jobs')
      .select('id, job_number, title, status, esg_score, total_weight_lbs, created_at')
      .eq('company_id', companyId)
      .order('created_at', { ascending: false })
      .limit(5);

    // Get milestones
    const { data: milestones } = await supabase
      .from('milestones')
      .select('*')
      .eq('company_id', companyId)
      .order('threshold_value');

    // Update milestone progress
    const updatedMilestones = milestones?.map(m => {
      let currentValue = 0;
      switch (m.milestone_type) {
        case 'tons_diverted':
          currentValue = (metrics.recycledWeight + metrics.donatedWeight);
          break;
        case 'carbon_saved':
          currentValue = metrics.carbonOffset;
          break;
        case 'jobs_completed':
          currentValue = metrics.totalJobs;
          break;
        case 'diversion_rate':
          currentValue = metrics.diversionRate;
          break;
      }
      return {
        ...m,
        current_value: currentValue,
        progress: Math.min(100, (currentValue / m.threshold_value) * 100)
      };
    }) || [];

    res.json({
      metrics,
      recentJobs: recentJobs || [],
      milestones: updatedMilestones
    });
  } catch (error) {
    logger.error('Dashboard metrics error:', error);
    res.status(500).json({ error: 'Failed to fetch dashboard metrics' });
  }
});

// GET /api/metrics/trends
router.get('/trends', authenticate, [
  query('period').optional().isIn(['7d', '30d', '90d', '12m']),
  query('groupBy').optional().isIn(['day', 'week', 'month'])
], async (req, res) => {
  try {
    const companyId = req.companyId;
    const { period = '30d', groupBy = 'day' } = req.query;

    // Calculate date range
    const endDate = new Date();
    const startDate = new Date();

    switch (period) {
      case '7d':
        startDate.setDate(startDate.getDate() - 7);
        break;
      case '30d':
        startDate.setDate(startDate.getDate() - 30);
        break;
      case '90d':
        startDate.setDate(startDate.getDate() - 90);
        break;
      case '12m':
        startDate.setMonth(startDate.getMonth() - 12);
        break;
    }

    // Fetch jobs in date range
    const { data: jobs } = await supabase
      .from('jobs')
      .select('*')
      .eq('company_id', companyId)
      .eq('status', 'completed')
      .gte('completed_at', startDate.toISOString())
      .lte('completed_at', endDate.toISOString())
      .order('completed_at');

    // Group data by period
    const grouped = {};

    jobs?.forEach(job => {
      const date = new Date(job.completed_at);
      let key;

      switch (groupBy) {
        case 'week':
          const weekStart = new Date(date);
          weekStart.setDate(date.getDate() - date.getDay());
          key = weekStart.toISOString().split('T')[0];
          break;
        case 'month':
          key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
          break;
        default:
          key = date.toISOString().split('T')[0];
      }

      if (!grouped[key]) {
        grouped[key] = {
          date: key,
          jobs: 0,
          totalWeight: 0,
          recycledWeight: 0,
          carbonOffset: 0,
          averageEsgScore: 0,
          esgScores: []
        };
      }

      grouped[key].jobs++;
      grouped[key].totalWeight += job.total_weight_lbs || 0;
      grouped[key].recycledWeight += job.recycled_weight_lbs || 0;
      grouped[key].carbonOffset += job.carbon_offset_lbs || 0;
      grouped[key].esgScores.push(job.esg_score || 0);
    });

    // Calculate averages and format data
    const trends = Object.values(grouped).map(g => ({
      date: g.date,
      jobs: g.jobs,
      totalWeight: Math.round(g.totalWeight),
      recycledWeight: Math.round(g.recycledWeight),
      carbonOffset: Math.round(g.carbonOffset),
      diversionRate: g.totalWeight > 0 ? Math.round((g.recycledWeight / g.totalWeight) * 100) : 0,
      averageEsgScore: g.esgScores.length > 0
        ? Math.round(g.esgScores.reduce((a, b) => a + b, 0) / g.esgScores.length)
        : 0
    }));

    res.json({ trends, period, groupBy });
  } catch (error) {
    logger.error('Trends error:', error);
    res.status(500).json({ error: 'Failed to fetch trends' });
  }
});

// GET /api/metrics/by-category
router.get('/by-category', authenticate, async (req, res) => {
  try {
    const companyId = req.companyId;

    // Fetch all job items for completed jobs
    const { data: items } = await supabase
      .from('job_items')
      .select(`
        *,
        jobs!inner (company_id, status)
      `)
      .eq('jobs.company_id', companyId)
      .eq('jobs.status', 'completed');

    // Group by category
    const categories = {};

    items?.forEach(item => {
      const category = item.category || 'general';

      if (!categories[category]) {
        categories[category] = {
          category,
          itemCount: 0,
          totalWeight: 0,
          recycledWeight: 0,
          carbonOffset: 0
        };
      }

      const weight = (item.weight_lbs || 0) * (item.quantity || 1);
      categories[category].itemCount += item.quantity || 1;
      categories[category].totalWeight += weight;

      if (item.disposal_method === 'recycled' || item.disposal_method === 'donated') {
        categories[category].recycledWeight += weight;
      }

      categories[category].carbonOffset += item.carbon_offset_lbs || 0;
    });

    const categoryData = Object.values(categories)
      .sort((a, b) => b.totalWeight - a.totalWeight)
      .map(c => ({
        ...c,
        diversionRate: c.totalWeight > 0
          ? Math.round((c.recycledWeight / c.totalWeight) * 100)
          : 0
      }));

    res.json({ categories: categoryData });
  } catch (error) {
    logger.error('Category metrics error:', error);
    res.status(500).json({ error: 'Failed to fetch category metrics' });
  }
});

// GET /api/metrics/leaderboard
router.get('/leaderboard', authenticate, async (req, res) => {
  try {
    // Fetch aggregate metrics for all companies (anonymized for competitive display)
    const { data: companies } = await supabase
      .from('companies')
      .select(`
        id,
        name,
        jobs (
          total_weight_lbs,
          recycled_weight_lbs,
          donated_weight_lbs,
          carbon_offset_lbs,
          esg_score,
          status
        )
      `)
      .eq('is_active', true);

    const leaderboard = companies?.map(company => {
      const completedJobs = company.jobs?.filter(j => j.status === 'completed') || [];

      if (completedJobs.length === 0) {
        return null;
      }

      const metrics = completedJobs.reduce((acc, job) => ({
        totalWeight: acc.totalWeight + (job.total_weight_lbs || 0),
        recycledWeight: acc.recycledWeight + (job.recycled_weight_lbs || 0),
        donatedWeight: acc.donatedWeight + (job.donated_weight_lbs || 0),
        carbonOffset: acc.carbonOffset + (job.carbon_offset_lbs || 0),
        totalEsgScore: acc.totalEsgScore + (job.esg_score || 0),
        jobCount: acc.jobCount + 1
      }), { totalWeight: 0, recycledWeight: 0, donatedWeight: 0, carbonOffset: 0, totalEsgScore: 0, jobCount: 0 });

      return {
        companyId: company.id,
        companyName: company.id === req.companyId ? company.name : `Company ${company.id.slice(0, 4)}`,
        isCurrentCompany: company.id === req.companyId,
        totalDiverted: metrics.recycledWeight + metrics.donatedWeight,
        carbonOffset: metrics.carbonOffset,
        averageEsgScore: Math.round(metrics.totalEsgScore / metrics.jobCount),
        jobCount: metrics.jobCount
      };
    }).filter(Boolean)
      .sort((a, b) => b.totalDiverted - a.totalDiverted)
      .slice(0, 10);

    // Add rank
    leaderboard?.forEach((entry, index) => {
      entry.rank = index + 1;
    });

    res.json({ leaderboard });
  } catch (error) {
    logger.error('Leaderboard error:', error);
    res.status(500).json({ error: 'Failed to fetch leaderboard' });
  }
});

// GET /api/metrics/milestones
router.get('/milestones', authenticate, async (req, res) => {
  try {
    const { data: milestones } = await supabase
      .from('milestones')
      .select('*')
      .eq('company_id', req.companyId)
      .order('threshold_value');

    // Fetch current metrics to update progress
    const { data: jobs } = await supabase
      .from('jobs')
      .select('total_weight_lbs, recycled_weight_lbs, donated_weight_lbs, carbon_offset_lbs')
      .eq('company_id', req.companyId)
      .eq('status', 'completed');

    const totals = jobs?.reduce((acc, job) => ({
      diverted: acc.diverted + (job.recycled_weight_lbs || 0) + (job.donated_weight_lbs || 0),
      carbon: acc.carbon + (job.carbon_offset_lbs || 0),
      total: acc.total + (job.total_weight_lbs || 0),
      count: acc.count + 1
    }), { diverted: 0, carbon: 0, total: 0, count: 0 }) || { diverted: 0, carbon: 0, total: 0, count: 0 };

    const diversionRate = totals.total > 0 ? (totals.diverted / totals.total) * 100 : 0;

    const updatedMilestones = milestones?.map(m => {
      let currentValue = 0;
      switch (m.milestone_type) {
        case 'tons_diverted':
          currentValue = totals.diverted;
          break;
        case 'carbon_saved':
          currentValue = totals.carbon;
          break;
        case 'jobs_completed':
          currentValue = totals.count;
          break;
        case 'diversion_rate':
          currentValue = diversionRate;
          break;
      }

      const achieved = currentValue >= m.threshold_value;
      const progress = Math.min(100, (currentValue / m.threshold_value) * 100);

      return {
        ...m,
        current_value: currentValue,
        progress,
        achieved,
        achieved_at: achieved && !m.achieved_at ? new Date().toISOString() : m.achieved_at
      };
    }) || [];

    // Update milestones that were just achieved
    for (const milestone of updatedMilestones) {
      if (milestone.achieved && !milestones.find(m => m.id === milestone.id)?.achieved) {
        await supabase
          .from('milestones')
          .update({
            achieved: true,
            achieved_at: milestone.achieved_at,
            current_value: milestone.current_value
          })
          .eq('id', milestone.id);
      }
    }

    res.json({ milestones: updatedMilestones });
  } catch (error) {
    logger.error('Milestones error:', error);
    res.status(500).json({ error: 'Failed to fetch milestones' });
  }
});

module.exports = router;
