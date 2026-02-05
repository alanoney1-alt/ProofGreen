import React, { useState, useEffect } from 'react';
import { api } from '../utils/api';

/**
 * Agents Dashboard
 * Central hub for multi-agent ESG automation
 */
const AgentsDashboard = () => {
  const [activeAgent, setActiveAgent] = useState('intake');
  const [loading, setLoading] = useState(false);
  const [agents, setAgents] = useState(null);

  // Fetch available agents
  useEffect(() => {
    const loadAgents = async () => {
      try {
        const response = await api.get('/agents/available');
        if (response.success) {
          setAgents(response.agents);
        }
      } catch (error) {
        console.error('Failed to load agents:', error);
      }
    };
    loadAgents();
  }, []);

  const agentTabs = [
    {
      id: 'intake',
      name: 'Intake Agent',
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
      description: 'Lead generation, CV surveys, instant quotes'
    },
    {
      id: 'ops',
      name: 'Ops Agent',
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
        </svg>
      ),
      description: 'Route optimization, fleet tracking, empty miles'
    },
    {
      id: 'verifier',
      name: 'Green Verifier',
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
        </svg>
      ),
      description: 'Carbon verification, certificates, ESG reports'
    },
    {
      id: 'tax',
      name: 'Tax Credit Matcher',
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      description: 'Federal & state incentives (45W, 48C, 179D)'
    }
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">AI Agents Dashboard</h1>
              <p className="text-gray-500 mt-1">Multi-agent ESG automation system</p>
            </div>
            <div className="flex items-center gap-3">
              <span className="px-3 py-1 bg-green-100 text-green-700 text-sm rounded-full flex items-center gap-1">
                <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                All systems operational
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Agent tabs */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 mb-6">
          <div className="flex border-b border-gray-200">
            {agentTabs.map(agent => (
              <button
                key={agent.id}
                onClick={() => setActiveAgent(agent.id)}
                className={`flex-1 px-4 py-4 text-center transition-colors ${
                  activeAgent === agent.id
                    ? 'bg-green-50 border-b-2 border-green-600'
                    : 'hover:bg-gray-50'
                }`}
              >
                <div className="flex items-center justify-center gap-2">
                  <span className={activeAgent === agent.id ? 'text-green-600' : 'text-gray-400'}>
                    {agent.icon}
                  </span>
                  <span className={`font-medium ${activeAgent === agent.id ? 'text-green-600' : 'text-gray-700'}`}>
                    {agent.name}
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-1 hidden md:block">{agent.description}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Agent content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main panel */}
          <div className="lg:col-span-2">
            {activeAgent === 'intake' && <IntakeAgentPanel />}
            {activeAgent === 'ops' && <OpsAgentPanel />}
            {activeAgent === 'verifier' && <VerifierAgentPanel />}
            {activeAgent === 'tax' && <TaxAgentPanel />}
          </div>

          {/* Side panel */}
          <div className="space-y-6">
            <QuickActions activeAgent={activeAgent} />
            <RecentActivity />
          </div>
        </div>
      </div>
    </div>
  );
};

/**
 * Intake Agent Panel
 */
const IntakeAgentPanel = () => {
  const [mode, setMode] = useState('survey');

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">Intake Agent</h2>
        <p className="text-sm text-gray-500">Computer vision surveys and instant quotes</p>
      </div>

      <div className="p-6">
        {/* Mode selector */}
        <div className="flex gap-2 mb-6">
          {['survey', 'quote', 'chat'].map(m => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                mode === m
                  ? 'bg-green-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {m === 'survey' && 'CV Survey'}
              {m === 'quote' && 'Instant Quote'}
              {m === 'chat' && 'Customer Chat'}
            </button>
          ))}
        </div>

        {mode === 'survey' && (
          <div className="space-y-4">
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <p className="mt-2 text-gray-600">Upload room photos for AI inventory analysis</p>
              <p className="text-sm text-gray-400 mt-1">Supports: Living room, bedroom, kitchen, garage, office</p>
              <button className="mt-4 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700">
                Select Photos
              </button>
            </div>

            <div className="bg-gray-50 rounded-lg p-4">
              <h4 className="font-medium text-gray-900 mb-2">How it works:</h4>
              <ol className="text-sm text-gray-600 space-y-2">
                <li className="flex items-start gap-2">
                  <span className="w-5 h-5 bg-green-100 text-green-600 rounded-full flex items-center justify-center text-xs flex-shrink-0">1</span>
                  <span>Upload photos of each room (up to 20 images)</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="w-5 h-5 bg-green-100 text-green-600 rounded-full flex items-center justify-center text-xs flex-shrink-0">2</span>
                  <span>AI identifies furniture, boxes, and special items</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="w-5 h-5 bg-green-100 text-green-600 rounded-full flex items-center justify-center text-xs flex-shrink-0">3</span>
                  <span>Estimates weight, volume, and required truck size</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="w-5 h-5 bg-green-100 text-green-600 rounded-full flex items-center justify-center text-xs flex-shrink-0">4</span>
                  <span>Generates instant quote with carbon footprint</span>
                </li>
              </ol>
            </div>
          </div>
        )}

        {mode === 'quote' && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Origin Address</label>
                <input type="text" placeholder="123 Main St, City, State" className="w-full px-3 py-2 border border-gray-300 rounded-lg" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Destination Address</label>
                <input type="text" placeholder="456 Oak Ave, City, State" className="w-full px-3 py-2 border border-gray-300 rounded-lg" />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Home Size</label>
                <select className="w-full px-3 py-2 border border-gray-300 rounded-lg">
                  <option>Studio</option>
                  <option>1 Bedroom</option>
                  <option>2 Bedroom</option>
                  <option>3 Bedroom</option>
                  <option>4+ Bedroom</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Move Date</label>
                <input type="date" className="w-full px-3 py-2 border border-gray-300 rounded-lg" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Distance (mi)</label>
                <input type="number" placeholder="50" className="w-full px-3 py-2 border border-gray-300 rounded-lg" />
              </div>
            </div>

            <button className="w-full py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium">
              Generate Instant Quote
            </button>
          </div>
        )}

        {mode === 'chat' && (
          <div className="space-y-4">
            <div className="h-64 bg-gray-50 rounded-lg p-4 overflow-y-auto">
              <div className="space-y-3">
                <div className="flex gap-2">
                  <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
                    <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <div className="bg-white border border-gray-200 rounded-lg px-3 py-2 max-w-xs">
                    <p className="text-sm text-gray-700">Hi! I'm your ProofGreen assistant. I can help you get a quote, schedule a move, or answer questions about our eco-friendly services. How can I help today?</p>
                  </div>
                </div>
              </div>
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Type your message..."
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg"
              />
              <button className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700">
                Send
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * Ops Agent Panel
 */
const OpsAgentPanel = () => {
  const [fleetStatus, setFleetStatus] = useState(null);

  useEffect(() => {
    const loadFleetStatus = async () => {
      try {
        const response = await api.get('/telematics/fleet/demo');
        if (response.success) {
          setFleetStatus(response);
        }
      } catch (error) {
        console.error('Failed to load fleet status:', error);
      }
    };
    loadFleetStatus();
  }, []);

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">Operations Agent</h2>
        <p className="text-sm text-gray-500">Fleet tracking and route optimization</p>
      </div>

      <div className="p-6 space-y-6">
        {/* Fleet status */}
        <div>
          <h3 className="font-medium text-gray-900 mb-3">Live Fleet Status</h3>
          <div className="grid grid-cols-4 gap-4 mb-4">
            {[
              { label: 'Total Vehicles', value: fleetStatus?.summary?.total_vehicles || 3, color: 'blue' },
              { label: 'Moving', value: fleetStatus?.summary?.moving || 2, color: 'green' },
              { label: 'At Job', value: fleetStatus?.summary?.at_job || 1, color: 'yellow' },
              { label: 'Idle', value: fleetStatus?.summary?.idle || 0, color: 'gray' }
            ].map(stat => (
              <div key={stat.label} className={`bg-${stat.color}-50 rounded-lg p-3`}>
                <p className={`text-2xl font-bold text-${stat.color}-600`}>{stat.value}</p>
                <p className="text-xs text-gray-500">{stat.label}</p>
              </div>
            ))}
          </div>

          {/* Vehicle list */}
          <div className="space-y-2">
            {(fleetStatus?.vehicles || []).map((vehicle, idx) => (
              <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <div className={`w-3 h-3 rounded-full ${
                    vehicle.status === 'moving' ? 'bg-green-500' :
                    vehicle.status === 'at_job' ? 'bg-yellow-500' : 'bg-gray-400'
                  }`}></div>
                  <div>
                    <p className="font-medium text-gray-900">{vehicle.vehicle_name}</p>
                    <p className="text-xs text-gray-500">{vehicle.driver || 'Unassigned'}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm text-gray-900">{vehicle.speed_mph} mph</p>
                  <p className="text-xs text-gray-500">{vehicle.current_job || 'No active job'}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Route optimization */}
        <div>
          <h3 className="font-medium text-gray-900 mb-3">Route Optimization</h3>
          <div className="bg-green-50 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-green-700 font-medium">Today's Optimized Routes</span>
              <span className="text-green-600 text-sm">12% fuel savings</span>
            </div>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-xl font-bold text-green-700">156</p>
                <p className="text-xs text-gray-500">Total Miles</p>
              </div>
              <div>
                <p className="text-xl font-bold text-green-700">18</p>
                <p className="text-xs text-gray-500">Miles Saved</p>
              </div>
              <div>
                <p className="text-xl font-bold text-green-700">35 lbs</p>
                <p className="text-xs text-gray-500">CO2 Avoided</p>
              </div>
            </div>
          </div>
          <button className="mt-3 w-full py-2 border border-green-600 text-green-600 rounded-lg hover:bg-green-50 font-medium">
            View Route Details
          </button>
        </div>
      </div>
    </div>
  );
};

/**
 * Verifier Agent Panel
 */
const VerifierAgentPanel = () => {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">Green Verifier Agent</h2>
        <p className="text-sm text-gray-500">Carbon verification and certificate generation</p>
      </div>

      <div className="p-6 space-y-6">
        {/* Certificate types */}
        <div>
          <h3 className="font-medium text-gray-900 mb-3">Generate Certificate</h3>
          <div className="grid grid-cols-2 gap-3">
            {[
              { type: 'Green Move', icon: '🚚', desc: 'GLEC Framework v3.0' },
              { type: 'Refrigerant Compliance', icon: '❄️', desc: 'EPA Section 608' },
              { type: 'Energy Efficiency', icon: '⚡', desc: 'ENERGY STAR verified' },
              { type: 'Waste Diversion', icon: '♻️', desc: 'EPA WARM Model' }
            ].map(cert => (
              <button
                key={cert.type}
                className="p-4 border border-gray-200 rounded-lg hover:border-green-500 hover:bg-green-50 text-left transition-colors"
              >
                <span className="text-2xl">{cert.icon}</span>
                <p className="font-medium text-gray-900 mt-2">{cert.type}</p>
                <p className="text-xs text-gray-500">{cert.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Recent certificates */}
        <div>
          <h3 className="font-medium text-gray-900 mb-3">Recent Certificates</h3>
          <div className="space-y-2">
            {[
              { id: 'PG-GRE-ABC123', type: 'Green Move', date: '2024-01-15', co2: '125 kg' },
              { id: 'PG-REF-DEF456', type: 'Refrigerant', date: '2024-01-14', co2: '0 kg (recovered)' },
              { id: 'PG-EFF-GHI789', type: 'Efficiency', date: '2024-01-13', co2: '-450 kg/yr' }
            ].map(cert => (
              <div key={cert.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-mono text-sm text-gray-900">{cert.id}</p>
                  <p className="text-xs text-gray-500">{cert.type} • {cert.date}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium text-green-600">{cert.co2}</p>
                  <button className="text-xs text-blue-600 hover:underline">View</button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ESG Report */}
        <div className="bg-gray-50 rounded-lg p-4">
          <h3 className="font-medium text-gray-900 mb-2">Annual ESG Report</h3>
          <p className="text-sm text-gray-500 mb-3">Generate comprehensive Scope 1, 2, 3 emissions report</p>
          <button className="w-full py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium">
            Generate 2024 Report
          </button>
        </div>
      </div>
    </div>
  );
};

/**
 * Tax Agent Panel
 */
const TaxAgentPanel = () => {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">Tax Credit Matcher</h2>
        <p className="text-sm text-gray-500">Federal and state green incentives</p>
      </div>

      <div className="p-6 space-y-6">
        {/* Available credits */}
        <div>
          <h3 className="font-medium text-gray-900 mb-3">Available Federal Credits</h3>
          <div className="space-y-3">
            {[
              { code: '45W', name: 'Commercial Clean Vehicle Credit', max: '$7,500 - $40,000', eligible: true },
              { code: '48C', name: 'Advanced Energy Project Credit', max: '30% ITC', eligible: true },
              { code: '179D', name: 'Energy Efficient Building Deduction', max: '$5/sq ft', eligible: false },
              { code: '25C', name: 'Home Improvement Credit', max: '$3,200/yr', eligible: true },
              { code: '30D', name: 'New Clean Vehicle Credit', max: '$7,500', eligible: true }
            ].map(credit => (
              <div
                key={credit.code}
                className={`p-3 rounded-lg border ${
                  credit.eligible ? 'border-green-200 bg-green-50' : 'border-gray-200 bg-gray-50'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-mono text-sm font-bold text-gray-700">{credit.code}</span>
                    <p className="text-sm text-gray-900">{credit.name}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium text-gray-900">{credit.max}</p>
                    {credit.eligible ? (
                      <span className="text-xs text-green-600">Potentially eligible</span>
                    ) : (
                      <span className="text-xs text-gray-400">Not applicable</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Potential savings */}
        <div className="bg-gradient-to-r from-green-500 to-green-600 rounded-lg p-4 text-white">
          <h3 className="font-medium mb-1">Estimated Available Credits</h3>
          <p className="text-3xl font-bold">$47,500</p>
          <p className="text-green-100 text-sm mt-1">Based on your fleet and equipment</p>
          <button className="mt-3 w-full py-2 bg-white text-green-600 rounded-lg font-medium hover:bg-green-50">
            Run Full Analysis
          </button>
        </div>

        {/* State incentives */}
        <div>
          <h3 className="font-medium text-gray-900 mb-3">State Incentives</h3>
          <select className="w-full px-3 py-2 border border-gray-300 rounded-lg mb-3">
            <option>California</option>
            <option>New York</option>
            <option>Texas</option>
            <option>Florida</option>
          </select>
          <div className="space-y-2">
            <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="font-medium text-blue-900">HVIP - Hybrid & Zero-Emission Truck Voucher</p>
              <p className="text-sm text-blue-700">Up to $120,000 per vehicle</p>
            </div>
            <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="font-medium text-blue-900">SGIP - Self-Generation Incentive Program</p>
              <p className="text-sm text-blue-700">Energy storage rebates</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

/**
 * Quick Actions Component
 */
const QuickActions = ({ activeAgent }) => {
  const actions = {
    intake: [
      { label: 'New CV Survey', icon: '📸' },
      { label: 'Generate Quote', icon: '💰' },
      { label: 'Customer Lookup', icon: '🔍' }
    ],
    ops: [
      { label: 'Optimize Today\'s Routes', icon: '🗺️' },
      { label: 'View Empty Miles Report', icon: '📊' },
      { label: 'Sync Telematics', icon: '🔄' }
    ],
    verifier: [
      { label: 'New Certificate', icon: '📜' },
      { label: 'Verify Certificate', icon: '✅' },
      { label: 'ESG Report', icon: '📈' }
    ],
    tax: [
      { label: 'Credit Analysis', icon: '💵' },
      { label: 'View Eligible Equipment', icon: '🚛' },
      { label: 'Generate Tax Report', icon: '📋' }
    ]
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <h3 className="font-medium text-gray-900 mb-3">Quick Actions</h3>
      <div className="space-y-2">
        {actions[activeAgent]?.map((action, idx) => (
          <button
            key={idx}
            className="w-full flex items-center gap-3 p-3 text-left hover:bg-gray-50 rounded-lg transition-colors"
          >
            <span className="text-xl">{action.icon}</span>
            <span className="text-sm text-gray-700">{action.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
};

/**
 * Recent Activity Component
 */
const RecentActivity = () => {
  const activities = [
    { time: '2 min ago', action: 'Route optimized', details: '12% fuel savings', type: 'success' },
    { time: '15 min ago', action: 'Certificate generated', details: 'PG-GRE-XYZ789', type: 'info' },
    { time: '1 hr ago', action: 'Tax credit identified', details: '$7,500 - 45W', type: 'success' },
    { time: '2 hrs ago', action: 'CV Survey completed', details: '3BR home - 8,500 lbs', type: 'info' }
  ];

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <h3 className="font-medium text-gray-900 mb-3">Recent Activity</h3>
      <div className="space-y-3">
        {activities.map((activity, idx) => (
          <div key={idx} className="flex items-start gap-3">
            <div className={`w-2 h-2 mt-1.5 rounded-full ${
              activity.type === 'success' ? 'bg-green-500' : 'bg-blue-500'
            }`}></div>
            <div className="flex-1">
              <p className="text-sm text-gray-900">{activity.action}</p>
              <p className="text-xs text-gray-500">{activity.details}</p>
            </div>
            <span className="text-xs text-gray-400">{activity.time}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default AgentsDashboard;
