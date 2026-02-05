const express = require('express');
const router = express.Router();
const { v4: uuidv4 } = require('uuid');
const bcrypt = require('bcryptjs');
const { supabase } = require('../utils/supabase');
const { authenticate, authorize, generateToken } = require('../middleware/auth');
const { logger } = require('../utils/logger');
const { sendTeamInviteEmail } = require('../services/email');
const { validate, inviteUserSchema, z } = require('../utils/validation');

// GET /api/team
// Get team members for the company
router.get('/', authenticate, async (req, res) => {
  try {
    const { data: members, error } = await supabase
      .from('users')
      .select('id, email, first_name, last_name, role, avatar_url, is_active, last_login_at, created_at')
      .eq('company_id', req.companyId)
      .order('created_at', { ascending: true });

    if (error) {
      return res.status(500).json({ error: 'Failed to fetch team members' });
    }

    // Get pending invitations
    const { data: invitations } = await supabase
      .from('team_invitations')
      .select('*')
      .eq('company_id', req.companyId)
      .eq('status', 'pending');

    res.json({
      members,
      invitations: invitations || []
    });
  } catch (error) {
    logger.error('Get team error:', error);
    res.status(500).json({ error: 'Failed to fetch team' });
  }
});

// POST /api/team/invite
// Invite a new team member
router.post('/invite', authenticate, authorize('owner', 'admin'), async (req, res) => {
  try {
    const { email, role = 'member', firstName, lastName } = req.body;

    // Check if user already exists
    const { data: existingUser } = await supabase
      .from('users')
      .select('id')
      .eq('email', email)
      .eq('company_id', req.companyId)
      .single();

    if (existingUser) {
      return res.status(400).json({ error: 'User already exists in your team' });
    }

    // Check subscription limits
    const { data: subscription } = await supabase
      .from('subscriptions')
      .select('pricing_plans(user_limit)')
      .eq('company_id', req.companyId)
      .in('status', ['active', 'trialing'])
      .single();

    if (subscription?.pricing_plans?.user_limit) {
      const { count } = await supabase
        .from('users')
        .select('*', { count: 'exact', head: true })
        .eq('company_id', req.companyId)
        .eq('is_active', true);

      if (count >= subscription.pricing_plans.user_limit) {
        return res.status(403).json({
          error: 'User limit reached for your plan. Please upgrade to add more team members.'
        });
      }
    }

    // Check for existing pending invitation
    const { data: existingInvite } = await supabase
      .from('team_invitations')
      .select('id')
      .eq('email', email)
      .eq('company_id', req.companyId)
      .eq('status', 'pending')
      .single();

    if (existingInvite) {
      return res.status(400).json({ error: 'An invitation has already been sent to this email' });
    }

    // Generate invitation token
    const inviteToken = uuidv4();
    const expiresAt = new Date();
    expiresAt.setDate(expiresAt.getDate() + 7); // 7 days expiry

    // Create invitation record
    const { data: invitation, error } = await supabase
      .from('team_invitations')
      .insert({
        company_id: req.companyId,
        email,
        role,
        first_name: firstName,
        last_name: lastName,
        token: inviteToken,
        invited_by: req.user.id,
        expires_at: expiresAt.toISOString(),
        status: 'pending'
      })
      .select()
      .single();

    if (error) {
      logger.error('Failed to create invitation:', error);
      return res.status(500).json({ error: 'Failed to create invitation' });
    }

    // Send invitation email
    try {
      const inviterName = `${req.user.first_name} ${req.user.last_name}`;
      await sendTeamInviteEmail(inviterName, req.user.companies.name, email, inviteToken);
    } catch (emailError) {
      logger.error('Failed to send invitation email:', emailError);
      // Continue even if email fails
    }

    logger.info(`Invitation sent to ${email} for company ${req.companyId}`);

    res.status(201).json({
      invitation,
      message: 'Invitation sent successfully'
    });
  } catch (error) {
    logger.error('Invite team member error:', error);
    res.status(500).json({ error: 'Failed to send invitation' });
  }
});

