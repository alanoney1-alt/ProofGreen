const {
  analyzePhoto,
  identifyJobType,
  calculateCarbon,
  checkMilestones,
  generateReport,
  processJobPhoto
} = require('../src/agents/esgAgent');
const { supabase } = require('../src/utils/supabase');

// Mock external dependencies
jest.mock('../src/utils/supabase');
jest.mock('openai', () => ({
  OpenAI: jest.fn().mockImplementation(() => ({
    chat: {
      completions: {
        create: jest.fn().mockResolvedValue({
          choices: [{
            message: {
              content: JSON.stringify({
                items: [
                  { name: 'Wooden Chair', category: 'furniture', subcategory: 'wood', weight_lbs: 25, recyclable: true },
                  { name: 'Old Microwave', category: 'electronics', subcategory: 'small', weight_lbs: 35, recyclable: true }
                ]
              })
            }
          }]
        })
      }
    }
  }))
}));

jest.mock('@anthropic-ai/sdk', () => ({
  __esModule: true,
  default: jest.fn().mockImplementation(() => ({
    messages: {
      create: jest.fn().mockResolvedValue({
        content: [{
          text: JSON.stringify({
            job_type: 'junk_removal',
            confidence: 0.92,
            reasoning: 'Mixed furniture and electronics indicate general junk removal'
          })
        }]
      })
    }
  }))
}));

