const request = require('supertest');
const app = require('../src/index');
const { supabase } = require('../src/utils/supabase');

// Mock Supabase
jest.mock('../src/utils/supabase', () => ({
  supabase: {
    from: jest.fn(() => ({
      select: jest.fn().mockReturnThis(),
      insert: jest.fn().mockReturnThis(),
      update: jest.fn().mockReturnThis(),
      delete: jest.fn().mockReturnThis(),
      eq: jest.fn().mockReturnThis(),
      in: jest.fn().mockReturnThis(),
      single: jest.fn(),
      order: jest.fn().mockReturnThis(),
      range: jest.fn().mockReturnThis(),
      limit: jest.fn().mockReturnThis(),
      gte: jest.fn().mockReturnThis(),
      lte: jest.fn().mockReturnThis()
    }))
  }
}));

// Mock bcrypt
jest.mock('bcryptjs', () => ({
  hash: jest.fn().mockResolvedValue('hashed_password'),
  compare: jest.fn().mockResolvedValue(true)
}));

describe('Health Check', () => {
  it('should return healthy status', async () => {
    const response = await request(app).get('/health');
    expect(response.status).toBe(200);
    expect(response.body.status).toBe('healthy');
    expect(response.body.service).toBe('ProofGreen API');
  });
});

describe('Auth Routes', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('POST /api/auth/register', () => {
    it('should register a new user successfully', async () => {
      const mockCompany = { id: 'company-123', name: 'Test Company' };
      const mockUser = { id: 'user-123', email: 'test@example.com' };

      supabase.from.mockImplementation((table) => {
        const chain = {
          select: jest.fn().mockReturnThis(),
          insert: jest.fn().mockReturnThis(),
          eq: jest.fn().mockReturnThis(),
          single: jest.fn()
        };

        if (table === 'companies') {
          chain.single.mockResolvedValue({ data: mockCompany, error: null });
        } else if (table === 'users') {
          chain.select.mockReturnValue({
            eq: jest.fn().mockReturnValue({
              single: jest.fn().mockResolvedValue({ data: null, error: { code: 'PGRST116' } })
            })
          });
          chain.single.mockResolvedValue({ data: mockUser, error: null });
        } else if (table === 'subscriptions') {
          chain.single.mockResolvedValue({ data: { id: 'sub-123' }, error: null });
        } else if (table === 'pricing_plans') {
          chain.single.mockResolvedValue({ data: { id: 'plan-123' }, error: null });
        }

        return chain;
      });

      const response = await request(app)
        .post('/api/auth/register')
        .send({
          email: 'test@example.com',
          password: 'Password123!',
          firstName: 'Test',
          lastName: 'User',
          companyName: 'Test Company'
        });

      expect(response.status).toBe(201);
      expect(response.body).toHaveProperty('token');
      expect(response.body).toHaveProperty('user');
    });

    it('should reject registration with missing fields', async () => {
      const response = await request(app)
        .post('/api/auth/register')
        .send({
          email: 'test@example.com'
        });

      expect(response.status).toBe(400);
      expect(response.body).toHaveProperty('errors');
    });

    it('should reject registration with invalid email', async () => {
      const response = await request(app)
        .post('/api/auth/register')
        .send({
          email: 'invalid-email',
          password: 'Password123!',
          firstName: 'Test',
          lastName: 'User',
          companyName: 'Test Company'
        });

      expect(response.status).toBe(400);
    });
  });

  describe('POST /api/auth/login', () => {
    it('should login successfully with valid credentials', async () => {
      const mockUser = {
        id: 'user-123',
        email: 'test@example.com',
        password_hash: 'hashed_password',
        is_active: true,
        company_id: 'company-123'
      };

      supabase.from.mockReturnValue({
        select: jest.fn().mockReturnThis(),
        eq: jest.fn().mockReturnThis(),
        single: jest.fn().mockResolvedValue({ data: mockUser, error: null })
      });

      const response = await request(app)
        .post('/api/auth/login')
        .send({
          email: 'test@example.com',
          password: 'Password123!'
        });

      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('token');
    });

    it('should reject login with invalid credentials', async () => {
      supabase.from.mockReturnValue({
        select: jest.fn().mockReturnThis(),
        eq: jest.fn().mockReturnThis(),
        single: jest.fn().mockResolvedValue({ data: null, error: { code: 'PGRST116' } })
      });

      const response = await request(app)
        .post('/api/auth/login')
        .send({
          email: 'wrong@example.com',
          password: 'WrongPassword!'
        });

      expect(response.status).toBe(401);
    });
  });
});

