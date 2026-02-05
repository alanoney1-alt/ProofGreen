import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { reportsAPI } from '../services/api'
import { format } from 'date-fns'

export default function PublicReport() {
  const { token } = useParams()
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchReport()
  }, [token])

  const fetchReport = async () => {
    try {
      const response = await reportsAPI.getPublic(token)
      setReport(response.data.report)
    } catch (error) {
      setError('Report not found or is no longer public')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Report Not Found</h1>
          <p className="text-gray-600">{error}</p>
        </div>
      </div>
    )
  }

  if (!report) return null

  const reportData = report.report_data || {}
  const metrics = reportData.metrics || report.metrics_snapshot || {}

  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <div className="max-w-4xl mx-auto px-4">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center space-x-2 mb-4">
            <div className="w-10 h-10 bg-primary-600 rounded-lg flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <span className="text-xl font-bold text-gray-900">ProofGreen</span>
          </div>
          <p className="text-gray-600">Environmental Impact Report</p>
        </div>

        {/* Report Card */}
        <div className="bg-white rounded-2xl shadow-lg overflow-hidden">
          {/* Report Header */}
          <div className="p-8 bg-gradient-to-br from-primary-600 to-accent-600 text-white">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold">ESG Impact Report</h1>
                <p className="mt-2 opacity-90">
                  {reportData.company?.name || report.companies?.name}
                </p>
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
              <h2 className="text-lg font-semibold text-gray-900 mb-3">Summary</h2>
              <p className="text-gray-700 leading-relaxed">{report.summary}</p>
            </div>
          )}

          {/* Key Metrics */}
          <div className="p-8 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900 mb-6">Key Metrics</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              <div className="text-center p-4 bg-green-50 rounded-xl">
                <p className="text-3xl font-bold text-green-700">
                  {(metrics.totalWeight || 0).toLocaleString()}
                </p>
                <p className="text-sm text-green-600 mt-1">lbs Processed</p>
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

          {/* Material Breakdown */}
          <div className="p-8 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900 mb-6">Material Disposition</h2>
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
              <h2 className="text-lg font-semibold text-gray-900 mb-6">Environmental Impact</h2>
              <div className="grid grid-cols-3 gap-6 text-center">
                <div>
                  <span className="text-4xl">🌳</span>
                  <p className="text-2xl font-bold text-gray-900 mt-2">
                    {reportData.environmental.treesEquivalent || 0}
                  </p>
                  <p className="text-sm text-gray-600">Trees Planted</p>
                </div>
                <div>
                  <span className="text-4xl">🚗</span>
                  <p className="text-2xl font-bold text-gray-900 mt-2">
                    {(reportData.environmental.milesEquivalent || 0).toLocaleString()}
                  </p>
                  <p className="text-sm text-gray-600">Miles Not Driven</p>
                </div>
                <div>
                  <span className="text-4xl">⛽</span>
                  <p className="text-2xl font-bold text-gray-900 mt-2">
                    {reportData.environmental.gallonsGasEquivalent || 0}
                  </p>
                  <p className="text-sm text-gray-600">Gallons Gas Saved</p>
                </div>
              </div>
            </div>
          )}

          {/* Footer */}
          <div className="p-6 bg-gray-50 text-center">
            <p className="text-sm text-gray-500">
              Generated by ProofGreen • {format(new Date(report.generated_at), 'MMMM d, yyyy')}
            </p>
            <p className="text-xs text-gray-400 mt-1">
              This report verifies the environmental impact of services provided.
            </p>
          </div>
        </div>

        {/* Powered By */}
        <div className="text-center mt-8">
          <p className="text-sm text-gray-500">
            Track your environmental impact with{' '}
            <a href="/" className="text-primary-600 hover:text-primary-700 font-medium">
              ProofGreen
            </a>
          </p>
        </div>
      </div>
    </div>
  )
}
