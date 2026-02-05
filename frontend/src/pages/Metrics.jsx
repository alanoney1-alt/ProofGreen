import { useState, useEffect } from 'react'
import { metricsAPI } from '../services/api'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'
import { Line, Doughnut, Bar } from 'react-chartjs-2'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

export default function Metrics() {
  const [dashboard, setDashboard] = useState(null)
  const [trends, setTrends] = useState([])
  const [categories, setCategories] = useState([])
  const [period, setPeriod] = useState('30d')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
  }, [period])

  const fetchData = async () => {
    try {
      setLoading(true)
      const [dashboardRes, trendsRes, categoriesRes] = await Promise.all([
        metricsAPI.dashboard(),
        metricsAPI.trends({ period }),
        metricsAPI.byCategory()
      ])

      setDashboard(dashboardRes.data.metrics)
      setTrends(trendsRes.data.trends)
      setCategories(categoriesRes.data.categories)
    } catch (error) {
      console.error('Failed to fetch metrics:', error)
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

  // Trends chart data
  const trendsChartData = {
    labels: trends.map(t => t.date),
    datasets: [
      {
        label: 'Carbon Offset (lbs)',
        data: trends.map(t => t.carbonOffset),
        borderColor: 'rgb(34, 197, 94)',
        backgroundColor: 'rgba(34, 197, 94, 0.1)',
        fill: true,
        tension: 0.4
      },
      {
        label: 'Recycled Weight (lbs)',
        data: trends.map(t => t.recycledWeight),
        borderColor: 'rgb(59, 130, 246)',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        fill: true,
        tension: 0.4
      }
    ]
  }

  // Disposition chart data
  const dispositionData = {
    labels: ['Recycled', 'Donated', 'Landfill'],
    datasets: [{
      data: [
        dashboard?.recycledWeight || 0,
        dashboard?.donatedWeight || 0,
        dashboard?.landfillWeight || 0
      ],
      backgroundColor: [
        'rgb(34, 197, 94)',
        'rgb(59, 130, 246)',
        'rgb(156, 163, 175)'
      ],
      borderWidth: 0
    }]
  }

  // Category chart data
  const categoryChartData = {
    labels: categories.slice(0, 8).map(c => c.category),
    datasets: [{
      label: 'Weight (lbs)',
      data: categories.slice(0, 8).map(c => c.totalWeight),
      backgroundColor: 'rgba(34, 197, 94, 0.8)',
      borderRadius: 4
    }]
  }

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Metrics & Analytics</h1>
          <p className="text-gray-600 mt-1">
            Track your environmental impact over time
          </p>
        </div>
        <select
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
          className="input w-40"
        >
          <option value="7d">Last 7 days</option>
          <option value="30d">Last 30 days</option>
          <option value="90d">Last 90 days</option>
          <option value="12m">Last 12 months</option>
        </select>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="stat-card">
          <p className="text-sm text-gray-500">Total Weight</p>
          <p className="text-2xl font-bold text-gray-900">
            {(dashboard?.totalWeight || 0).toLocaleString()} lbs
          </p>
        </div>
        <div className="stat-card">
          <p className="text-sm text-gray-500">Diversion Rate</p>
          <p className="text-2xl font-bold text-green-600">
            {(dashboard?.diversionRate || 0).toFixed(1)}%
          </p>
        </div>
        <div className="stat-card">
          <p className="text-sm text-gray-500">Carbon Offset</p>
          <p className="text-2xl font-bold text-purple-600">
            {(dashboard?.carbonOffset || 0).toLocaleString()} lbs
          </p>
        </div>
        <div className="stat-card">
          <p className="text-sm text-gray-500">Jobs Completed</p>
          <p className="text-2xl font-bold text-blue-600">
            {dashboard?.totalJobs || 0}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Trends Chart */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Trends Over Time</h2>
          {trends.length > 0 ? (
            <Line
              data={trendsChartData}
              options={{
                responsive: true,
                plugins: {
                  legend: {
                    position: 'bottom'
                  }
                },
                scales: {
                  y: {
                    beginAtZero: true
                  }
                }
              }}
            />
          ) : (
            <div className="h-64 flex items-center justify-center text-gray-500">
              No data available for this period
            </div>
          )}
        </div>

        {/* Disposition Chart */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Material Disposition</h2>
          {dashboard?.totalWeight > 0 ? (
            <div className="max-w-xs mx-auto">
              <Doughnut
                data={dispositionData}
                options={{
                  responsive: true,
                  plugins: {
                    legend: {
                      position: 'bottom'
                    }
                  },
                  cutout: '60%'
                }}
              />
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-gray-500">
              No data available
            </div>
          )}
        </div>

        {/* Category Chart */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Weight by Category</h2>
          {categories.length > 0 ? (
            <Bar
              data={categoryChartData}
              options={{
                responsive: true,
                plugins: {
                  legend: {
                    display: false
                  }
                },
                scales: {
                  y: {
                    beginAtZero: true
                  }
                }
              }}
            />
          ) : (
            <div className="h-64 flex items-center justify-center text-gray-500">
              No category data available
            </div>
          )}
        </div>

        {/* Category Breakdown Table */}
        <div className="card">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-lg font-semibold text-gray-900">Category Breakdown</h2>
          </div>
          {categories.length > 0 ? (
            <div className="divide-y divide-gray-100">
              {categories.map((cat) => (
                <div key={cat.category} className="px-6 py-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-gray-900 capitalize">
                      {cat.category}
                    </span>
                    <span className="text-gray-600">
                      {cat.totalWeight.toLocaleString()} lbs
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-500">{cat.itemCount} items</span>
                    <span className="text-green-600">
                      {cat.diversionRate}% diverted
                    </span>
                  </div>
                  <div className="mt-2 h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-green-500 rounded-full"
                      style={{ width: `${cat.diversionRate}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-8 text-center text-gray-500">
              No category data available
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
