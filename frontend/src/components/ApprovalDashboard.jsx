import React, { useState, useEffect } from 'react'
import { useAuth } from '../hooks/useAuth'
import {
  ShieldCheckIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  DocumentTextIcon,
  CurrencyDollarIcon,
  UserIcon,
  CalendarIcon,
  ChevronRightIcon,
  FunnelIcon,
  MagnifyingGlassIcon
} from '@heroicons/react/24/outline'

const riskColors = {
  high: { bg: 'bg-red-100', text: 'text-red-700', border: 'border-red-200' },
  medium: { bg: 'bg-yellow-100', text: 'text-yellow-700', border: 'border-yellow-200' },
  low: { bg: 'bg-green-100', text: 'text-green-700', border: 'border-green-200' }
}

const statusColors = {
  pending: { bg: 'bg-gray-100', text: 'text-gray-700' },
  approved: { bg: 'bg-green-100', text: 'text-green-700' },
  rejected: { bg: 'bg-red-100', text: 'text-red-700' },
  expired: { bg: 'bg-orange-100', text: 'text-orange-700' }
}

const taskTypeIcons = {
  tax_credit: CurrencyDollarIcon,
  esg_report: DocumentTextIcon,
  compliance_filing: ShieldCheckIcon,
  rebate_application: CurrencyDollarIcon
}

