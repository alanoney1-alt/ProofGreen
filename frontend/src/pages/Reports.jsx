import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { reportsAPI } from '../services/api'
import { format } from 'date-fns'
import {
  DocumentTextIcon,
  ShareIcon,
  TrashIcon,
  EyeIcon
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'

export default function Reports() {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [typeFilter, setTypeFilter] = useState('')

  useEffect(() => {
    fetchReports()
  }, [typeFilter])

  const fetchReports = async () => {
    try {
      setLoading(true)
      const response = await reportsAPI.list({ type: typeFilter || undefined })
      setReports(response.data.reports)
    } catch (error) {
      console.error('Failed to fetch reports:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleShare = async (report) => {
    try {
      const response = await reportsAPI.share(report.id, !report.is_public)
      const updatedReport = response.data.report

      setReports(prev =>
        prev.map(r => r.id === report.id ? updatedReport : r)
      )

      if (updatedReport.is_public) {
        const publicUrl = `${window.location.origin}/reports/public/${updatedReport.public_token}`
        await navigator.clipboard.writeText(publicUrl)
        toast.success('Public link copied to clipboard!')
      } else {
        toast.success('Report is now private')
      }
    } catch (error) {
      toast.error('Failed to update sharing')
    }
  }

  const handleDelete = async (reportId) => {
    if (!confirm('Are you sure you want to delete this report?')) return

    try {
      await reportsAPI.delete(reportId)
      setReports(prev => prev.filter(r => r.id !== reportId))
      toast.success('Report deleted')
    } catch (error) {
      toast.error('Failed to delete report')
    }
  }

  const reportTypeLabels = {
    job: 'Job Report',
    weekly: 'Weekly',
    monthly: 'Monthly',
    quarterly: 'Quarterly',
    annual: 'Annual',
    custom: 'Custom'
  }

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">ESG Reports</h1>
          <p className="text-gray-600 mt-1">
            View and share your environmental impact reports
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="input"
          >
            <option value="">All Types</option>
            <option value="job">Job Reports</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
            <option value="quarterly">Quarterly</option>
            <option value="annual">Annual</option>
          </select>
        </div>
      </div>

      {/* Reports Grid */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      ) : reports.length === 0 ? (
        <div className="card p-12 text-center">
          <DocumentTextIcon className="w-16 h-16 mx-auto text-gray-300 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No reports yet</h3>
          <p className="text-gray-500 mb-6">
            Reports are automatically generated when you complete jobs with AI analysis.
          </p>
          <Link to="/jobs" className="btn-primary inline-flex">
            View Jobs
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {reports.map((report) => (
            <div key={report.id} className="card hover:shadow-md transition-shadow">
              <div className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex items-center">
                    <div className="p-2 bg-primary-100 rounded-lg">
                      <DocumentTextIcon className="w-6 h-6 text-primary-600" />
                    </div>
                    <div className="ml-3">
                      <span className="badge badge-blue text-xs">
                        {reportTypeLabels[report.report_type] || report.report_type}
                      </span>
                    </div>
                  </div>
                  {report.is_public && (
                    <span className="badge badge-green">Public</span>
                  )}
                </div>

                <h3 className="mt-4 text-lg font-semibold text-gray-900 line-clamp-2">
                  {report.title}
                </h3>

                {report.summary && (
                  <p className="mt-2 text-sm text-gray-600 line-clamp-2">
                    {report.summary}
                  </p>
                )}

                {report.metrics_snapshot && (
                  <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
                    <div className="p-2 bg-gray-50 rounded">
                      <p className="text-gray-500">ESG Score</p>
                      <p className="font-semibold text-gray-900">
                        {report.metrics_snapshot.esgScore || '-'}
                      </p>
                    </div>
                    <div className="p-2 bg-gray-50 rounded">
                      <p className="text-gray-500">Diversion</p>
                      <p className="font-semibold text-gray-900">
                        {report.metrics_snapshot.diversionRate?.toFixed(1) || '-'}%
                      </p>
                    </div>
                  </div>
                )}

                <p className="mt-4 text-xs text-gray-500">
                  Generated {format(new Date(report.generated_at), 'MMM d, yyyy')}
                  {report.viewed_count > 0 && ` • ${report.viewed_count} views`}
                </p>
              </div>

              <div className="px-6 py-3 bg-gray-50 border-t border-gray-100 flex justify-between">
                <Link
                  to={`/reports/${report.id}`}
                  className="flex items-center text-sm text-primary-600 hover:text-primary-700"
                >
                  <EyeIcon className="w-4 h-4 mr-1" />
                  View
                </Link>
                <button
                  onClick={() => handleShare(report)}
                  className="flex items-center text-sm text-gray-600 hover:text-gray-900"
                >
                  <ShareIcon className="w-4 h-4 mr-1" />
                  {report.is_public ? 'Make Private' : 'Share'}
                </button>
                <button
                  onClick={() => handleDelete(report.id)}
                  className="flex items-center text-sm text-red-600 hover:text-red-700"
                >
                  <TrashIcon className="w-4 h-4 mr-1" />
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