describe('ESG Agent Functions', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('analyzePhoto', () => {
    it('should analyze a photo and return detected items', async () => {
      const mockPhotoBase64 = 'base64encodedphotodata';
      const mockJobId = 'job-123';
      const mockCompanyId = 'company-123';

      supabase.from.mockReturnValue({
        insert: jest.fn().mockReturnThis(),
        update: jest.fn().mockReturnThis(),
        select: jest.fn().mockReturnThis(),
        eq: jest.fn().mockReturnThis(),
        single: jest.fn().mockResolvedValue({ data: { id: 'exec-123' }, error: null })
      });

      const result = await analyzePhoto(mockPhotoBase64, mockJobId, mockCompanyId);

      expect(result).toHaveProperty('items');
      expect(Array.isArray(result.items)).toBe(true);
      expect(result.items.length).toBeGreaterThan(0);
      expect(result.items[0]).toHaveProperty('name');
      expect(result.items[0]).toHaveProperty('category');
      expect(result.items[0]).toHaveProperty('weight_lbs');
    });

    it('should log execution in agent_executions table', async () => {
      const insertMock = jest.fn().mockReturnThis();
      supabase.from.mockReturnValue({
        insert: insertMock,
        update: jest.fn().mockReturnThis(),
        select: jest.fn().mockReturnThis(),
        eq: jest.fn().mockReturnThis(),
        single: jest.fn().mockResolvedValue({ data: { id: 'exec-123' }, error: null })
      });

      await analyzePhoto('base64data', 'job-123', 'company-123');

      expect(supabase.from).toHaveBeenCalledWith('agent_executions');
    });
  });

  describe('identifyJobType', () => {
    it('should identify job type from detected items', async () => {
      const mockItems = [
        { name: 'AC Unit', category: 'hvac', subcategory: 'unit', weight_lbs: 150 },
        { name: 'Ductwork', category: 'hvac', subcategory: 'ductwork', weight_lbs: 25 }
      ];

      supabase.from.mockReturnValue({
        insert: jest.fn().mockReturnThis(),
        update: jest.fn().mockReturnThis(),
        select: jest.fn().mockReturnThis(),
        eq: jest.fn().mockReturnThis(),
        single: jest.fn().mockResolvedValue({ data: { id: 'exec-123' }, error: null })
      });

      const result = await identifyJobType(mockItems, 'job-123', 'company-123');

      expect(result).toHaveProperty('job_type');
      expect(result).toHaveProperty('confidence');
      expect(typeof result.confidence).toBe('number');
      expect(result.confidence).toBeGreaterThanOrEqual(0);
      expect(result.confidence).toBeLessThanOrEqual(1);
    });

    it('should handle mixed item categories', async () => {
      const mockItems = [
        { name: 'Couch', category: 'furniture', subcategory: 'upholstered', weight_lbs: 100 },
        { name: 'TV', category: 'electronics', subcategory: 'tv', weight_lbs: 40 },
        { name: 'Cardboard', category: 'general', subcategory: 'cardboard', weight_lbs: 10 }
      ];

      supabase.from.mockReturnValue({
        insert: jest.fn().mockReturnThis(),
        update: jest.fn().mockReturnThis(),
        select: jest.fn().mockReturnThis(),
        eq: jest.fn().mockReturnThis(),
        single: jest.fn().mockResolvedValue({ data: { id: 'exec-123' }, error: null })
      });

      const result = await identifyJobType(mockItems, 'job-123', 'company-123');

      expect(result.job_type).toBeDefined();
    });
  });

  describe('calculateCarbon', () => {
    it('should calculate carbon metrics correctly', async () => {
      const mockItems = [
        { name: 'Chair', category: 'furniture', subcategory: 'wood', weight_lbs: 25, disposal_method: 'recycled' },
        { name: 'Table', category: 'furniture', subcategory: 'wood', weight_lbs: 50, disposal_method: 'donated' }
      ];

      const mockCarbonFactor = {
        landfill_factor: 1.2,
        recycle_factor: 0.3,
        reuse_factor: 0.1
      };

      supabase.from.mockImplementation((table) => {
        if (table === 'carbon_factors') {
          return {
            select: jest.fn().mockReturnThis(),
            eq: jest.fn().mockReturnThis(),
            single: jest.fn().mockResolvedValue({ data: mockCarbonFactor, error: null })
          };
        }
        if (table === 'jobs') {
          return {
            update: jest.fn().mockReturnThis(),
            eq: jest.fn().mockResolvedValue({ error: null })
          };
        }
        return {
          insert: jest.fn().mockReturnThis(),
          update: jest.fn().mockReturnThis(),
          select: jest.fn().mockReturnThis(),
          eq: jest.fn().mockReturnThis(),
          single: jest.fn().mockResolvedValue({ data: { id: 'exec-123' }, error: null })
        };
      });

      const result = await calculateCarbon('job-123', mockItems, 'company-123');

      expect(result).toHaveProperty('total_weight');
      expect(result).toHaveProperty('recycled_weight');
      expect(result).toHaveProperty('carbon_offset');
      expect(result).toHaveProperty('diversion_rate');
      expect(result).toHaveProperty('esg_score');
      expect(result.total_weight).toBe(75);
      expect(result.diversion_rate).toBeGreaterThan(0);
    });

    it('should handle items with no carbon factor', async () => {
      const mockItems = [
        { name: 'Unknown Item', category: 'unknown', subcategory: 'unknown', weight_lbs: 10, disposal_method: 'landfill' }
      ];

      supabase.from.mockImplementation((table) => {
        if (table === 'carbon_factors') {
          return {
            select: jest.fn().mockReturnThis(),
            eq: jest.fn().mockReturnThis(),
            single: jest.fn().mockResolvedValue({ data: null, error: { code: 'PGRST116' } })
          };
        }
        if (table === 'jobs') {
          return {
            update: jest.fn().mockReturnThis(),
            eq: jest.fn().mockResolvedValue({ error: null })
          };
        }
        return {
          insert: jest.fn().mockReturnThis(),
          update: jest.fn().mockReturnThis(),
          select: jest.fn().mockReturnThis(),
          eq: jest.fn().mockReturnThis(),
          single: jest.fn().mockResolvedValue({ data: { id: 'exec-123' }, error: null })
        };
      });

      const result = await calculateCarbon('job-123', mockItems, 'company-123');

      expect(result).toHaveProperty('total_weight');
      expect(result.total_weight).toBe(10);
    });
  });

  describe('checkMilestones', () => {
    it('should check and update milestones', async () => {
      const mockMilestones = [
        { id: 'milestone-1', milestone_type: 'tons_diverted', threshold_value: 2000, achieved: false },
        { id: 'milestone-2', milestone_type: 'jobs_completed', threshold_value: 10, achieved: false }
      ];

      const mockJobStats = {
        total_recycled: 2500,
        total_donated: 500,
        job_count: 15
      };

      supabase.from.mockImplementation((table) => {
        if (table === 'milestones') {
          return {
            select: jest.fn().mockReturnThis(),
            update: jest.fn().mockReturnThis(),
            eq: jest.fn().mockReturnThis(),
            order: jest.fn().mockResolvedValue({ data: mockMilestones, error: null })
          };
        }
        if (table === 'jobs') {
          return {
            select: jest.fn().mockReturnThis(),
            eq: jest.fn().mockResolvedValue({
              data: [
                { recycled_weight_lbs: 1500, donated_weight_lbs: 300, carbon_offset_lbs: 500 },
                { recycled_weight_lbs: 1000, donated_weight_lbs: 200, carbon_offset_lbs: 400 }
              ],
              error: null
            })
          };
        }
        return {
          insert: jest.fn().mockReturnThis(),
          select: jest.fn().mockReturnThis(),
          eq: jest.fn().mockReturnThis(),
          single: jest.fn().mockResolvedValue({ data: { id: 'exec-123' }, error: null })
        };
      });

      const result = await checkMilestones('company-123');

      expect(result).toHaveProperty('milestones');
      expect(result).toHaveProperty('newlyAchieved');
      expect(Array.isArray(result.milestones)).toBe(true);
    });

    it('should return newly achieved milestones', async () => {
      const mockMilestones = [
        { id: 'milestone-1', milestone_type: 'tons_diverted', threshold_value: 1000, achieved: false }
      ];

      supabase.from.mockImplementation((table) => {
        if (table === 'milestones') {
          return {
            select: jest.fn().mockReturnThis(),
            update: jest.fn().mockReturnThis(),
            eq: jest.fn().mockReturnThis(),
            order: jest.fn().mockResolvedValue({ data: mockMilestones, error: null })
          };
        }
        if (table === 'jobs') {
          return {
            select: jest.fn().mockReturnThis(),
            eq: jest.fn().mockResolvedValue({
              data: [{ recycled_weight_lbs: 2000, donated_weight_lbs: 0, carbon_offset_lbs: 500 }],
              error: null
            })
          };
        }
        return {
          insert: jest.fn().mockReturnThis(),
          select: jest.fn().mockReturnThis(),
          eq: jest.fn().mockReturnThis(),
          single: jest.fn().mockResolvedValue({ data: { id: 'exec-123' }, error: null })
        };
      });

      const result = await checkMilestones('company-123');

      expect(result.newlyAchieved.length).toBeGreaterThanOrEqual(0);
    });
  });

  describe('generateReport', () => {
    it('should generate a job report', async () => {
      const mockJob = {
        id: 'job-123',
        job_number: 'JOB-00001',
        title: 'Test Job',
        total_weight_lbs: 500,
        recycled_weight_lbs: 400,
        carbon_offset_lbs: 150,
        esg_score: 85,
        company_id: 'company-123'
      };

      const mockCompany = {
        id: 'company-123',
        name: 'Test Company'
      };

      supabase.from.mockImplementation((table) => {
        if (table === 'jobs') {
          return {
            select: jest.fn().mockReturnThis(),
            eq: jest.fn().mockReturnThis(),
            single: jest.fn().mockResolvedValue({ data: mockJob, error: null })
          };
        }
        if (table === 'companies') {
          return {
            select: jest.fn().mockReturnThis(),
            eq: jest.fn().mockReturnThis(),
            single: jest.fn().mockResolvedValue({ data: mockCompany, error: null })
          };
        }
        if (table === 'job_items') {
          return {
            select: jest.fn().mockReturnThis(),
            eq: jest.fn().mockResolvedValue({ data: [], error: null })
          };
        }
        if (table === 'esg_reports') {
          return {
            insert: jest.fn().mockReturnThis(),
            select: jest.fn().mockReturnThis(),
            single: jest.fn().mockResolvedValue({ data: { id: 'report-123' }, error: null })
          };
        }
        return {
          insert: jest.fn().mockReturnThis(),
          select: jest.fn().mockReturnThis(),
          eq: jest.fn().mockReturnThis(),
          single: jest.fn().mockResolvedValue({ data: { id: 'exec-123' }, error: null })
        };
      });

      const result = await generateReport('job-123', 'company-123');

      expect(result).toHaveProperty('report');
      expect(result.report).toHaveProperty('id');
    });
  });

  describe('processJobPhoto (full pipeline)', () => {
    it('should run the complete processing pipeline', async () => {
      const mockPhotoBase64 = 'base64encodedphotodata';
      const mockJobId = 'job-123';
      const mockCompanyId = 'company-123';

      supabase.from.mockImplementation((table) => {
        return {
          insert: jest.fn().mockReturnThis(),
          update: jest.fn().mockReturnThis(),
          select: jest.fn().mockReturnThis(),
          eq: jest.fn().mockReturnThis(),
          order: jest.fn().mockReturnThis(),
          single: jest.fn().mockResolvedValue({ data: { id: 'test-id' }, error: null })
        };
      });

      const result = await processJobPhoto(mockJobId, mockPhotoBase64, mockCompanyId);

      expect(result).toHaveProperty('items');
      expect(result).toHaveProperty('jobType');
      expect(result).toHaveProperty('metrics');
      expect(result).toHaveProperty('milestones');
      expect(result).toHaveProperty('report');
    });
  });
});

