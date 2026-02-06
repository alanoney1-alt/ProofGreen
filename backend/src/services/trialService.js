/**
 * ProofGreen Trial Management Service
 *
 * Handles 14-day free trial logic:
 * - All new signups get 14 days full access
 * - Credit card required at signup
 * - Auto-convert to Starter plan ($149) after 14 days
 * - User can cancel before trial ends
 */

const { supabase } = require('../utils/supabase');
const { logger } = require('../utils/logger');
const stripeService = require('./stripe');
const emailService = require('./email');

// Trial configuration
const TRIAL_CONFIG = {
  durationDays: 14,
  defaultPlanAfterTrial: 'starter',
  defaultPlanPrice: 149, // $149/month
  reminderDays: [7, 3, 1] // Days before trial ends to send reminders
};

/**
 * Start a new trial for a company
 *
 * @param {string} companyId - Company UUID
 * @param {string} stripeCustomerId - Stripe customer ID (card already on file)
 * @returns {Object} Trial details
 */
async function startTrial(companyId, stripeCustomerId) {
  try {
    const trialEndsAt = new Date();
    trialEndsAt.setDate(trialEndsAt.getDate() + TRIAL_CONFIG.durationDays);

    // Update company with trial info
    const { data, error } = await supabase
      .from('companies')
      .update({
        trial_ends_at: trialEndsAt.toISOString(),
        trial_converted: false,
        stripe_customer_id: stripeCustomerId,
        status: 'trialing'
      })
      .eq('id', companyId)
      .select()
      .single();

    if (error) {
      logger.error('Error starting trial:', error);
      throw error;
    }

    // Create subscription record (inactive until trial ends)
    await supabase
      .from('subscriptions')
      .insert({
        company_id: companyId,
        plan_id: TRIAL_CONFIG.defaultPlanAfterTrial,
        status: 'trialing',
        trial_ends_at: trialEndsAt.toISOString(),
        current_period_start: new Date().toISOString(),
        current_period_end: trialEndsAt.toISOString()
      });

    // Send welcome email
    await sendTrialWelcomeEmail(companyId);

    logger.info(`Trial started for company ${companyId}, ends at ${trialEndsAt.toISOString()}`);

    return {
      success: true,
      trialEndsAt: trialEndsAt.toISOString(),
      daysRemaining: TRIAL_CONFIG.durationDays,
      willConvertTo: {
        plan: TRIAL_CONFIG.defaultPlanAfterTrial,
        price: TRIAL_CONFIG.defaultPlanPrice
      }
    };
  } catch (error) {
    logger.error('Error starting trial:', error);
    throw error;
  }
}

/**
 * Get trial status for a company
 */
async function getTrialStatus(companyId) {
  try {
    const { data: company } = await supabase
      .from('companies')
      .select('trial_ends_at, trial_converted, status')
      .eq('id', companyId)
      .single();

    if (!company || !company.trial_ends_at) {
      return { isTrialing: false };
    }

    const trialEndsAt = new Date(company.trial_ends_at);
    const now = new Date();
    const daysRemaining = Math.ceil((trialEndsAt - now) / (1000 * 60 * 60 * 24));

    return {
      isTrialing: company.status === 'trialing' && !company.trial_converted,
      trialEndsAt: company.trial_ends_at,
      daysRemaining: Math.max(0, daysRemaining),
      isExpired: daysRemaining <= 0,
      willConvertTo: {
        plan: TRIAL_CONFIG.defaultPlanAfterTrial,
        price: TRIAL_CONFIG.defaultPlanPrice
      }
    };
  } catch (error) {
    logger.error('Error getting trial status:', error);
    return { isTrialing: false };
  }
}

/**
 * Convert trial to paid subscription
 * Called automatically when trial ends or when user upgrades early
 */
async function convertTrial(companyId, selectedPlan = null) {
  try {
    const planToUse = selectedPlan || TRIAL_CONFIG.defaultPlanAfterTrial;

    // Get company and subscription info
    const { data: company } = await supabase
      .from('companies')
      .select('stripe_customer_id, owner_email, name')
      .eq('id', companyId)
      .single();

    if (!company?.stripe_customer_id) {
      throw new Error('No payment method on file');
    }

    // Get plan details
    const { data: plan } = await supabase
      .from('pricing_plans')
      .select('*')
      .eq('plan_name', planToUse)
      .single();

    if (!plan) {
      throw new Error('Plan not found');
    }

    // Create Stripe subscription
    const stripeSubscription = await stripeService.createSubscription(
      company.stripe_customer_id,
      plan.stripe_price_id
    );

    // Update subscription record
    await supabase
      .from('subscriptions')
      .update({
        status: 'active',
        stripe_subscription_id: stripeSubscription.id,
        current_period_start: new Date().toISOString(),
        current_period_end: new Date(stripeSubscription.current_period_end * 1000).toISOString()
      })
      .eq('company_id', companyId);

    // Update company status
    await supabase
      .from('companies')
      .update({
        trial_converted: true,
        status: 'active'
      })
      .eq('id', companyId);

    // Send conversion confirmation email
    await emailService.send({
      to: company.owner_email,
      subject: 'Welcome to ProofGreen! Your subscription is now active',
      body: `Hi ${company.name.split(' ')[0]},

Your 14-day trial has ended and your ${plan.display_name} subscription is now active!

You'll be billed $${plan.price_monthly}/month going forward.

Thank you for choosing ProofGreen. If you have any questions, just reply to this email.

Best,
The ProofGreen Team`
    });

    logger.info(`Trial converted for company ${companyId} to ${planToUse}`);

    return {
      success: true,
      plan: planToUse,
      subscriptionId: stripeSubscription.id
    };
  } catch (error) {
    logger.error('Error converting trial:', error);
    throw error;
  }
}

