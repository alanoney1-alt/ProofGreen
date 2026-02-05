const { z } = require('zod');

// Common schemas
const uuidSchema = z.string().uuid();
const emailSchema = z.string().email();
const phoneSchema = z.string().regex(/^[\d\s\-\+\(\)]+$/).optional();

const passwordSchema = z.string()
  .min(8, 'Password must be at least 8 characters')
  .regex(/[A-Z]/, 'Password must contain at least one uppercase letter')
  .regex(/[a-z]/, 'Password must contain at least one lowercase letter')
  .regex(/[0-9]/, 'Password must contain at least one number');

// Auth schemas
const registerSchema = z.object({
  email: emailSchema,
  password: passwordSchema,
  firstName: z.string().min(1).max(100),
  lastName: z.string().min(1).max(100),
  companyName: z.string().min(1).max(255),
  phone: phoneSchema,
  verticalIds: z.array(uuidSchema).optional()
});

const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1)
});

const forgotPasswordSchema = z.object({
  email: emailSchema
});

const resetPasswordSchema = z.object({
  token: z.string().min(1),
  password: passwordSchema
});

const changePasswordSchema = z.object({
  currentPassword: z.string().min(1),
  newPassword: passwordSchema
});

// Company schemas
const updateCompanySchema = z.object({
  name: z.string().min(1).max(255).optional(),
  phone: phoneSchema,
  addressLine1: z.string().max(255).optional(),
  addressLine2: z.string().max(255).optional(),
  city: z.string().max(100).optional(),
  state: z.string().max(50).optional(),
  zipCode: z.string().max(20).optional(),
  website: z.string().url().optional().or(z.literal('')),
  description: z.string().max(1000).optional(),
  employeeCount: z.number().int().positive().optional(),
  foundedYear: z.number().int().min(1800).max(new Date().getFullYear()).optional()
});

// Job schemas
const createJobSchema = z.object({
  title: z.string().min(1).max(255),
  description: z.string().max(2000).optional(),
  verticalId: uuidSchema.optional(),
  assignedUserId: uuidSchema.optional(),
  customerName: z.string().max(255).optional(),
  customerEmail: emailSchema.optional().or(z.literal('')),
  customerPhone: phoneSchema,
  addressLine1: z.string().max(255).optional(),
  addressLine2: z.string().max(255).optional(),
  city: z.string().max(100).optional(),
  state: z.string().max(50).optional(),
  zipCode: z.string().max(20).optional(),
  scheduledDate: z.string().datetime().optional().or(z.string().regex(/^\d{4}-\d{2}-\d{2}$/)),
  scheduledTimeStart: z.string().regex(/^\d{2}:\d{2}(:\d{2})?$/).optional(),
  scheduledTimeEnd: z.string().regex(/^\d{2}:\d{2}(:\d{2})?$/).optional(),
  estimatedCost: z.number().positive().optional(),
  notes: z.string().max(5000).optional()
});

const updateJobSchema = z.object({
  title: z.string().min(1).max(255).optional(),
  description: z.string().max(2000).optional(),
  status: z.enum(['pending', 'in_progress', 'completed', 'cancelled']).optional(),
  verticalId: uuidSchema.optional(),
  assignedUserId: uuidSchema.optional(),
  customerName: z.string().max(255).optional(),
  customerEmail: emailSchema.optional().or(z.literal('')),
  customerPhone: phoneSchema,
  addressLine1: z.string().max(255).optional(),
  addressLine2: z.string().max(255).optional(),
  city: z.string().max(100).optional(),
  state: z.string().max(50).optional(),
  zipCode: z.string().max(20).optional(),
  scheduledDate: z.string().datetime().optional().or(z.string().regex(/^\d{4}-\d{2}-\d{2}$/)),
  scheduledTimeStart: z.string().regex(/^\d{2}:\d{2}(:\d{2})?$/).optional(),
  scheduledTimeEnd: z.string().regex(/^\d{2}:\d{2}(:\d{2})?$/).optional(),
  estimatedCost: z.number().positive().optional(),
  finalCost: z.number().positive().optional(),
  notes: z.string().max(5000).optional()
});