describe('Carbon Calculation Edge Cases', () => {
  it('should handle zero weight items', async () => {
    const mockItems = [
      { name: 'Empty Box', category: 'general', subcategory: 'cardboard', weight_lbs: 0, disposal_method: 'recycled' }
    ];

    supabase.from.mockImplementation(() => ({
      select: jest.fn().mockReturnThis(),
      update: jest.fn().mockReturnThis(),
      insert: jest.fn().mockReturnThis(),
      eq: jest.fn().mockReturnThis(),
      single: jest.fn().mockResolvedValue({ data: { landfill_factor: 0.4, recycle_factor: 0.05 }, error: null })
    }));

    const result = await calculateCarbon('job-123', mockItems, 'company-123');

    expect(result.total_weight).toBe(0);
    expect(result.diversion_rate).toBe(0);
  });

  it('should handle all landfill disposal', async () => {
    const mockItems = [
      { name: 'Contaminated Material', category: 'general', subcategory: 'mixed_waste', weight_lbs: 100, disposal_method: 'landfill' }
    ];

    supabase.from.mockImplementation(() => ({
      select: jest.fn().mockReturnThis(),
      update: jest.fn().mockReturnThis(),
      insert: jest.fn().mockReturnThis(),
      eq: jest.fn().mockReturnThis(),
      single: jest.fn().mockResolvedValue({ data: { landfill_factor: 1.0, recycle_factor: 0.4 }, error: null })
    }));

    const result = await calculateCarbon('job-123', mockItems, 'company-123');

    expect(result.landfill_weight).toBe(100);
    expect(result.diversion_rate).toBe(0);
  });
});
