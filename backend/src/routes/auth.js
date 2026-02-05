const express = require('express');
const router = express.Router();
const { body, validationResult } = require('express-validator');
const bcrypt = require('bcryptjs');
const { supabase } = require('../utils/supabase');
const { generateToken, authenticate } = require('../middleware/auth');
const { logger } = require('../utils/logger');

// Validation middleware
const validateRegistration = [
  body('email').isEmail().normalizeEmail(),
  body('password').isLength({ min: 8 }).withMessage('Password must be at least 8 characters'),
  body('firstName').trim().notEmpty(),
  body('lastName').trim().notEmpty(),
  body('companyName').trim().notEmpty()
];

const validateLogin = [
  body('email').isEmail().normalizeEmail(),
  body('password').notEmpty()
];

// POST /api/auth/register
router.post('/register', validateRegistration, async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const { email, password, firstName, lastName, companyName, phone, verticals } = req.body;

    // Check if user exists
    const { data: existingUser } = await supabase
      .from('users')
      .select('id')
      .eq('email', email)
      .single();

    if (existingUser) {
      return res.status(400).json({ error: 'Email already registered' });
    }

    // Hash password
    const passwordHash = await bcrypt.hash(password, 12);

    // Create company
    const { data: company, error: companyError } = await supabase
      .from('companies')
      .insert({
        name: companyName,
        email: email,
        phone: phone
      })
      .select()
      .single();

    if (companyError) {
      logger.error('Company creation error:', companyError);
      return res.status(500).json({ error: 'Failed to create company' });
    }

    // Create user
    const { data: user, error: userError } = await supabase
      .from('users')
      .insert({
        company_id: company.id,
        email: email,
        password_hash: passwordHash,
        first_name: firstName,
        last_name: lastName,
        phone: phone,
        role: 'owner'
      })
      .select()
      .single();

    if (userError) {
      // Rollback company creation
      await supabase.from('companies').delete().eq('id', company.id);
      logger.error('User creation error:', userError);
      return res.status(500).json({ error: 'Failed to create user' });
    }

    // Add company verticals if provided
    if (verticals && verticals.length > 0) {
      const verticalRecords = verticals.map((verticalId, index) => ({
        company_id: company.id,
        vertical_id: verticalId,
        is_primary: index === 0
      }));

      await supabase.from('company_verticals').insert(verticalRecords);
    }

    // Create default subscription (trial on Founders plan)
    const { data: foundersPlan } = await supabase
      .from('pricing_plans')
      .select('id')
      .eq('slug', 'founders')
      .single();

    if (foundersPlan) {
      const trialEnd = new Date();
      trialEnd.setDate(trialEnd.getDate() + 14);

      await supabase.from('subscriptions').insert({
        company_id: company.id,
        plan_id: foundersPlan.id,
        status: 'trialing',
        billing_cycle: 'monthly',
        trial_end: trialEnd.toISOString(),
        current_period_start: new Date().toISOString(),
        current_period_end: trialEnd.toISOString()
      });
    }

    // Create default milestones for new company
    const defaultMilestones = [
      { milestone_type: 'tons_diverted', name: 'First Ton', threshold_value: 2000, threshold_unit: 'lbs', points: 100 },
      { milestone_type: 'tons_diverted', name: '10 Tons Club', threshold_value: 20000, threshold_unit: 'lbs', points: 500 },
      { milestone_type: 'carbon_saved', name: 'Carbon Starter', threshold_value: 1000, threshold_unit: 'lbs', points: 100 },
      { milestone_type: 'jobs_completed', name: 'First 10 Jobs', threshold_value: 10, threshold_unit: 'jobs', points: 50 },
      { milestone_type: 'diversion_rate', name: 'Green Starter', threshold_value: 50, threshold_unit: 'percent', points: 100 }
    ];

    await supabase.from('milestones').insert(
      defaultMilestones.map(m => ({ ...m, company_id: company.id }))
    );

    // Generate token
    const token = generateToken(user.id, company.id);

    logger.info(`New user registered: ${email}`);

    res.status(201).json({
      message: 'Registration successful',
      token,
      user: {
        id: user.id,
        email: user.email,
        firstName: user.first_name,
        lastName: user.last_name,
        role: user.role
      },
      company: {
        id: company.id,
        name: company.name
      }
    });
  } catch (error) {
    logger.error('Registration error:', error);
    res.status(500).json({ error: 'Registration failed' });
  }
});

// POST /api/auth/login
router.post('/login', validateLogin, async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const { email, password } = req.body;

    // Find user
    const { data: user, error } = await supabase
      .from('users')
      .select('*, companies(*)')
      .eq('email', email)
      .single();

    if (error || !user) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    if (!user.is_active) {
      return res.status(401).json({ error: 'Account is deactivated' });
    }

    // Verify password
    const isValidPassword = await bcrypt.compare(password, user.password_hash);
    if (!isValidPassword) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    // Update last login
    await supabase
      .from('users')
      .update({ last_login_at: new Date().toISOString() })
      .eq('id', user.id);

    // Generate token
    const token = generateToken(user.id, user.company_id);

    logger.info(`User logged in: ${email}`);

    res.json({
      token,
      user: {
        id: user.id,
        email: user.email,
        firstName: user.first_name,
        lastName: user.last_name,
        role: user.role
      },
      company: user.companies
    });
  } catch (error) {
    logger.error('Login error:', error);
    res.status(500).json({ error: 'Login failed' });
  }
});

// GET /api/auth/me
router.get('/me', authenticate, async (req, res) => {
  try {
    const { data: user } = await supabase
      .from('users')
      .select(`
        *,
        companies (
          *,
          company_verticals (
            verticals (*)
          ),
          subscriptions (
            *,
            pricing_plans (*)
          )
        )
      `)
      .eq('id', req.user.id)
      .single();

    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }

    res.json({
      user: {
        id: user.id,
        email: user.email,
        firstName: user.first_name,
        lastName: user.last_name,
        phone: user.phone,
        role: user.role,
        avatarUrl: user.avatar_url
      },
      company: user.companies
    });
  } catch (error) {
    logger.error('Get profile error:', error);
    res.status(500).json({ error: 'Failed to fetch profile' });
  }
});

// PUT /api/auth/password
router.put('/password', authenticate, [
  body('currentPassword').notEmpty(),
  body('newPassword').isLength({ min: 8 })
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const { currentPassword, newPassword } = req.body;

    // Verify current password
    const isValidPassword = await bcrypt.compare(currentPassword, req.user.password_hash);
    if (!isValidPassword) {
      return res.status(401).json({ error: 'Current password is incorrect' });
    }

    // Hash new password
    const passwordHash = await bcrypt.hash(newPassword, 12);

    await supabase
      .from('users')
      .update({ password_hash: passwordHash })
      .eq('id', req.user.id);

    res.json({ message: 'Password updated successfully' });
  } catch (error) {
    logger.error('Password update error:', error);
    res.status(500).json({ error: 'Failed to update password' });
  }
});

// GET /api/auth/verticals
router.get('/verticals', async (req, res) => {
  try {
    const { data: verticals } = await supabase
      .from('verticals')
      .select('*')
      .eq('is_active', true)
      .order('display_order');

    res.json({ verticals });
  } catch (error) {
    logger.error('Verticals fetch error:', error);
    res.status(500).json({ error: 'Failed to fetch verticals' });
  }
});

module.exports = router;
