/**
 * ProofGreen MAS - Connection Status Panel
 * Admin dashboard component showing FSM connection health indicators.
 */

import React, { useState, useEffect, useCallback } from 'react';

const ConnectionStatusPanel = ({ companyId, apiBaseUrl = '/api/v1' }) => {
  const [connections, setConnections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState({});

  // Fetch connection statuses
  const fetchStatuses = useCallback(async () => {
    try {
      const response = await fetch(
        `${apiBaseUrl}/credentials/status?company_id=${companyId}`
      );
      if (!response.ok) throw new Error('Failed to fetch connection statuses');
      const data = await response.json();
      setConnections(data.connections || []);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [companyId, apiBaseUrl]);

  // Initial load and periodic refresh
  useEffect(() => {
    fetchStatuses();
    const interval = setInterval(fetchStatuses, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [fetchStatuses]);

  // Verify connection
  const verifyConnection = async (provider) => {
    setRefreshing((prev) => ({ ...prev, [provider]: true }));
    try {
      const response = await fetch(
        `${apiBaseUrl}/credentials/verify`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ company_id: companyId, provider }),
        }
      );
      const result = await response.json();

      // Update local state with new status
      setConnections((prev) =>
        prev.map((conn) =>
          conn.provider === provider
            ? { ...conn, status: result.status, color: getStatusColor(result.status) }
            : conn
        )
      );
    } catch (err) {
      console.error('Verification failed:', err);
    } finally {
      setRefreshing((prev) => ({ ...prev, [provider]: false }));
    }
  };

  // Refresh OAuth token
  const refreshToken = async (provider) => {
    setRefreshing((prev) => ({ ...prev, [provider]: true }));
    try {
      const response = await fetch(
        `${apiBaseUrl}/credentials/refresh-token`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ company_id: companyId, provider }),
        }
      );
      const result = await response.json();

      if (result.success) {
        // Refresh statuses to get updated info
        await fetchStatuses();
      }
    } catch (err) {
      console.error('Token refresh failed:', err);
    } finally {
      setRefreshing((prev) => ({ ...prev, [provider]: false }));
    }
  };

  // Get status color
  const getStatusColor = (status) => {
    const colors = {
      connected: '#22c55e',    // Green
      auth_failed: '#ef4444',  // Red
      expired: '#eab308',      // Yellow
      refreshing: '#3b82f6',   // Blue
      unknown: '#9ca3af',      // Gray
    };
    return colors[status] || colors.unknown;
  };

  // Get status icon
  const StatusIcon = ({ status }) => {
    const color = getStatusColor(status);

    if (status === 'refreshing') {
      return (
        <div className="status-icon spinning" style={{ borderColor: color }}>
          <svg viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2">
            <path d="M21 12a9 9 0 11-6.219-8.56" />
          </svg>
        </div>
      );
    }

    return (
      <div
        className="status-indicator"
        style={{
          backgroundColor: color,
          boxShadow: `0 0 8px ${color}40`
        }}
      />
    );
  };

  // Provider icon mapping
  const getProviderIcon = (provider) => {
    const icons = {
      servicetitan: '🔧',
      jobber: '📋',
      housecall_pro: '🏠',
      fieldedge: '⚡',
    };
    return icons[provider.toLowerCase().replace(' ', '_')] || '🔌';
  };

  if (loading) {
    return (
      <div className="connection-status-panel loading">
        <div className="spinner" />
        <span>Loading connection statuses...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="connection-status-panel error">
        <span className="error-icon">⚠️</span>
        <span>{error}</span>
        <button onClick={fetchStatuses}>Retry</button>
      </div>
    );
  }

  return (
    <div className="connection-status-panel">
      <div className="panel-header">
        <h3>FSM Connections</h3>
        <button
          className="refresh-all-btn"
          onClick={fetchStatuses}
          title="Refresh all statuses"
        >
          🔄
        </button>
      </div>

      {connections.length === 0 ? (
        <div className="no-connections">
          <span className="icon">🔌</span>
          <p>No FSM connections configured</p>
          <a href="/admin/integrations/setup" className="setup-link">
            + Add Integration
          </a>
        </div>
      ) : (
        <div className="connections-list">
          {connections.map((conn) => (
            <div
              key={conn.provider}
              className={`connection-card ${conn.status}`}
            >
              <div className="connection-header">
                <span className="provider-icon">
                  {getProviderIcon(conn.provider)}
                </span>
                <span className="provider-name">{conn.provider}</span>
                <StatusIcon status={conn.status} />
              </div>

              <div className="connection-details">
                <span className="status-message">{conn.message}</span>
                {conn.last_verified && (
                  <span className="last-verified">
                    Last verified: {new Date(conn.last_verified).toLocaleString()}
                  </span>
                )}
              </div>

              <div className="connection-actions">
                <button
                  className="action-btn verify"
                  onClick={() => verifyConnection(conn.provider)}
                  disabled={refreshing[conn.provider]}
                  title="Test connection"
                >
                  {refreshing[conn.provider] ? '...' : '✓ Verify'}
                </button>

                {(conn.status === 'expired' || conn.status === 'auth_failed') && (
                  <button
                    className="action-btn refresh"
                    onClick={() => refreshToken(conn.provider)}
                    disabled={refreshing[conn.provider]}
                    title="Refresh OAuth token"
                  >
                    {refreshing[conn.provider] ? '...' : '🔄 Refresh Token'}
                  </button>
                )}

                <a
                  href={`/admin/integrations/${conn.provider.toLowerCase()}/settings`}
                  className="action-btn settings"
                  title="Connection settings"
                >
                  ⚙️
                </a>
              </div>
            </div>
          ))}
        </div>
      )}

      <style>{`
        .connection-status-panel {
          background: #1a1a2e;
          border-radius: 12px;
          padding: 20px;
          color: #e0e0e0;
        }

        .panel-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
        }

        .panel-header h3 {
          margin: 0;
          font-size: 18px;
          font-weight: 600;
        }

        .refresh-all-btn {
          background: transparent;
          border: none;
          cursor: pointer;
          font-size: 18px;
          padding: 4px 8px;
          border-radius: 4px;
          transition: background 0.2s;
        }

        .refresh-all-btn:hover {
          background: rgba(255, 255, 255, 0.1);
        }

        .connections-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .connection-card {
          background: #16213e;
          border-radius: 8px;
          padding: 16px;
          border-left: 4px solid #9ca3af;
          transition: all 0.2s;
        }

        .connection-card.connected {
          border-left-color: #22c55e;
        }

        .connection-card.auth_failed {
          border-left-color: #ef4444;
        }

        .connection-card.expired {
          border-left-color: #eab308;
        }

        .connection-card.refreshing {
          border-left-color: #3b82f6;
        }

        .connection-header {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 8px;
        }

        .provider-icon {
          font-size: 24px;
        }

        .provider-name {
          font-weight: 600;
          flex: 1;
          text-transform: capitalize;
        }

        .status-indicator {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          animation: pulse 2s infinite;
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.6; }
        }

        .status-icon {
          width: 20px;
          height: 20px;
        }

        .status-icon.spinning svg {
          animation: spin 1s linear infinite;
        }

        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        .connection-details {
          display: flex;
          flex-direction: column;
          gap: 4px;
          margin-bottom: 12px;
          font-size: 13px;
        }

        .status-message {
          color: #a0a0a0;
        }

        .last-verified {
          color: #6b7280;
          font-size: 11px;
        }

        .connection-actions {
          display: flex;
          gap: 8px;
        }

        .action-btn {
          padding: 6px 12px;
          border-radius: 4px;
          border: none;
          cursor: pointer;
          font-size: 12px;
          transition: all 0.2s;
          text-decoration: none;
          display: inline-flex;
          align-items: center;
          gap: 4px;
        }

        .action-btn.verify {
          background: #1e3a5f;
          color: #60a5fa;
        }

        .action-btn.verify:hover:not(:disabled) {
          background: #2563eb;
          color: white;
        }

        .action-btn.refresh {
          background: #422006;
          color: #fbbf24;
        }

        .action-btn.refresh:hover:not(:disabled) {
          background: #d97706;
          color: white;
        }

        .action-btn.settings {
          background: #374151;
          color: #9ca3af;
        }

        .action-btn.settings:hover {
          background: #4b5563;
          color: white;
        }

        .action-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .no-connections {
          text-align: center;
          padding: 32px;
          color: #6b7280;
        }

        .no-connections .icon {
          font-size: 48px;
          display: block;
          margin-bottom: 16px;
        }

        .setup-link {
          display: inline-block;
          margin-top: 16px;
          padding: 8px 16px;
          background: #22c55e;
          color: white;
          border-radius: 6px;
          text-decoration: none;
          font-weight: 500;
        }

        .setup-link:hover {
          background: #16a34a;
        }

        .loading, .error {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 12px;
          padding: 32px;
          color: #6b7280;
        }

        .error {
          color: #ef4444;
        }

        .error button {
          padding: 4px 12px;
          background: #1e3a5f;
          border: none;
          border-radius: 4px;
          color: #60a5fa;
          cursor: pointer;
        }

        .spinner {
          width: 20px;
          height: 20px;
          border: 2px solid #374151;
          border-top-color: #60a5fa;
          border-radius: 50%;
          animation: spin 1s linear infinite;
        }
      `}</style>
    </div>
  );
};

export default ConnectionStatusPanel;