// Job items schema
const jobItemSchema = z.object({
  name: z.string().min(1).max(255),
  category: z.string().min(1).max(100),
  subcategory: z.string().max(100).optional(),
  quantity: z.number().int().positive().default(1),
  weightLbs: z.number().positive().optional(),
  disposalMethod: z.enum(['recycled', 'donated', 'landfill', 'hazardous', 'compost', 'reused']).optional(),
  detectedByAi: z.boolean().default(false),
  aiConfidence: z.number().min(0).max(1).optional(),
  notes: z.string().max(500).optional()
});

const addJobItemsSchema = z.object({
  items: z.array(jobItemSchema).min(1)
});

// Subscription schemas
const upgradeSubscriptionSchema = z.object({
  planId: uuidSchema,
  billingCycle: z.enum(['monthly', 'yearly']).default('monthly')
});

// User schemas
const updateUserSchema = z.object({
  firstName: z.string().min(1).max(100).optional(),
  lastName: z.string().min(1).max(100).optional(),
  phone: phoneSchema,
  avatarUrl: z.string().url().optional().or(z.literal(''))
});

const inviteUserSchema = z.object({
  email: emailSchema,
  role: z.enum(['admin', 'manager', 'member']).default('member'),
  firstName: z.string().min(1).max(100).optional(),
  lastName: z.string().min(1).max(100).optional()
});

// Report schemas
const generateReportSchema = z.object({
  jobId: uuidSchema.optional(),
  reportType: z.enum(['job', 'weekly', 'monthly', 'quarterly', 'annual', 'custom']).default('job'),
  periodStart: z.string().datetime().optional().or(z.string().regex(/^\d{4}-\d{2}-\d{2}$/)),
  periodEnd: z.string().datetime().optional().or(z.string().regex(/^\d{4}-\d{2}-\d{2}$/)),
  format: z.enum(['json', 'pdf']).default('json')
});

// Agent schemas
const processPhotoSchema = z.object({
  jobId: uuidSchema,
  photoBase64: z.string().min(1).optional()
});

const calculateCarbonSchema = z.object({
  jobId: uuidSchema,
  items: z.array(jobItemSchema).min(1)
});

// Query parameter schemas
const paginationSchema = z.object({
  limit: z.coerce.number().int().min(1).max(100).default(20),
  offset: z.coerce.number().int().min(0).default(0)
});

const jobsQuerySchema = paginationSchema.extend({
  status: z.enum(['pending', 'in_progress', 'completed', 'cancelled']).optional(),
  verticalId: uuidSchema.optional(),
  startDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
  endDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional()
});

const metricsQuerySchema = z.object({
  period: z.enum(['7d', '30d', '90d', '12m', 'all']).default('30d'),
  groupBy: z.enum(['day', 'week', 'month']).optional()
});

// Validation middleware factory
function validate(schema, source = 'body') {
  return (req, res, next) => {
    try {
      const data = source === 'body' ? req.body
        : source === 'query' ? req.query
        : source === 'params' ? req.params
        : req[source];

      const validated = schema.parse(data);

      // Replace the source with validated data
      if (source === 'body') req.body = validated;
      else if (source === 'query') req.query = validated;
      else if (source === 'params') req.params = validated;

      next();
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({
          error: 'Validation failed',
          details: error.errors.map(e => ({
            field: e.path.join('.'),
            message: e.message
          }))
        });
      }
      next(error);
    }
  };
}

// Async validation helper
async function validateAsync(schema, data) {
  return schema.parseAsync(data);
}

// Safe parse helper (doesn't throw)
function safeParse(schema, data) {
  return schema.safeParse(data);
}

module.exports = {
  // Schemas
  registerSchema,
  loginSchema,
  forgotPasswordSchema,
  resetPasswordSchema,
  changePasswordSchema,
  updateCompanySchema,
  createJobSchema,
  updateJobSchema,
  jobItemSchema,
  addJobItemsSchema,
  upgradeSubscriptionSchema,
  updateUserSchema,
  inviteUserSchema,
  generateReportSchema,
  processPhotoSchema,
  calculateCarbonSchema,
  paginationSchema,
  jobsQuerySchema,
  metricsQuerySchema,

  // Common schemas
  uuidSchema,
  emailSchema,
  phoneSchema,
  passwordSchema,

  // Helpers
  validate,
  validateAsync,
  safeParse,

  // Re-export zod for custom schemas
  z
};