/**
 * Cancel trial before it ends
 */
async function cancelTrial(companyId, reason = null) {
  try {
    // Get company info
    const { data: company } = await supabase
      .from('companies')
      .select('stripe_customer_id, owner_email, name')
      .eq('id', companyId)
      .single();

    // Cancel any pending Stripe setup
    if (company?.stripe_customer_id) {
      // Delete payment method from Stripe (optional - prevents accidental charges)
      // await stripeService.deletePaymentMethods(company.stripe_customer_id);
    }

    // Update company status
    await supabase
      .from('companies')
      .update({
        status: 'canceled',
        canceled_at: new Date().toISOString(),
        cancellation_reason: reason
      })
      .eq('id', companyId);

    // Update subscription
    await supabase
      .from('subscriptions')
      .update({ status: 'canceled' })
      .eq('company_id', companyId);

    // Send cancellation email
    await emailService.send({
      to: company.owner_email,
      subject: 'We\'re sorry to see you go',
      body: `Hi ${company.name.split(' ')[0]},

Your ProofGreen trial has been canceled. We're sorry it wasn't the right fit.

If there's anything we could have done better, please reply to this email - we read every message.

If you change your mind, you can always start a new trial at proofgreen.io.

Best,
Alan
Founder, ProofGreen`
    });

    logger.info(`Trial canceled for company ${companyId}`);

    return { success: true };
  } catch (error) {
    logger.error('Error canceling trial:', error);
    throw error;
  }
}

/**
 * Process expiring trials (run daily via cron)
 */
async function processExpiringTrials() {
  logger.info('Processing expiring trials...');

  try {
    const now = new Date();

    // Find trials that expired
    const { data: expiredTrials } = await supabase
      .from('companies')
      .select('id')
      .eq('status', 'trialing')
      .eq('trial_converted', false)
      .lt('trial_ends_at', now.toISOString());

    // Convert expired trials
    for (const company of expiredTrials || []) {
      try {
        await convertTrial(company.id);
      } catch (error) {
        logger.error(`Failed to convert trial for ${company.id}:`, error);
        // Mark as conversion failed for manual review
        await supabase
          .from('companies')
          .update({ status: 'conversion_failed' })
          .eq('id', company.id);
      }
    }

    // Send reminder emails for trials ending soon
    for (const days of TRIAL_CONFIG.reminderDays) {
      const reminderDate = new Date();
      reminderDate.setDate(reminderDate.getDate() + days);

      const startOfDay = new Date(reminderDate);
      startOfDay.setHours(0, 0, 0, 0);

      const endOfDay = new Date(reminderDate);
      endOfDay.setHours(23, 59, 59, 999);

      const { data: upcomingExpiries } = await supabase
        .from('companies')
        .select('id, name, owner_email, trial_ends_at')
        .eq('status', 'trialing')
        .eq('trial_converted', false)
        .gte('trial_ends_at', startOfDay.toISOString())
        .lte('trial_ends_at', endOfDay.toISOString());

      for (const company of upcomingExpiries || []) {
        await sendTrialReminderEmail(company, days);
      }
    }

    logger.info(`Processed ${expiredTrials?.length || 0} expired trials`);

    return {
      converted: expiredTrials?.length || 0
    };
  } catch (error) {
    logger.error('Error processing expiring trials:', error);
    throw error;
  }
}

/**
 * Send trial welcome email
 */
async function sendTrialWelcomeEmail(companyId) {
  const { data: company } = await supabase
    .from('companies')
    .select('name, owner_email, trial_ends_at')
    .eq('id', companyId)
    .single();

  if (!company) return;

  const trialEndsAt = new Date(company.trial_ends_at);
  const formattedDate = trialEndsAt.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });

  await emailService.send({
    to: company.owner_email,
    subject: 'Welcome to ProofGreen! Your 14-day trial has started',
    body: `Hi ${company.name.split(' ')[0]},

Welcome to ProofGreen! Your 14-day free trial is now active.

WHAT YOU GET:
- Full access to all features
- Unlimited jobs during trial
- AI-powered photo analysis
- Professional ESG reports

YOUR TRIAL ENDS: ${formattedDate}

After your trial ends, you'll be automatically subscribed to our Starter plan ($149/month). You can cancel anytime before then.

GETTING STARTED:
1. Log a job and upload photos
2. Let our AI analyze your ESG metrics
3. Generate your first sustainability report

Need help? Just reply to this email.

Best,
The ProofGreen Team`
  });
}

/**
 * Send trial reminder email
 */
async function sendTrialReminderEmail(company, daysRemaining) {
  const urgency = daysRemaining === 1 ? 'LAST DAY' : `${daysRemaining} days left`;

  await emailService.send({
    to: company.owner_email,
    subject: `[${urgency}] Your ProofGreen trial ends soon`,
    body: `Hi ${company.name.split(' ')[0]},

Your ProofGreen trial ends in ${daysRemaining} day${daysRemaining === 1 ? '' : 's'}.

After your trial ends, you'll be automatically subscribed to our Starter plan ($149/month).

NOT READY TO CONTINUE?
Reply to this email before your trial ends to cancel - no charge.

WANT TO UPGRADE?
Visit your account settings to choose a different plan before your trial ends.

Questions? Just reply to this email.

Best,
The ProofGreen Team`
  });
}

module.exports = {
  startTrial,
  getTrialStatus,
  convertTrial,
  cancelTrial,
  processExpiringTrials,
  TRIAL_CONFIG
};
