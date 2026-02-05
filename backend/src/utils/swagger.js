const swaggerJsdoc = require('swagger-jsdoc');
const swaggerUi = require('swagger-ui-express');

const options = {
  definition: {
    openapi: '3.0.0',
    info: {
      title: 'ProofGreen API',
      version: '1.0.0',
      description: 'AI-powered ESG tracking platform for home service businesses',
      contact: {
        name: 'ProofGreen Support',
        email: 'support@proofgreen.com'
      },
      license: {
        name: 'MIT',
        url: 'https://opensource.org/licenses/MIT'
      }
    },
    servers: [
      {
        url: process.env.API_URL || 'http://localhost:3001',
        description: 'API Server'
      }
    ],
    tags: [
      { name: 'Auth', description: 'Authentication endpoints' },
      { name: 'Companies', description: 'Company management' },
      { name: 'Jobs', description: 'Job management' },
      { name: 'Agent', description: 'AI agent processing' },
      { name: 'Metrics', description: 'ESG metrics and analytics' },
      { name: 'Reports', description: 'Report generation' },
      { name: 'Subscriptions', description: 'Subscription and billing' },
      { name: 'Team', description: 'Team management' },
      { name: 'Admin', description: 'Admin dashboard (restricted)' }
    ],
    components: {
      securitySchemes: {
        bearerAuth: {
          type: 'http',
          scheme: 'bearer',
          bearerFormat: 'JWT',
          description: 'Enter your JWT token'
        }
      },
      schemas: {
        Error: {
          type: 'object',
          properties: {
            error: { type: 'string' },
            details: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  field: { type: 'string' },
                  message: { type: 'string' }
                }
              }
            }
          }
        },
        Pagination: {
          type: 'object',
          properties: {
            total: { type: 'integer' },
            limit: { type: 'integer' },
            offset: { type: 'integer' }
          }
        },
        User: {
          type: 'object',
          properties: {
            id: { type: 'string', format: 'uuid' },
            email: { type: 'string', format: 'email' },
            firstName: { type: 'string' },
            lastName: { type: 'string' },
            role: { type: 'string', enum: ['owner', 'admin', 'manager', 'member'] },
            avatarUrl: { type: 'string', format: 'uri', nullable: true },
            isActive: { type: 'boolean' },
            createdAt: { type: 'string', format: 'date-time' }
          }
        },
        Company: {
          type: 'object',
          properties: {
            id: { type: 'string', format: 'uuid' },
            name: { type: 'string' },
            email: { type: 'string', format: 'email' },
            phone: { type: 'string', nullable: true },
            addressLine1: { type: 'string', nullable: true },
            city: { type: 'string', nullable: true },
            state: { type: 'string', nullable: true },
            zipCode: { type: 'string', nullable: true },
            website: { type: 'string', format: 'uri', nullable: true },
            description: { type: 'string', nullable: true },
            logoUrl: { type: 'string', format: 'uri', nullable: true },
            createdAt: { type: 'string', format: 'date-time' }
          }
        },
        Job: {
          type: 'object',
          properties: {
            id: { type: 'string', format: 'uuid' },
            companyId: { type: 'string', format: 'uuid' },
            jobNumber: { type: 'string' },
            title: { type: 'string' },
            description: { type: 'string', nullable: true },
            status: { type: 'string', enum: ['pending', 'in_progress', 'completed', 'cancelled'] },
            customerName: { type: 'string', nullable: true },
            customerEmail: { type: 'string', format: 'email', nullable: true },
            customerPhone: { type: 'string', nullable: true },
            addressLine1: { type: 'string', nullable: true },
            city: { type: 'string', nullable: true },
            state: { type: 'string', nullable: true },
            zipCode: { type: 'string', nullable: true },
            scheduledDate: { type: 'string', format: 'date', nullable: true },
            completedAt: { type: 'string', format: 'date-time', nullable: true },
            totalWeightLbs: { type: 'number' },
            recycledWeightLbs: { type: 'number' },
            landfillWeightLbs: { type: 'number' },
            donatedWeightLbs: { type: 'number' },
            carbonOffsetLbs: { type: 'number' },
            diversionRate: { type: 'number' },
            esgScore: { type: 'integer', minimum: 0, maximum: 100 },
            aiProcessed: { type: 'boolean' },
            createdAt: { type: 'string', format: 'date-time' }
          }
        },
        JobItem: {
          type: 'object',
          properties: {
            id: { type: 'string', format: 'uuid' },
            jobId: { type: 'string', format: 'uuid' },
            name: { type: 'string' },
            category: { type: 'string' },
            subcategory: { type: 'string', nullable: true },
            quantity: { type: 'integer' },
            weightLbs: { type: 'number' },
            disposalMethod: { type: 'string', enum: ['recycled', 'donated', 'landfill', 'hazardous', 'compost', 'reused'] },
            detectedByAi: { type: 'boolean' },
            aiConfidence: { type: 'number', minimum: 0, maximum: 1 }
          }
        },
        ESGMetrics: {
          type: 'object',
          properties: {
            totalWeight: { type: 'number' },
            recycledWeight: { type: 'number' },
            donatedWeight: { type: 'number' },
            landfillWeight: { type: 'number' },
            carbonOffset: { type: 'number' },
            diversionRate: { type: 'number' },
            averageEsgScore: { type: 'integer' },
            totalJobs: { type: 'integer' },
            treesEquivalent: { type: 'integer' },
            milesEquivalent: { type: 'integer' }
          }
        },
        Report: {
          type: 'object',
          properties: {
            id: { type: 'string', format: 'uuid' },
            companyId: { type: 'string', format: 'uuid' },
            jobId: { type: 'string', format: 'uuid', nullable: true },
            reportType: { type: 'string', enum: ['job', 'weekly', 'monthly', 'quarterly', 'annual', 'custom'] },
            title: { type: 'string' },
            summary: { type: 'string', nullable: true },
            metricsSnapshot: { type: 'object' },
            isPublic: { type: 'boolean' },
            publicToken: { type: 'string', nullable: true },
            generatedAt: { type: 'string', format: 'date-time' }
          }
        },
        PricingPlan: {
          type: 'object',
          properties: {
            id: { type: 'string', format: 'uuid' },
            slug: { type: 'string' },
            name: { type: 'string' },
            description: { type: 'string' },
            priceMonthly: { type: 'number' },
            priceYearly: { type: 'number' },
            features: { type: 'array', items: { type: 'string' } },
            jobLimit: { type: 'integer', nullable: true },
            userLimit: { type: 'integer', nullable: true },
            aiAnalysisLimit: { type: 'integer', nullable: true }
          }
        },
        Subscription: {
          type: 'object',
          properties: {
            id: { type: 'string', format: 'uuid' },
            companyId: { type: 'string', format: 'uuid' },
            planId: { type: 'string', format: 'uuid' },
            status: { type: 'string', enum: ['active', 'cancelled', 'past_due', 'trialing', 'paused'] },
            billingCycle: { type: 'string', enum: ['monthly', 'yearly'] },
            currentPeriodStart: { type: 'string', format: 'date-time' },
            currentPeriodEnd: { type: 'string', format: 'date-time' }
          }
        },
        Milestone: {
          type: 'object',
          properties: {
            id: { type: 'string', format: 'uuid' },
            name: { type: 'string' },
            description: { type: 'string' },
            milestoneType: { type: 'string', enum: ['tons_diverted', 'carbon_saved', 'jobs_completed', 'diversion_rate', 'custom'] },
            thresholdValue: { type: 'number' },
            thresholdUnit: { type: 'string' },
            achieved: { type: 'boolean' },
            achievedAt: { type: 'string', format: 'date-time', nullable: true },
            currentValue: { type: 'number' },
            progress: { type: 'number' }
          }
        }
      }
    },
    security: [{ bearerAuth: [] }]
  },
  apis: [] // We'll define routes inline
};

