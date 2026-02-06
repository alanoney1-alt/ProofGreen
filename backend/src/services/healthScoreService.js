/**
 * ProofGreen Customer Health Score Service
 *
 * Tracks customer engagement and predicts churn risk based on:
 * - Usage patterns (jobs logged)
 * - Login frequency
 * - Feature adoption
 * - Vertical activity
 *
 * Triggers proactive interventions for at-risk customers.
 */

const { supabase } = require('../utils/supabase');
const { logger } = require('../utils/logger');
const emailService = require('./email');

/**
 * Risk level thresholds
 */
const RISK_LEVELS = {
  CRITICAL: { min: 0, max: 29, label: 'critical', color: 'red', action: 'immediate_outreach' },
  HIGH: { min: 30, max: 49, label: 'high', color: 'orange', action: 'check_in_email' },
  MEDIUM: { min: 50, max: 69, label: 'medium', color: 'yellow', action: 'monitor' },
  LOW: { min: 70, max: 100, label: 'low', color: 'green', action: 'none' }
};

/**
 * Calculate comprehensive health score for a company
 *
 * @param {string} companyId - Company UUID
 * @returns {Object} Health score with metrics, risk level, and issues
 */
async function calculateHealthScore(companyId) {
  try {
    // Get company metrics
    const { data: company, error: companyError } = await supabase
      .from('companies')
      .select('id, name, created_at, owner_email')
      .eq('id', companyId)
      .single();

    if (companyError || !company) {
      logger.error('Company not found for health score:', companyId);
      return null;
    }

    // Get jobs metrics
    const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
    const ninetyDaysAgo = new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString();

    const { data: recentJobs } = await supabase
      .from('jobs')
      .select('id, created_at')
      .eq('company_id', companyId)
      .gte('created_at', thirtyDaysAgo);

    const { data: allJobs } = await supabase
      .from('jobs')
      .select('id, created_at')
      .eq('company_id', companyId)
      .gte('created_at', ninetyDaysAgo);

    // Get user login data
    const { data: users } = await supabase
      .from('users')
      .select('id, last_login, login_count')
      .eq('company_id', companyId);

    // Get active verticals
    const { data: verticals } = await supabase
      .from('company_verticals')
      .select('id, vertical_id')
      .eq('company_id', companyId)
      .eq('active', true);

    // Calculate metrics
    const jobsThisMonth = recentJobs?.length || 0;
    const jobsLast90Days = allJobs?.length || 0;
    const avgJobsPerMonth = jobsLast90Days / 3;

    const mostRecentLogin = users?.reduce((latest, user) => {
      if (!user.last_login) return latest;
      const loginDate = new Date(user.last_login);
      return loginDate > latest ? loginDate : latest;
    }, new Date(0));

    const daysSinceLogin = mostRecentLogin.getTime() > 0
      ? Math.floor((Date.now() - mostRecentLogin.getTime()) / (1000 * 60 * 60 * 24))
      : 999;

    const verticalsActive = verticals?.length || 0;

    // Calculate score components
    let score = 0;
    const issues = [];
    const positives = [];

    // Usage Score (40 points max)
    if (jobsThisMonth === 0) {
      issues.push({
        urgency: 'critical',
        category: 'usage',
        message: 'No jobs logged this month',
        suggestion: 'Check if they need help with the platform'
      });
    } else if (jobsThisMonth >= avgJobsPerMonth) {
      score += 40;
      positives.push('Usage maintained or growing');
    } else if (jobsThisMonth >= avgJobsPerMonth * 0.5) {
      score += 25;
      issues.push({
        urgency: 'medium',
        category: 'usage',
        message: 'Usage declined from average',
        suggestion: 'Check if there are seasonal factors or issues'
      });
    } else {
      score += 10;
      issues.push({
        urgency: 'high',
        category: 'usage',
        message: 'Significant usage decline',
        suggestion: 'Immediate outreach recommended'
      });
    }

    // Engagement Score (30 points max)
    if (daysSinceLogin > 30) {
      issues.push({
        urgency: 'critical',
        category: 'engagement',
        message: 'No login in 30+ days',
        suggestion: 'Send re-engagement email'
      });
    } else if (daysSinceLogin > 14) {
      score += 10;
      issues.push({
        urgency: 'high',
        category: 'engagement',
        message: 'Login frequency low (14+ days)',
        suggestion: 'Send check-in email'
      });
    } else if (daysSinceLogin > 7) {
      score += 20;
      issues.push({
        urgency: 'medium',
        category: 'engagement',
        message: 'Login frequency moderate',
        suggestion: 'Monitor'
      });
    } else {
      score += 30;
      positives.push('Active user engagement');
    }

    // Feature Adoption Score (20 points max)
    if (verticalsActive >= 3) {
      score += 20;
      positives.push('Using multiple verticals');
    } else if (verticalsActive >= 2) {
      score += 15;
    } else if (verticalsActive === 1) {
      score += 10;
      issues.push({
        urgency: 'low',
        category: 'adoption',
        message: 'Only using one vertical',
        suggestion: 'Educate on additional verticals'
      });
    } else {
      issues.push({
        urgency: 'medium',
        category: 'adoption',
        message: 'No verticals configured',
        suggestion: 'Help with onboarding'
      });
    }

    // Account Age Bonus (10 points max)
    const accountAgeDays = Math.floor(
      (Date.now() - new Date(company.created_at).getTime()) / (1000 * 60 * 60 * 24)
    );

    if (accountAgeDays > 180 && score > 50) {
      score += 10;
      positives.push('Long-term customer');
    } else if (accountAgeDays < 30) {
      // New accounts get a grace period
      score += 5;
    }

    // Ensure score is within bounds
    score = Math.max(0, Math.min(100, score));

    // Determine risk level
    let riskLevel;
    if (score < RISK_LEVELS.CRITICAL.max) {
      riskLevel = 'critical';
    } else if (score < RISK_LEVELS.HIGH.max) {
      riskLevel = 'high';
    } else if (score < RISK_LEVELS.MEDIUM.max) {
      riskLevel = 'medium';
    } else {
      riskLevel = 'low';
    }

    return {
      companyId,
      companyName: company.name,
      ownerEmail: company.owner_email,
      score,
      riskLevel,
      issues,
      positives,
      metrics: {
        jobsThisMonth,
        avgJobsPerMonth: avgJobsPerMonth.toFixed(1),
        daysSinceLogin,
        verticalsActive,
        accountAgeDays
      },
      recommendations: generateRecommendations(issues),
      calculatedAt: new Date().toISOString()
    };
  } catch (error) {
    logger.error('Error calculating health score:', error);
    return null;
  }
}