// GET /api/team/invite/:token
// Get invitation details (public route)
router.get('/invite/:token', async (req, res) => {
  try {
    const { token } = req.params;

    const { data: invitation, error } = await supabase
      .from('team_invitations')
      .select(`
        *,
        companies(name, logo_url),
        users!invited_by(first_name, last_name)
      `)
      .eq('token', token)
      .eq('status', 'pending')
      .single();

    if (error || !invitation) {
      return res.status(404).json({ error: 'Invalid or expired invitation' });
    }

    // Check expiry
    if (new Date(invitation.expires_at) < new Date()) {
      await supabase
        .from('team_invitations')
        .update({ status: 'expired' })
        .eq('id', invitation.id);

      return res.status(410).json({ error: 'This invitation has expired' });
    }

    res.json({
      invitation: {
        email: invitation.email,
        role: invitation.role,
        firstName: invitation.first_name,
        lastName: invitation.last_name,
        companyName: invitation.companies.name,
        companyLogo: invitation.companies.logo_url,
        invitedBy: invitation.users ? `${invitation.users.first_name} ${invitation.users.last_name}` : null
      }
    });
  } catch (error) {
    logger.error('Get invitation error:', error);
    res.status(500).json({ error: 'Failed to get invitation' });
  }
});

// POST /api/team/invite/:token/accept
// Accept invitation and create account
router.post('/invite/:token/accept', async (req, res) => {
  try {
    const { token } = req.params;
    const { password, firstName, lastName } = req.body;

    if (!password || password.length < 8) {
      return res.status(400).json({ error: 'Password must be at least 8 characters' });
    }

    // Get invitation
    const { data: invitation, error } = await supabase
      .from('team_invitations')
      .select('*, companies(id, name)')
      .eq('token', token)
      .eq('status', 'pending')
      .single();

    if (error || !invitation) {
      return res.status(404).json({ error: 'Invalid or expired invitation' });
    }

    // Check expiry
    if (new Date(invitation.expires_at) < new Date()) {
      await supabase
        .from('team_invitations')
        .update({ status: 'expired' })
        .eq('id', invitation.id);

      return res.status(410).json({ error: 'This invitation has expired' });
    }

    // Hash password
    const passwordHash = await bcrypt.hash(password, 12);

    // Create user
    const { data: user, error: userError } = await supabase
      .from('users')
      .insert({
        company_id: invitation.company_id,
        email: invitation.email,
        password_hash: passwordHash,
        first_name: firstName || invitation.first_name || '',
        last_name: lastName || invitation.last_name || '',
        role: invitation.role,
        email_verified: true, // Verified through invitation email
        is_active: true
      })
      .select()
      .single();

    if (userError) {
      logger.error('Failed to create user from invitation:', userError);
      return res.status(500).json({ error: 'Failed to create account' });
    }

    // Update invitation status
    await supabase
      .from('team_invitations')
      .update({
        status: 'accepted',
        accepted_at: new Date().toISOString()
      })
      .eq('id', invitation.id);

    // Generate token
    const authToken = generateToken(user.id, invitation.company_id);

    logger.info(`User ${user.id} created from invitation for company ${invitation.company_id}`);

    res.status(201).json({
      token: authToken,
      user: {
        id: user.id,
        email: user.email,
        firstName: user.first_name,
        lastName: user.last_name,
        role: user.role
      },
      company: {
        id: invitation.companies.id,
        name: invitation.companies.name
      }
    });
  } catch (error) {
    logger.error('Accept invitation error:', error);
    res.status(500).json({ error: 'Failed to accept invitation' });
  }
});

// DELETE /api/team/invite/:id
// Cancel/revoke invitation
router.delete('/invite/:id', authenticate, authorize('owner', 'admin'), async (req, res) => {
  try {
    const { id } = req.params;

    const { error } = await supabase
      .from('team_invitations')
      .update({ status: 'revoked' })
      .eq('id', id)
      .eq('company_id', req.companyId)
      .eq('status', 'pending');

    if (error) {
      return res.status(500).json({ error: 'Failed to revoke invitation' });
    }

    res.json({ message: 'Invitation revoked' });
  } catch (error) {
    logger.error('Revoke invitation error:', error);
    res.status(500).json({ error: 'Failed to revoke invitation' });
  }
});