// Define API documentation
const apiDocs = {
  paths: {
    '/api/auth/register': {
      post: {
        tags: ['Auth'],
        summary: 'Register a new company and user',
        security: [],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                required: ['email', 'password', 'firstName', 'lastName', 'companyName'],
                properties: {
                  email: { type: 'string', format: 'email' },
                  password: { type: 'string', minLength: 8 },
                  firstName: { type: 'string' },
                  lastName: { type: 'string' },
                  companyName: { type: 'string' },
                  phone: { type: 'string' }
                }
              }
            }
          }
        },
        responses: {
          201: {
            description: 'Registration successful',
            content: {
              'application/json': {
                schema: {
                  type: 'object',
                  properties: {
                    token: { type: 'string' },
                    user: { $ref: '#/components/schemas/User' },
                    company: { $ref: '#/components/schemas/Company' }
                  }
                }
              }
            }
          },
          400: { description: 'Validation error' },
          409: { description: 'Email already registered' }
        }
      }
    },
    '/api/auth/login': {
      post: {
        tags: ['Auth'],
        summary: 'Login with email and password',
        security: [],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                required: ['email', 'password'],
                properties: {
                  email: { type: 'string', format: 'email' },
                  password: { type: 'string' }
                }
              }
            }
          }
        },
        responses: {
          200: {
            description: 'Login successful',
            content: {
              'application/json': {
                schema: {
                  type: 'object',
                  properties: {
                    token: { type: 'string' },
                    user: { $ref: '#/components/schemas/User' },
                    company: { $ref: '#/components/schemas/Company' }
                  }
                }
              }
            }
          },
          401: { description: 'Invalid credentials' }
        }
      }
    },
    '/api/jobs': {
      get: {
        tags: ['Jobs'],
        summary: 'List jobs for the company',
        parameters: [
          { name: 'status', in: 'query', schema: { type: 'string', enum: ['pending', 'in_progress', 'completed', 'cancelled'] } },
          { name: 'limit', in: 'query', schema: { type: 'integer', default: 20 } },
          { name: 'offset', in: 'query', schema: { type: 'integer', default: 0 } },
          { name: 'startDate', in: 'query', schema: { type: 'string', format: 'date' } },
          { name: 'endDate', in: 'query', schema: { type: 'string', format: 'date' } }
        ],
        responses: {
          200: {
            description: 'Jobs list',
            content: {
              'application/json': {
                schema: {
                  type: 'object',
                  properties: {
                    jobs: { type: 'array', items: { $ref: '#/components/schemas/Job' } },
                    pagination: { $ref: '#/components/schemas/Pagination' }
                  }
                }
              }
            }
          }
        }
      },
      post: {
        tags: ['Jobs'],
        summary: 'Create a new job',
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                required: ['title'],
                properties: {
                  title: { type: 'string' },
                  description: { type: 'string' },
                  verticalId: { type: 'string', format: 'uuid' },
                  customerName: { type: 'string' },
                  customerEmail: { type: 'string', format: 'email' },
                  customerPhone: { type: 'string' },
                  addressLine1: { type: 'string' },
                  city: { type: 'string' },
                  state: { type: 'string' },
                  zipCode: { type: 'string' },
                  scheduledDate: { type: 'string', format: 'date' }
                }
              }
            }
          }
        },
        responses: {
          201: {
            description: 'Job created',
            content: {
              'application/json': {
                schema: {
                  type: 'object',
                  properties: {
                    job: { $ref: '#/components/schemas/Job' }
                  }
                }
              }
            }
          }
        }
      }
    },
    '/api/jobs/{id}': {
      get: {
        tags: ['Jobs'],
        summary: 'Get job details',
        parameters: [
          { name: 'id', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } }
        ],
        responses: {
          200: {
            description: 'Job details',
            content: {
              'application/json': {
                schema: {
                  type: 'object',
                  properties: {
                    job: { $ref: '#/components/schemas/Job' }
                  }
                }
              }
            }
          }
        }
      },
      put: {
        tags: ['Jobs'],
        summary: 'Update job',
        parameters: [
          { name: 'id', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } }
        ],
        requestBody: {
          content: {
            'application/json': {
              schema: {
                type: 'object',
                properties: {
                  title: { type: 'string' },
                  status: { type: 'string', enum: ['pending', 'in_progress', 'completed', 'cancelled'] },
                  description: { type: 'string' }
                }
              }
            }
          }
        },
        responses: {
          200: { description: 'Job updated' }
        }
      }
    },
    '/api/jobs/{id}/photos': {
      post: {
        tags: ['Jobs'],
        summary: 'Upload photos for a job',
        parameters: [
          { name: 'id', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } }
        ],
        requestBody: {
          required: true,
          content: {
            'multipart/form-data': {
              schema: {
                type: 'object',
                properties: {
                  photos: { type: 'array', items: { type: 'string', format: 'binary' } },
                  photoType: { type: 'string', enum: ['before', 'after'] }
                }
              }
            }
          }
        },
        responses: {
          200: { description: 'Photos uploaded, AI processing started' }
        }
      }
    },
    '/api/agent/process': {
      post: {
        tags: ['Agent'],
        summary: 'Process a job photo with AI',
        description: 'Runs the full AI processing pipeline: photo analysis, job type identification, carbon calculation, milestone check, and report generation',
        requestBody: {
          required: true,
          content: {
            'multipart/form-data': {
              schema: {
                type: 'object',
                required: ['jobId'],
                properties: {
                  jobId: { type: 'string', format: 'uuid' },
                  photo: { type: 'string', format: 'binary' }
                }
              }
            }
          }
        },
        responses: {
          200: {
            description: 'Processing started',
            content: {
              'application/json': {
                schema: {
                  type: 'object',
                  properties: {
                    message: { type: 'string' },
                    jobId: { type: 'string' },
                    status: { type: 'string' }
                  }
                }
              }
            }
          }
        }
      }
    },
    '/api/agent/status/{jobId}': {
      get: {
        tags: ['Agent'],
        summary: 'Get AI processing status for a job',
        parameters: [
          { name: 'jobId', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } }
        ],
        responses: {
          200: {
            description: 'Processing status',
            content: {
              'application/json': {
                schema: {
                  type: 'object',
                  properties: {
                    jobId: { type: 'string' },
                    processed: { type: 'boolean' },
                    processedAt: { type: 'string', format: 'date-time', nullable: true },
                    confidence: { type: 'number' }
                  }
                }
              }
            }
          }
        }
      }
    },
    '/api/metrics/dashboard': {
      get: {
        tags: ['Metrics'],
        summary: 'Get dashboard metrics',
        responses: {
          200: {
            description: 'Dashboard data',
            content: {
              'application/json': {
                schema: {
                  type: 'object',
                  properties: {
                    metrics: { $ref: '#/components/schemas/ESGMetrics' },
                    recentJobs: { type: 'array', items: { $ref: '#/components/schemas/Job' } },
                    milestones: { type: 'array', items: { $ref: '#/components/schemas/Milestone' } }
                  }
                }
              }
            }
          }
        }
      }
    },
    '/api/subscriptions/plans': {
      get: {
        tags: ['Subscriptions'],
        summary: 'Get available pricing plans',
        security: [],
        responses: {
          200: {
            description: 'Pricing plans',
            content: {
              'application/json': {
                schema: {
                  type: 'object',
                  properties: {
                    plans: { type: 'array', items: { $ref: '#/components/schemas/PricingPlan' } }
                  }
                }
              }
            }
          }
        }
      }
    },
    '/api/subscriptions/current': {
      get: {
        tags: ['Subscriptions'],
        summary: 'Get current subscription',
        responses: {
          200: {
            description: 'Current subscription and usage',
            content: {
              'application/json': {
                schema: {
                  type: 'object',
                  properties: {
                    subscription: { $ref: '#/components/schemas/Subscription' },
                    usage: {
                      type: 'object',
                      properties: {
                        jobs: {
                          type: 'object',
                          properties: {
                            used: { type: 'integer' },
                            limit: { type: 'integer', nullable: true },
                            percentage: { type: 'integer' }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    },
    '/api/reports/{id}': {
      get: {
        tags: ['Reports'],
        summary: 'Get report details',
        parameters: [
          { name: 'id', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } }
        ],
        responses: {
          200: {
            description: 'Report details',
            content: {
              'application/json': {
                schema: {
                  type: 'object',
                  properties: {
                    report: { $ref: '#/components/schemas/Report' }
                  }
                }
              }
            }
          }
        }
      }
    },
    '/api/reports/{id}/pdf': {
      get: {
        tags: ['Reports'],
        summary: 'Download report as PDF',
        parameters: [
          { name: 'id', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } }
        ],
        responses: {
          200: {
            description: 'PDF file',
            content: {
              'application/pdf': {
                schema: {
                  type: 'string',
                  format: 'binary'
                }
              }
            }
          }
        }
      }
    }
  }
};

// Merge API docs with options
options.definition.paths = apiDocs.paths;

const specs = swaggerJsdoc(options);

function setupSwagger(app) {
  app.use('/api/docs', swaggerUi.serve, swaggerUi.setup(specs, {
    customCss: '.swagger-ui .topbar { display: none }',
    customSiteTitle: 'ProofGreen API Documentation'
  }));

  // Serve OpenAPI spec as JSON
  app.get('/api/docs.json', (req, res) => {
    res.json(specs);
  });
}

module.exports = { setupSwagger, specs };