/**
 * Generate actionable recommendations based on issues
 */
function generateRecommendations(issues) {
  const recommendations = [];
  const criticalIssues = issues.filter(i => i.urgency === 'critical');
  const highIssues = issues.filter(i => i.urgency === 'high');

  if (criticalIssues.length > 0) {
    recommendations.push({
      priority: 1,
      action: 'immediate_call',
      message: 'Schedule a call with this customer - critical churn risk'
    });
  }

  if (highIssues.some(i => i.category === 'engagement')) {
    recommendations.push({
      priority: 2,
      action: 'send_checkin_email',
      message: 'Send personalized check-in email'
    });
  }

  if (issues.some(i => i.category === 'adoption')) {
    recommendations.push({
      priority: 3,
      action: 'training_offer',
      message: 'Offer training session for additional features'
    });
  }

  return recommendations;
}

/**
 * Run daily health checks for all active companies
 */
async function runDailyHealthChecks() {
  logger.info('Starting daily health checks...');

  try {
    // Get all active companies with subscriptions
    const { data: companies, error } = await supabase
      .from('companies')
      .select('id, name, owner_email')
      .eq('status', 'active');

    if (error) {
      logger.error('Error fetching companies:', error);
      return;
    }

    let processed = 0;
    let criticalCount = 0;
    let highRiskCount = 0;

    for (const company of companies || []) {
      const health = await calculateHealthScore(company.id);

      if (!health) continue;

      // Store health score
      await supabase
        .from('customer_health_scores')
        .insert({
          company_id: company.id,
          score: health.score,
          risk_level: health.riskLevel,
          issues: health.issues,
          metrics: health.metrics,
          created_at: new Date().toISOString()
        });

      // Trigger interventions based on risk level
      if (health.riskLevel === 'critical') {
        criticalCount++;
        await sendCriticalAlert(company, health);
      } else if (health.riskLevel === 'high') {
        highRiskCount++;
        await sendCheckInEmail(company, health);
      }

      processed++;
    }

    logger.info(`Daily health checks complete: ${processed} companies processed, ${criticalCount} critical, ${highRiskCount} high risk`);

    return {
      processed,
      criticalCount,
      highRiskCount
    };
  } catch (error) {
    logger.error('Error running daily health checks:', error);
    throw error;
  }
}

