const Stripe = require('stripe');
const { supabase } = require('../utils/supabase');
const { logger } = require('../utils/logger');

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY);

const PRICE_IDS = {
  founders_monthly: process.env.STRIPE_PRICE_FOUNDERS_MONTHLY,
  founders_yearly: process.env.STRIPE_PRICE_FOUNDERS_YEARLY,
  starter_monthly: process.env.STRIPE_PRICE_STARTER_MONTHLY,
  starter_yearly: process.env.STRIPE_PRICE_STARTER_YEARLY,
  professional_monthly: process.env.STRIPE_PRICE_PROFESSIONAL_MONTHLY,
  professional_yearly: process.env.STRIPE_PRICE_PROFESSIONAL_YEARLY,
  business_monthly: process.env.STRIPE_PRICE_BUSINESS_MONTHLY,
  business_yearly: process.env.STRIPE_PRICE_BUSINESS_YEARLY,
  enterprise_monthly: process.env.STRIPE_PRICE_ENTERPRISE_MONTHLY,
  enterprise_yearly: process.env.STRIPE_PRICE_ENTERPRISE_YEARLY
};

/**
 * Create a Stripe customer for a company
 */
async function createCustomer(company, user) {
  try {
    const customer = await stripe.customers.create({
      email: user.email,
      name: company.name,
      metadata: {
        company_id: company.id,
        user_id: user.id
      }
    });

    // Update company with Stripe customer ID
    await supabase
      .from('companies')
      .update({ stripe_customer_id: customer.id })
      .eq('id', company.id);

    logger.info(`Created Stripe customer ${customer.id} for company ${company.id}`);
    return customer;
  } catch (error) {
    logger.error('Failed to create Stripe customer:', error);
    throw error;
  }
}

/**
 * Create a checkout session for subscription
 */