describe('Jobs Routes', () => {
  const mockToken = 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiJ1c2VyLTEyMyIsImNvbXBhbnlJZCI6ImNvbXBhbnktMTIzIiwiaWF0IjoxNjE2MjM5MDIyfQ.test';

  beforeEach(() => {
    jest.clearAllMocks();

    // Mock user authentication
    supabase.from.mockImplementation((table) => {
      if (table === 'users') {
        return {
          select: jest.fn().mockReturnThis(),
          eq: jest.fn().mockReturnThis(),
          single: jest.fn().mockResolvedValue({
            data: {
              id: 'user-123',
              company_id: 'company-123',
              is_active: true,
              role: 'owner'
            },
            error: null
          })
        };
      }
      return {
        select: jest.fn().mockReturnThis(),
        insert: jest.fn().mockReturnThis(),
        update: jest.fn().mockReturnThis(),
        eq: jest.fn().mockReturnThis(),
        in: jest.fn().mockReturnThis(),
        order: jest.fn().mockReturnThis(),
        range: jest.fn().mockReturnThis(),
        single: jest.fn().mockResolvedValue({ data: null, error: null })
      };
    });
  });

  describe('GET /api/jobs', () => {
    it('should return jobs list for authenticated user', async () => {
      const mockJobs = [
        { id: 'job-1', title: 'Test Job 1', status: 'pending' },
        { id: 'job-2', title: 'Test Job 2', status: 'completed' }
      ];

      supabase.from.mockImplementation((table) => {
        if (table === 'users') {
          return {
            select: jest.fn().mockReturnThis(),
            eq: jest.fn().mockReturnThis(),
            single: jest.fn().mockResolvedValue({
              data: { id: 'user-123', company_id: 'company-123', is_active: true },
              error: null
            })
          };
        }
        return {
          select: jest.fn().mockReturnThis(),
          eq: jest.fn().mockReturnThis(),
          order: jest.fn().mockReturnThis(),
          range: jest.fn().mockResolvedValue({ data: mockJobs, error: null, count: 2 })
        };
      });

      const response = await request(app)
        .get('/api/jobs')
        .set('Authorization', mockToken);

      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('jobs');
      expect(response.body).toHaveProperty('pagination');
    });

    it('should reject unauthenticated requests', async () => {
      const response = await request(app).get('/api/jobs');
      expect(response.status).toBe(401);
    });
  });

  describe('POST /api/jobs', () => {
    it('should create a new job', async () => {
      const mockJob = {
        id: 'job-123',
        job_number: 'JOB-00001',
        title: 'Test Job',
        status: 'pending'
      };

      supabase.from.mockImplementation((table) => {
        if (table === 'users') {
          return {
            select: jest.fn().mockReturnThis(),
            eq: jest.fn().mockReturnThis(),
            single: jest.fn().mockResolvedValue({
              data: { id: 'user-123', company_id: 'company-123', is_active: true },
              error: null
            })
          };
        }
        if (table === 'subscriptions') {
          return {
            select: jest.fn().mockReturnThis(),
            eq: jest.fn().mockReturnThis(),
            in: jest.fn().mockReturnThis(),
            single: jest.fn().mockResolvedValue({ data: null, error: null })
          };
        }
        if (table === 'jobs') {
          return {
            select: jest.fn().mockReturnThis(),
            insert: jest.fn().mockReturnThis(),
            eq: jest.fn().mockReturnThis(),
            single: jest.fn().mockResolvedValue({ data: mockJob, error: null, count: 0 })
          };
        }
        return {
          select: jest.fn().mockReturnThis(),
          single: jest.fn().mockResolvedValue({ data: null, error: null })
        };
      });

      const response = await request(app)
        .post('/api/jobs')
        .set('Authorization', mockToken)
        .send({
          title: 'Test Job',
          customerName: 'John Doe'
        });

      expect(response.status).toBe(201);
      expect(response.body).toHaveProperty('job');
    });
  });
});

describe('Metrics Routes', () => {
  const mockToken = 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiJ1c2VyLTEyMyIsImNvbXBhbnlJZCI6ImNvbXBhbnktMTIzIiwiaWF0IjoxNjE2MjM5MDIyfQ.test';

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('GET /api/metrics/dashboard', () => {
    it('should return dashboard metrics', async () => {
      supabase.from.mockImplementation((table) => {
        if (table === 'users') {
          return {
            select: jest.fn().mockReturnThis(),
            eq: jest.fn().mockReturnThis(),
            single: jest.fn().mockResolvedValue({
              data: { id: 'user-123', company_id: 'company-123', is_active: true },
              error: null
            })
          };
        }
        if (table === 'jobs') {
          return {
            select: jest.fn().mockReturnThis(),
            eq: jest.fn().mockReturnThis(),
            order: jest.fn().mockReturnThis(),
            limit: jest.fn().mockResolvedValue({
              data: [{ total_weight_lbs: 1000, recycled_weight_lbs: 800 }],
              error: null
            })
          };
        }
        if (table === 'milestones') {
          return {
            select: jest.fn().mockReturnThis(),
            eq: jest.fn().mockReturnThis(),
            order: jest.fn().mockResolvedValue({ data: [], error: null })
          };
        }
        return {
          select: jest.fn().mockReturnThis(),
          eq: jest.fn().mockReturnThis(),
          single: jest.fn().mockResolvedValue({ data: null, error: null })
        };
      });

      const response = await request(app)
        .get('/api/metrics/dashboard')
        .set('Authorization', mockToken);

      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('metrics');
    });
  });
});

describe('Subscriptions Routes', () => {
  describe('GET /api/subscriptions/plans', () => {
    it('should return available pricing plans', async () => {
      const mockPlans = [
        { id: 'plan-1', name: 'Founders', price_monthly: 99 },
        { id: 'plan-2', name: 'Starter', price_monthly: 149 }
      ];

      supabase.from.mockReturnValue({
        select: jest.fn().mockReturnThis(),
        eq: jest.fn().mockReturnThis(),
        order: jest.fn().mockResolvedValue({ data: mockPlans, error: null })
      });

      const response = await request(app).get('/api/subscriptions/plans');

      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('plans');
      expect(Array.isArray(response.body.plans)).toBe(true);
    });
  });
});
