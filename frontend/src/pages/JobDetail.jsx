import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { jobsAPI, agentAPI, reportsAPI } from '../services/api'
import { format } from 'date-fns'
import toast from 'react-hot-toast'
import {
  ArrowLeftIcon,
  PhotoIcon,
  SparklesIcon,
  DocumentTextIcon,
  TrashIcon
} from '@heroicons/react/24/outline'

export default function JobDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [job, setJob] = useState(null)
  const [loading, setLoading] = useState(true)
  const [processing, setProcessing] = useState(false)
  const [uploadingPhotos, setUploadingPhotos] = useState(false)

  useEffect(() => {
    fetchJob()
  }, [id])

  const fetchJob = async () => {
    try {
      const response = await jobsAPI.get(id)
      setJob(response.data.job)
    } catch (error) {
      console.error('Failed to fetch job:', error)
      toast.error('Failed to load job')
      navigate('/jobs')
    } finally {
      setLoading(false)
    }
  }

  const onDrop = useCallback(async (acceptedFiles) => {
    if (acceptedFiles.length === 0) return

    setUploadingPhotos(true)
    const formData = new FormData()
    acceptedFiles.forEach(file => {
      formData.append('photos', file)
    })
    formData.append('photoType', 'before')

    try {
      await jobsAPI.uploadPhotos(id, formData)
      toast.success('Photos uploaded! AI processing started.')
      // Poll for processing status
      pollProcessingStatus()
    } catch (error) {
      toast.error('Failed to upload photos')
    } finally {
      setUploadingPhotos(false)
    }
  }, [id])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': ['.png', '.jpg', '.jpeg', '.webp'] },
    maxSize: 10 * 1024 * 1024
  })

  const pollProcessingStatus = async () => {
    setProcessing(true)
    let attempts = 0
    const maxAttempts = 30

    const poll = async () => {
      try {
        const response = await agentAPI.getStatus(id)
        if (response.data.processed || attempts >= maxAttempts) {
          setProcessing(false)
          fetchJob()
          if (response.data.processed) {
            toast.success('AI analysis complete!')
          }
          return
        }
        attempts++
        setTimeout(poll, 2000)
      } catch (error) {
        setProcessing(false)
      }
    }

    poll()
  }

  const handleProcessPhoto = async () => {
    if (!job.before_photos?.length) {
      toast.error('Please upload photos first')
      return
    }

    setProcessing(true)
    try {
      const formData = new FormData()
      formData.append('jobId', id)
      formData.append('photoBase64', job.before_photos[0].data)

      await agentAPI.process(formData)
      toast.success('AI processing started')
      pollProcessingStatus()
    } catch (error) {
      toast.error('Failed to start processing')
      setProcessing(false)
    }
  }

  const handleGenerateReport = async () => {
    try {
      const response = await reportsAPI.generateJob(id)
      toast.success('Report generated!')
      navigate(`/reports/${response.data.report.id}`)
    } catch (error) {
      toast.error('Failed to generate report')
    }
  }

  const handleStatusChange = async (newStatus) => {
    try {
      await jobsAPI.update(id, { status: newStatus })
      setJob(prev => ({ ...prev, status: newStatus }))
      toast.success('Status updated')
    } catch (error) {
      toast.error('Failed to update status')
    }
  }

  const handleDeleteItem = async (itemId) => {
    try {
      await jobsAPI.deleteItem(id, itemId)
      setJob(prev => ({
        ...prev,
        job_items: prev.job_items.filter(item => item.id !== itemId)
      }))
      toast.success('Item removed')
    } catch (error) {
      toast.error('Failed to remove item')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!job) return null

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => navigate('/jobs')}
          className="flex items-center text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeftIcon className="w-5 h-5 mr-2" />
          Back to Jobs
        </button>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{job.job_number}</h1>
            <p className="text-gray-600 mt-1">{job.title}</p>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={job.status}
              onChange={(e) => handleStatusChange(e.target.value)}
              className="input"
            >
              <option value="pending">Pending</option>
              <option value="in_progress">In Progress</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <button onClick={handleGenerateReport} className="btn-secondary">
              <DocumentTextIcon className="w-5 h-5 mr-2" />
              Generate Report
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* ESG Metrics */}
          {job.ai_processed && (
            <div className="card p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">ESG Metrics</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-4 bg-green-50 rounded-lg">
                  <p className="text-2xl font-bold text-green-700">
                    {job.esg_score || 0}
                  </p>
                  <p className="text-sm text-green-600">ESG Score</p>
                </div>
                <div className="text-center p-4 bg-blue-50 rounded-lg">
                  <p className="text-2xl font-bold text-blue-700">
                    {(job.diversion_rate || 0).toFixed(1)}%
                  </p>
                  <p className="text-sm text-blue-600">Diversion Rate</p>
                </div>
                <div className="text-center p-4 bg-purple-50 rounded-lg">
                  <p className="text-2xl font-bold text-purple-700">
                    {(job.carbon_offset_lbs || 0).toFixed(0)}
                  </p>
                  <p className="text-sm text-purple-600">lbs CO2 Offset</p>
                </div>
                <div className="text-center p-4 bg-yellow-50 rounded-lg">
                  <p className="text-2xl font-bold text-yellow-700">
                    {(job.total_weight_lbs || 0).toFixed(0)}
                  </p>
                  <p className="text-sm text-yellow-600">lbs Total</p>
                </div>
              </div>
            </div>
          )}

          {/* Photo Upload */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Photos</h2>
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                isDragActive ? 'border-primary-500 bg-primary-50' : 'border-gray-300 hover:border-gray-400'
              }`}
            >
              <input {...getInputProps()} />
              <PhotoIcon className="w-12 h-12 mx-auto text-gray-400 mb-4" />
              {uploadingPhotos ? (
                <p className="text-gray-600">Uploading...</p>
              ) : isDragActive ? (
                <p className="text-primary-600">Drop photos here</p>
              ) : (
                <>
                  <p className="text-gray-600">Drag and drop photos here, or click to select</p>
                  <p className="text-sm text-gray-500 mt-1">PNG, JPG up to 10MB</p>
                </>
              )}
            </div>

            {job.before_photos?.length > 0 && (
              <div className="mt-4 grid grid-cols-3 gap-4">
                {job.before_photos.map((photo, index) => (
                  <div key={index} className="relative">
                    <img
                      src={`data:${photo.mimeType};base64,${photo.data}`}
                      alt={`Job photo ${index + 1}`}
                      className="w-full h-24 object-cover rounded-lg"
                    />
                  </div>
                ))}
              </div>
            )}

            {job.before_photos?.length > 0 && !job.ai_processed && (
              <button
                onClick={handleProcessPhoto}
                disabled={processing}
                className="btn-primary w-full mt-4"
              >
                <SparklesIcon className="w-5 h-5 mr-2" />
                {processing ? 'Processing...' : 'Analyze with AI'}
              </button>
            )}

            {processing && (
              <div className="mt-4 p-4 bg-blue-50 rounded-lg">
                <div className="flex items-center">
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600 mr-3"></div>
                  <p className="text-blue-700">AI is analyzing your photo...</p>
                </div>
              </div>
            )}
          </div>

          {/* Items */}
          {job.job_items?.length > 0 && (
            <div className="card">
              <div className="px-6 py-4 border-b border-gray-100">
                <h2 className="text-lg font-semibold text-gray-900">
                  Detected Items ({job.job_items.length})
                </h2>
              </div>
              <div className="divide-y divide-gray-100">
                {job.job_items.map((item) => (
                  <div key={item.id} className="p-4 flex items-center justify-between">
                    <div>
                      <p className="font-medium text-gray-900">{item.name}</p>
                      <p className="text-sm text-gray-500">
                        {item.category} | {item.weight_lbs} lbs | {item.disposal_method}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {item.detected_by_ai && (
                        <span className="badge badge-blue">AI Detected</span>
                      )}
                      <button
                        onClick={() => handleDeleteItem(item.id)}
                        className="p-2 text-gray-400 hover:text-red-500"
                      >
                        <TrashIcon className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Job Info */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Details</h2>
            <dl className="space-y-3">
              <div>
                <dt className="text-sm text-gray-500">Service Type</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {job.verticals?.name || 'Not specified'}
                </dd>
              </div>
              {job.scheduled_date && (
                <div>
                  <dt className="text-sm text-gray-500">Scheduled Date</dt>
                  <dd className="text-sm font-medium text-gray-900">
                    {format(new Date(job.scheduled_date), 'MMM d, yyyy')}
                  </dd>
                </div>
              )}
              <div>
                <dt className="text-sm text-gray-500">Created</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {format(new Date(job.created_at), 'MMM d, yyyy h:mm a')}
                </dd>
              </div>
              {job.ai_processed_at && (
                <div>
                  <dt className="text-sm text-gray-500">AI Processed</dt>
                  <dd className="text-sm font-medium text-gray-900">
                    {format(new Date(job.ai_processed_at), 'MMM d, yyyy h:mm a')}
                  </dd>
                </div>
              )}
            </dl>
          </div>

          {/* Customer Info */}
          {job.customer_name && (
            <div className="card p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Customer</h2>
              <dl className="space-y-3">
                <div>
                  <dt className="text-sm text-gray-500">Name</dt>
                  <dd className="text-sm font-medium text-gray-900">{job.customer_name}</dd>
                </div>
                {job.customer_email && (
                  <div>
                    <dt className="text-sm text-gray-500">Email</dt>
                    <dd className="text-sm font-medium text-gray-900">{job.customer_email}</dd>
                  </div>
                )}
                {job.customer_phone && (
                  <div>
                    <dt className="text-sm text-gray-500">Phone</dt>
                    <dd className="text-sm font-medium text-gray-900">{job.customer_phone}</dd>
                  </div>
                )}
              </dl>
            </div>
          )}

          {/* Location */}
          {job.address_line1 && (
            <div className="card p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Location</h2>
              <p className="text-sm text-gray-900">
                {job.address_line1}<br />
                {job.city}, {job.state} {job.zip_code}
              </p>
            </div>
          )}

          {/* Reports */}
          {job.esg_reports?.length > 0 && (
            <div className="card p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Reports</h2>
              <div className="space-y-2">
                {job.esg_reports.map((report) => (
                  <Link
                    key={report.id}
                    to={`/reports/${report.id}`}
                    className="block p-3 bg-gray-50 rounded-lg hover:bg-gray-100"
                  >
                    <p className="text-sm font-medium text-gray-900">{report.title}</p>
                    <p className="text-xs text-gray-500">
                      {format(new Date(report.generated_at), 'MMM d, yyyy')}
                    </p>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
