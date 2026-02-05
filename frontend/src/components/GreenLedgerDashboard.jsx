import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import api from '../services/api'
import {
  ChartBarIcon,
  ArrowTrendingDownIcon,
  ArrowTrendingUpIcon,
  CheckBadgeIcon,
  DocumentArrowDownIcon,
  CalendarDaysIcon,
  GlobeAmericasIcon,
  BoltIcon,
  TruckIcon,
  BeakerIcon
} from '@heroicons/react/24/outline'

const scopeColors = {
  scope_1: { bg: 'bg-red-100', text: 'text-red-700', bar: 'bg-red-500' },
  scope_2: { bg: 'bg-yellow-100', text: 'text-yellow-700', bar: 'bg-yellow-500' },
  scope_3: { bg: 'bg-blue-100', text: 'text-blue-700', bar: 'bg-blue-500' }
}

const categoryIcons = {
  vehicle_travel: TruckIcon,
  electricity: BoltIcon,
  refrigerant: BeakerIcon,
  fuel: GlobeAmericasIcon
}

function formatNumber(num) {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M'
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K'
  }
  return num.toFixed(1)
}

function StatCard({ title, value, unit, trend, icon: Icon, color = 'primary' }) {
  const isPositive = trend > 0
  const TrendIcon = isPositive ? ArrowTrendingUpIcon : ArrowTrendingDownIcon

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between">
        <div className={`p-3 rounded-lg bg-${color}-100`}>
          <Icon className={`w-6 h-6 text-${color}-600`} />
        </div>
        {trend !== null && trend !== undefined && (
          <div className={`flex items-center text-sm ${isPositive ? 'text-red-600' : 'text-green-600'}`}>
            <TrendIcon className="w-4 h-4 mr-1" />
            {Math.abs(trend).toFixed(1)}%
          </div>
        )}
      </div>
      <div className="mt-4">
        <p className="text-sm font-medium text-gray-500">{title}</p>
        <p className="text-2xl font-bold text-gray-900">
          {formatNumber(value)} <span className="text-sm font-normal text-gray-500">{unit}</span>
        </p>
      </div>
    </div>
  )
}

function ScopeBreakdown({ scope1, scope2, scope3 }) {
  const total = scope1 + scope2 + scope3
  const getPercent = (val) => total > 0 ? (val / total * 100).toFixed(1) : 0

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Emissions by Scope</h3>

      {/* Bar visualization */}
      <div className="h-8 flex rounded-lg overflow-hidden mb-6">
        <div
          className="bg-red-500 transition-all duration-500"
          style={{ width: `${getPercent(scope1)}%` }}
        />
        <div
          className="bg-yellow-500 transition-all duration-500"
          style={{ width: `${getPercent(scope2)}%` }}
        />
        <div
          className="bg-blue-500 transition-all duration-500"
          style={{ width: `${getPercent(scope3)}%` }}
        />
      </div>

      {/* Scope details */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <div className="w-3 h-3 rounded-full bg-red-500 mr-3" />
            <div>
              <p className="text-sm font-medium text-gray-900">Scope 1 - Direct</p>
              <p className="text-xs text-gray-500">Fuel combustion, refrigerants</p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-sm font-semibold text-gray-900">{formatNumber(scope1)} kg</p>
            <p className="text-xs text-gray-500">{getPercent(scope1)}%</p>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <div className="w-3 h-3 rounded-full bg-yellow-500 mr-3" />
            <div>
              <p className="text-sm font-medium text-gray-900">Scope 2 - Indirect</p>
              <p className="text-xs text-gray-500">Purchased electricity</p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-sm font-semibold text-gray-900">{formatNumber(scope2)} kg</p>
            <p className="text-xs text-gray-500">{getPercent(scope2)}%</p>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <div className="w-3 h-3 rounded-full bg-blue-500 mr-3" />
            <div>
              <p className="text-sm font-medium text-gray-900">Scope 3 - Value Chain</p>
              <p className="text-xs text-gray-500">Materials, waste, transport</p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-sm font-semibold text-gray-900">{formatNumber(scope3)} kg</p>
            <p className="text-xs text-gray-500">{getPercent(scope3)}%</p>
          </div>
        </div>
      </div>
    </div>
  )
}