async function createCheckoutSession(companyId, planSlug, billingCycle, successUrl, cancelUrl) {
  try {
    // Get company and check for existing customer
    const { data: company } = await supabase
      .from('companies')
      .select('*, users(*)')
      .eq('id', companyId)
      .single();

    if (!company) {
      throw new Error('Company not found');
    }

    let customerId = company.stripe_customer_id;

    // Create customer if doesn't exist
    if (!customerId) {
      const owner = company.users.find(u => u.role === 'owner') || company.users[0];
      const customer = await createCustomer(company, owner);
      customerId = customer.id;
    }

    // Get price ID
    const priceKey = `${planSlug}_${billingCycle}`;
    const priceId = PRICE_IDS[priceKey];

    if (!priceId) {
      throw new Error(`No price configured for ${priceKey}`);
    }

    // Create checkout session
    const session = await stripe.checkout.sessions.create({
      customer: customerId,
      payment_method_types: ['card'],
      line_items: [{
        price: priceId,
        quantity: 1
      }],
      mode: 'subscription',
      success_url: `${successUrl}?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: cancelUrl,
      metadata: {
        company_id: companyId,
        plan_slug: planSlug,
        billing_cycle: billingCycle
      },
      subscription_data: {
        metadata: {
          company_id: companyId
        }
      },
      allow_promotion_codes: true
    });

    logger.info(`Created checkout session ${session.id} for company ${companyId}`);
    return session;
  } catch (error) {
    logger.error('Failed to create checkout session:', error);
    throw error;
  }
}

/**
 * Create a billing portal session
 */
async function createBillingPortalSession(companyId, returnUrl) {
  try {
    const { data: company } = await supabase
      .from('companies')
      .select('stripe_customer_id')
      .eq('id', companyId)
      .single();

    if (!company?.stripe_customer_id) {
      throw new Error('No Stripe customer found for this company');
    }

    const session = await stripe.billingPortal.sessions.create({
      customer: company.stripe_customer_id,
      return_url: returnUrl
    });

    return session;
  } catch (error) {
    logger.error('Failed to create billing portal session:', error);
    throw error;
  }
}

/**
 * Cancel a subscription
 */
async function cancelSubscription(subscriptionId, cancelAtPeriodEnd = true) {
  try {
    const subscription = await stripe.subscriptions.update(subscriptionId, {
      cancel_at_period_end: cancelAtPeriodEnd
    });

    logger.info(`Subscription ${subscriptionId} set to cancel at period end`);
    return subscription;
  } catch (error) {
    logger.error('Failed to cancel subscription:', error);
    throw error;
  }
}

/**
 * Reactivate a cancelled subscription
 */
async function reactivateSubscription(subscriptionId) {
  try {
    const subscription = await stripe.subscriptions.update(subscriptionId, {
      cancel_at_period_end: false
    });

    logger.info(`Subscription ${subscriptionId} reactivated`);
    return subscription;
  } catch (error) {
    logger.error('Failed to reactivate subscription:', error);
    throw error;
  }
}

/**
 * Update subscription plan
 */
async function updateSubscription(subscriptionId, newPriceId, prorationBehavior = 'create_prorations') {
  try {
    const subscription = await stripe.subscriptions.retrieve(subscriptionId);

    const updatedSubscription = await stripe.subscriptions.update(subscriptionId, {
      items: [{
        id: subscription.items.data[0].id,
        price: newPriceId
      }],
      proration_behavior: prorationBehavior
    });

    logger.info(`Subscription ${subscriptionId} updated to new price ${newPriceId}`);
    return updatedSubscription;
  } catch (error) {
    logger.error('Failed to update subscription:', error);
    throw error;
  }
}

/**
 * Get subscription details
 */
async function getSubscription(subscriptionId) {
  try {
    const subscription = await stripe.subscriptions.retrieve(subscriptionId, {
      expand: ['default_payment_method', 'latest_invoice']
    });
    return subscription;
  } catch (error) {
    logger.error('Failed to get subscription:', error);
    throw error;
  }
}

/**
 * Handle Stripe webhook events
 */
async function handleWebhookEvent(event) {
  try {
    switch (event.type) {
      case 'checkout.session.completed':
        await handleCheckoutCompleted(event.data.object);
        break;

      case 'customer.subscription.created':
      case 'customer.subscription.updated':
        await handleSubscriptionUpdated(event.data.object);
        break;

      case 'customer.subscription.deleted':
        await handleSubscriptionDeleted(event.data.object);
        break;

      case 'invoice.payment_succeeded':
        await handlePaymentSucceeded(event.data.object);
        break;

      case 'invoice.payment_failed':
        await handlePaymentFailed(event.data.object);
        break;

      default:
        logger.info(`Unhandled webhook event type: ${event.type}`);
    }
  } catch (error) {
    logger.error('Webhook handler error:', error);
    throw error;
  }
}

async function handleCheckoutCompleted(session) {
  const { company_id, plan_slug, billing_cycle } = session.metadata;

  logger.info(`Checkout completed for company ${company_id}, plan ${plan_slug}`);

  // Get plan ID from database
  const { data: plan } = await supabase
    .from('pricing_plans')
    .select('id')
    .eq('slug', plan_slug)
    .single();

  if (!plan) {
    logger.error(`Plan ${plan_slug} not found`);
    return;
  }

  // Update or create subscription record
  await supabase
    .from('subscriptions')
    .upsert({
      company_id,
      plan_id: plan.id,
      status: 'active',
      billing_cycle,
      stripe_subscription_id: session.subscription,
      stripe_customer_id: session.customer,
      current_period_start: new Date().toISOString(),
      current_period_end: new Date(Date.now() + (billing_cycle === 'yearly' ? 365 : 30) * 24 * 60 * 60 * 1000).toISOString()
    }, {
      onConflict: 'company_id'
    });
}

async function handleSubscriptionUpdated(subscription) {
  const companyId = subscription.metadata.company_id;

  if (!companyId) {
    logger.warn('Subscription update missing company_id metadata');
    return;
  }

  const status = subscription.cancel_at_period_end ? 'cancelled' : subscription.status;

  await supabase
    .from('subscriptions')
    .update({
      status: status === 'active' ? 'active' : status === 'past_due' ? 'past_due' : status,
      current_period_start: new Date(subscription.current_period_start * 1000).toISOString(),
      current_period_end: new Date(subscription.current_period_end * 1000).toISOString(),
      cancelled_at: subscription.canceled_at ? new Date(subscription.canceled_at * 1000).toISOString() : null
    })
    .eq('stripe_subscription_id', subscription.id);

  logger.info(`Subscription ${subscription.id} updated to status ${status}`);
}

async function handleSubscriptionDeleted(subscription) {
  await supabase
    .from('subscriptions')
    .update({
      status: 'cancelled',
      cancelled_at: new Date().toISOString()
    })
    .eq('stripe_subscription_id', subscription.id);

  logger.info(`Subscription ${subscription.id} deleted`);
}

async function handlePaymentSucceeded(invoice) {
  logger.info(`Payment succeeded for invoice ${invoice.id}`);
  // Could send email notification here
}

async function handlePaymentFailed(invoice) {
  logger.warn(`Payment failed for invoice ${invoice.id}`);

  // Update subscription status
  if (invoice.subscription) {
    await supabase
      .from('subscriptions')
      .update({ status: 'past_due' })
      .eq('stripe_subscription_id', invoice.subscription);
  }

  // Could send email notification here
}

/**
 * Verify webhook signature
 */
function verifyWebhookSignature(payload, signature) {
  try {
    return stripe.webhooks.constructEvent(
      payload,
      signature,
      process.env.STRIPE_WEBHOOK_SECRET
    );
  } catch (error) {
    logger.error('Webhook signature verification failed:', error);
    throw error;
  }
}

module.exports = {
  stripe,
  createCustomer,
  createCheckoutSession,
  createBillingPortalSession,
  cancelSubscription,
  reactivateSubscription,
  updateSubscription,
  getSubscription,
  handleWebhookEvent,
  verifyWebhookSignature,
  PRICE_IDS
};
