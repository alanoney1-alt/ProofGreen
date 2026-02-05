import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { reportsAPI } from '../services/api'
import { format } from 'date-fns'
import toast from 'react-hot-toast'
import {
  ArrowLeftIcon,
  ShareIcon,
  PrinterIcon
} from '@heroicons/react/24/outline'

export default function ReportDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchReport()
  }, [id])

  const fetchReport = async () => {
    try {
      const response = await reportsAPI.get(id)
      setReport(response.data.report)
    } catch (error) {
      console.error('Failed to fetch report:', error)
      toast.error('Failed to load report')
      navigate('/reports')
    } finally {
      setLoading(false)
    }
  }

  const handleShare = async () => {
    try {
      const response = await reportsAPI.share(id, true)
      const publicUrl = `${window.location.origin}/reports/public/${response.data.report.public_token}`
      await navigator.clipboard.writeText(publicUrl)
      toast.success('Public link copied to clipboard!')
      setReport(prev => ({ ...prev, is_public: true }))
    } catch (error) {
      toast.error('Failed to share report')
    }
  }

  const handlePrint = () => {
    window.print()
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!report) return null

  const reportData = report.report_data || {}
  const metrics = reportData.metrics || report.metrics_snapshot || {}

  return (
    <div className="animate-fade-in max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8 print:hidden">
        <button
          onClick={() => navigate('/reports')}
          className="flex items-center text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeftIcon className="w-5 h-5 mr-2" />
          Back to Reports
        </button>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{report.title}</h1>
            <p className="text-gray-600 mt-1">
              Generated {format(new Date(report.generated_at), 'MMMM d, yyyy')}
            </p>
          </div>
          <div className="flex gap-3">
            <button onClick={handleShare} className="btn-secondary">
              <ShareIcon className="w-5 h-5 mr-2" />
              Share
            </button>
            <button onClick={handlePrint} className="btn-primary">
              <PrinterIcon className="w-5 h-5 mr-2" />
              Print
            </button>
          </div>
        </div>
      </div>

      {/* Report Content */}
      <div className="card print:shadow-none print:border-none">
        {/* Report Header */}
        <div className="p-8 bg-gradient-to-br from-primary-600 to-accent-600 text-white print:bg-primary-600">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-3xl font-bold">ESG Impact Report</h2>
              <p className="mt-2 opacity-90">{reportData.company?.name}</p>
            </div>
            <div className="text-right">
              <p className="text-5xl font-bold">{metrics.esgScore || 0}</p>
              <p className="opacity-90">ESG Score</p>
            </div>
          </div>
        </div>

        {/* Summary */}
        {report.summary && (
          <div className="p-8 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Executive Summary</h3>
            <p className="text-gray-700 leading-relaxed">{report.summary}</p>
          </div>
        )}

        {/* Key Metrics */}
        <div className="p-8 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-6">Key Metrics</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div className="text-center p-4 bg-green-50 rounded-xl">
              <p className="text-3xl font-bold text-green-700">
                {(metrics.totalWeight || 0).toLocaleString()}
              </p>
              <p className="text-sm text-green-600 mt-1">lbs Total Weight</p>
            </div>
            <div className="text-center p-4 bg-blue-50 rounded-xl">
              <p className="text-3xl font-bold text-blue-700">
                {(metrics.diversionRate || 0).toFixed(1)}%
              </p>
              <p className="text-sm text-blue-600 mt-1">Diversion Rate</p>
            </div>
            <div className="text-center p-4 bg-purple-50 rounded-xl">
              <p className="text-3xl font-bold text-purple-700">
                {(metrics.carbonOffset || 0).toLocaleString()}
              </p>
              <p className="text-sm text-purple-600 mt-1">lbs CO2 Offset</p>
            </div>
            <div className="text-center p-4 bg-yellow-50 rounded-xl">
              <p className="text-3xl font-bold text-yellow-700">
                {(metrics.recycledWeight || 0).toLocaleString()}
              </p>
              <p className="text-sm text-yellow-600 mt-1">lbs Recycled</p>
            </div>
          </div>
        </div>

        {/* Weight Breakdown */}
        <div className="p-8 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-6">Material Disposition</h3>
          <div className="space-y-4">
            {[
              { label: 'Recycled', value: metrics.recycledWeight || 0, color: 'bg-green-500' },
              { label: 'Donated', value: metrics.donatedWeight || 0, color: 'bg-blue-500' },
              { label: 'Landfill', value: metrics.landfillWeight || 0, color: 'bg-gray-400' }
            ].map((item) => {
              const total = metrics.totalWeight || 1
              const percentage = (item.value / total) * 100
              return (
                <div key={item.label}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-700">{item.label}</span>
                    <span className="text-gray-900 font-medium">
                      {item.value.toLocaleString()} lbs ({percentage.toFixed(1)}%)
                    </span>
                  </div>
                  <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${item.color} rounded-full`}
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Environmental Equivalents */}
        {reportData.environmental && (
          <div className="p-8 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900 mb-6">Environmental Impact Equivalents</h3>
            <div className="grid grid-cols-3 gap-6">
              <div className="text-center">
                <span className="text-4xl">🌳</span>
                <p className="text-2xl font-bold text-gray-900 mt-2">
                  {reportData.environmental.treesEquivalent || 0}
                </p>
                <p className="text-sm text-gray-600">Trees Planted</p>
              </div>
              <div className="text-center">
                <span className="text-4xl">🚗</span>
                <p className="text-2xl font-bold text-gray-900 mt-2">
                  {(reportData.environmental.milesEquivalent || 0).toLocaleString()}
                </p>
                <p className="text-sm text-gray-600">Miles Not Driven</p>
              </div>
              <div className="text-center">
                <span className="text-4xl">⛽</span>
                <p className="text-2xl font-bold text-gray-900 mt-2">
                  {reportData.environmental.gallonsGasEquivalent || 0}
                </p>
                <p className="text-sm text-gray-600">Gallons Gas Saved</p>
              </div>
            </div>
          </div>
        )}

        {/* Items Table */}
        {reportData.items?.length > 0 && (
          <div className="p-8">
            <h3 className="text-lg font-semibold text-gray-900 mb-6">Items Processed</h3>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead>
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Item</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Category</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Weight</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Disposition</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {reportData.items.map((item, index) => (
                    <tr key={index}>
                      <td className="px-4 py-3 text-sm text-gray-900">{item.name}</td>
                      <td className="px-4 py-3 text-sm text-gray-500">{item.category}</td>
                      <td className="px-4 py-3 text-sm text-gray-500">{item.weight} lbs</td>
                      <td className="px-4 py-3">
                        <span className={`badge ${
                          item.disposalMethod === 'recycled' ? 'badge-green' :
                          item.disposalMethod === 'donated' ? 'badge-blue' :
                          'badge-gray'
                        }`}>
                          {item.disposalMethod}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="p-6 bg-gray-50 text-center text-sm text-gray-500">
          <p>Generated by ProofGreen • {format(new Date(report.generated_at), 'MMMM d, yyyy h:mm a')}</p>
        </div>
      </div>
    </div>
  )
}
