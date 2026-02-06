/**
 * ProofGreen Referral System Routes
 *
 * Enables customers to refer other businesses and earn rewards:
 * - $500 credit for each successful referral
 * - Referral tracking and status
 * - Automated email invitations
 */

const express = require('express');
const router = express.Router();
const { body, validationResult } = require('express-validator');
const { supabase } = require('../utils/supabase');
const { authenticate } = require('../middleware/auth');
const { logger } = require('../utils/logger');
const emailService = require('../services/email');
const crypto = require('crypto');

// Referral reward amount
const REFERRAL_REWARD = 500.00; // $500 per successful referral

/**
 * GET /api/referrals/my-program
 * Get current user's referral program details
 */
router.get('/my-program', authenticate, async (req, res) => {
  try {
    // Get or create referral program for this company
    let { data: program, error } = await supabase
      .from('referral_programs')
      .select('*')
      .eq('company_id', req.companyId)
      .single();

    // Create program if doesn't exist
    if (!program) {
      const referralCode = generateReferralCode(req.companyId);

      const { data: newProgram, error: createError } = await supabase
        .from('referral_programs')
        .insert({
          company_id: req.companyId,
          referral_code: referralCode,
          referrals_sent: 0,
          referrals_converted: 0,
          total_rewards_earned: 0
        })
        .select()
        .single();

      if (createError) {
        logger.error('Error creating referral program:', createError);
        return res.status(500).json({ error: 'Failed to create referral program' });
      }

      program = newProgram;
    }

    // Get referral statistics
    const { data: referrals } = await supabase
      .from('referrals')
      .select('id, status, referred_email, created_at, reward_amount, reward_paid')
      .eq('referrer_company_id', req.companyId)
      .order('created_at', { ascending: false });

    const stats = {
      sent: referrals?.filter(r => r.status === 'sent').length || 0,
      pending: referrals?.filter(r => r.status === 'pending').length || 0,
      converted: referrals?.filter(r => r.status === 'converted').length || 0,
      total_rewards_earned: referrals?.filter(r => r.status === 'converted')
        .reduce((sum, r) => sum + (r.reward_amount || 0), 0) || 0,
      rewards_paid: referrals?.filter(r => r.reward_paid)
        .reduce((sum, r) => sum + (r.reward_amount || 0), 0) || 0,
      rewards_pending: referrals?.filter(r => r.status === 'converted' && !r.reward_paid)
        .reduce((sum, r) => sum + (r.reward_amount || 0), 0) || 0
    };

    res.json({
      success: true,
      referral_code: program.referral_code,
      referral_link: `${process.env.APP_URL || 'https://app.proofgreen.io'}/signup?ref=${program.referral_code}`,
      reward_per_referral: REFERRAL_REWARD,
      stats,
      recent_referrals: referrals?.slice(0, 10) || [],
      share_message: generateShareMessage(program.referral_code)
    });
  } catch (error) {
    logger.error('Get referral program error:', error);
    res.status(500).json({ error: 'Failed to get referral program' });
  }
});

/**
 * POST /api/referrals/send-invites
 * Send referral invitations via email
 */