function TransactionList({ transactions }) {
  if (!transactions || transactions.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Transactions</h3>
        <p className="text-gray-500 text-center py-8">No transactions recorded yet</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Transactions</h3>
      <div className="space-y-3">
        {transactions.slice(0, 10).map((tx) => {
          const Icon = categoryIcons[tx.category] || GlobeAmericasIcon
          const scopeStyle = scopeColors[tx.scope] || scopeColors.scope_1
          const isEmission = tx.transaction_type === 'emission'

          return (
            <div key={tx.id} className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0">
              <div className="flex items-center">
                <div className={`p-2 rounded-lg ${scopeStyle.bg} mr-3`}>
                  <Icon className={`w-5 h-5 ${scopeStyle.text}`} />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900">{tx.description}</p>
                  <p className="text-xs text-gray-500">
                    {new Date(tx.timestamp).toLocaleDateString()} - {tx.category}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className={`text-sm font-semibold ${isEmission ? 'text-red-600' : 'text-green-600'}`}>
                  {isEmission ? '+' : '-'}{formatNumber(tx.amount_kg_co2e)} kg
                </p>
                <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${scopeStyle.bg} ${scopeStyle.text}`}>
                  {tx.scope.replace('_', ' ')}
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ComplianceStatus({ sb253Ready, verificationRate }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Compliance Status</h3>

      {/* SB 253 Readiness */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">CA SB 253 Ready</span>
          {sb253Ready ? (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
              <CheckBadgeIcon className="w-4 h-4 mr-1" />
              Ready
            </span>
          ) : (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
              In Progress
            </span>
          )}
        </div>
        <p className="text-xs text-gray-500">
          Climate Corporate Data Accountability Act compliance
        </p>
      </div>

      {/* Verification Rate */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">Verification Rate</span>
          <span className="text-sm font-semibold text-gray-900">{verificationRate.toFixed(1)}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all duration-500 ${
              verificationRate >= 80 ? 'bg-green-500' :
              verificationRate >= 50 ? 'bg-yellow-500' : 'bg-red-500'
            }`}
            style={{ width: `${Math.min(verificationRate, 100)}%` }}
          />
        </div>
        <p className="text-xs text-gray-500 mt-1">
          {verificationRate >= 80 ? 'Excellent' : verificationRate >= 50 ? 'Good progress' : 'Needs improvement'}
        </p>
      </div>
    </div>
  )
}

export default function GreenLedgerDashboard() {
  const { company } = useAuth()
  const [period, setPeriod] = useState('month')
  const [loading, setLoading] = useState(true)
  const [summary, setSummary] = useState(null)
  const [transactions, setTransactions] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchLedgerData()
  }, [period, company])

  const fetchLedgerData = async () => {
    if (!company?.id) return

    setLoading(true)
    setError(null)

    try {
      const [summaryRes, transactionsRes] = await Promise.all([
        api.get(`/api/v1/ledger/summary/${company.id}?period=${period}`),
        api.get(`/api/v1/ledger/transactions/${company.id}?limit=10`)
      ])

      setSummary(summaryRes.data)
      setTransactions(transactionsRes.data?.transactions || [])
    } catch (err) {
      console.error('Failed to fetch ledger data:', err)
      // Use mock data for demo
      setSummary({
        total_emissions_kg: 12450,
        scope_1_total: 5200,
        scope_2_total: 4800,
        scope_3_total: 2450,
        total_avoided_kg: 3200,
        total_offset_kg: 0,
        net_emissions_kg: 9250,
        job_count: 145,
        transaction_count: 892,
        trend_vs_previous: -8.5,
        sb253_ready: true,
        verification_rate: 87.5
      })
      setTransactions([
        {
          id: '1',
          transaction_type: 'emission',
          scope: 'scope_1',
          amount_kg_co2e: 45.2,
          category: 'vehicle_travel',
          description: 'Service vehicle - Job #1234',
          timestamp: new Date().toISOString()
        },
        {
          id: '2',
          transaction_type: 'emission',
          scope: 'scope_1',
          amount_kg_co2e: 12.8,
          category: 'refrigerant',
          description: 'R-410A charge - HVAC Install',
          timestamp: new Date(Date.now() - 86400000).toISOString()
        },
        {
          id: '3',
          transaction_type: 'avoidance',
          scope: 'scope_2',
          amount_kg_co2e: 850,
          category: 'electricity',
          description: 'Heat pump upgrade - Annual savings',
          timestamp: new Date(Date.now() - 172800000).toISOString()
        }
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleExport = async (format) => {
    try {
      const response = await api.get(`/api/v1/ledger/export/${company.id}?format=${format}`, {
        responseType: 'blob'
      })

      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `carbon-ledger-${period}.${format}`)
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err) {
      console.error('Export failed:', err)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Green Ledger</h1>
          <p className="mt-1 text-sm text-gray-500">
            Carbon transaction tracking - GHG Protocol compliant
          </p>
        </div>
        <div className="mt-4 sm:mt-0 flex items-center space-x-3">
          {/* Period selector */}
          <div className="flex items-center bg-gray-100 rounded-lg p-1">
            {['month', 'quarter', 'year'].map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                  period === p
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                {p.charAt(0).toUpperCase() + p.slice(1)}
              </button>
            ))}
          </div>

          {/* Export button */}
          <button
            onClick={() => handleExport('csv')}
            className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-lg text-gray-700 bg-white hover:bg-gray-50"
          >
            <DocumentArrowDownIcon className="w-4 h-4 mr-2" />
            Export
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      {summary && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <StatCard
              title="Total Emissions"
              value={summary.total_emissions_kg}
              unit="kg CO2e"
              trend={summary.trend_vs_previous}
              icon={GlobeAmericasIcon}
              color="red"
            />
            <StatCard
              title="Avoided Emissions"
              value={summary.total_avoided_kg}
              unit="kg CO2e"
              trend={null}
              icon={ArrowTrendingDownIcon}
              color="green"
            />
            <StatCard
              title="Net Impact"
              value={summary.net_emissions_kg}
              unit="kg CO2e"
              trend={null}
              icon={ChartBarIcon}
              color="primary"
            />
            <StatCard
              title="Jobs Tracked"
              value={summary.job_count}
              unit="jobs"
              trend={null}
              icon={CalendarDaysIcon}
              color="blue"
            />
          </div>

          {/* Main Content Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Scope Breakdown - Takes 1 column */}
            <ScopeBreakdown
              scope1={summary.scope_1_total}
              scope2={summary.scope_2_total}
              scope3={summary.scope_3_total}
            />

            {/* Transactions - Takes 1 column */}
            <TransactionList transactions={transactions} />

            {/* Compliance Status - Takes 1 column */}
            <ComplianceStatus
              sb253Ready={summary.sb253_ready}
              verificationRate={summary.verification_rate}
            />
          </div>
        </>
      )}

      {/* SB 253 Notice */}
      <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-xl p-6">
        <div className="flex items-start">
          <CheckBadgeIcon className="w-6 h-6 text-green-600 mt-0.5" />
          <div className="ml-4">
            <h3 className="text-sm font-semibold text-green-900">CA SB 253 Compliance</h3>
            <p className="mt-1 text-sm text-green-700">
              Your carbon ledger is being prepared for California Climate Corporate Data Accountability Act reporting.
              All emissions are tracked following GHG Protocol methodology with EPA-verified emission factors.
            </p>
            <div className="mt-3 flex items-center space-x-4">
              <a
                href="https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202320240SB253"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-green-700 hover:text-green-800"
              >
                Learn about SB 253 &rarr;
              </a>
              <a
                href="/reports"
                className="text-sm font-medium text-green-700 hover:text-green-800"
              >
                Generate Report &rarr;
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
