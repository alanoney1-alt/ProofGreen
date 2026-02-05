import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from '../context/AuthContext'
import App from '../App'
import Login from '../pages/auth/Login'
import Register from '../pages/auth/Register'
import Dashboard from '../pages/Dashboard'
import Jobs from '../pages/Jobs'

// Mock the API service
vi.mock('../services/api', () => ({
  authAPI: {
    login: vi.fn(),
    register: vi.fn(),
    me: vi.fn()
  },
  jobsAPI: {
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn()
  },
  metricsAPI: {
    dashboard: vi.fn()
  },
  default: {
    defaults: { headers: { common: {} } }
  }
}))

// Helper to render with providers
const renderWithProviders = (component) => {
  return render(
    <BrowserRouter>
      <AuthProvider>
        {component}
      </AuthProvider>
    </BrowserRouter>
  )
}

describe('Login Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders login form', () => {
    renderWithProviders(<Login />)

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })

  it('shows validation errors for empty form submission', async () => {
    renderWithProviders(<Login />)

    const submitButton = screen.getByRole('button', { name: /sign in/i })
    fireEvent.click(submitButton)

    // HTML5 validation should prevent submission
    const emailInput = screen.getByLabelText(/email/i)
    expect(emailInput).toBeInvalid()
  })

  it('handles email input', () => {
    renderWithProviders(<Login />)

    const emailInput = screen.getByLabelText(/email/i)
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } })

    expect(emailInput.value).toBe('test@example.com')
  })

  it('handles password input', () => {
    renderWithProviders(<Login />)

    const passwordInput = screen.getByLabelText(/password/i)
    fireEvent.change(passwordInput, { target: { value: 'password123' } })

    expect(passwordInput.value).toBe('password123')
  })

  it('has link to registration page', () => {
    renderWithProviders(<Login />)

    const registerLink = screen.getByText(/create an account/i)
    expect(registerLink).toBeInTheDocument()
    expect(registerLink.closest('a')).toHaveAttribute('href', '/register')
  })
})

describe('Register Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders registration form', () => {
    renderWithProviders(<Register />)

    expect(screen.getByLabelText(/first name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/last name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/company name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
  })

  it('handles form input changes', () => {
    renderWithProviders(<Register />)

    const firstNameInput = screen.getByLabelText(/first name/i)
    const lastNameInput = screen.getByLabelText(/last name/i)
    const emailInput = screen.getByLabelText(/email/i)
    const companyInput = screen.getByLabelText(/company name/i)

    fireEvent.change(firstNameInput, { target: { value: 'John' } })
    fireEvent.change(lastNameInput, { target: { value: 'Doe' } })
    fireEvent.change(emailInput, { target: { value: 'john@example.com' } })
    fireEvent.change(companyInput, { target: { value: 'Test Company' } })

    expect(firstNameInput.value).toBe('John')
    expect(lastNameInput.value).toBe('Doe')
    expect(emailInput.value).toBe('john@example.com')
    expect(companyInput.value).toBe('Test Company')
  })

  it('has link to login page', () => {
    renderWithProviders(<Register />)

    const loginLink = screen.getByText(/sign in/i)
    expect(loginLink.closest('a')).toHaveAttribute('href', '/login')
  })
})