/**
 * Send critical churn alert to internal team
 */
async function sendCriticalAlert(company, health) {
  try {
    // Log the alert
    await supabase
      .from('customer_alerts')
      .insert({
        company_id: company.id,
        alert_type: 'critical_churn_risk',
        severity: 'critical',
        details: {
          score: health.score,
          issues: health.issues,
          metrics: health.metrics
        },
        created_at: new Date().toISOString()
      });

    // Send internal alert email (to ProofGreen team)
    if (process.env.INTERNAL_ALERT_EMAIL) {
      await emailService.send({
        to: process.env.INTERNAL_ALERT_EMAIL,
        subject: `[CRITICAL] Churn Risk Alert: ${company.name}`,
        body: `
CRITICAL CHURN RISK DETECTED

Company: ${company.name}
Health Score: ${health.score}/100
Owner Email: ${company.owner_email}

Issues:
${health.issues.map(i => `- [${i.urgency.toUpperCase()}] ${i.message}`).join('\n')}

Metrics:
- Jobs this month: ${health.metrics.jobsThisMonth}
- Days since login: ${health.metrics.daysSinceLogin}
- Verticals active: ${health.metrics.verticalsActive}

ACTION REQUIRED: Schedule a call with this customer immediately.
        `
      });
    }

    logger.info(`Critical alert sent for company ${company.id}`);
  } catch (error) {
    logger.error('Error sending critical alert:', error);
  }
}

/**
 * Send personalized check-in email to customer
 */
async function sendCheckInEmail(company, health) {
  try {
    // Check if we've sent a check-in recently (avoid spamming)
    const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();

    const { data: recentEmails } = await supabase
      .from('customer_emails')
      .select('id')
      .eq('company_id', company.id)
      .eq('email_type', 'check_in')
      .gte('sent_at', sevenDaysAgo);

    if (recentEmails && recentEmails.length > 0) {
      logger.info(`Skipping check-in for ${company.id} - sent recently`);
      return;
    }

    // Send check-in email
    const firstName = company.name.split(' ')[0];

    await emailService.send({
      to: company.owner_email,
      subject: "Quick check-in - How's ProofGreen working for you?",
      body: `Hi ${firstName},

I noticed you haven't been using ProofGreen much lately. Just wanted to check in!

Common issues we can help with:
- Not sure how to use a feature?
- Need help with a specific workflow?
- Want to see what's new?

Reply to this email - I read every message personally.

Best,
Alan
Founder, ProofGreen

P.S. If everything's great and you're just busy, no worries! We're here when you need us.`
    });

    // Log the email
    await supabase
      .from('customer_emails')
      .insert({
        company_id: company.id,
        email_type: 'check_in',
        subject: "Quick check-in - How's ProofGreen working for you?",
        sent_at: new Date().toISOString()
      });

    logger.info(`Check-in email sent to company ${company.id}`);
  } catch (error) {
    logger.error('Error sending check-in email:', error);
  }
}

/**
 * Get health score history for a company
 */
async function getHealthScoreHistory(companyId, days = 30) {
  const startDate = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();

  const { data, error } = await supabase
    .from('customer_health_scores')
    .select('*')
    .eq('company_id', companyId)
    .gte('created_at', startDate)
    .order('created_at', { ascending: true });

  if (error) {
    logger.error('Error fetching health score history:', error);
    return [];
  }

  return data || [];
}

/**
 * Get all at-risk customers (for admin dashboard)
 */
async function getAtRiskCustomers() {
  const { data, error } = await supabase
    .from('customer_health_scores')
    .select(`
      *,
      companies (id, name, owner_email)
    `)
    .in('risk_level', ['critical', 'high'])
    .order('score', { ascending: true })
    .limit(50);

  if (error) {
    logger.error('Error fetching at-risk customers:', error);
    return [];
  }

  return data || [];
}

module.exports = {
  calculateHealthScore,
  runDailyHealthChecks,
  getHealthScoreHistory,
  getAtRiskCustomers,
  sendCheckInEmail,
  RISK_LEVELS
};