function TaskCard({ task, onApprove, onReject, onViewDetails }) {
  const riskStyle = riskColors[task.risk.toLowerCase()] || riskColors.medium
  const statusStyle = statusColors[task.status.toLowerCase()] || statusColors.pending
  const TaskIcon = taskTypeIcons[task.type] || DocumentTextIcon

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
      <div className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-50 rounded-lg">
              <TaskIcon className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className={`text-xs font-semibold uppercase px-2 py-0.5 rounded ${riskStyle.bg} ${riskStyle.text}`}>
                  {task.risk} Risk
                </span>
                <span className={`text-xs font-medium px-2 py-0.5 rounded ${statusStyle.bg} ${statusStyle.text}`}>
                  {task.status}
                </span>
              </div>
              <h3 className="text-sm font-semibold text-gray-900 mt-1">{task.title}</h3>
            </div>
          </div>
          <span className="text-xs text-gray-500">{task.id}</span>
        </div>

        {/* Details */}
        <p className="text-sm text-gray-600 mb-4">{task.detail}</p>

        {/* Metadata */}
        <div className="flex flex-wrap gap-4 text-xs text-gray-500 mb-4">
          <div className="flex items-center gap-1">
            <CurrencyDollarIcon className="w-4 h-4" />
            <span>${task.amount?.toLocaleString() || '0'}</span>
          </div>
          <div className="flex items-center gap-1">
            <CalendarIcon className="w-4 h-4" />
            <span>{task.created_at}</span>
          </div>
          {task.job_id && (
            <div className="flex items-center gap-1">
              <DocumentTextIcon className="w-4 h-4" />
              <span>Job #{task.job_id}</span>
            </div>
          )}
        </div>

        {/* AI Reasoning */}
        {task.ai_reasoning && (
          <div className="bg-gray-50 rounded-lg p-3 mb-4">
            <p className="text-xs font-medium text-gray-700 mb-1">AI Reasoning:</p>
            <p className="text-xs text-gray-600">{task.ai_reasoning}</p>
          </div>
        )}

        {/* Actions */}
        {task.status.toLowerCase() === 'pending' && (
          <div className="flex items-center justify-between pt-4 border-t border-gray-100">
            <button
              onClick={() => onViewDetails(task)}
              className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1"
            >
              View Details
              <ChevronRightIcon className="w-4 h-4" />
            </button>
            <div className="flex gap-2">
              <button
                onClick={() => onReject(task.id)}
                className="px-4 py-2 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded-lg transition-colors flex items-center gap-1"
              >
                <XCircleIcon className="w-4 h-4" />
                Reject
              </button>
              <button
                onClick={() => onApprove(task.id)}
                className="px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors flex items-center gap-1"
              >
                <CheckCircleIcon className="w-4 h-4" />
                Approve
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function StatsCard({ title, value, icon: Icon, color }) {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    yellow: 'bg-yellow-50 text-yellow-600',
    red: 'bg-red-50 text-red-600'
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center gap-4">
        <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
          <Icon className="w-6 h-6" />
        </div>
        <div>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          <p className="text-sm text-gray-500">{title}</p>
        </div>
      </div>
    </div>
  )
}

function AuditLogEntry({ entry }) {
  return (
    <div className="flex items-start gap-3 py-3 border-b border-gray-100 last:border-0">
      <div className={`p-1.5 rounded-full ${entry.action === 'approved' ? 'bg-green-100' : 'bg-red-100'}`}>
        {entry.action === 'approved' ? (
          <CheckCircleIcon className="w-4 h-4 text-green-600" />
        ) : (
          <XCircleIcon className="w-4 h-4 text-red-600" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-gray-900">{entry.task_title}</p>
          <span className="text-xs text-gray-500">{entry.timestamp}</span>
        </div>
        <p className="text-xs text-gray-500 mt-0.5">
          {entry.action} by {entry.approver} • ${entry.amount?.toLocaleString()}
        </p>
        {entry.evidence_hash && (
          <p className="text-xs text-gray-400 font-mono mt-1 truncate">
            Hash: {entry.evidence_hash}
          </p>
        )}
      </div>
    </div>
  )
}

export default function ApprovalDashboard() {
  const { user } = useAuth()
  const [tasks, setTasks] = useState([])
  const [auditLog, setAuditLog] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedTask, setSelectedTask] = useState(null)

  useEffect(() => {
    // Fetch pending tasks from API
    const fetchTasks = async () => {
      try {
        // Mock data - replace with actual API call
        setTasks([
          {
            id: 'TSK-001',
            type: 'tax_credit',
            title: 'IRA Tax Credit Filing',
            detail: 'Apply for $2,000 Section 25C Credit for HVAC upgrade at 123 Main St. Customer qualifies based on equipment efficiency (SEER2 16+) and income verification.',
            risk: 'High',
            status: 'Pending',
            amount: 2000,
            job_id: '45678',
            created_at: '2026-02-05',
            ai_reasoning: 'Equipment meets 25C requirements: SEER2 17, installed by certified technician, customer income verified under 150% AMI threshold.',
            agent_id: 'auditor-001',
            evidence_hash: 'sha256:a1b2c3d4e5f6...'
          },
          {
            id: 'TSK-002',
            type: 'esg_report',
            title: 'Q1 Scope 3 Certificate',
            detail: 'Generate verified ESG certificate for ABC Property Management covering 45 commercial installations.',
            risk: 'Medium',
            status: 'Pending',
            amount: 0,
            job_id: null,
            created_at: '2026-02-04',
            ai_reasoning: 'All 45 jobs verified. Total CO2 avoided: 12.5 tons. Compliance rate: 98%. Ready for SB 253 submission.',
            agent_id: 'auditor-001',
            evidence_hash: 'sha256:f6e5d4c3b2a1...'
          },
          {
            id: 'TSK-003',
            type: 'rebate_application',
            title: 'HEEHRA Rebate Submission',
            detail: 'Submit $8,000 HEEHRA rebate application for heat pump installation. Customer verified under 80% AMI.',
            risk: 'High',
            status: 'Pending',
            amount: 8000,
            job_id: '45901',
            created_at: '2026-02-03',
            ai_reasoning: 'Customer income verified at 72% AMI. Heat pump meets efficiency requirements. All documentation complete.',
            agent_id: 'rebate-specialist-001',
            evidence_hash: 'sha256:1a2b3c4d5e6f...'
          },
          {
            id: 'TSK-004',
            type: 'compliance_filing',
            title: 'EPA Section 608 Certification',
            detail: 'File refrigerant recovery documentation for R-410A to R-454B transition.',
            risk: 'Low',
            status: 'Pending',
            amount: 0,
            job_id: '45234',
            created_at: '2026-02-02',
            ai_reasoning: 'Proper recovery procedures documented. Technician Section 608 certification verified. Waste manifest attached.',
            agent_id: 'auditor-001',
            evidence_hash: 'sha256:9z8y7x6w5v4u...'
          }
        ])

        setAuditLog([
          {
            id: 'LOG-001',
            task_id: 'TSK-098',
            task_title: 'IRA Tax Credit Filing',
            action: 'approved',
            approver: 'John Smith',
            timestamp: '2026-02-01 14:32',
            amount: 1500,
            evidence_hash: 'sha256:abc123def456...'
          },
          {
            id: 'LOG-002',
            task_id: 'TSK-097',
            task_title: 'HEEHRA Rebate',
            action: 'rejected',
            approver: 'Jane Doe',
            timestamp: '2026-01-31 09:15',
            amount: 4000,
            reason: 'Income documentation incomplete'
          },
          {
            id: 'LOG-003',
            task_id: 'TSK-096',
            task_title: 'Q4 ESG Report',
            action: 'approved',
            approver: 'John Smith',
            timestamp: '2026-01-30 16:45',
            amount: 0,
            evidence_hash: 'sha256:789xyz012abc...'
          }
        ])

        setLoading(false)
      } catch (error) {
        console.error('Failed to fetch tasks:', error)
        setLoading(false)
      }
    }

    fetchTasks()
  }, [])

  const handleApprove = async (taskId) => {
    try {
      // API call to approve task and resume agent
      // POST /api/v1/governance/approve
      const response = await fetch('/api/v1/governance/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_id: taskId,
          approver_id: user?.id,
          action: 'approve'
        })
      })

      // Update local state
      setTasks(tasks.map(t =>
        t.id === taskId ? { ...t, status: 'Approved' } : t
      ))

      // Add to audit log
      const task = tasks.find(t => t.id === taskId)
      setAuditLog([
        {
          id: `LOG-${Date.now()}`,
          task_id: taskId,
          task_title: task?.title,
          action: 'approved',
          approver: user?.name || 'Current User',
          timestamp: new Date().toLocaleString(),
          amount: task?.amount,
          evidence_hash: task?.evidence_hash
        },
        ...auditLog
      ])
    } catch (error) {
      console.error('Failed to approve task:', error)
    }
  }

  const handleReject = async (taskId) => {
    try {
      // API call to reject task
      await fetch('/api/v1/governance/reject', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_id: taskId,
          approver_id: user?.id,
          action: 'reject'
        })
      })

      setTasks(tasks.map(t =>
        t.id === taskId ? { ...t, status: 'Rejected' } : t
      ))

      const task = tasks.find(t => t.id === taskId)
      setAuditLog([
        {
          id: `LOG-${Date.now()}`,
          task_id: taskId,
          task_title: task?.title,
          action: 'rejected',
          approver: user?.name || 'Current User',
          timestamp: new Date().toLocaleString(),
          amount: task?.amount
        },
        ...auditLog
      ])
    } catch (error) {
      console.error('Failed to reject task:', error)
    }
  }

  const handleViewDetails = (task) => {
    setSelectedTask(task)
  }

  // Filter tasks
  const filteredTasks = tasks.filter(task => {
    const matchesFilter = filter === 'all' || task.status.toLowerCase() === filter
    const matchesSearch = !searchQuery ||
      task.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      task.detail.toLowerCase().includes(searchQuery.toLowerCase()) ||
      task.id.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesFilter && matchesSearch
  })

  const pendingCount = tasks.filter(t => t.status.toLowerCase() === 'pending').length
  const highRiskCount = tasks.filter(t => t.risk.toLowerCase() === 'high' && t.status.toLowerCase() === 'pending').length
  const totalValue = tasks.filter(t => t.status.toLowerCase() === 'pending').reduce((sum, t) => sum + (t.amount || 0), 0)

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div className="p-6 bg-gray-50 min-h-screen">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <ShieldCheckIcon className="w-8 h-8 text-blue-600" />
          AI Governance & Approval Queue
        </h1>
        <p className="text-gray-600 mt-1">
          Review and approve AI-generated filings, reports, and rebate applications
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <StatsCard
          title="Pending Approvals"
          value={pendingCount}
          icon={ClockIcon}
          color="blue"
        />
        <StatsCard
          title="High Risk Items"
          value={highRiskCount}
          icon={ExclamationTriangleIcon}
          color="red"
        />
        <StatsCard
          title="Total Value Pending"
          value={`$${totalValue.toLocaleString()}`}
          icon={CurrencyDollarIcon}
          color="green"
        />
        <StatsCard
          title="Approved Today"
          value={auditLog.filter(l => l.action === 'approved').length}
          icon={CheckCircleIcon}
          color="yellow"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Tasks List */}
        <div className="lg:col-span-2 space-y-4">
          {/* Filters */}
          <div className="flex flex-wrap items-center gap-4 bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-2">
              <FunnelIcon className="w-5 h-5 text-gray-400" />
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="text-sm border-0 bg-transparent focus:ring-0 text-gray-700"
              >
                <option value="all">All Tasks</option>
                <option value="pending">Pending</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
              </select>
            </div>
            <div className="flex-1 relative">
              <MagnifyingGlassIcon className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search tasks..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* Task Cards */}
          {filteredTasks.length === 0 ? (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
              <CheckCircleIcon className="w-12 h-12 text-green-500 mx-auto mb-3" />
              <p className="text-gray-600">No tasks matching your criteria</p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredTasks.map(task => (
                <TaskCard
                  key={task.id}
                  task={task}
                  onApprove={handleApprove}
                  onReject={handleReject}
                  onViewDetails={handleViewDetails}
                />
              ))}
            </div>
          )}
        </div>

        {/* Audit Log */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <DocumentTextIcon className="w-5 h-5 text-gray-500" />
            Audit Trail
          </h3>
          <p className="text-xs text-gray-500 mb-4">
            Immutable record of all approval decisions for SB 253 & SEC compliance
          </p>
          <div className="divide-y divide-gray-100">
            {auditLog.map(entry => (
              <AuditLogEntry key={entry.id} entry={entry} />
            ))}
          </div>
          {auditLog.length > 0 && (
            <button className="w-full mt-4 text-sm text-blue-600 hover:text-blue-700 font-medium">
              View Full Audit Log →
            </button>
          )}
        </div>
      </div>

      {/* Detail Modal */}
      {selectedTask && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold text-gray-900">{selectedTask.title}</h2>
                <button
                  onClick={() => setSelectedTask(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <XCircleIcon className="w-6 h-6" />
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <h4 className="text-sm font-medium text-gray-700">Description</h4>
                  <p className="text-sm text-gray-600 mt-1">{selectedTask.detail}</p>
                </div>

                <div>
                  <h4 className="text-sm font-medium text-gray-700">AI Reasoning</h4>
                  <p className="text-sm text-gray-600 mt-1 bg-blue-50 p-3 rounded-lg">
                    {selectedTask.ai_reasoning}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <h4 className="text-sm font-medium text-gray-700">Amount</h4>
                    <p className="text-lg font-semibold text-gray-900">${selectedTask.amount?.toLocaleString()}</p>
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-gray-700">Risk Level</h4>
                    <span className={`inline-block px-2 py-1 text-sm font-medium rounded ${riskColors[selectedTask.risk.toLowerCase()]?.bg} ${riskColors[selectedTask.risk.toLowerCase()]?.text}`}>
                      {selectedTask.risk}
                    </span>
                  </div>
                </div>

                <div>
                  <h4 className="text-sm font-medium text-gray-700">Evidence Hash</h4>
                  <p className="text-xs text-gray-500 font-mono bg-gray-100 p-2 rounded mt-1">
                    {selectedTask.evidence_hash}
                  </p>
                </div>

                <div className="flex gap-3 pt-4 border-t">
                  <button
                    onClick={() => {
                      handleReject(selectedTask.id)
                      setSelectedTask(null)
                    }}
                    className="flex-1 px-4 py-2 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded-lg transition-colors"
                  >
                    Reject
                  </button>
                  <button
                    onClick={() => {
                      handleApprove(selectedTask.id)
                      setSelectedTask(null)
                    }}
                    className="flex-1 px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors"
                  >
                    Approve
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
