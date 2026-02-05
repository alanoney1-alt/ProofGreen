const jwt = require('jsonwebtoken');
const { supabase } = require('../utils/supabase');
const { logger } = require('../utils/logger');

const JWT_SECRET = process.env.JWT_SECRET || 'development-secret-change-in-production';

// Generate JWT token
const generateToken = (userId, companyId) => {
  return jwt.sign(
    { userId, companyId },
    JWT_SECRET,
    { expiresIn: process.env.JWT_EXPIRES_IN || '7d' }
  );
};

// Verify JWT token
const verifyToken = (token) => {
  try {
    return jwt.verify(token, JWT_SECRET);
  } catch (error) {
    return null;
  }
};

// Authentication middleware
const authenticate = async (req, res, next) => {
  try {
    const authHeader = req.headers.authorization;

    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return res.status(401).json({ error: 'No authentication token provided' });
    }

    const token = authHeader.split(' ')[1];
    const decoded = verifyToken(token);

    if (!decoded) {
      return res.status(401).json({ error: 'Invalid or expired token' });
    }

    // Fetch user from database
    const { data: user, error } = await supabase
      .from('users')
      .select('*, companies(*)')
      .eq('id', decoded.userId)
      .single();

    if (error || !user) {
      return res.status(401).json({ error: 'User not found' });
    }

    if (!user.is_active) {
      return res.status(401).json({ error: 'Account is deactivated' });
    }

    // Attach user and company to request
    req.user = user;
    req.companyId = decoded.companyId;

    next();
  } catch (error) {
    logger.error('Authentication error:', error);
    res.status(500).json({ error: 'Authentication failed' });
  }
};

// Optional authentication (doesn't fail if no token)
const optionalAuth = async (req, res, next) => {
  try {
    const authHeader = req.headers.authorization;

    if (authHeader && authHeader.startsWith('Bearer ')) {
      const token = authHeader.split(' ')[1];
      const decoded = verifyToken(token);

      if (decoded) {
        const { data: user } = await supabase
          .from('users')
          .select('*, companies(*)')
          .eq('id', decoded.userId)
          .single();

        if (user && user.is_active) {
          req.user = user;
          req.companyId = decoded.companyId;
        }
      }
    }

    next();
  } catch (error) {
    next();
  }
};

// Role-based authorization
const authorize = (...allowedRoles) => {
  return (req, res, next) => {
    if (!req.user) {
      return res.status(401).json({ error: 'Authentication required' });
    }

    if (!allowedRoles.includes(req.user.role)) {
      return res.status(403).json({ error: 'Insufficient permissions' });
    }

    next();
  };
};

// Company ownership check
const requireCompanyAccess = async (req, res, next) => {
  const companyId = req.params.companyId || req.body.company_id || req.companyId;

  if (!companyId) {
    return res.status(400).json({ error: 'Company ID required' });
  }

  if (req.user.company_id !== companyId && req.user.role !== 'admin') {
    return res.status(403).json({ error: 'Access denied to this company' });
  }

  next();
};

module.exports = {
  generateToken,
  verifyToken,
  authenticate,
  optionalAuth,
  authorize,
  requireCompanyAccess
};
