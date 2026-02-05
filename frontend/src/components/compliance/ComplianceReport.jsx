import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  DocumentTextIcon,
  ArrowDownTrayIcon,
  ShareIcon,
  PrinterIcon,
  ChartBarIcon,
  ShieldCheckIcon,
  GlobeAltIcon,
  UserGroupIcon,
  BuildingOfficeIcon
} from '@heroicons/react/24/outline';
import { Chart as ChartJS, ArcElement, Tooltip, Legend, CategoryScale, LinearScale, LineElement, PointElement } from 'chart.js';
import { Doughnut, Line } from 'react-chartjs-2';
import api from '../../utils/api';
import toast from 'react-hot-toast';

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, LineElement, PointElement);

export default function ComplianceReport({ verticalId, dateRange = '30d' }) {
  const [loading, setLoading] = useState(true);
  const [report, setReport] = useState(null);

  useEffect(() => {
    fetchReport();
  }, [verticalId, dateRange]);

  const fetchReport = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (verticalId) params.append('verticalId', verticalId);
      if (dateRange) params.append('dateRange', dateRange);

      const response = await api.get(`/compliance/report?${params}`);
      setReport(response.data);
    } catch (error) {
      toast.error('Failed to load compliance report');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const downloadPDF = async () => {
    toast.loading('Generating PDF report...');
    try {
      const response = await api.get('/reports/compliance/pdf', {
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `compliance-report-${new Date().toISOString().split('T')[0]}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      toast.dismiss();
      toast.success('PDF downloaded');
    } catch (error) {
      toast.dismiss();
      toast.error('Failed to generate PDF');
    }
  };

  const shareReport = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: 'ESG Compliance Report',
          text: `ESG Score: ${report?.overallScore || 0}/100`,
          url: window.location.href
        });
      } catch (error) {
        console.error('Share failed:', error);
      }
    } else {
      navigator.clipboard.writeText(window.location.href);
      toast.success('Link copied to clipboard');
    }
  };

  const getScoreColor = (score) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    if (score >= 40) return 'text-orange-600';
    return 'text-red-600';
  };

  const breakdownChartData = report ? {
    labels: ['Environmental', 'Social', 'Governance'],
    datasets: [{
      data: [
        report.breakdown?.environmental || 0,
        report.breakdown?.social || 0,
        report.breakdown?.governance || 0
      ],
      backgroundColor: ['#10B981', '#3B82F6', '#8B5CF6'],
      borderWidth: 0
    }]
  } : null;

  const trendChartData = report?.historicalScores ? {
    labels: report.historicalScores.map(s => new Date(s.created_at).toLocaleDateString()),
    datasets: [{
      label: 'ESG Score',
      data: report.historicalScores.map(s => s.esg_score),
      borderColor: '#10B981',
      backgroundColor: 'rgba(16, 185, 129, 0.1)',
      tension: 0.4,
      fill: true
    }]
  } : null;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600"></div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="text-center py-12">
        <DocumentTextIcon className="h-12 w-12 mx-auto text-gray-400 mb-4" />
        <p className="text-gray-500">No report data available</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Report Header */}
      <div className="bg-white rounded-xl shadow-lg p-6">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">ESG Compliance Report</h1>
            <p className="text-gray-600 mt-1">
              Generated on {new Date().toLocaleDateString()}
            </p>
          </div>
          <div className="flex space-x-2">
            <button
              onClick={downloadPDF}
              className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
              PDF
            </button>
            <button
              onClick={() => window.print()}
              className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              <PrinterIcon className="h-4 w-4 mr-2" />
              Print
            </button>
            <button
              onClick={shareReport}
              className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              <ShareIcon className="h-4 w-4 mr-2" />
              Share
            </button>
          </div>
        </div>
      </div>

      {/* Overall Score Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-gradient-to-r from-green-600 to-green-700 rounded-xl shadow-lg p-8 text-white"
      >
        <div className="flex items-center justify-between">
          <div>
            <p className="text-green-100 text-sm font-medium">Overall ESG Score</p>
            <div className="flex items-baseline mt-2">
              <span className="text-6xl font-bold">{report.overallScore || 0}</span>
              <span className="text-2xl text-green-200 ml-2">/100</span>
            </div>
            <p className="mt-4 text-green-100">
              {report.overallScore >= 80 ? 'Excellent - Contract Ready' :
               report.overallScore >= 60 ? 'Good - Minor improvements needed' :
               report.overallScore >= 40 ? 'Fair - Significant gaps to address' :
               'Needs Work - Major improvements required'}
            </p>
          </div>
          <ShieldCheckIcon className="h-24 w-24 text-green-400 opacity-50" />
        </div>
      </motion.div>

      {/* ESG Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-white rounded-xl shadow-lg p-6"
        >
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Score Breakdown</h2>
          <div className="flex items-center justify-center h-64">
            {breakdownChartData && (
              <Doughnut
                data={breakdownChartData}
                options={{
                  plugins: { legend: { position: 'bottom' } },
                  cutout: '60%'
                }}
              />
            )}
          </div>
        </motion.div>

        {/* Score Details */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-white rounded-xl shadow-lg p-6"
        >
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Category Scores</h2>
          <div className="space-y-6">
            <ScoreCategory
              icon={<GlobeAltIcon className="h-6 w-6" />}
              label="Environmental"
              score={report.breakdown?.environmental || 0}
              color="green"
              description="Waste diversion, recycling, carbon offset"
            />
            <ScoreCategory
              icon={<UserGroupIcon className="h-6 w-6" />}
              label="Social"
              score={report.breakdown?.social || 0}
              color="blue"
              description="Community impact, donations, safety"
            />
            <ScoreCategory
              icon={<BuildingOfficeIcon className="h-6 w-6" />}
              label="Governance"
              score={report.breakdown?.governance || 0}
              color="purple"
              description="Certifications, compliance, documentation"
            />
          </div>
        </motion.div>
      </div>

      {/* Trend Chart */}
      {trendChartData && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="bg-white rounded-xl shadow-lg p-6"
        >
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <ChartBarIcon className="h-5 w-5 text-gray-600 mr-2" />
            Score Trend
          </h2>
          <div className="h-64">
            <Line
              data={trendChartData}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                  y: { beginAtZero: true, max: 100 }
                }
              }}
            />
          </div>
          {report.trend && (
            <p className="mt-4 text-center text-sm text-gray-600">
              Trend: <span className={`font-medium ${
                report.trend === 'improving' ? 'text-green-600' :
                report.trend === 'declining' ? 'text-red-600' : 'text-gray-600'
              }`}>
                {report.trend.charAt(0).toUpperCase() + report.trend.slice(1)}
              </span>
            </p>
          )}
        </motion.div>
      )}

      {/* Certifications */}
      {report.certifications?.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="bg-white rounded-xl shadow-lg p-6"
        >
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Certifications</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {report.certifications.map((cert, index) => (
              <div key={index} className="border rounded-lg p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium text-gray-900">{cert.certification_name}</p>
                    <p className="text-sm text-gray-500">{cert.issued_by}</p>
                  </div>
                  {cert.verified && (
                    <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
                      Verified
                    </span>
                  )}
                </div>
                {cert.expires_at && (
                  <p className="mt-2 text-xs text-gray-500">
                    Expires: {new Date(cert.expires_at).toLocaleDateString()}
                  </p>
                )}
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Key Metrics */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="bg-white rounded-xl shadow-lg p-6"
      >
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Key Metrics Summary</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard
            label="Total Jobs"
            value={report.metrics?.totalJobs || 0}
            unit="jobs"
          />
          <MetricCard
            label="Waste Diverted"
            value={((report.metrics?.totalDiverted || 0) / 2000).toFixed(1)}
            unit="tons"
          />
          <MetricCard
            label="Carbon Offset"
            value={((report.metrics?.totalCarbon || 0) / 2000).toFixed(1)}
            unit="tons CO2"
          />
          <MetricCard
            label="Diversion Rate"
            value={(report.metrics?.avgDiversionRate || 0).toFixed(1)}
            unit="%"
          />
        </div>
      </motion.div>

      {/* Requirements Summary */}
      {report.requirementsSummary && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="bg-white rounded-xl shadow-lg p-6"
        >
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Compliance Status</h2>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div className="p-4 bg-green-50 rounded-lg">
              <p className="text-3xl font-bold text-green-600">{report.requirementsSummary?.compliant || 0}</p>
              <p className="text-sm text-gray-600">Compliant</p>
            </div>
            <div className="p-4 bg-yellow-50 rounded-lg">
              <p className="text-3xl font-bold text-yellow-600">{report.requirementsSummary?.pending || 0}</p>
              <p className="text-sm text-gray-600">Pending</p>
            </div>
            <div className="p-4 bg-red-50 rounded-lg">
              <p className="text-3xl font-bold text-red-600">{report.requirementsSummary?.missing || 0}</p>
              <p className="text-sm text-gray-600">Missing</p>
            </div>
          </div>
        </motion.div>
      )}

      {/* Report Footer */}
      <div className="bg-gray-50 rounded-xl p-6 text-center text-sm text-gray-500">
        <p>
          This report was generated by ProofGreen ESG Compliance System.
          Data is based on verified job records and submitted documentation.
        </p>
        <p className="mt-2">
          Report ID: {report.reportId || 'N/A'} | Generated: {new Date().toISOString()}
        </p>
      </div>
    </div>
  );
}

function ScoreCategory({ icon, label, score, color, description }) {
  const colorClasses = {
    green: 'bg-green-100 text-green-600',
    blue: 'bg-blue-100 text-blue-600',
    purple: 'bg-purple-100 text-purple-600'
  };

  const progressColors = {
    green: 'bg-green-500',
    blue: 'bg-blue-500',
    purple: 'bg-purple-500'
  };

  return (
    <div className="flex items-center space-x-4">
      <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
        {icon}
      </div>
      <div className="flex-1">
        <div className="flex justify-between items-center mb-1">
          <span className="font-medium text-gray-900">{label}</span>
          <span className="font-bold text-gray-900">{score}/100</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className={`${progressColors[color]} h-2 rounded-full transition-all duration-500`}
            style={{ width: `${score}%` }}
          ></div>
        </div>
        <p className="text-xs text-gray-500 mt-1">{description}</p>
      </div>
    </div>
  );
}

function MetricCard({ label, value, unit }) {
  return (
    <div className="text-center p-4 bg-gray-50 rounded-lg">
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      <p className="text-xs text-gray-500">{unit}</p>
      <p className="text-sm text-gray-600 mt-1">{label}</p>
    </div>
  );
}