// POST /api/team/invite/:id/resend
// Resend invitation email
router.post('/invite/:id/resend', authenticate, authorize('owner', 'admin'), async (req, res) => {
  try {
    const { id } = req.params;

    const { data: invitation, error } = await supabase
      .from('team_invitations')
      .select('*')
      .eq('id', id)
      .eq('company_id', req.companyId)
      .eq('status', 'pending')
      .single();

    if (error || !invitation) {
      return res.status(404).json({ error: 'Invitation not found' });
    }

    // Extend expiry
    const expiresAt = new Date();
    expiresAt.setDate(expiresAt.getDate() + 7);

    await supabase
      .from('team_invitations')
      .update({ expires_at: expiresAt.toISOString() })
      .eq('id', id);

    // Resend email
    try {
      const inviterName = `${req.user.first_name} ${req.user.last_name}`;
      await sendTeamInviteEmail(inviterName, req.user.companies.name, invitation.email, invitation.token);
    } catch (emailError) {
      logger.error('Failed to resend invitation email:', emailError);
      return res.status(500).json({ error: 'Failed to send email' });
    }

    res.json({ message: 'Invitation resent successfully' });
  } catch (error) {
    logger.error('Resend invitation error:', error);
    res.status(500).json({ error: 'Failed to resend invitation' });
  }
});

// PUT /api/team/:userId
// Update team member role
router.put('/:userId', authenticate, authorize('owner', 'admin'), async (req, res) => {
  try {
    const { userId } = req.params;
    const { role, isActive } = req.body;

    // Can't modify yourself
    if (userId === req.user.id) {
      return res.status(400).json({ error: 'Cannot modify your own account' });
    }

    // Verify user belongs to company
    const { data: targetUser } = await supabase
      .from('users')
      .select('id, role')
      .eq('id', userId)
      .eq('company_id', req.companyId)
      .single();

    if (!targetUser) {
      return res.status(404).json({ error: 'User not found' });
    }

    // Only owner can modify admin roles
    if (targetUser.role === 'owner' || role === 'owner') {
      if (req.user.role !== 'owner') {
        return res.status(403).json({ error: 'Only the owner can modify owner roles' });
      }
    }

    const updates = {};
    if (role && ['admin', 'manager', 'member'].includes(role)) {
      updates.role = role;
    }
    if (typeof isActive === 'boolean') {
      updates.is_active = isActive;
    }

    const { data: user, error } = await supabase
      .from('users')
      .update(updates)
      .eq('id', userId)
      .select('id, email, first_name, last_name, role, is_active')
      .single();

    if (error) {
      return res.status(500).json({ error: 'Failed to update team member' });
    }

    logger.info(`Team member ${userId} updated by ${req.user.id}`, { updates });

    res.json({ user });
  } catch (error) {
    logger.error('Update team member error:', error);
    res.status(500).json({ error: 'Failed to update team member' });
  }
});

// DELETE /api/team/:userId
// Remove team member
router.delete('/:userId', authenticate, authorize('owner', 'admin'), async (req, res) => {
  try {
    const { userId } = req.params;

    // Can't remove yourself
    if (userId === req.user.id) {
      return res.status(400).json({ error: 'Cannot remove yourself' });
    }

    // Verify user belongs to company
    const { data: targetUser } = await supabase
      .from('users')
      .select('id, role')
      .eq('id', userId)
      .eq('company_id', req.companyId)
      .single();

    if (!targetUser) {
      return res.status(404).json({ error: 'User not found' });
    }

    // Can't remove owner
    if (targetUser.role === 'owner') {
      return res.status(403).json({ error: 'Cannot remove the company owner' });
    }

    // Only owner can remove admins
    if (targetUser.role === 'admin' && req.user.role !== 'owner') {
      return res.status(403).json({ error: 'Only the owner can remove admins' });
    }

    // Soft delete - deactivate the user
    const { error } = await supabase
      .from('users')
      .update({ is_active: false })
      .eq('id', userId);

    if (error) {
      return res.status(500).json({ error: 'Failed to remove team member' });
    }

    logger.info(`Team member ${userId} removed by ${req.user.id}`);

    res.json({ message: 'Team member removed' });
  } catch (error) {
    logger.error('Remove team member error:', error);
    res.status(500).json({ error: 'Failed to remove team member' });
  }
});

module.exports = router;
