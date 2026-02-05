import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  DocumentCheckIcon,
  ArrowRightIcon,
  LightBulbIcon
} from '@heroicons/react/24/outline';
import api from '../../utils/api';
import toast from 'react-hot-toast';

export default function ContractReadinessChecker({ verticalId }) {
  const [loading, setLoading] = useState(false);
  const [selectedContractType, setSelectedContractType] = useState('government');
  const [readiness, setReadiness] = useState(null);
  const [verticals, setVerticals] = useState([]);
  const [selectedVertical, setSelectedVertical] = useState(verticalId || '');

  useEffect(() => {
    fetchVerticals();
  }, []);

  useEffect(() => {
    if (verticalId) {
      setSelectedVertical(verticalId);
    }
  }, [verticalId]);

  const fetchVerticals = async () => {
    try {
      const response = await api.get('/jobs/verticals');
      setVerticals(response.data.verticals || []);
    } catch (error) {
      console.error('Failed to fetch verticals:', error);
    }
  };

  const checkReadiness = async () => {
    if (!selectedVertical) {
      toast.error('Please select a service vertical');
      return;
    }

    try {
      setLoading(true);
      const response = await api.post('/compliance/check-readiness', {
        contractType: selectedContractType,
        verticalId: selectedVertical
      });
      setReadiness(response.data);
    } catch (error) {
      toast.error('Failed to check contract readiness');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const contractTypes = [
    { value: 'government', label: 'Government Contract', icon: '🏛️', description: 'Federal, state, or local government contracts' },
    { value: 'commercial', label: 'Commercial Contract', icon: '🏢', description: 'Private enterprise contracts' },
    { value: 'municipal', label: 'Municipal Contract', icon: '🏘️', description: 'City and county contracts' },
    { value: 'institutional', label: 'Institutional Contract', icon: '🏫', description: 'Schools, hospitals, nonprofits' }
  ];

  const getScoreColor = (score) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getScoreBg = (score) => {
    if (score >= 80) return 'bg-green-100';
    if (score >= 60) return 'bg-yellow-100';
    return 'bg-red-100';
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'high': return 'text-red-600 bg-red-100';
      case 'medium': return 'text-yellow-600 bg-yellow-100';
      default: return 'text-blue-600 bg-blue-100';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-xl shadow-lg p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-2 flex items-center">
          <ShieldCheckIcon className="h-6 w-6 text-green-600 mr-2" />
          Contract Readiness Checker
        </h2>
        <p className="text-gray-600">
          Check if your company meets the ESG compliance requirements for different contract types.
        </p>
      </div>

      {/* Selection Panel */}
      <div className="bg-white rounded-xl shadow-lg p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Vertical Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Service Vertical
            </label>
            <select
              value={selectedVertical}
              onChange={(e) => setSelectedVertical(e.target.value)}
              className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500"
            >
              <option value="">Select a vertical</option>
              {verticals.map(v => (
                <option key={v.id} value={v.id}>{v.name}</option>
              ))}
            </select>
          </div>

          {/* Contract Type Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Contract Type
            </label>
            <select
              value={selectedContractType}
              onChange={(e) => setSelectedContractType(e.target.value)}
              className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500"
            >
              {contractTypes.map(type => (
                <option key={type.value} value={type.value}>
                  {type.icon} {type.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Contract Type Cards */}
        <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
          {contractTypes.map(type => (
            <button
              key={type.value}
              onClick={() => setSelectedContractType(type.value)}
              className={`p-4 rounded-lg border-2 transition-all ${
                selectedContractType === type.value
                  ? 'border-green-500 bg-green-50'
                  : 'border-gray-200 hover:border-green-300'
              }`}
            >
              <span className="text-2xl">{type.icon}</span>
              <p className="mt-2 font-medium text-sm text-gray-900">{type.label}</p>
            </button>
          ))}
        </div>

        <button
          onClick={checkReadiness}
          disabled={loading || !selectedVertical}
          className="mt-6 w-full bg-green-600 text-white py-3 px-6 rounded-lg font-medium hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center"
        >
          {loading ? (
            <>
              <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Checking Readiness...
            </>
          ) : (
            <>
              Check Contract Readiness
              <ArrowRightIcon className="h-5 w-5 ml-2" />
            </>
          )}
        </button>
      </div>

      {/* Results */}
      {readiness && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-6"
        >
          {/* Readiness Score */}
          <div className={`rounded-xl shadow-lg p-6 ${readiness.ready ? 'bg-green-50' : 'bg-yellow-50'}`}>
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center">
                  {readiness.ready ? (
                    <CheckCircleIcon className="h-8 w-8 text-green-600 mr-3" />
                  ) : (
                    <ExclamationTriangleIcon className="h-8 w-8 text-yellow-600 mr-3" />
                  )}
                  <div>
                    <h3 className={`text-xl font-bold ${readiness.ready ? 'text-green-900' : 'text-yellow-900'}`}>
                      {readiness.ready ? 'Contract Ready!' : 'Not Yet Ready'}
                    </h3>
                    <p className={`text-sm ${readiness.ready ? 'text-green-700' : 'text-yellow-700'}`}>
                      {readiness.ready
                        ? 'Your company meets the ESG requirements for this contract type'
                        : `You need a score of ${readiness.minimumRequired}+ to qualify`}
                    </p>
                  </div>
                </div>
              </div>
              <div className={`p-4 rounded-full ${getScoreBg(readiness.score)}`}>
                <span className={`text-3xl font-bold ${getScoreColor(readiness.score)}`}>
                  {readiness.score}%
                </span>
              </div>
            </div>

            {/* Progress Bar */}
            <div className="mt-4">
              <div className="flex justify-between text-sm mb-1">
                <span className={readiness.ready ? 'text-green-700' : 'text-yellow-700'}>Current Score</span>
                <span className={readiness.ready ? 'text-green-700' : 'text-yellow-700'}>Required: {readiness.minimumRequired}%</span>
              </div>
              <div className="w-full bg-white rounded-full h-4 overflow-hidden">
                <div
                  className={`h-4 rounded-full transition-all duration-500 ${readiness.ready ? 'bg-green-500' : 'bg-yellow-500'}`}
                  style={{ width: `${Math.min(readiness.score, 100)}%` }}
                ></div>
              </div>
            </div>
          </div>

          {/* Timeline */}
          {readiness.timeline && (
            <div className="bg-white rounded-xl shadow-lg p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                <ClockIcon className="h-5 w-5 text-gray-600 mr-2" />
                Estimated Timeline
              </h3>
              <p className="text-gray-700">{readiness.timeline.message}</p>
            </div>
          )}

          {/* Gaps */}
          {readiness.gaps?.length > 0 && (
            <div className="bg-white rounded-xl shadow-lg p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                <DocumentCheckIcon className="h-5 w-5 text-red-500 mr-2" />
                Compliance Gaps ({readiness.gaps.length})
              </h3>
              <div className="space-y-4">
                {readiness.gaps.map((gap, index) => (
                  <div key={index} className="border rounded-lg p-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${getPriorityColor(gap.priority)}`}>
                            {gap.priority}
                          </span>
                          <span className="ml-2 font-medium text-gray-900">{gap.requirement}</span>
                        </div>
                        <p className="text-sm text-gray-500 mt-1">{gap.type}</p>
                      </div>
                      <span className="text-sm text-gray-500">{gap.estimatedEffort}</span>
                    </div>
                    {gap.actionItems && (
                      <div className="mt-3">
                        <p className="text-xs font-medium text-gray-600 mb-1">Action Items:</p>
                        <ul className="text-sm text-gray-600 space-y-1">
                          {gap.actionItems.map((action, i) => (
                            <li key={i} className="flex items-center">
                              <span className="h-1.5 w-1.5 bg-gray-400 rounded-full mr-2"></span>
                              {action}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recommendations */}
          {readiness.recommendations?.length > 0 && (
            <div className="bg-white rounded-xl shadow-lg p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                <LightBulbIcon className="h-5 w-5 text-yellow-500 mr-2" />
                Recommendations
              </h3>
              <div className="space-y-3">
                {readiness.recommendations.map((rec, index) => (
                  <div key={index} className={`p-4 rounded-lg ${getPriorityColor(rec.priority).replace('text-', 'bg-').replace('-600', '-50')}`}>
                    <div className="flex items-start">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${getPriorityColor(rec.priority)}`}>
                        {rec.priority}
                      </span>
                      <p className="ml-3 text-gray-800">{rec.message}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Ready State Actions */}
          {readiness.ready && (
            <div className="bg-green-600 rounded-xl shadow-lg p-6 text-white">
              <h3 className="text-lg font-semibold mb-2">You're Ready to Bid!</h3>
              <p className="text-green-100 mb-4">
                Your company meets all the ESG compliance requirements for {contractTypes.find(t => t.value === selectedContractType)?.label}s.
              </p>
              <div className="flex space-x-4">
                <button className="bg-white text-green-600 px-4 py-2 rounded-lg font-medium hover:bg-green-50 transition-colors">
                  Generate Compliance Report
                </button>
                <button className="border border-white text-white px-4 py-2 rounded-lg font-medium hover:bg-green-700 transition-colors">
                  View Full Certification
                </button>
              </div>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}
