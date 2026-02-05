import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { jobsAPI, authAPI } from '../services/api'
import toast from 'react-hot-toast'
import { ArrowLeftIcon } from '@heroicons/react/24/outline'

export default function NewJob() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [verticals, setVerticals] = useState([])
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    verticalId: '',
    customerName: '',
    customerEmail: '',
    customerPhone: '',
    addressLine1: '',
    city: '',
    state: '',
    zipCode: '',
    scheduledDate: '',
    notes: ''
  })

  useEffect(() => {
    fetchVerticals()
  }, [])

  const fetchVerticals = async () => {
    try {
      const response = await authAPI.getVerticals()
      setVerticals(response.data.verticals)
    } catch (error) {
      console.error('Failed to fetch verticals:', error)
    }
  }

  const handleChange = (e) => {
    setFormData(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!formData.title) {
      toast.error('Please enter a job title')
      return
    }

    setLoading(true)

    try {
      const response = await jobsAPI.create(formData)
      toast.success('Job created successfully!')
      navigate(`/jobs/${response.data.job.id}`)
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to create job')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="animate-fade-in max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => navigate('/jobs')}
          className="flex items-center text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeftIcon className="w-5 h-5 mr-2" />
          Back to Jobs
        </button>
        <h1 className="text-2xl font-bold text-gray-900">Create New Job</h1>
        <p className="text-gray-600 mt-1">
          Fill in the details to create a new service job
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Job Details */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Job Details</h2>
          <div className="space-y-4">
            <div>
              <label htmlFor="title" className="label">Job Title *</label>
              <input
                id="title"
                name="title"
                type="text"
                required
                value={formData.title}
                onChange={handleChange}
                className="input"
                placeholder="e.g., Residential Junk Removal"
              />
            </div>

            <div>
              <label htmlFor="verticalId" className="label">Service Type</label>
              <select
                id="verticalId"
                name="verticalId"
                value={formData.verticalId}
                onChange={handleChange}
                className="input"
              >
                <option value="">Select a service type</option>
                {verticals.map((vertical) => (
                  <option key={vertical.id} value={vertical.id}>
                    {vertical.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="description" className="label">Description</label>
              <textarea
                id="description"
                name="description"
                rows={3}
                value={formData.description}
                onChange={handleChange}
                className="input"
                placeholder="Job details and notes..."
              />
            </div>

            <div>
              <label htmlFor="scheduledDate" className="label">Scheduled Date</label>
              <input
                id="scheduledDate"
                name="scheduledDate"
                type="date"
                value={formData.scheduledDate}
                onChange={handleChange}
                className="input"
              />
            </div>
          </div>
        </div>

        {/* Customer Info */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Customer Information</h2>
          <div className="space-y-4">
            <div>
              <label htmlFor="customerName" className="label">Customer Name</label>
              <input
                id="customerName"
                name="customerName"
                type="text"
                value={formData.customerName}
                onChange={handleChange}
                className="input"
                placeholder="John Smith"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor="customerEmail" className="label">Email</label>
                <input
                  id="customerEmail"
                  name="customerEmail"
                  type="email"
                  value={formData.customerEmail}
                  onChange={handleChange}
                  className="input"
                  placeholder="customer@email.com"
                />
              </div>
              <div>
                <label htmlFor="customerPhone" className="label">Phone</label>
                <input
                  id="customerPhone"
                  name="customerPhone"
                  type="tel"
                  value={formData.customerPhone}
                  onChange={handleChange}
                  className="input"
                  placeholder="(555) 123-4567"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Location */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Service Location</h2>
          <div className="space-y-4">
            <div>
              <label htmlFor="addressLine1" className="label">Street Address</label>
              <input
                id="addressLine1"
                name="addressLine1"
                type="text"
                value={formData.addressLine1}
                onChange={handleChange}
                className="input"
                placeholder="123 Main Street"
              />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="col-span-2">
                <label htmlFor="city" className="label">City</label>
                <input
                  id="city"
                  name="city"
                  type="text"
                  value={formData.city}
                  onChange={handleChange}
                  className="input"
                />
              </div>
              <div>
                <label htmlFor="state" className="label">State</label>
                <input
                  id="state"
                  name="state"
                  type="text"
                  value={formData.state}
                  onChange={handleChange}
                  className="input"
                  placeholder="CA"
                />
              </div>
              <div>
                <label htmlFor="zipCode" className="label">ZIP</label>
                <input
                  id="zipCode"
                  name="zipCode"
                  type="text"
                  value={formData.zipCode}
                  onChange={handleChange}
                  className="input"
                  placeholder="94102"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Notes */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Additional Notes</h2>
          <textarea
            name="notes"
            rows={3}
            value={formData.notes}
            onChange={handleChange}
            className="input"
            placeholder="Any additional information about this job..."
          />
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-4">
          <button
            type="button"
            onClick={() => navigate('/jobs')}
            className="btn-secondary"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            className="btn-primary"
          >
            {loading ? (
              <span className="flex items-center">
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Creating...
              </span>
            ) : 'Create Job'}
          </button>
        </div>
      </form>
    </div>
  )
}
