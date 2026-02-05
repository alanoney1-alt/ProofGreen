import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  ShieldCheckIcon,
  DocumentCheckIcon,
  ExclamationTriangleIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon
} from '@heroicons/react/24/outline';
import { Chart as ChartJS, ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement } from 'chart.js';
import { Doughnut, Bar } from 'react-chartjs-2';
import api from '../../utils/api';
import toast from 'react-hot-toast';

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement);

export default function ComplianceDashboard() {
  const [loading, setLoading] = useState(true);
  const [compliance, setCompliance] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [period, setPeriod] = useState('30');

  useEffect(() => {
    fetchComplianceData();
  }, [period]);

  const fetchComplianceData = async () => {
    try {
      setLoading(true);
      const [statusRes, analyticsRes] = await Promise.all([
        api.get('/compliance/status'),
        api.get(`/compliance/analytics?period=${period}`)
      ]);
      setCompliance(statusRes.data);
      setAnalytics(analyticsRes.data.analytics);
    } catch (error) {
      toast.error('Failed to load compliance data');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const getScoreColor = (score) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    if (score >= 40) return 'text-orange-600';
    return 'text-red-600';
  };

  const getScoreBg = (score) => {
    if (score >= 80) return 'bg-green-100';
    if (score >= 60) return 'bg-yellow-100';
    if (score >= 40) return 'bg-orange-100';
    return 'bg-red-100';
  };

  const scoreChartData = compliance ? {
    labels: ['Environmental', 'Social', 'Governance'],
    datasets: [{
      data: [
        compliance.compliance?.breakdown?.environmental || 0,
        compliance.compliance?.breakdown?.social || 0,
        compliance.compliance?.breakdown?.governance || 0
      ],
      backgroundColor: ['#10B981', '#3B82F6', '#8B5CF6'],
      borderWidth: 0
    }]
  } : null;

  const distributionChartData = analytics ? {
    labels: ['Excellent (80+)', 'Good (60-79)', 'Fair (40-59)', 'Needs Work (<40)'],
    datasets: [{
      label: 'Jobs',
      data: [
        analytics.distribution?.excellent || 0,
        analytics.distribution?.good || 0,
        analytics.distribution?.fair || 0,
        analytics.distribution?.needsWork || 0
      ],
      backgroundColor: ['#10B981', '#3B82F6', '#F59E0B', '#EF4444']
    }]
  } : null;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">ESG Compliance Dashboard</h1>
          <p className="text-gray-600">Monitor your environmental, social, and governance metrics</p>
        </div>
        <select
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
          className="rounded-lg border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500"
        >
          <option value="7">Last 7 days</option>
          <option value="30">Last 30 days</option>
          <option value="90">Last 90 days</option>
          <option value="365">Last year</option>
        </select>
      </div>

      {/* Overall Score Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-xl shadow-lg p-6"
      >
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-600">Overall ESG Score</p>
            <div className="flex items-center mt-2">
              <span className={`text-4xl font-bold ${getScoreColor(compliance?.summary?.overallScore || 0)}`}>
                {compliance?.summary?.overallScore || 0}
              </span>
              <span className="text-2xl text-gray-400 ml-1">/100</span>
              {compliance?.summary?.trend === 'improving' && (
                <ArrowTrendingUpIcon className="h-6 w-6 text-green-500 ml-3" />
              )}
              {compliance?.summary?.trend === 'declining' && (
                <ArrowTrendingDownIcon className="h-6 w-6 text-red-500 ml-3" />
              )}
            </div>
          </div>
          <div className={`p-4 rounded-full ${getScoreBg(compliance?.summary?.overallScore || 0)}`}>
            <ShieldCheckIcon className={`h-12 w-12 ${getScoreColor(compliance?.summary?.overallScore || 0)}`} />
          </div>
        </div>

        {/* Contract Readiness */}
        <div className="mt-6 grid grid-cols-2 gap-4">
          <div className={`p-4 rounded-lg ${compliance?.summary?.contractReady ? 'bg-green-50' : 'bg-yellow-50'}`}>
            <div className="flex items-center">
              {compliance?.summary?.contractReady ? (
                <CheckCircleIcon className="h-5 w-5 text-green-600 mr-2" />
              ) : (
                <XCircleIcon className="h-5 w-5 text-yellow-600 mr-2" />
              )}
              <span className={`font-medium ${compliance?.summary?.contractReady ? 'text-green-800' : 'text-yellow-800'}`}>
                {compliance?.summary?.contractReady ? 'Contract Ready' : 'Not Contract Ready'}
              </span>
            </div>
            <p className="text-sm text-gray-600 mt-1">
              {compliance?.summary?.contractReady
                ? 'You meet requirements for ESG-focused contracts'
                : 'Score must be 70+ for contract readiness'}
            </p>
          </div>
          <div className={`p-4 rounded-lg ${compliance?.summary?.actionRequired ? 'bg-red-50' : 'bg-green-50'}`}>
            <div className="flex items-center">
              {compliance?.summary?.actionRequired ? (
                <ExclamationTriangleIcon className="h-5 w-5 text-red-600 mr-2" />
              ) : (
                <CheckCircleIcon className="h-5 w-5 text-green-600 mr-2" />
              )}
              <span className={`font-medium ${compliance?.summary?.actionRequired ? 'text-red-800' : 'text-green-800'}`}>
                {compliance?.summary?.actionRequired ? 'Action Required' : 'All Clear'}
              </span>
            </div>
            <p className="text-sm text-gray-600 mt-1">
              {compliance?.expiringItems?.length || 0} items expiring soon
            </p>
          </div>
        </div>
      </motion.div>

      {/* Score Breakdown and Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ESG Breakdown */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-white rounded-xl shadow-lg p-6"
        >
          <h2 className="text-lg font-semibold text-gray-900 mb-4">ESG Score Breakdown</h2>
          <div className="flex items-center justify-center">
            {scoreChartData && (
              <div className="w-48 h-48">
                <Doughnut
                  data={scoreChartData}
                  options={{
                    plugins: {
                      legend: { position: 'bottom' }
                    },
                    cutout: '60%'
                  }}
                />
              </div>
            )}
          </div>
          <div className="mt-4 space-y-3">
            <ScoreBar label="Environmental" score={compliance?.compliance?.breakdown?.environmental || 0} color="bg-green-500" />
            <ScoreBar label="Social" score={compliance?.compliance?.breakdown?.social || 0} color="bg-blue-500" />
            <ScoreBar label="Governance" score={compliance?.compliance?.breakdown?.governance || 0} color="bg-purple-500" />
          </div>
        </motion.div>

        {/* Score Distribution */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-white rounded-xl shadow-lg p-6"
        >
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Job Score Distribution</h2>
          {distributionChartData && (
            <Bar
              data={distributionChartData}
              options={{
                plugins: { legend: { display: false } },
                scales: {
                  y: { beginAtZero: true, ticks: { stepSize: 1 } }
                }
              }}
            />
          )}
          <div className="mt-4 text-center">
            <p className="text-sm text-gray-600">
              Average Score: <span className="font-semibold">{analytics?.averageScore?.toFixed(1) || 0}</span>
            </p>
          </div>
        </motion.div>
      </div>

      {/* Expiring Items */}
      {compliance?.expiringItems?.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="bg-white rounded-xl shadow-lg p-6"
        >
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <ClockIcon className="h-5 w-5 text-yellow-500 mr-2" />
            Expiring Soon
          </h2>
          <div className="space-y-3">
            {compliance.expiringItems.map((item, index) => (
              <div key={index} className="flex items-center justify-between p-3 bg-yellow-50 rounded-lg">
                <div>
                  <p className="font-medium text-gray-900">{item.name || item.certification_name || item.file_name}</p>
                  <p className="text-sm text-gray-600">{item.type || 'Document'}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium text-yellow-600">
                    Expires: {new Date(item.expires_at).toLocaleDateString()}
                  </p>
                  <p className="text-xs text-gray-500">
                    {Math.ceil((new Date(item.expires_at) - new Date()) / (1000 * 60 * 60 * 24))} days left
                  </p>
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Recent Jobs */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="bg-white rounded-xl shadow-lg p-6"
      >
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Jobs ESG Scores</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead>
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Job</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Vertical</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ESG Score</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {compliance?.recentJobs?.map((job) => (
                <tr key={job.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span className="font-medium text-gray-900">{job.title || `Job #${job.id.slice(0, 8)}`}</span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-gray-600">
                    {job.verticals?.name || 'N/A'}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getScoreBg(job.esgScore?.overall || 0)} ${getScoreColor(job.esgScore?.overall || 0)}`}>
                      {job.esgScore?.overall || 0}
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      job.status === 'completed' ? 'bg-green-100 text-green-800' :
                      job.status === 'in_progress' ? 'bg-blue-100 text-blue-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {job.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-gray-600">
                    {new Date(job.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>
    </div>
  );
}

function ScoreBar({ label, score, color }) {
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-600">{label}</span>
        <span className="font-medium">{score}/100</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div className={`${color} h-2 rounded-full transition-all duration-500`} style={{ width: `${score}%` }}></div>
      </div>
    </div>
  );
}
