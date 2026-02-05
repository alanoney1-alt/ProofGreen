import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { metricsAPI } from '../services/api'
import { useAuth } from '../context/AuthContext'
import {
  ScaleIcon,
  ArrowTrendingUpIcon,
  CloudIcon,
  TrophyIcon,
  PlusIcon
} from '@heroicons/react/24/outline'

export default function Dashboard() {
  const { company } = useAuth()
  const [metrics, setMetrics] = useState(null)
  const [recentJobs, setRecentJobs] = useState([])
  const [milestones, setMilestones] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchDashboardData()
  }, [])

  const fetchDashboardData = async () => {
    try {
      const response = await metricsAPI.dashboard()
      setMetrics(response.data.metrics)
      setRecentJobs(response.data.recentJobs)
      setMilestones(response.data.milestones)
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  const stats = [
    {
      name: 'Total Diverted',
      value: `${((metrics?.recycledWeight || 0) + (metrics?.donatedWeight || 0)).toLocaleString()} lbs`,
      subValue: `${((metrics?.recycledWeight || 0) + (metrics?.donatedWeight || 0)) / 2000} tons`,
      icon: ScaleIcon,
      color: 'bg-green-500'
    },
    {
      name: 'Diversion Rate',
      value: `${(metrics?.diversionRate || 0).toFixed(1)}%`,
      subValue: 'Recycled + Donated',
      icon: ArrowTrendingUpIcon,
      color: 'bg-blue-500'
    },
    {
      name: 'Carbon Offset',
      value: `${(metrics?.carbonOffset || 0).toLocaleString()} lbs`,
      subValue: `${metrics?.treesEquivalent || 0} trees equivalent`,
      icon: CloudIcon,
      color: 'bg-purple-500'
    },
    {
      name: 'ESG Score',
      value: metrics?.averageEsgScore || 0,
      subValue: 'Out of 100',
      icon: TrophyIcon,
      color: 'bg-yellow-500'
    }
  ]

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Welcome back, {company?.name}
          </h1>
          <p className="text-gray-600 mt-1">
            Here's your environmental impact overview
          </p>
        </div>
        <Link to="/jobs/new" className="btn-primary">
          <PlusIcon className="w-5 h-5 mr-2" />
          New Job
        </Link>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {stats.map((stat) => (
          <div key={stat.name} className="stat-card">
            <div className="flex items-center">
              <div className={`p-3 rounded-lg ${stat.color}`}>
                <stat.icon className="w-6 h-6 text-white" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">{stat.name}</p>
                <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
                <p className="text-xs text-gray-500">{stat.subValue}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Recent Jobs */}
        <div className="card">
          <div className="px-6 py-4 border-b border-gray-100">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Recent Jobs</h2>
              <Link to="/jobs" className="text-sm text-primary-600 hover:text-primary-700">
                View all
              </Link>
            </div>
          </div>
          <div className="divide-y divide-gray-100">
            {recentJobs.length === 0 ? (
              <div className="p-6 text-center text-gray-500">
                <p>No jobs yet. Create your first job to start tracking.</p>
                <Link to="/jobs/new" className="btn-primary mt-4 inline-flex">
                  <PlusIcon className="w-5 h-5 mr-2" />
                  Create Job
                </Link>
              </div>
            ) : (
              recentJobs.map((job) => (
                <Link
                  key={job.id}
                  to={`/jobs/${job.id}`}
                  className="flex items-center justify-between p-4 hover:bg-gray-50 transition-colors"
                >
                  <div>
                    <p className="font-medium text-gray-900">{job.job_number}</p>
                    <p className="text-sm text-gray-500">{job.title}</p>
                  </div>
                  <div className="text-right">
                    <span className={`badge ${
                      job.status === 'completed' ? 'badge-green' :
                      job.status === 'in_progress' ? 'badge-blue' :
                      'badge-gray'
                    }`}>
                      {job.status.replace('_', ' ')}
                    </span>
                    {job.esg_score > 0 && (
                      <p className="text-sm text-gray-500 mt-1">
                        ESG: {job.esg_score}/100
                      </p>
                    )}
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>

        {/* Milestones */}
        <div className="card">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-lg font-semibold text-gray-900">Milestones</h2>
          </div>
          <div className="p-6 space-y-4">
            {milestones.length === 0 ? (
              <p className="text-center text-gray-500">
                Complete jobs to start earning milestones!
              </p>
            ) : (
              milestones.slice(0, 5).map((milestone) => (
                <div key={milestone.id} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center">
                      <span className={`text-lg ${milestone.achieved ? '' : 'grayscale opacity-50'}`}>
                        {milestone.achieved ? '🏆' : '🔒'}
                      </span>
                      <span className={`ml-2 font-medium ${
                        milestone.achieved ? 'text-gray-900' : 'text-gray-500'
                      }`}>
                        {milestone.name}
                      </span>
                    </div>
                    <span className="text-sm text-gray-500">
                      {milestone.progress?.toFixed(0) || 0}%
                    </span>
                  </div>
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        milestone.achieved ? 'bg-primary-500' : 'bg-gray-400'
                      }`}
                      style={{ width: `${Math.min(milestone.progress || 0, 100)}%` }}
                    />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Environmental Equivalents */}
      {metrics && (metrics.treesEquivalent > 0 || metrics.milesEquivalent > 0) && (
        <div className="mt-8 card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Your Environmental Impact
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="flex items-center p-4 bg-green-50 rounded-lg">
              <span className="text-4xl">🌳</span>
              <div className="ml-4">
                <p className="text-2xl font-bold text-green-700">
                  {metrics.treesEquivalent}
                </p>
                <p className="text-sm text-green-600">Trees planted equivalent</p>
              </div>
            </div>
            <div className="flex items-center p-4 bg-blue-50 rounded-lg">
              <span className="text-4xl">🚗</span>
              <div className="ml-4">
                <p className="text-2xl font-bold text-blue-700">
                  {metrics.milesEquivalent?.toLocaleString()}
                </p>
                <p className="text-sm text-blue-600">Miles not driven</p>
              </div>
            </div>
            <div className="flex items-center p-4 bg-purple-50 rounded-lg">
              <span className="text-4xl">♻️</span>
              <div className="ml-4">
                <p className="text-2xl font-bold text-purple-700">
                  {metrics.tonsFromLandfill?.toFixed(2)}
                </p>
                <p className="text-sm text-purple-600">Tons from landfill</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