router.post('/send-invites', authenticate, [
  body('emails').isArray({ min: 1, max: 10 }).withMessage('1-10 email addresses required'),
  body('emails.*').isEmail().withMessage('Invalid email address'),
  body('personalMessage').optional().isString().isLength({ max: 500 })
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const { emails, personalMessage } = req.body;

    // Get referrer's company and referral code
    const { data: company } = await supabase
      .from('companies')
      .select('name')
      .eq('id', req.companyId)
      .single();

    const { data: program } = await supabase
      .from('referral_programs')
      .select('referral_code')
      .eq('company_id', req.companyId)
      .single();

    if (!program) {
      return res.status(404).json({ error: 'Referral program not found' });
    }

    const referralLink = `${process.env.APP_URL || 'https://app.proofgreen.io'}/signup?ref=${program.referral_code}`;
    const successfulSends = [];
    const failedSends = [];

    for (const email of emails) {
      try {
        // Check if already referred
        const { data: existing } = await supabase
          .from('referrals')
          .select('id')
          .eq('referrer_company_id', req.companyId)
          .eq('referred_email', email.toLowerCase())
          .single();

        if (existing) {
          failedSends.push({ email, reason: 'Already referred' });
          continue;
        }

        // Check if email is already a ProofGreen customer
        const { data: existingUser } = await supabase
          .from('users')
          .select('id')
          .eq('email', email.toLowerCase())
          .single();

        if (existingUser) {
          failedSends.push({ email, reason: 'Already a ProofGreen customer' });
          continue;
        }

        // Create referral record
        await supabase
          .from('referrals')
          .insert({
            referrer_company_id: req.companyId,
            referred_email: email.toLowerCase(),
            status: 'sent',
            reward_amount: REFERRAL_REWARD,
            created_at: new Date().toISOString()
          });

        // Send invitation email
        await emailService.send({
          to: email,
          subject: `${company?.name || 'A colleague'} invited you to try ProofGreen`,
          body: `Hi there,

${company?.name || 'A colleague'} thinks you'd benefit from ProofGreen - the ESG tracking platform for home service businesses.

${personalMessage ? `Personal note: "${personalMessage}"\n` : ''}
With ProofGreen, you can:
- Track waste diversion and carbon offsets automatically
- Win more government and commercial contracts with ESG documentation
- Generate professional sustainability reports in seconds

Get started with a FREE trial:
${referralLink}

Best,
The ProofGreen Team

P.S. Both you and ${company?.name || 'your referrer'} will receive $${REFERRAL_REWARD} credit when you subscribe!`
        });

        successfulSends.push(email);

        // Update referral count
        await supabase
          .from('referral_programs')
          .update({ referrals_sent: supabase.sql`referrals_sent + 1` })
          .eq('company_id', req.companyId);

      } catch (emailError) {
        logger.error(`Failed to send referral to ${email}:`, emailError);
        failedSends.push({ email, reason: 'Email send failed' });
      }
    }

    res.json({
      success: true,
      sent: successfulSends.length,
      failed: failedSends.length,
      successful_emails: successfulSends,
      failed_emails: failedSends
    });
  } catch (error) {
    logger.error('Send invites error:', error);
    res.status(500).json({ error: 'Failed to send invitations' });
  }
});

/**
 * POST /api/referrals/validate-code
 * Validate a referral code during signup
 */
router.post('/validate-code', [
  body('code').notEmpty().isString()
], async (req, res) => {
  try {
    const { code } = req.body;

    const { data: program, error } = await supabase
      .from('referral_programs')
      .select(`
        referral_code,
        companies (name)
      `)
      .eq('referral_code', code.toUpperCase())
      .single();

    if (!program) {
      return res.json({
        valid: false,
        message: 'Invalid referral code'
      });
    }

    res.json({
      valid: true,
      referrer_name: program.companies?.name || 'A ProofGreen customer',
      reward_amount: REFERRAL_REWARD,
      message: `You were referred by ${program.companies?.name || 'a ProofGreen customer'}. You'll both receive $${REFERRAL_REWARD} credit!`
    });
  } catch (error) {
    logger.error('Validate code error:', error);
    res.status(500).json({ error: 'Failed to validate code' });
  }
});

/**
 * POST /api/referrals/track-conversion
 * Track when a referred user signs up (called during registration)
 */
router.post('/track-conversion', [
  body('referralCode').notEmpty(),
  body('newCompanyId').notEmpty(),
  body('email').isEmail()
], async (req, res) => {
  try {
    const { referralCode, newCompanyId, email } = req.body;

    // Find the referral program
    const { data: program } = await supabase
      .from('referral_programs')
      .select('company_id')
      .eq('referral_code', referralCode.toUpperCase())
      .single();

    if (!program) {
      return res.status(404).json({ error: 'Referral program not found' });
    }

    // Find the referral record
    const { data: referral } = await supabase
      .from('referrals')
      .select('id, status')
      .eq('referrer_company_id', program.company_id)
      .eq('referred_email', email.toLowerCase())
      .single();

    if (referral && referral.status === 'sent') {
      // Update referral to converted
      await supabase
        .from('referrals')
        .update({
          referred_company_id: newCompanyId,
          status: 'converted',
          converted_at: new Date().toISOString()
        })
        .eq('id', referral.id);
    } else {
      // Create new referral record if not found (direct code usage)
      await supabase
        .from('referrals')
        .insert({
          referrer_company_id: program.company_id,
          referred_email: email.toLowerCase(),
          referred_company_id: newCompanyId,
          status: 'converted',
          reward_amount: REFERRAL_REWARD,
          converted_at: new Date().toISOString()
        });
    }

    // Update referral program stats
    await supabase
      .from('referral_programs')
      .update({
        referrals_converted: supabase.sql`referrals_converted + 1`,
        total_rewards_earned: supabase.sql`total_rewards_earned + ${REFERRAL_REWARD}`
      })
      .eq('company_id', program.company_id);

    // Apply credits to both accounts
    await applyReferralCredits(program.company_id, newCompanyId);

    res.json({
      success: true,
      message: 'Referral conversion tracked successfully',
      reward_applied: REFERRAL_REWARD
    });
  } catch (error) {
    logger.error('Track conversion error:', error);
    res.status(500).json({ error: 'Failed to track conversion' });
  }
});

