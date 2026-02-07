import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { authAPI } from '../../services/api'
import toast from 'react-hot-toast'

export default function Register() {
  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    email: '',
    password: '',
    companyName: '',
    phone: '',
    verticals: []
  })
  const [verticals, setVerticals] = useState([])
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState(1)
  const { register } = useAuth()

  useEffect(() => {
    fetchVerticals()
  }, [])

  const fetchVerticals = async () => {
    try {
      const response = await authAPI.getVerticals()
      setVerticals(response.data?.verticals || [])
    } catch (error) {
      console.error('Failed to fetch verticals:', error)
      setVerticals([])
    }
  }

  const handleChange = (e) => {
    setFormData(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }))
  }

  const toggleVertical = (verticalId) => {
    setFormData(prev => ({
      ...prev,
      verticals: prev.verticals.includes(verticalId)
        ? prev.verticals.filter(id => id !== verticalId)
        : [...prev.verticals, verticalId]
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (step === 1) {
      if (!formData.firstName || !formData.lastName || !formData.email || !formData.password) {
        toast.error('Please fill in all required fields')
        return
      }
      if (formData.password.length < 8) {
        toast.error('Password must be at least 8 characters')
        return
      }
      setStep(2)
      return
    }

    if (step === 2) {
      if (!formData.companyName) {
        toast.error('Please enter your company name')
        return
      }
      setStep(3)
      return
    }

    setLoading(true)

    try {
      await register(formData)
      toast.success('Welcome to ProofGreen!')
    } catch (error) {
      toast.error(error.response?.data?.error || 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-900 text-center">
        Create your account
      </h2>

      {/* Progress steps */}
      <div className="mt-6 flex items-center justify-center space-x-2">
        {[1, 2, 3].map((s) => (
          <div
            key={s}
            className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
              s < step
                ? 'bg-primary-600 text-white'
                : s === step
                ? 'bg-primary-100 text-primary-700 border-2 border-primary-600'
                : 'bg-gray-100 text-gray-400'
            }`}
          >
            {s < step ? '✓' : s}
          </div>
        ))}
      </div>

      <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
        {step === 1 && (
          <>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="firstName" className="label">First name</label>
                <input
                  id="firstName"
                  name="firstName"
                  type="text"
                  required
                  value={formData.firstName}
                  onChange={handleChange}
                  className="input"
                />
              </div>
              <div>
                <label htmlFor="lastName" className="label">Last name</label>
                <input
                  id="lastName"
                  name="lastName"
                  type="text"
                  required
                  value={formData.lastName}
                  onChange={handleChange}
                  className="input"
                />
              </div>
            </div>

            <div>
              <label htmlFor="email" className="label">Email address</label>
              <input
                id="email"
                name="email"
                type="email"
                required
                value={formData.email}
                onChange={handleChange}
                className="input"
                placeholder="you@company.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="label">Password</label>
              <input
                id="password"
                name="password"
                type="password"
                required
                value={formData.password}
                onChange={handleChange}
                className="input"
                placeholder="Min. 8 characters"
              />
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <div>
              <label htmlFor="companyName" className="label">Company name</label>
              <input
                id="companyName"
                name="companyName"
                type="text"
                required
                value={formData.companyName}
                onChange={handleChange}
                className="input"
                placeholder="Your Business Name"
              />
            </div>

            <div>
              <label htmlFor="phone" className="label">Phone (optional)</label>
              <input
                id="phone"
                name="phone"
                type="tel"
                value={formData.phone}
                onChange={handleChange}
                className="input"
                placeholder="(555) 123-4567"
              />
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <div>
              <label className="label">Select your service types</label>
              <p className="text-sm text-gray-500 mb-3">
                Choose all that apply. You can change this later.
              </p>
              <div className="grid grid-cols-2 gap-2 max-h-64 overflow-y-auto">
                {(verticals || []).map((vertical) => (
                  <button
                    key={vertical.id}
                    type="button"
                    onClick={() => toggleVertical(vertical.id)}
                    className={`p-3 text-left rounded-lg border-2 transition-colors ${
                      formData.verticals.includes(vertical.id)
                        ? 'border-primary-600 bg-primary-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <span className="text-sm font-medium text-gray-900">
                      {vertical.name}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </>
        )}

        <div className="flex space-x-3">
          {step > 1 && (
            <button
              type="button"
              onClick={() => setStep(step - 1)}
              className="btn-secondary flex-1"
            >
              Back
            </button>
          )}
          <button
            type="submit"
            disabled={loading}
            className="btn-primary flex-1"
          >
            {loading ? (
              <span className="flex items-center justify-center">
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Creating account...
              </span>
            ) : step === 3 ? 'Create account' : 'Continue'}
          </button>
        </div>

        <p className="text-center text-sm text-gray-600">
          Already have an account?{' '}
          <Link to="/login" className="text-primary-600 hover:text-primary-500 font-medium">
            Sign in
          </Link>
        </p>
      </form>
    </div>
  )
}