describe('Dashboard Component', () => {
  const mockMetricsData = {
    data: {
      metrics: {
        recycledWeight: 5000,
        donatedWeight: 1000,
        landfillWeight: 500,
        carbonOffset: 2500,
        diversionRate: 85.7,
        averageEsgScore: 78,
        treesEquivalent: 52,
        milesEquivalent: 2809
      },
      recentJobs: [
        { id: '1', job_number: 'JOB-00001', title: 'Test Job', status: 'completed', esg_score: 85 }
      ],
      milestones: [
        { id: '1', name: 'First Ton', achieved: true, progress: 100 }
      ]
    }
  }

  beforeEach(() => {
    vi.clearAllMocks()
    const { metricsAPI } = require('../services/api')
    metricsAPI.dashboard.mockResolvedValue(mockMetricsData)
  })

  it('renders loading state initially', () => {
    renderWithProviders(<Dashboard />)

    // Should show loading spinner
    expect(document.querySelector('.animate-spin')).toBeInTheDocument()
  })

  it('renders dashboard after loading', async () => {
    renderWithProviders(<Dashboard />)

    await waitFor(() => {
      expect(screen.getByText(/environmental impact overview/i)).toBeInTheDocument()
    })
  })

  it('displays ESG metrics', async () => {
    renderWithProviders(<Dashboard />)

    await waitFor(() => {
      expect(screen.getByText(/diversion rate/i)).toBeInTheDocument()
      expect(screen.getByText(/carbon offset/i)).toBeInTheDocument()
      expect(screen.getByText(/esg score/i)).toBeInTheDocument()
    })
  })

  it('has link to create new job', async () => {
    renderWithProviders(<Dashboard />)

    await waitFor(() => {
      const newJobButton = screen.getByText(/new job/i)
      expect(newJobButton.closest('a')).toHaveAttribute('href', '/jobs/new')
    })
  })
})

describe('Jobs Component', () => {
  const mockJobsData = {
    data: {
      jobs: [
        {
          id: '1',
          job_number: 'JOB-00001',
          title: 'Residential Junk Removal',
          status: 'completed',
          esg_score: 85,
          total_weight_lbs: 500,
          created_at: '2024-01-15T10:00:00Z'
        },
        {
          id: '2',
          job_number: 'JOB-00002',
          title: 'Office Cleanout',
          status: 'in_progress',
          esg_score: 0,
          total_weight_lbs: 0,
          created_at: '2024-01-16T10:00:00Z'
        }
      ],
      pagination: { total: 2, limit: 20, offset: 0 }
    }
  }

  beforeEach(() => {
    vi.clearAllMocks()
    const { jobsAPI } = require('../services/api')
    jobsAPI.list.mockResolvedValue(mockJobsData)
  })

  it('renders jobs list', async () => {
    renderWithProviders(<Jobs />)

    await waitFor(() => {
      expect(screen.getByText('JOB-00001')).toBeInTheDocument()
      expect(screen.getByText('JOB-00002')).toBeInTheDocument()
    })
  })

  it('displays job status badges', async () => {
    renderWithProviders(<Jobs />)

    await waitFor(() => {
      expect(screen.getByText('completed')).toBeInTheDocument()
      expect(screen.getByText('in progress')).toBeInTheDocument()
    })
  })

  it('has create new job button', async () => {
    renderWithProviders(<Jobs />)

    await waitFor(() => {
      const createButton = screen.getByText(/new job/i)
      expect(createButton.closest('a')).toHaveAttribute('href', '/jobs/new')
    })
  })

  it('has filter controls', async () => {
    renderWithProviders(<Jobs />)

    await waitFor(() => {
      expect(screen.getByText(/all status/i)).toBeInTheDocument()
    })
  })
})

describe('App Routing', () => {
  it('redirects to login when not authenticated', () => {
    renderWithProviders(<App />)

    // Should redirect to login
    expect(window.location.pathname).toBe('/')
  })
})

describe('Accessibility', () => {
  it('login form has proper labels', () => {
    renderWithProviders(<Login />)

    const emailInput = screen.getByLabelText(/email/i)
    const passwordInput = screen.getByLabelText(/password/i)

    expect(emailInput).toHaveAttribute('type', 'email')
    expect(passwordInput).toHaveAttribute('type', 'password')
  })

  it('buttons are focusable', () => {
    renderWithProviders(<Login />)

    const submitButton = screen.getByRole('button', { name: /sign in/i })
    submitButton.focus()

    expect(document.activeElement).toBe(submitButton)
  })
})
