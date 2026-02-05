const express = require('express');
const router = express.Router();
const { body } = require('express-validator');
const { supabase } = require('../utils/supabase');
const { authenticate, authorize } = require('../middleware/auth');
const { logger } = require('../utils/logger');

// GET /api/subscriptions/plans
router.get('/plans', async (req, res) => {
  try {
    const { data: plans, error } = await supabase
      .from('pricing_plans')
      .select('*')
      .eq('is_active', true)
      .order('display_order');

    if (error) {
      return res.status(500).json({ error: 'Failed to fetch plans' });
    }

    res.json({ plans });
  } catch (error) {
    logger.error('Get plans error:', error);
    res.status(500).json({ error: 'Failed to fetch plans' });
  }
});

// GET /api/subscriptions/current
router.get('/current', authenticate, async (req, res) => {
  try {
    const { data: subscription, error } = await supabase
      .from('subscriptions')
      .select(`
        *,
        pricing_plans (*)
      `)
      .eq('company_id', req.companyId)
      .in('status', ['active', 'trialing'])
      .order('created_at', { ascending: false })
      .limit(1)
      .single();

    if (error && error.code !== 'PGRST116') {
      return res.status(500).json({ error: 'Failed to fetch subscription' });
    }

    // Calculate usage
    const { count: jobCount } = await supabase
      .from('jobs')
      .select('*', { count: 'exact', head: true })
      .eq('company_id', req.companyId)
      .gte('created_at', new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString());

    const { count: userCount } = await supabase
      .from('users')
      .select('*', { count: 'exact', head: true })
      .eq('company_id', req.companyId)
      .eq('is_active', true);

    const usage = {
      jobs: {
        used: jobCount || 0,
        limit: subscription?.pricing_plans?.job_limit || null,
        percentage: subscription?.pricing_plans?.job_limit
          ? Math.round((jobCount / subscription.pricing_plans.job_limit) * 100)
          : 0
      },
      users: {
        used: userCount || 0,
        limit: subscription?.pricing_plans?.user_limit || null,
        percentage: subscription?.pricing_plans?.user_limit
          ? Math.round((userCount / subscription.pricing_plans.user_limit) * 100)
          : 0
      }
    };

    res.json({
      subscription: subscription || null,
      usage
    });
  } catch (error) {
    logger.error('Get subscription error:', error);
    res.status(500).json({ error: 'Failed to fetch subscription' });
  }
});

// POST /api/subscriptions/upgrade
router.post('/upgrade', authenticate, authorize('owner', 'admin'), [
  body('planId').notEmpty()
], async (req, res) => {
  try {
    const { planId, billingCycle = 'monthly' } = req.body;

    // Verify plan exists
    const { data: plan, error: planError } = await supabase
      .from('pricing_plans')
      .select('*')
      .eq('id', planId)
      .eq('is_active', true)
      .single();

    if (planError || !plan) {
      return res.status(404).json({ error: 'Plan not found' });
    }

    // Get current subscription
    const { data: currentSub } = await supabase
      .from('subscriptions')
      .select('*')
      .eq('company_id', req.companyId)
      .in('status', ['active', 'trialing'])
      .single();

    if (currentSub) {
      // Update existing subscription
      const { data: subscription, error } = await supabase
        .from('subscriptions')
        .update({
          plan_id: planId,
          billing_cycle: billingCycle,
          status: 'active',
          current_period_start: new Date().toISOString(),
          current_period_end: new Date(
            new Date().setMonth(new Date().getMonth() + (billingCycle === 'yearly' ? 12 : 1))
          ).toISOString()
        })
        .eq('id', currentSub.id)
        .select(`
          *,
          pricing_plans (*)
        `)
        .single();

      if (error) {
        return res.status(500).json({ error: 'Failed to upgrade subscription' });
      }

      return res.json({
        subscription,
        message: `Successfully upgraded to ${plan.name}`
      });
    } else {
      // Create new subscription
      const { data: subscription, error } = await supabase
        .from('subscriptions')
        .insert({
          company_id: req.companyId,
          plan_id: planId,
          billing_cycle: billingCycle,
          status: 'active',
          current_period_start: new Date().toISOString(),
          current_period_end: new Date(
            new Date().setMonth(new Date().getMonth() + (billingCycle === 'yearly' ? 12 : 1))
          ).toISOString()
        })
        .select(`
          *,
          pricing_plans (*)
        `)
        .single();

      if (error) {
        return res.status(500).json({ error: 'Failed to create subscription' });
      }

      return res.status(201).json({
        subscription,
        message: `Successfully subscribed to ${plan.name}`
      });
    }
  } catch (error) {
    logger.error('Upgrade subscription error:', error);
    res.status(500).json({ error: 'Failed to upgrade subscription' });
  }
});

// POST /api/subscriptions/cancel
router.post('/cancel', authenticate, authorize('owner', 'admin'), async (req, res) => {
  try {
    const { data: subscription, error } = await supabase
      .from('subscriptions')
      .update({
        status: 'cancelled',
        cancelled_at: new Date().toISOString()
      })
      .eq('company_id', req.companyId)
      .in('status', ['active', 'trialing'])
      .select()
      .single();

    if (error || !subscription) {
      return res.status(404).json({ error: 'No active subscription found' });
    }

    res.json({
      subscription,
      message: 'Subscription cancelled. You will retain access until the end of your billing period.'
    });
  } catch (error) {
    logger.error('Cancel subscription error:', error);
    res.status(500).json({ error: 'Failed to cancel subscription' });
  }
});

// GET /api/subscriptions/history
router.get('/history', authenticate, async (req, res) => {
  try {
    const { data: subscriptions, error } = await supabase
      .from('subscriptions')
      .select(`
        *,
        pricing_plans (name, price_monthly, price_yearly)
      `)
      .eq('company_id', req.companyId)
      .order('created_at', { ascending: false });

    if (error) {
      return res.status(500).json({ error: 'Failed to fetch subscription history' });
    }

    res.json({ subscriptions });
  } catch (error) {
    logger.error('Get subscription history error:', error);
    res.status(500).json({ error: 'Failed to fetch subscription history' });
  }
});

// POST /api/subscriptions/webhook (Stripe webhook - placeholder)
router.post('/webhook', express.raw({ type: 'application/json' }), async (req, res) => {
  // TODO: Implement Stripe webhook handling
  // This would handle subscription updates from Stripe

  logger.info('Stripe webhook received');
  res.json({ received: true });
});

module.exports = router;
