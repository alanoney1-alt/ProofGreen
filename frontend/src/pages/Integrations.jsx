import React, { useState, useEffect } from 'react';
import { api } from '../utils/api';

/**
 * Integrations Page
 * Connect and manage external service integrations
 */
const Integrations = () => {
  const [availableIntegrations, setAvailableIntegrations] = useState([]);
  const [connectedIntegrations, setConnectedIntegrations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState({});

  // Mock company ID - in production, get from auth context
  const companyId = localStorage.getItem('companyId') || 'demo-company';

  useEffect(() => {
    loadIntegrations();
  }, []);

  const loadIntegrations = async () => {
    try {
      setLoading(true);

      // Load available integrations
      const availableResponse = await api.get('/integrations/available');
      if (availableResponse.success) {
        setAvailableIntegrations(availableResponse.integrations);
      }

      // Load connected integrations
      const connectedResponse = await api.get(`/integrations/company/${companyId}`);
      if (connectedResponse.success) {
        setConnectedIntegrations(connectedResponse.integrations);
      }
    } catch (error) {
      console.error('Failed to load integrations:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleConnect = async (providerId) => {
    try {
      const response = await api.post('/integrations/oauth/authorize', {
        providerId,
        redirectUri: `${window.location.origin}/integrations/callback`,
        state: `${companyId}_${providerId}`
      });

      if (response.success && response.authorizationUrl) {
        // In production, redirect to OAuth URL
        alert(`OAuth integration ready. In production, you would be redirected to:\n\n${response.authorizationUrl}`);

        // For demo, simulate a successful connection
        const mockCredentials = {
          accessToken: 'demo_access_token',
          refreshToken: 'demo_refresh_token',
          expiresAt: new Date(Date.now() + 3600000).toISOString()
        };

        await api.post('/integrations/connect', {
          companyId,
          providerId,
          credentials: mockCredentials
        });

        loadIntegrations();
      }
    } catch (error) {
      console.error('Connection error:', error);
      alert('Failed to connect integration. Please try again.');
    }
  };

  const handleSync = async (integrationId) => {
    setSyncing(prev => ({ ...prev, [integrationId]: true }));

    try {
      const response = await api.post(`/integrations/sync/${integrationId}`, {
        syncType: 'incremental'
      });

      if (response.success) {
        alert(`Sync completed!\n\nRecords synced: ${response.result?.recordsSynced || 0}\n${response.result?.message || ''}`);
      }
    } catch (error) {
      console.error('Sync error:', error);
      alert('Sync failed. Please try again.');
    } finally {
      setSyncing(prev => ({ ...prev, [integrationId]: false }));
    }
  };

  const handleDisconnect = async (integrationId) => {
    if (!confirm('Are you sure you want to disconnect this integration?')) {
      return;
    }

    try {
      await api.delete(`/integrations/${integrationId}`);
      loadIntegrations();
    } catch (error) {
      console.error('Disconnect error:', error);
      alert('Failed to disconnect. Please try again.');
    }
  };

  const getIntegrationIcon = (type) => {
    switch (type) {
      case 'field_service':
        return (
          <svg className="w-8 h-8 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
          </svg>
        );
      case 'accounting':
        return (
          <svg className="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
          </svg>
        );
      case 'fleet_gps':
      case 'fleet_management':
        return (
          <svg className="w-8 h-8 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        );
      default:
        return (
          <svg className="w-8 h-8 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
          </svg>
        );
    }
  };

  const isConnected = (providerId) => {
    return connectedIntegrations.some(i => i.provider === providerId && i.status === 'active');
  };

  const getConnectedIntegration = (providerId) => {
    return connectedIntegrations.find(i => i.provider === providerId);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-6xl mx-auto px-4">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Integrations</h1>
          <p className="text-gray-600 mt-1">
            Connect your existing tools to automatically sync job data and track ESG metrics
          </p>
        </div>

        {/* Connected integrations */}
        {connectedIntegrations.length > 0 && (
          <div className="mb-8">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Connected</h2>
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {connectedIntegrations.map(integration => {
                const config = availableIntegrations.find(a => a.id === integration.provider);
                return (
                  <div key={integration.id} className="bg-white rounded-lg border border-green-200 p-4 shadow-sm">
                    <div className="flex items-center gap-3 mb-3">
                      {getIntegrationIcon(integration.providerConfig?.type)}
                      <div>
                        <h3 className="font-medium text-gray-900">
                          {config?.name || integration.provider}
                        </h3>
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                          Connected
                        </span>
                      </div>
                    </div>

                    {integration.last_sync_at && (
                      <p className="text-xs text-gray-500 mb-3">
                        Last synced: {new Date(integration.last_sync_at).toLocaleString()}
                      </p>
                    )}

                    <div className="flex gap-2">
                      <button
                        onClick={() => handleSync(integration.id)}
                        disabled={syncing[integration.id]}
                        className="flex-1 px-3 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:bg-gray-400 flex items-center justify-center gap-1"
                      >
                        {syncing[integration.id] ? (
                          <>
                            <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></div>
                            Syncing...
                          </>
                        ) : (
                          <>
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                            Sync Now
                          </>
                        )}
                      </button>
                      <button
                        onClick={() => handleDisconnect(integration.id)}
                        className="px-3 py-2 border border-gray-300 text-gray-600 rounded-lg text-sm hover:bg-gray-50"
                      >
                        Disconnect
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Available integrations */}
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Available Integrations</h2>

          {/* Field Service Software */}
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3">
              Field Service Software
            </h3>
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {availableIntegrations.filter(i => i.type === 'field_service').map(integration => (
                <IntegrationCard
                  key={integration.id}
                  integration={integration}
                  icon={getIntegrationIcon(integration.type)}
                  connected={isConnected(integration.id)}
                  onConnect={() => handleConnect(integration.id)}
                />
              ))}
            </div>
          </div>

          {/* Accounting */}
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3">
              Accounting Software
            </h3>
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {availableIntegrations.filter(i => i.type === 'accounting').map(integration => (
                <IntegrationCard
                  key={integration.id}
                  integration={integration}
                  icon={getIntegrationIcon(integration.type)}
                  connected={isConnected(integration.id)}
                  onConnect={() => handleConnect(integration.id)}
                />
              ))}
            </div>
          </div>

          {/* Fleet/GPS */}
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3">
              Fleet & GPS Tracking
            </h3>
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {availableIntegrations.filter(i => i.type === 'fleet_gps' || i.type === 'fleet_management').map(integration => (
                <IntegrationCard
                  key={integration.id}
                  integration={integration}
                  icon={getIntegrationIcon(integration.type)}
                  connected={isConnected(integration.id)}
                  onConnect={() => handleConnect(integration.id)}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Data sync info */}
        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="font-medium text-blue-900 mb-2">How Data Syncing Works</h3>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>• Jobs and invoices are automatically imported from connected systems</li>
            <li>• Material usage is extracted and mapped to our ESG database</li>
            <li>• Fleet data calculates mileage emissions automatically</li>
            <li>• Accounting data tracks material purchases for embodied carbon</li>
            <li>• Data syncs every hour, or sync manually anytime</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

/**
 * Integration Card Component
 */
const IntegrationCard = ({ integration, icon, connected, onConnect }) => {
  const descriptions = {
    servicetitan: 'Sync jobs, customers, and invoices from ServiceTitan',
    housecall_pro: 'Import jobs and customer data from Housecall Pro',
    jobber: 'Connect your Jobber account for automatic job syncing',
    quickbooks: 'Track purchases and materials from QuickBooks',
    samsara: 'Import fleet data and trip logs from Samsara',
    verizon_connect: 'Sync vehicle tracking and fuel data',
    fleetio: 'Import vehicle maintenance and fuel records'
  };

  return (
    <div className={`bg-white rounded-lg border p-4 shadow-sm ${connected ? 'border-green-200' : 'border-gray-200'}`}>
      <div className="flex items-center gap-3 mb-3">
        {icon}
        <div>
          <h3 className="font-medium text-gray-900">{integration.name}</h3>
          <p className="text-xs text-gray-500 capitalize">{integration.type.replace(/_/g, ' ')}</p>
        </div>
      </div>

      <p className="text-sm text-gray-600 mb-4">
        {descriptions[integration.id] || `Connect your ${integration.name} account`}
      </p>

      {connected ? (
        <span className="inline-flex items-center px-3 py-1.5 rounded-lg text-sm font-medium bg-green-100 text-green-800">
          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          Connected
        </span>
      ) : (
        <button
          onClick={onConnect}
          className="w-full px-4 py-2 bg-gray-900 text-white rounded-lg text-sm hover:bg-gray-800 transition-colors"
        >
          Connect {integration.name}
        </button>
      )}
    </div>
  );
};

export default Integrations;
