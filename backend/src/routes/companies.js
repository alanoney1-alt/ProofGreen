const express = require('express');
const router = express.Router();
const { body, validationResult } = require('express-validator');
const { supabase } = require('../utils/supabase');
const { authenticate, authorize } = require('../middleware/auth');
const { logger } = require('../utils/logger');

// GET /api/companies/:id
router.get('/:id', authenticate, async (req, res) => {
  try {
    const { id } = req.params;

    // Check access
    if (req.user.company_id !== id && req.user.role !== 'admin') {
      return res.status(403).json({ error: 'Access denied' });
    }

    const { data: company, error } = await supabase
      .from('companies')
      .select(`
        *,
        company_verticals (
          is_primary,
          verticals (*)
        ),
        subscriptions (
          *,
          pricing_plans (*)
        )
      `)
      .eq('id', id)
      .single();

    if (error || !company) {
      return res.status(404).json({ error: 'Company not found' });
    }

    res.json({ company });
  } catch (error) {
    logger.error('Get company error:', error);
    res.status(500).json({ error: 'Failed to fetch company' });
  }
});

// PUT /api/companies/:id
router.put('/:id', authenticate, authorize('owner', 'admin'), [
  body('name').optional().trim().notEmpty(),
  body('email').optional().isEmail(),
  body('phone').optional().trim()
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const { id } = req.params;

    // Check access
    if (req.user.company_id !== id && req.user.role !== 'admin') {
      return res.status(403).json({ error: 'Access denied' });
    }

    const updates = {};
    const allowedFields = [
      'name', 'email', 'phone', 'address_line1', 'address_line2',
      'city', 'state', 'zip_code', 'country', 'logo_url', 'website',
      'description', 'employee_count', 'founded_year'
    ];

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

    if (error) {
      logger.error('Company update error:', error);
      return res.status(500).json({ error: 'Failed to update company' });
    }

    res.json({ company });
  } catch (error) {
    logger.error('Update company error:', error);
    res.status(500).json({ error: 'Failed to update company' });
  }
});

// PUT /api/companies/:id/verticals
router.put('/:id/verticals', authenticate, authorize('owner', 'admin'), async (req, res) => {
  try {
    const { id } = req.params;
    const { verticals } = req.body;

    if (!Array.isArray(verticals)) {
      return res.status(400).json({ error: 'Verticals must be an array' });
    }

    // Check access
    if (req.user.company_id !== id && req.user.role !== 'admin') {
      return res.status(403).json({ error: 'Access denied' });
    }

    // Delete existing verticals
    await supabase
      .from('company_verticals')
      .delete()
      .eq('company_id', id);

    // Insert new verticals
    if (verticals.length > 0) {
      const verticalRecords = verticals.map((verticalId, index) => ({
        company_id: id,
        vertical_id: verticalId,
        is_primary: index === 0
      }));

      await supabase.from('company_verticals').insert(verticalRecords);
    }

    // Fetch updated company with verticals
    const { data: company } = await supabase
      .from('companies')
      .select(`
        *,
        company_verticals (
          is_primary,
          verticals (*)
        )
      `)
      .eq('id', id)
      .single();

    res.json({ company });
  } catch (error) {
    logger.error('Update verticals error:', error);
    res.status(500).json({ error: 'Failed to update verticals' });
  }
});

// GET /api/companies/:id/users
router.get('/:id/users', authenticate, async (req, res) => {
  try {
    const { id } = req.params;

    // Check access
    if (req.user.company_id !== id && req.user.role !== 'admin') {
      return res.status(403).json({ error: 'Access denied' });
    }

    const { data: users, error } = await supabase
      .from('users')
      .select('id, email, first_name, last_name, role, is_active, created_at, last_login_at')
      .eq('company_id', id)
      .order('created_at');

    if (error) {
      return res.status(500).json({ error: 'Failed to fetch users' });
    }

    res.json({ users });
  } catch (error) {
    logger.error('Get users error:', error);
    res.status(500).json({ error: 'Failed to fetch users' });
  }
});

// POST /api/companies/:id/users
router.post('/:id/users', authenticate, authorize('owner', 'admin', 'manager'), [
  body('email').isEmail(),
  body('firstName').trim().notEmpty(),
  body('lastName').trim().notEmpty(),
  body('role').isIn(['admin', 'manager', 'member'])
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const { id } = req.params;
    const { email, firstName, lastName, role, phone } = req.body;

    // Check access
    if (req.user.company_id !== id && req.user.role !== 'admin') {
      return res.status(403).json({ error: 'Access denied' });
    }

    // Check subscription limits
    const { data: subscription } = await supabase
      .from('subscriptions')
      .select('pricing_plans(user_limit)')
      .eq('company_id', id)
      .eq('status', 'active')
      .single();

    if (subscription?.pricing_plans?.user_limit) {
      const { count } = await supabase
        .from('users')
        .select('*', { count: 'exact', head: true })
        .eq('company_id', id);

      if (count >= subscription.pricing_plans.user_limit) {
        return res.status(403).json({ error: 'User limit reached for your plan' });
      }
    }

    // Check if email exists
    const { data: existingUser } = await supabase
      .from('users')
      .select('id')
      .eq('email', email)
      .single();

    if (existingUser) {
      return res.status(400).json({ error: 'Email already in use' });
    }

    // Generate temporary password
    const bcrypt = require('bcryptjs');
    const tempPassword = Math.random().toString(36).slice(-8);
    const passwordHash = await bcrypt.hash(tempPassword, 12);

    const { data: user, error } = await supabase
      .from('users')
      .insert({
        company_id: id,
        email,
        password_hash: passwordHash,
        first_name: firstName,
        last_name: lastName,
        phone,
        role
      })
      .select()
      .single();

    if (error) {
      return res.status(500).json({ error: 'Failed to create user' });
    }

    // TODO: Send email with temporary password

    res.status(201).json({
      user: {
        id: user.id,
        email: user.email,
        firstName: user.first_name,
        lastName: user.last_name,
        role: user.role
      },
      tempPassword // Remove in production, send via email instead
    });
  } catch (error) {
    logger.error('Create user error:', error);
    res.status(500).json({ error: 'Failed to create user' });
  }
});

// PUT /api/companies/:id/onboarding
router.put('/:id/onboarding', authenticate, async (req, res) => {
  try {
    const { id } = req.params;

    // Check access
    if (req.user.company_id !== id) {
      return res.status(403).json({ error: 'Access denied' });
    }

    const { data: company, error } = await supabase
      .from('companies')
      .update({ onboarding_completed: true })
      .eq('id', id)
      .select()
      .single();

    if (error) {
      return res.status(500).json({ error: 'Failed to update onboarding status' });
    }

    res.json({ company });
  } catch (error) {
    logger.error('Onboarding update error:', error);
    res.status(500).json({ error: 'Failed to update onboarding status' });
  }
});

module.exports = router;