/**
 * GET /api/referrals/leaderboard
 * Get top referrers (public leaderboard)
 */
router.get('/leaderboard', async (req, res) => {
  try {
    const { data: leaderboard } = await supabase
      .from('referral_programs')
      .select(`
        referrals_converted,
        total_rewards_earned,
        companies (name)
      `)
      .gt('referrals_converted', 0)
      .order('referrals_converted', { ascending: false })
      .limit(10);

    // Anonymize company names for privacy
    const anonymizedLeaderboard = leaderboard?.map((entry, index) => ({
      rank: index + 1,
      company: entry.companies?.name?.substring(0, 3) + '***',
      referrals: entry.referrals_converted,
      rewards_earned: entry.total_rewards_earned
    })) || [];

    res.json({
      success: true,
      leaderboard: anonymizedLeaderboard,
      total_referrals_program: leaderboard?.reduce((sum, e) => sum + e.referrals_converted, 0) || 0
    });
  } catch (error) {
    logger.error('Get leaderboard error:', error);
    res.status(500).json({ error: 'Failed to get leaderboard' });
  }
});

/**
 * Helper: Generate unique referral code
 */
function generateReferralCode(companyId) {
  const hash = crypto.createHash('md5').update(companyId).digest('hex');
  return `PG-${hash.substring(0, 6).toUpperCase()}`;
}

/**
 * Helper: Generate share message for social media
 */
function generateShareMessage(referralCode) {
  return {
    twitter: `I'm using @ProofGreen to track ESG metrics for my business. Check it out and we both get $${REFERRAL_REWARD}! https://app.proofgreen.io/signup?ref=${referralCode}`,
    linkedin: `ProofGreen has made ESG tracking so much easier for our service business. If you're looking for a way to track sustainability metrics and win more contracts, check it out: https://app.proofgreen.io/signup?ref=${referralCode}`,
    email: {
      subject: "Check out ProofGreen - ESG tracking made easy",
      body: `Hey,\n\nI've been using ProofGreen for ESG tracking and thought you might find it useful. It helps track waste diversion, carbon offsets, and generates reports for contracts.\n\nSign up here and we both get $${REFERRAL_REWARD}: https://app.proofgreen.io/signup?ref=${referralCode}\n\nLet me know if you have questions!`
    }
  };
}

/**
 * Helper: Apply referral credits to both accounts
 */
async function applyReferralCredits(referrerCompanyId, referredCompanyId) {
  try {
    // Apply credit to referrer
    await supabase
      .from('account_credits')
      .insert({
        company_id: referrerCompanyId,
        amount: REFERRAL_REWARD,
        type: 'referral_reward',
        description: 'Referral reward - new customer signed up',
        created_at: new Date().toISOString()
      });

    // Apply credit to referred (new customer)
    await supabase
      .from('account_credits')
      .insert({
        company_id: referredCompanyId,
        amount: REFERRAL_REWARD,
        type: 'referral_bonus',
        description: 'Welcome bonus - referred by existing customer',
        created_at: new Date().toISOString()
      });

    logger.info(`Applied $${REFERRAL_REWARD} credits to companies ${referrerCompanyId} and ${referredCompanyId}`);
  } catch (error) {
    logger.error('Error applying referral credits:', error);
  }
}

module.exports = router;
