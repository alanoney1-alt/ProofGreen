# ProofGreen

AI-powered ESG tracking platform for home service businesses.

ProofGreen helps home service companies (junk removal, HVAC, roofing, cleaning, etc.) track sustainability metrics, prove environmental impact, and win ESG-focused contracts.

## Features

- **AI Photo Analysis**: Upload job photos and GPT-4 Vision automatically identifies items, estimates weights, and categorizes materials
- **Carbon Tracking**: Automatically calculate carbon offset based on recycling, donations, and diversion rates
- **ESG Scoring**: Get a 0-100 ESG score for every job based on environmental impact
- **Milestone Achievements**: Track progress with gamified milestones for tons diverted, carbon saved, and more
- **Shareable Reports**: Generate professional ESG reports to share with clients and win contracts
- **Multi-Vertical Support**: Works for 20+ service types including junk removal, HVAC, roofing, and more

## Tech Stack

- **Backend**: Node.js + Express
- **Database**: PostgreSQL via Supabase
- **AI**: OpenAI GPT-4 Vision + Anthropic Claude
- **Frontend**: React + TailwindCSS + Vite
- **Deployment**: Vercel (frontend) + Railway (backend)

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn
- Supabase account
- OpenAI API key
- Anthropic API key (optional, for enhanced reports)

### Backend Setup

```bash
cd backend
npm install
cp .env.example .env
# Edit .env with your configuration
npm run dev
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Database Setup

1. Create a new Supabase project
2. Run the SQL schema in `database/schema.sql` in Supabase SQL Editor
3. Copy your Supabase URL and keys to backend `.env`

## Environment Variables

### Backend (.env)

```
PORT=3001
NODE_ENV=development

# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_key

# JWT
JWT_SECRET=your_jwt_secret
JWT_EXPIRES_IN=7d

# AI
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key

# Frontend URL
FRONTEND_URL=http://localhost:5173
```

### Frontend (.env)

```
VITE_API_URL=http://localhost:3001/api
```

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user/company
- `POST /api/auth/login` - Login
- `GET /api/auth/me` - Get current user
- `GET /api/auth/verticals` - List service verticals

### Jobs
- `GET /api/jobs` - List jobs
- `POST /api/jobs` - Create job
- `GET /api/jobs/:id` - Get job details
- `PUT /api/jobs/:id` - Update job
- `POST /api/jobs/:id/photos` - Upload photos

### AI Agent
- `POST /api/agent/process` - Full AI processing pipeline
- `POST /api/agent/analyze-photo` - Analyze photo only
- `GET /api/agent/status/:jobId` - Check processing status

### Metrics
- `GET /api/metrics/dashboard` - Dashboard metrics
- `GET /api/metrics/trends` - Historical trends
- `GET /api/metrics/milestones` - Achievement milestones

### Reports
- `GET /api/reports` - List reports
- `POST /api/reports/generate/job/:jobId` - Generate job report
- `GET /api/reports/public/:token` - View public report

### Subscriptions
- `GET /api/subscriptions/plans` - List pricing plans
- `GET /api/subscriptions/current` - Get current subscription
- `POST /api/subscriptions/upgrade` - Upgrade plan

## Autonomous AI Agent

The core feature is an autonomous AI agent that processes job photos:

1. **analyze_photo()** - GPT-4 Vision identifies items, weights, and categories
2. **identify_job_type()** - Classifies the service vertical
3. **calculate_carbon()** - Computes carbon offset and ESG metrics
4. **check_milestones()** - Awards achievements
5. **generate_report()** - Creates shareable ESG report

## Pricing Plans

| Plan | Price | Jobs/mo | Users | AI Analyses |
|------|-------|---------|-------|-------------|
| Founders | $99 | 100 | 3 | 100 |
| Starter | $149 | 250 | 5 | 250 |
| Professional | $299 | 1,000 | 15 | 1,000 |
| Business | $599 | 5,000 | 50 | 5,000 |
| Enterprise | $1,999 | Unlimited | Unlimited | Unlimited |

## Deployment

### Backend (Railway)

1. Connect your GitHub repo to Railway
2. Set environment variables
3. Deploy

### Frontend (Vercel)

1. Connect your GitHub repo to Vercel
2. Set `VITE_API_URL` to your Railway backend URL
3. Deploy

## License

MIT
